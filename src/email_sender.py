"""Skickar e-post via Resend API."""

import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader

from config import RESEND_API_KEY, RECIPIENT_EMAIL, SENDER_EMAIL


def render_email_html(news_data: dict) -> str:
    """
    Renderar HTML-mall med nyhetsdata.

    Args:
        news_data: Dict från fetch_all_news() med news_by_category, top_news, etc.

    Returns:
        Renderad HTML-sträng
    """
    # Hitta templates-mappen
    templates_dir = Path(__file__).parent / "templates"

    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("email.html")

    # Räkna totalt antal nyheter
    total_news = sum(
        len(cat["news_items"])
        for cat in news_data["news_by_category"].values()
    )

    html = template.render(
        news_by_category=news_data["news_by_category"],
        top_news=news_data.get("top_news", []),
        fetch_date=news_data["fetch_date"],
        fetch_time=news_data.get("fetch_time", ""),
        news_count=total_news,
        recipient_email=RECIPIENT_EMAIL,
    )

    return html


def send_email(news_data: dict) -> dict:
    """
    Skickar nyhetsuppdatering via e-post.

    Args:
        news_data: Dict från fetch_all_news()

    Returns:
        Resend API-svar
    """
    resend.api_key = RESEND_API_KEY

    html_content = render_email_html(news_data)

    # Skapa subject med datum
    subject = f"☀️ Nyhetsuppdatering Sol & Batteri - {news_data['fetch_date']}"

    # Räkna nyheter
    total_news = sum(
        len(cat["news_items"])
        for cat in news_data["news_by_category"].values()
    )

    params = {
        "from": SENDER_EMAIL,
        "to": [RECIPIENT_EMAIL],
        "subject": subject,
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        print(f"E-post skickad! ID: {response.get('id', 'unknown')}")
        print(f"Till: {RECIPIENT_EMAIL}")
        print(f"Antal nyheter: {total_news}")
        return response
    except Exception as e:
        print(f"Fel vid skickande av e-post: {e}")
        raise


def send_test_email() -> dict:
    """Skickar ett test-mail för att verifiera konfigurationen."""
    resend.api_key = RESEND_API_KEY

    params = {
        "from": SENDER_EMAIL,
        "to": [RECIPIENT_EMAIL],
        "subject": "🧪 Test - Nyhetssammanfattning fungerar!",
        "html": """
        <h1>Test lyckades!</h1>
        <p>Din nyhetssammanfattning är korrekt konfigurerad.</p>
        <p>Du kommer få dagliga uppdateringar kl 06:00.</p>
        """,
    }

    return resend.Emails.send(params)


def render_deep_email_html(news_data: dict) -> str:
    """
    Renderar HTML-mall för veckorapport med AI-insikter.

    Args:
        news_data: Dict med news_by_category, ai_insights, etc.

    Returns:
        Renderad HTML-sträng
    """
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("deep_email.html")

    # Räkna statistik
    total_news = sum(
        len(cat["news_items"])
        for cat in news_data["news_by_category"].values()
    )

    verified_count = sum(
        1 for cat in news_data["news_by_category"].values()
        for item in cat["news_items"]
        if item.get("url_verified", False)
    )

    category_count = len([
        cat for cat in news_data["news_by_category"].values()
        if cat["news_items"]
    ])

    # Markera verified för template
    for cat in news_data["news_by_category"].values():
        for item in cat["news_items"]:
            item["verified"] = item.get("url_verified", False)

    html = template.render(
        news_by_category=news_data["news_by_category"],
        ai_insights=news_data.get("ai_insights", {
            "trends": [],
            "company_context": [],
            "predictions": []
        }),
        fetch_date=news_data["fetch_date"],
        news_count=total_news,
        verified_count=verified_count,
        category_count=category_count,
    )

    return html


def send_deep_email(news_data: dict) -> dict:
    """
    Skickar veckorapport med djupanalys via e-post.

    Args:
        news_data: Dict med news_by_category och ai_insights

    Returns:
        Resend API-svar
    """
    resend.api_key = RESEND_API_KEY

    html_content = render_deep_email_html(news_data)

    # Veckonummer för subject
    from datetime import datetime
    week_num = datetime.now().isocalendar()[1]

    subject = f"📊 Veckoanalys Sol & Batteri - v.{week_num}"

    params = {
        "from": SENDER_EMAIL,
        "to": [RECIPIENT_EMAIL],
        "subject": subject,
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        print(f"Veckorapport skickad! ID: {response.get('id', 'unknown')}")
        print(f"Till: {RECIPIENT_EMAIL}")
        return response
    except Exception as e:
        print(f"Fel vid skickande av veckorapport: {e}")
        raise


if __name__ == "__main__":
    # Test rendering
    from dotenv import load_dotenv
    load_dotenv()

    # Skapa testdata
    test_data = {
        "news_by_category": {
            "sverige_norden": {
                "name": "Sverige & Norden",
                "emoji": "🇸🇪",
                "news_items": [
                    {
                        "title": "Testnyheter: Stor solpark planeras i Skåne",
                        "summary": "Detta är en testsammanfattning för att visa hur formateringen ser ut.",
                        "url": "https://example.com/test",
                        "source": "Test Källa",
                        "relevance_score": 9,
                    }
                ]
            }
        },
        "fetch_date": "2024-01-15",
        "fetch_time": "06:00",
    }

    html = render_email_html(test_data)
    print("HTML renderad framgångsrikt!")
    print(f"Längd: {len(html)} tecken")

    # Spara för granskning
    with open("/tmp/test_email.html", "w") as f:
        f.write(html)
    print("Sparad till /tmp/test_email.html för granskning")
