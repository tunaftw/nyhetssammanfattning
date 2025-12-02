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
            "solcellspark Sverige nyheter 2024 2025",
            "batterilagring Sverige energi projekt",
            "solenergi investering Norden",
            "förnybar energi IPP Sverige",
            "nätanslutning solpark Svenska Kraftnät",
            # Utökade söktermer
            "Svea Solar OX2 Vattenfall Alight konkurrent",
            "solpark tillstånd miljöprövning Sverige",
            "BESS batterilager MW Sverige",
            "PPA avtal solenergi Sverige Norden",
            "hybridpark sol vind Sverige",
        ]
    },
    "europa": {
        "name": "Europa",
        "emoji": "🇪🇺",
        "queries": [
            "utility-scale solar Europe news 2024 2025",
            "battery energy storage BESS Europe project",
            "solar PPA Europe deal",
            "renewable energy policy EU regulation",
            "grid-scale storage Europe GW",
            # Utökade söktermer
            "solar farm construction Europe MW",
            "European solar auction tender",
            "BESS grid services Europe frequency",
            "renewable IPP Europe acquisition",
            "bifacial agrivoltaics Europe",
        ]
    },
    "globalt": {
        "name": "Globalt",
        "emoji": "🌍",
        "queries": [
            "large-scale solar project GW 2024 2025",
            "mega solar farm construction",
            "grid-scale battery storage project",
            "solar plus storage hybrid project",
            "renewable energy IPP investment",
            # Utökade söktermer
            "NEOM solar Saudi Arabia",
            "India solar park Khavda Adani",
            "China solar capacity GW",
            "US utility solar IRA investment",
            "Australia solar battery project",
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
            # Utökade söktermer
            "LFP battery price trend",
            "solar module price forecast",
            "PPA price Europe trend",
            "grid curtailment solar solution",
            "solar LCOE cost reduction",
        ]
    }
}
