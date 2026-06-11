import anthropic
import json
import os
import re
import requests
from datetime import datetime
from dotenv import load_dotenv

# Läs in .env-filen automatiskt
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# ─────────────────────────────────────────
#  KONFIGURATION
# ─────────────────────────────────────────
VARUMERKEN = [
    "Boråstapeter", "Sandberg Wallpaper", "Cole & Son", "Midbec", "Engblad & Co",
    "Jotun", "Little Greene", "Nordsjö", "Farrow & Ball"
]

SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "")

# ─────────────────────────────────────────
#  STEG 1: HÄMTA SHOPIFY-TOKEN
# ─────────────────────────────────────────
def get_shopify_token() -> str:
    store         = os.environ["SHOPIFY_STORE"]
    client_id     = os.environ["SHOPIFY_CLIENT_ID"]
    client_secret = os.environ["SHOPIFY_CLIENT_SECRET"]

    url  = f"https://{store}/admin/oauth/access_token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
    }
    resp = requests.post(url, json=data, timeout=10)
    resp.raise_for_status()
    return resp.json()["access_token"]

# ─────────────────────────────────────────
#  STEG 2: HÄMTA PRODUKTER FRÅN SHOPIFY
# ─────────────────────────────────────────
def fetch_shopify_products(token: str, limit: int = 50) -> list:
    store   = os.environ["SHOPIFY_STORE"]
    url     = f"https://{store}/admin/api/2024-01/products.json?limit={limit}&status=active"
    headers = {"X-Shopify-Access-Token": token}
    resp    = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    products = resp.json().get("products", [])
    simplified = []
    for p in products:
        simplified.append({
            "title":  p.get("title", ""),
            "handle": p.get("handle", ""),
            "type":   p.get("product_type", ""),
            "tags":   p.get("tags", ""),
            "url":    f"https://fargwebben.se/products/{p.get('handle', '')}",
        })
    return simplified

# ─────────────────────────────────────────
#  STEG 3: SÖK NYHETER PÅ WEBBEN VIA CLAUDE
# ─────────────────────────────────────────
def find_news_topic(varumärke: str) -> dict:
    """Låt Claude söka webben efter en aktuell nyhet om varumärket."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"  → Söker nyheter om {varumärke}...")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": (
                f"Sök på webben efter den senaste nyheten, trenden eller kollektionen från {varumärke} "
                f"inom tapeter eller färg. Hitta något konkret och aktuellt från 2024 eller 2025. "
                f"Returnera ENDAST ett JSON-objekt (ingen markdown) med:\n"
                f'{{"topic": "kort beskrivning av nyheten", "source_url": "url till källan", "summary": "2-3 meningar om vad nyheten handlar om"}}'
            )
        }]
    )

    # Plocka ut text från svaret
    raw = ""
    for block in message.content:
        if hasattr(block, "text"):
            raw += block.text

    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except Exception:
        return {
            "topic":      f"Nyheter och trender från {varumärke} 2025",
            "source_url": "",
            "summary":    f"Aktuella nyheter och trender från {varumärke}."
        }

# ─────────────────────────────────────────
#  STEG 4: HITTA MATCHANDE PRODUKTER
# ─────────────────────────────────────────
def find_matching_products(topic: str, varumärke: str, products: list) -> list:
    """Hitta produkter i butiken som är relevanta för ämnet."""
    matches = []
    search_terms = varumärke.lower().split() + topic.lower().split()

    for p in products:
        product_text = f"{p['title']} {p['type']} {p['tags']}".lower()
        if any(term in product_text for term in search_terms if len(term) > 3):
            matches.append(p)

    return matches[:5]  # Max 5 produkter

# ─────────────────────────────────────────
#  STEG 5: GENERERA ARTIKEL
# ─────────────────────────────────────────
def generate_article(topic_data: dict, varumärke: str, matching_products: list) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    topic   = topic_data["topic"]
    summary = topic_data["summary"]
    source  = topic_data.get("source_url", "")

    print(f"  → Skriver artikel om: {topic}")

    # Bygg produktlista om vi har matchningar
    product_text = ""
    if matching_products:
        product_text = "\n\nVi säljer dessa relevanta produkter – länka in dem naturligt om det passar:\n"
        for p in matching_products:
            product_text += f'- <a href="{p["url"]}">{p["title"]}</a>\n'

    prompt = f"""Du är en erfaren svensk inredningsjournalist för Fargwebben.se.

Skriv en naturlig, journalistisk artikel baserad på denna nyhet/trend:
Ämne: {topic}
Bakgrund: {summary}
{f'Källa: {source}' if source else ''}
{product_text}

Regler:
- Skriv som en riktig journalist – inte som en säljare
- Nämn varumärket {varumärke} naturligt i texten
- Länka bara in butiksprodukter om det verkligen passar kontexten – tvinga inte in dem
- Ge läsaren genuint värde och inspiration
- Inga tomma fraser som "i en värld där..." eller "mer än någonsin"

Returnera ENDAST ett JSON-objekt (ingen markdown, inga kodblock):
{{
  "title": "Rubrik (60-70 tecken, innehåller nyckelord)",
  "meta_description": "Meta-beskrivning (150-160 tecken)",
  "slug": "url-slug-med-bindestreck",
  "intro": "Ingress på 2-3 meningar",
  "sections": [
    {{
      "heading": "H2-rubrik",
      "body": "3-4 stycken text. HTML-länkar är okej här."
    }}
  ],
  "conclusion": "Avslutning på 2-3 meningar",
  "tags": ["tagg1", "tagg2", "tagg3", "tagg4", "tagg5"]
}}

Krav: 3-4 sektioner, 700-1000 ord totalt, naturlig svenska.
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    article = json.loads(raw)
    article["varumärke"]    = varumärke
    article["source_url"]   = source
    article["generated_at"] = datetime.now().isoformat()
    return article

# ─────────────────────────────────────────
#  SPARA JSON
# ─────────────────────────────────────────
def save_article(article: dict) -> str:
    os.makedirs("articles", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"articles/{date_str}-{article['slug']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)
    print(f"  ✓ JSON sparad: {filename}")
    return filename

# ─────────────────────────────────────────
#  SPARA HTML
# ─────────────────────────────────────────
def save_html_preview(article: dict) -> str:
    os.makedirs("articles", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"articles/{date_str}-{article['slug']}.html"

    sections_html = ""
    for s in article.get("sections", []):
        body_html = "".join(f"<p>{p}</p>" for p in s["body"].split("\n\n") if p.strip())
        sections_html += f"<h2>{s['heading']}</h2>\n{body_html}\n"

    tags_html = " ".join(f'<span class="tag">{t}</span>' for t in article.get("tags", []))
    source_html = f'<p class="source">Källa: <a href="{article["source_url"]}">{article["source_url"]}</a></p>' if article.get("source_url") else ""

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="description" content="{article['meta_description']}">
  <title>{article['title']}</title>
  <style>
    body {{ font-family: Georgia, serif; max-width: 740px; margin: 40px auto; padding: 0 20px; color: #222; line-height: 1.7; }}
    h1 {{ font-size: 2em; margin-bottom: .3em; }}
    .meta {{ color: #888; font-size: .85em; margin-bottom: 2em; }}
    .intro {{ font-size: 1.15em; color: #444; border-left: 3px solid #c8a96e; padding-left: 1em; margin-bottom: 2em; }}
    h2 {{ font-size: 1.3em; margin-top: 2em; color: #333; }}
    .conclusion {{ background: #faf6f0; border-radius: 6px; padding: 1em 1.4em; margin-top: 2em; }}
    .tag {{ background: #eee; border-radius: 3px; padding: 2px 8px; font-size: .8em; margin-right: 4px; font-family: sans-serif; }}
    .tags {{ margin-top: 2em; }}
    .source {{ font-size: .8em; color: #999; margin-top: 1em; }}
    a {{ color: #8b5e3c; }}
  </style>
</head>
<body>
  <h1>{article['title']}</h1>
  <p class="meta">Genererad: {article['generated_at'][:10]} | {article.get('varumärke', '')}</p>
  <div class="intro">{article['intro']}</div>
  {sections_html}
  <div class="conclusion">{article['conclusion']}</div>
  {source_html}
  <div class="tags">{tags_html}</div>
</body>
</html>"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ HTML sparad: {filename}")
    return filename

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    import random

    for key in ["ANTHROPIC_API_KEY", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET", "SHOPIFY_STORE"]:
        if not os.environ.get(key):
            raise EnvironmentError(f"Miljövariabeln {key} saknas. Kontrollera din .env-fil.")

    print(f"\n🎨 Färgsidan Pro – Artikelgenerator v2")
    print(f"{'─'*40}")

    # Hämta produkter från Shopify
    print("  → Hämtar produkter från Fargwebben.se...")
    try:
        token    = get_shopify_token()
        products = fetch_shopify_products(token)
        print(f"  ✓ Hämtade {len(products)} produkter")
    except Exception as e:
        print(f"  ⚠️  Shopify-fel ({e}) – kör utan produktdata")
        products = []

    # Välj slumpmässigt varumärke
    varumärke = random.choice(VARUMERKEN)
    print(f"  → Valt varumärke: {varumärke}")

    # Hitta nyhet på webben
    topic_data = find_news_topic(varumärke)
    print(f"  ✓ Hittade ämne: {topic_data['topic']}")

    # Hitta matchande produkter
    matching = find_matching_products(topic_data["topic"], varumärke, products)
    if matching:
        print(f"  ✓ Hittade {len(matching)} matchande produkter i butiken")
    else:
        print(f"  → Inga matchande produkter – skriver artikel utan produktlänkar")

    # Generera och spara artikel
    article = generate_article(topic_data, varumärke, matching)
    save_article(article)
    save_html_preview(article)

    print(f"\n✅ Klar! Öppna HTML-filen i articles/ för förhandsgranskning.")
