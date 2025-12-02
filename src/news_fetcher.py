"""Hämtar och sammanfattar nyheter med Gemini API och Google Search grounding."""

import json
from datetime import datetime, timedelta
from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    COMPANY_CONTEXT,
    SEARCH_CATEGORIES,
    MAX_NEWS_ITEMS,
)
from utils.retry import retry_with_backoff
from sources.google_rss import fetch_news_from_rss, RSS_FEEDS


def create_client() -> genai.Client:
    """Skapar Gemini API-klient."""
    return genai.Client(api_key=GEMINI_API_KEY)


@retry_with_backoff(max_retries=3, base_delay=2.0, exceptions=(Exception,))
def fetch_news_for_category(
    client: genai.Client,
    category_key: str,
    category_config: dict,
    max_items: int = 4
) -> list[dict]:
    """
    Hämtar nyheter för en specifik kategori med Google Search grounding.

    Returns:
        Lista med nyheter, varje nyhet är en dict med:
        - title: Rubrik
        - summary: Kort sammanfattning (2-3 meningar)
        - url: Länk till artikeln
        - source: Källans namn
        - relevance_score: 1-10 hur relevant för Svea Solar
    """

    queries_text = "\n".join(f"- {q}" for q in category_config["queries"])

    prompt = f"""
{COMPANY_CONTEXT}

Sök efter de senaste och mest relevanta nyheterna inom kategorin "{category_config['name']}"
med fokus på följande söktermer:
{queries_text}

Hitta de {max_items} mest relevanta nyheterna från de senaste 7 dagarna.

KRITISKT OM URL:ER:
- Returnera ENDAST direkta länkar till originalartiklar (t.ex. https://pv-magazine.com/2024/...)
- UNDVIK Google redirect-länkar (vertexaisearch.cloud.google.com)
- Om du inte kan hitta en direkt URL, ange källans huvuddomän (t.ex. https://www.reuters.com/)

För varje nyhet, returnera EXAKT följande JSON-format (och inget annat):
{{
    "news": [
        {{
            "title": "Nyhetens exakta rubrik från artikeln",
            "summary": "Kort sammanfattning på 2-3 meningar som förklarar varför detta är relevant.",
            "url": "https://direktlank-till-artikel.com/...",
            "source": "Källans namn (t.ex. Reuters, PV Magazine, Energimyndigheten)",
            "published_date": "2025-11-28",
            "relevance_score": 8
        }}
    ]
}}

REGLER:
- published_date: Datum i format YYYY-MM-DD. Uppskatta om exakt datum saknas.
- relevance_score: 1-10 baserat på relevans för svensk IPP som bygger sol/batteriparker
- Prioritera: konkreta projekt >10 MW, investeringar, PPA-avtal, policy-ändringar, teknikgenombrott
- Undvik: produkter för privatpersoner, installationer <1 MW, opinionsartiklar
- Språk: Behåll originalspråket (engelska/svenska) i sammanfattningen
- Format: Returnera ENDAST valid JSON, ingen markdown eller annan text
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
            )
        )

        # Extrahera text från svaret
        if not response.candidates:
            print(f"  Inga kandidater i svar för {category_key}")
            return []

        # Hämta text från response
        response_text = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                response_text += part.text

        response_text = response_text.strip()

        # Hantera om svaret är wrappat i markdown code block
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Ta bort första och sista raden (``` markers)
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        data = json.loads(response_text)
        news_items = data.get("news", [])

        # Lägg till kategori-info på varje nyhet
        for item in news_items:
            item["category"] = category_key
            item["category_name"] = category_config["name"]
            item["category_emoji"] = category_config["emoji"]

        return news_items

    except json.JSONDecodeError as e:
        print(f"  Kunde inte parsa JSON för kategori {category_key}: {e}")
        print(f"  Svar: {response_text[:500] if response_text else 'Inget svar'}")
        return []
    except Exception as e:
        print(f"  Fel vid hämtning av nyheter för {category_key}: {e}")
        import traceback
        traceback.print_exc()
        return []


def filter_by_date(news_items: list, max_days: int = 7) -> tuple[list, int]:
    """
    Filtrerar bort nyheter som är äldre än max_days.

    Args:
        news_items: Lista med nyhetsartiklar
        max_days: Max antal dagar gamla nyheter att behålla

    Returns:
        Tuple med (filtrerade nyheter, antal borttagna)
    """
    if not news_items:
        return [], 0

    cutoff_date = datetime.now() - timedelta(days=max_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    filtered = []
    removed = 0

    for item in news_items:
        pub_date = item.get("published_date", "")

        # Om inget datum finns, behåll artikeln (kan vara ny)
        if not pub_date:
            filtered.append(item)
            continue

        # Parsa datumet
        try:
            # Hantera olika datumformat
            if len(pub_date) == 10:  # YYYY-MM-DD
                item_date = pub_date
            elif len(pub_date) > 10:  # Längre format, ta bara datumdelen
                item_date = pub_date[:10]
            else:
                filtered.append(item)  # Ogiltig format, behåll
                continue

            # Jämför datum
            if item_date >= cutoff_str:
                filtered.append(item)
            else:
                removed += 1

        except (ValueError, TypeError):
            # Om datumparsning misslyckas, behåll artikeln
            filtered.append(item)

    return filtered, removed


def fetch_all_news(max_age_days: int = 7) -> dict:
    """
    Hämtar nyheter från alla kategorier och rankar dem.

    Returns:
        Dict med:
        - news_by_category: Dict med nyheter grupperade per kategori
        - top_news: Lista med de mest relevanta nyheterna totalt
        - fetch_date: Datum för hämtning
    """
    client = create_client()

    all_news = []
    news_by_category = {}

    # Beräkna hur många nyheter per kategori (fördela MAX_NEWS_ITEMS)
    num_categories = len(SEARCH_CATEGORIES)
    items_per_category = max(3, MAX_NEWS_ITEMS // num_categories)

    for category_key, category_config in SEARCH_CATEGORIES.items():
        print(f"Hämtar nyheter för: {category_config['name']}...")

        news_items = fetch_news_for_category(
            client,
            category_key,
            category_config,
            max_items=items_per_category
        )

        news_by_category[category_key] = {
            "name": category_config["name"],
            "emoji": category_config["emoji"],
            "news_items": news_items
        }

        all_news.extend(news_items)

    # Komplettera med Google RSS om vi har få nyheter
    total_gemini = len(all_news)
    if total_gemini < MAX_NEWS_ITEMS:
        print(f"\n📰 Kompletterar med Google RSS ({total_gemini}/{MAX_NEWS_ITEMS} nyheter)...")
        rss_news = fetch_news_from_rss(max_per_feed=3)

        # Filtrera bort dubbletter (baserat på URL)
        existing_urls = {item.get("url") for item in all_news if item.get("url")}
        unique_rss = [item for item in rss_news if item.get("url") not in existing_urls]

        if unique_rss:
            print(f"   ✅ Lade till {len(unique_rss)} unika RSS-nyheter")

            # Lägg till RSS-nyheter i en egen kategori eller fördela
            if "rss_news" not in news_by_category:
                news_by_category["rss_news"] = {
                    "name": "Fler nyheter (RSS)",
                    "emoji": "📰",
                    "news_items": unique_rss
                }
            all_news.extend(unique_rss)

    # Filtrera bort gamla nyheter
    total_before_date_filter = len(all_news)
    total_old_removed = 0

    for cat_key, cat_data in news_by_category.items():
        filtered, removed = filter_by_date(cat_data["news_items"], max_days=max_age_days)
        cat_data["news_items"] = filtered
        total_old_removed += removed

    if total_old_removed > 0:
        print(f"\n📅 Datumfilter: {total_old_removed} gamla nyheter borttagna (äldre än {max_age_days} dagar)")

    # Uppdatera all_news efter datumfiltrering
    all_news = [
        item
        for cat in news_by_category.values()
        for item in cat["news_items"]
    ]

    # Sortera alla nyheter efter relevans
    all_news_sorted = sorted(
        all_news,
        key=lambda x: x.get("relevance_score", 0),
        reverse=True
    )

    # Ta topp MAX_NEWS_ITEMS
    top_news = all_news_sorted[:MAX_NEWS_ITEMS]

    return {
        "news_by_category": news_by_category,
        "top_news": top_news,
        "fetch_date": datetime.now().strftime("%Y-%m-%d"),
        "fetch_time": datetime.now().strftime("%H:%M"),
    }


def generate_weekly_insights(news_data: dict) -> dict:
    """
    Genererar AI-baserade insikter från veckans nyheter.

    Args:
        news_data: Dict med news_by_category

    Returns:
        Dict med trends, company_context, predictions
    """
    client = create_client()

    # Sammanställ alla nyheter som kontext
    all_news_text = ""
    for cat in news_data["news_by_category"].values():
        all_news_text += f"\n## {cat['name']}\n"
        for item in cat["news_items"]:
            all_news_text += f"- {item['title']}: {item['summary']}\n"

    prompt = f"""
Analysera dessa nyheter från sol- och batteribranschen den senaste veckan:

{all_news_text}

Som strategisk analytiker för Svea Solar (svensk IPP som bygger sol- och batteriparker), generera:

1. OBSERVERADE TRENDER (4-6 punkter):
   - Vilka mönster ser du i nyheterna?
   - Geografiska, teknologiska eller marknadsmässiga trender?
   - Vad har hänt inom batterilagring?

2. RELEVANS FÖR SVEA SOLAR (4-6 punkter):
   - Hur påverkar dessa nyheter en svensk solparks-utvecklare?
   - Konkurrentrörelser att bevaka?
   - Möjligheter eller risker?

3. MARKNADSUTSIKTER (3-4 punkter):
   - Vad indikerar nyheterna om framtiden?
   - Prisförändringar eller investeringsläge?
   - Regulatoriska förändringar att bevaka?

Returnera som JSON (och ENDAST JSON, ingen annan text):
{{
    "trends": ["...", "...", "..."],
    "company_context": ["...", "...", "..."],
    "predictions": ["...", "..."]
}}

Skriv på svenska. Var konkret och specifik - referera till faktiska nyheter och siffror.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
            )
        )

        response_text = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                response_text += part.text

        response_text = response_text.strip()

        # Hantera markdown code block
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        insights = json.loads(response_text)

        return {
            "trends": insights.get("trends", []),
            "company_context": insights.get("company_context", []),
            "predictions": insights.get("predictions", []),
        }

    except Exception as e:
        print(f"Fel vid generering av AI-insikter: {e}")
        return {
            "trends": ["Kunde inte generera trender automatiskt."],
            "company_context": ["Kunde inte generera företagskontext automatiskt."],
            "predictions": ["Kunde inte generera prognoser automatiskt."],
        }


if __name__ == "__main__":
    # Test
    from dotenv import load_dotenv
    load_dotenv()

    result = fetch_all_news()
    print(f"\nHämtade {len(result['top_news'])} nyheter totalt")

    for category_key, category_data in result["news_by_category"].items():
        print(f"\n{category_data['emoji']} {category_data['name']}: {len(category_data['news_items'])} nyheter")
        for item in category_data["news_items"]:
            print(f"  - [{item.get('relevance_score', '?')}] {item['title'][:60]}...")
