"""Konfiguration för nyhetssammanfattning."""

import os
from dotenv import load_dotenv

load_dotenv()

# API-nycklar
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# E-post
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "pontus.skog@sveasolar.com")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")

# Nyhetsparametrar
MAX_NEWS_ITEMS = 15

# Sökprofil för Svea Solar
COMPANY_CONTEXT = """
Du söker nyheter för Pontus Skog, Head of Development på Svea Solar i Sverige.
Svea Solar är en IPP (Independent Power Producer) som utvecklar, bygger, driftar och äger:
- Solcellsparker (utility-scale, 10-200 MW)
- Batteriparker (BESS - Battery Energy Storage Systems)
- Hybridanläggningar (sol + batteri)

Fokusområden:
- Svenska energimarknaden
- Nordisk och europeisk solenergiutveckling
- Globala megaprojekt inom sol och batteri
- Nätanslutning och elmarknadsregler
- PPA-avtal (Power Purchase Agreements)
- Teknikutveckling (bifacial, agrivoltaics, LFP-batterier)
- Konkurrenter och branschaktörer
"""

SEARCH_CATEGORIES = {
    "sverige_norden": {
        "name": "Sverige & Norden",
        "emoji": "🇸🇪",
        "queries": [
            "solcellspark Sverige nyheter",
            "batterilagring Sverige energi",
            "solenergi investering Norden",
            "förnybar energi IPP Sverige",
            "nätanslutning solpark Svenska Kraftnät",
        ]
    },
    "europa": {
        "name": "Europa",
        "emoji": "🇪🇺",
        "queries": [
            "utility-scale solar Europe news",
            "battery energy storage BESS Europe",
            "solar PPA Europe deal",
            "renewable energy policy EU",
            "grid-scale storage Europe",
        ]
    },
    "globalt": {
        "name": "Globalt",
        "emoji": "🌍",
        "queries": [
            "large-scale solar project GW",
            "mega solar farm construction",
            "grid-scale battery storage project",
            "solar plus storage hybrid project",
            "renewable energy IPP investment",
        ]
    },
    "trender": {
        "name": "Trender & Analys",
        "emoji": "📈",
        "queries": [
            "solar energy market trend 2024 2025",
            "battery cost forecast BNEF",
            "renewable energy investment outlook",
            "solar technology innovation bifacial",
            "energy storage market analysis",
        ]
    }
}
