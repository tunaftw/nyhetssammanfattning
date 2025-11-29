# Nyhetssammanfattning - Sol & Batteri

Automatiserat verktyg som hämtar och sammanfattar relevanta nyheter om solenergi och batterilagring, och skickar en daglig uppdatering via e-post.

## Funktioner

- **AI-driven nyhetssökning** - Använder Gemini 2.5 med Google Search för att hitta relevanta nyheter
- **Intelligent filtrering** - Prioriterar nyheter baserat på relevans för utility-scale sol- och batteriprojekt
- **Kategorisering** - Sverige/Norden, Europa, Globalt, Trender
- **Daglig leverans** - Automatisk e-post kl 06:00 via GitHub Actions

## Snabbstart

### 1. Klona och konfigurera

```bash
git clone <repo-url>
cd nyhetssammanfattning
cp .env.example .env
```

### 2. Skaffa API-nycklar

#### Gemini API (Google)
1. Gå till [Google AI Studio](https://aistudio.google.com/apikey)
2. Klicka "Create API Key"
3. Kopiera nyckeln till `.env` som `GEMINI_API_KEY`

#### Resend (E-post)
1. Skapa konto på [resend.com](https://resend.com)
2. Gå till [API Keys](https://resend.com/api-keys)
3. Skapa ny nyckel och kopiera till `.env` som `RESEND_API_KEY`
4. **Viktig:** För att skicka från egen domän, verifiera domänen i Resend. Annars använd `onboarding@resend.dev` som avsändare (fungerar för test).

### 3. Fyll i .env

```env
GEMINI_API_KEY=din_gemini_nyckel
RESEND_API_KEY=din_resend_nyckel
RECIPIENT_EMAIL=pontus.skog@sveasolar.com
SENDER_EMAIL=onboarding@resend.dev
```

### 4. Installera beroenden

```bash
python -m venv venv
source venv/bin/activate  # På Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Testa lokalt

```bash
# Testa konfigurationen med test-mail
cd src
python main.py --test

# Förhandsgranska nyheter (sparar HTML lokalt)
python main.py --preview

# Kör full pipeline (hämta + skicka)
python main.py
```

## Deployment (GitHub Actions)

### 1. Pusha till GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <din-repo-url>
git push -u origin main
```

### 2. Konfigurera Secrets

I ditt GitHub-repo, gå till **Settings > Secrets and variables > Actions** och lägg till:

| Secret | Värde |
|--------|-------|
| `GEMINI_API_KEY` | Din Gemini API-nyckel |
| `RESEND_API_KEY` | Din Resend API-nyckel |
| `RECIPIENT_EMAIL` | `pontus.skog@sveasolar.com` |
| `SENDER_EMAIL` | Din verifierade avsändaradress |

### 3. Aktivera Actions

GitHub Actions är aktiverat automatiskt. Workflowen körs:
- **Automatiskt** varje dag kl 05:00 UTC (06:00 CET)
- **Manuellt** via "Run workflow" i Actions-fliken

### 4. Testa manuellt

1. Gå till **Actions** i ditt repo
2. Välj "Daily News Summary"
3. Klicka "Run workflow"
4. Vänta ~2-3 minuter
5. Kontrollera din inkorg!

## Projektstruktur

```
nyhetssammanfattning/
├── src/
│   ├── main.py           # Huvudscript med CLI
│   ├── news_fetcher.py   # Gemini-integration
│   ├── email_sender.py   # Resend-integration
│   ├── config.py         # Konfiguration
│   └── templates/
│       └── email.html    # HTML-mall för e-post
├── .github/
│   └── workflows/
│       └── daily-news.yml # GitHub Actions workflow
├── .env.example          # Mall för miljövariabler
├── requirements.txt      # Python-beroenden
└── README.md
```

## Anpassa nyhetskällor

Redigera `src/config.py` för att:
- Ändra söktermer per kategori
- Justera företagskontext (COMPANY_CONTEXT)
- Ändra antal nyheter (MAX_NEWS_ITEMS)

## Felsökning

### "GEMINI_API_KEY saknas"
Kontrollera att `.env` finns och innehåller rätt nyckel, eller att GitHub Secrets är korrekt konfigurerade.

### Inga nyheter hittas
- Prova `python main.py --dry-run` för att se vad som hämtas
- Kontrollera att Gemini API har grounding/search aktiverat

### E-post kommer inte fram
- Kontrollera spam-mappen
- Verifiera att RECIPIENT_EMAIL är korrekt
- För egen avsändardomän: verifiera i Resend Dashboard

### GitHub Actions misslyckas
- Kontrollera Actions-loggen för felmeddelanden
- Verifiera att alla Secrets är satta
- Kör manuellt för att se detaljerad output

## Kostnader

- **Gemini API**: Gratis tier räcker gott (15 req/min, 1M tokens/dag)
- **Resend**: Gratis upp till 3000 mail/månad
- **GitHub Actions**: Gratis för public repos, 2000 min/månad för private

## Licens

MIT
