"""Hämtar och sammanfattar nyheter med Gemini API och Google Search grounding."""

import json
from datetime import datetime
from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    COMPANY_CONTEXT,
    SEARCH_CATEGORIES,
    MAX_NEWS_ITEMS,
)


def create_client() -> genai.Client:
    """Skapar Gemini API-klient."""
    return genai.Client(api_key=GEMINI_API_KEY)


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

För varje nyhet, returnera EXAKT följande JSON-format (och inget annat):
{{
    "news": [
        {{
            "title": "Nyhetens rubrik",
            "summary": "Kort sammanfattning på 2-3 meningar som förklarar varför detta är relevant.",
            "url": "https://...",
            "source": "Källans namn (t.ex. Reuters, PV Magazine)",
            "relevance_score": 8
        }}
    ]
}}

Viktigt:
- Relevance_score 1-10 baserat på hur relevant nyheten är för en svensk IPP som bygger sol- och batteriparker
- Prioritera: konkreta projekt, investeringar, policy-ändringar, teknikgenombrott
- Undvik: produktlanseringar för privatpersoner, lokala småskaliga installationer
- Om nyheten är på engelska, skriv sammanfattningen på engelska
- Om nyheten är på svenska, skriv sammanfattningen på svenska
- Returnera ENDAST valid JSON, ingen annan text
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
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


def fetch_all_news() -> dict:
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
