# 🎨 Färgsidan Pro – AI-artikelgenerator

Automatisk generering av SEO-optimerade artiklar om färg, tapeter och inredning.

---

## ⚡ Kom igång (första gången)

### 1. Klona repot
```bash
git clone https://github.com/DITT-ANVÄNDARNAMN/fargsidan-pro.git
cd fargsidan-pro
```

### 2. Installera Python-beroenden
```bash
pip install -r requirements.txt
```

### 3. Lägg till din API-nyckel

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY="din-nyckel-här"
```

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="din-nyckel-här"
```

> ⚠️ Lägg ALDRIG nyckeln direkt i koden eller committa den till GitHub.

### 4. Kör generatorn
```bash
python scripts/generate_article.py
```

Artikeln sparas i mappen `articles/` som både `.json` och `.html`.  
Öppna `.html`-filen i webbläsaren för att förhandsgranska.

---

## 📁 Projektstruktur

```
fargsidan-pro/
├── scripts/
│   └── generate_article.py   # Huvudscript
├── articles/                  # Genererade artiklar (json + html)
├── requirements.txt
└── README.md
```

---

## ✏️ Anpassa ämnen

Öppna `scripts/generate_article.py` och redigera listan `TOPICS` högst upp i filen.  
Du kan lägga till hur många ämnen som helst – scriptet väljer ett slumpmässigt varje körning.

---

## 🔄 Nästa steg

- [ ] Sätt upp GitHub Actions för automatisk daglig körning
- [ ] Koppla till WordPress eller annan publiceringsplattform
- [ ] Bygg en enkel indexsida som listar alla artiklar

---

## 💰 Kostnad

Varje artikel kostar ca **$0.01–0.03** med Claude Sonnet.  
10 artiklar per dag ≈ $3–9 i månaden.
