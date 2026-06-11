import anthropic
import json
import os
import re
import requests
from datetime import datetime

# ─────────────────────────────────────────
#  KONFIGURATION
# ─────────────────────────────────────────
TOPICS = [
    "Trendiga tapetkombinationer för vardagsrummet 2025",
    "Bästa väggfärgerna för ett litet sovrum",
    "Hur du väljer rätt tapetmönster till hallen",
    "Inredningstrender inom färg och tapeter höst 2025",
    "Så kombinerar du mönstrade tapeter med enfärgade väggar",
    "Jordfärger i hemmet – guide för nybörjare",
    "Blå nyanser i inredningen – från navy till pastellblå",
    "Tapeter i köket – vad funkar och vad ska du undvika",
    "Grön väggfärg – vilken nyans passar vilket rum",
    "Retro-tapeter gör comeback – här är höstens hetaste mönster",
]

FARGER_MARKEN = ["Jotun", "Little Greene", "Nordsjö", "Farrow & Ball"]
TAPET_MARKEN  = ["Boråstapeter", "Sandberg", "Cole & Son", "Midbec", "Engblad & Co"]

# ─────────────────────────────────────────
#  HÄMTA SHOPIFY-TOKEN
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
#  HÄMTA PRODUKTER FRÅN SHOPIFY
# ─────────────────────────────────────────
def fetch_shopify_products(token: str, limit: int = 20) -> list:
    store = os.environ["SHOPIFY_STORE"]
    url   = f"https://{store}/admin/api/2024-01/products.json?limit={limit}&status=active"

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
#  ARTIKEL-PROMPT
# ─────────────────────────────────────────
def build_prompt(topic: str, products: list) -> str:
    product_list = ""
    if products:
        product_list = "\n\nProdukter från vår butik (nämn och länka gärna till relevanta):\n"
        for p in products[:15]:
            product_list += f"- {p['title']} (typ: {p['type']}) → {p['url']}\n"

    marken_text = (
        f"Färgmärken att nämna: {', '.join(FARGER_MARKEN)}\n"
        f"Tapetmärken att nämna: {', '.join(TAPET_MARKEN)}"
    )

    return f"""Du är en erfaren svensk inredningsjournalist som skriver för Fargwebben.se – en butik och nyhetssida om färg, tapeter och inredning.

Skriv en SEO-optimerad artikel på svenska om ämnet: "{topic}"

{marken_text}
{product_list}

Returnera ENDAST ett JSON-objekt (ingen markdown, inga kodblock) med exakt denna struktur:
{{
  "title": "Artikelns rubrik (60-70 tecken, innehåller nyckelord)",
  "meta_description": "Meta-beskrivning (150-160 tecken, lockande, innehåller nyckelord)",
  "slug": "url-vanlig-slug-med-bindestreck",
  "intro": "Ingress på 2-3 meningar som väcker intresse och sammanfattar artikeln",
  "sections": [
    {{
      "heading": "H2-rubrik",
      "body": "3-4 stycken med löpande text. Skriv informativt, konkret och engagerande."
    }}
  ],
  "conclusion": "Avslutande stycke på 2-3 meningar med uppmaning till läsaren att besöka Fargwebben.se",
  "tags": ["tagg1", "tagg2", "tagg3", "tagg4", "tagg5"]
}}

Krav:
- 3-4 sektioner (sections)
- Total längd: 600-900 ord
- Svenska, naturlig ton – inte för formell
- SEO-fokus: använd nyckelord naturligt i rubriker och text
- Nämn specifika kulörnamn och tapetmodeller från märkena ovan
- Om relevanta butiksprodukter finns – nämn dem med HTML-länk i texten
- Ge konkreta, praktiska råd som läsaren kan använda direkt
"""

# ─────────────────────────────────────────
#  GENERERA ARTIKEL
# ─────────────────────────────────────────
def generate_article(topic: str, products: list) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"  → Genererar: {topic}")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": build_prompt(topic, products)}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    article = json.loads(raw)
    article["topic"]        = topic
    article["generated_at"] = datetime.now().isoformat()
    return article

# ─────────────────────────────────────────
#  SPARA SOM JSON
# ─────────────────────────────────────────
def save_article(article: dict) -> str:
    os.makedirs("articles", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"articles/{date_str}-{article['slug']}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)

    print(f"  ✓ Sparad: {filename}")
    return filename

# ─────────────────────────────────────────
#  BYGG HTML-FÖRHANDSGRANSKNING
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
    a {{ color: #8b5e3c; }}
  </style>
</head>
<body>
  <h1>{article['title']}</h1>
  <p class="meta">Genererad: {article['generated_at'][:10]} | Fargwebben.se</p>
  <div class="intro">{article['intro']}</div>
  {sections_html}
  <div class="conclusion">{article['conclusion']}</div>
  <div class="tags">{tags_html}</div>
</body>
</html>"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  ✓ HTML-preview: {filename}")
    return filename

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    import random

    for key in ["ANTHROPIC_API_KEY", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET", "SHOPIFY_STORE"]:
        if not os.environ.get(key):
            raise EnvironmentError(f"Miljövariabeln {key} saknas. Sätt den i PowerShell innan du kör.")

    print(f"\n🎨 Färgsidan Pro – Artikelgenerator")
    print(f"{'─'*40}")

    # Hämta Shopify-token och produkter
    print("  → Hämtar produkter från Fargwebben.se...")
    try:
        token    = get_shopify_token()
        products = fetch_shopify_products(token)
        print(f"  ✓ Hämtade {len(products)} produkter från butiken")
    except Exception as e:
        print(f"  ⚠️  Kunde inte hämta Shopify-produkter ({e}) – kör utan produktdata")
        products = []

    # Välj ämne och generera
    topic   = random.choice(TOPICS)
    article = generate_article(topic, products)
    save_article(article)
    save_html_preview(article)

    print(f"\n✅ Klar! Öppna HTML-filen i articles/ i din webbläsare.")
