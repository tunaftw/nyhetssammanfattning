#!/usr/bin/env python3
"""
Huvudscript för daglig nyhetssammanfattning.

Hämtar nyheter om solenergi och batterilagring via Gemini API,
sammanfattar dem och skickar ett formaterat mail.

Användning:
    python main.py              # Kör full pipeline (hämta + skicka)
    python main.py --test       # Skicka test-mail
    python main.py --dry-run    # Hämta nyheter utan att skicka mail
    python main.py --preview    # Spara HTML lokalt för förhandsgranskning
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Lägg till src i path om vi kör från rot
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Ladda miljövariabler
load_dotenv()

from news_fetcher import fetch_all_news
from email_sender import send_email, send_test_email, render_email_html
from config import RECIPIENT_EMAIL, GEMINI_API_KEY, RESEND_API_KEY


def check_configuration() -> bool:
    """Kontrollerar att nödvändiga miljövariabler är satta."""
    errors = []

    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY saknas")

    if not RESEND_API_KEY:
        errors.append("RESEND_API_KEY saknas")

    if not RECIPIENT_EMAIL:
        errors.append("RECIPIENT_EMAIL saknas")

    if errors:
        print("❌ Konfigurationsfel:")
        for error in errors:
            print(f"   - {error}")
        print("\nSe .env.example för att konfigurera miljövariabler.")
        return False

    return True


def run_full_pipeline() -> bool:
    """
    Kör hela pipelinen: hämta nyheter och skicka mail.

    Returns:
        True om lyckad, False vid fel
    """
    print("=" * 60)
    print(f"🌅 Nyhetssammanfattning - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Kontrollera konfiguration
    if not check_configuration():
        return False

    try:
        # Steg 1: Hämta nyheter
        print("\n📡 Hämtar nyheter via Gemini...")
        news_data = fetch_all_news()

        total_news = sum(
            len(cat["news_items"])
            for cat in news_data["news_by_category"].values()
        )

        if total_news == 0:
            print("⚠️  Inga nyheter hittades. Avbryter.")
            return False

        print(f"✅ Hämtade {total_news} nyheter")

        # Visa sammanfattning per kategori
        for cat_key, cat_data in news_data["news_by_category"].items():
            count = len(cat_data["news_items"])
            print(f"   {cat_data['emoji']} {cat_data['name']}: {count} nyheter")

        # Steg 2: Skicka mail
        print(f"\n📧 Skickar mail till {RECIPIENT_EMAIL}...")
        result = send_email(news_data)

        print("\n✅ Klart!")
        print(f"   Mail-ID: {result.get('id', 'unknown')}")

        return True

    except Exception as e:
        print(f"\n❌ Fel: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_dry_run() -> bool:
    """Hämtar nyheter utan att skicka mail."""
    print("🔍 Dry-run läge - hämtar nyheter utan att skicka mail\n")

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY saknas")
        return False

    try:
        news_data = fetch_all_news()

        total_news = sum(
            len(cat["news_items"])
            for cat in news_data["news_by_category"].values()
        )

        print(f"\n📊 Resultat: {total_news} nyheter hämtade\n")

        for cat_key, cat_data in news_data["news_by_category"].items():
            print(f"\n{cat_data['emoji']} {cat_data['name']}")
            print("-" * 40)

            for item in cat_data["news_items"]:
                score = item.get("relevance_score", "?")
                print(f"[{score}] {item['title'][:70]}")
                print(f"    {item['summary'][:100]}...")
                print(f"    🔗 {item.get('url', 'Ingen länk')}")
                print()

        return True

    except Exception as e:
        print(f"❌ Fel: {e}")
        return False


def run_preview() -> bool:
    """Hämtar nyheter och sparar HTML lokalt för förhandsgranskning."""
    print("👁️  Preview-läge - sparar HTML lokalt\n")

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY saknas")
        return False

    try:
        news_data = fetch_all_news()

        html = render_email_html(news_data)

        # Spara till fil
        output_path = Path(__file__).parent.parent / "preview.html"
        output_path.write_text(html, encoding="utf-8")

        print(f"✅ HTML sparad till: {output_path}")
        print(f"   Öppna i webbläsare för att förhandsgranska")

        # Spara också JSON för debugging
        json_path = Path(__file__).parent.parent / "preview_data.json"
        json_path.write_text(
            json.dumps(news_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"   JSON-data sparad till: {json_path}")

        return True

    except Exception as e:
        print(f"❌ Fel: {e}")
        return False


def run_test() -> bool:
    """Skickar ett test-mail."""
    print("🧪 Test-läge - skickar test-mail\n")

    if not check_configuration():
        return False

    try:
        result = send_test_email()
        print(f"✅ Test-mail skickat!")
        print(f"   Till: {RECIPIENT_EMAIL}")
        print(f"   Mail-ID: {result.get('id', 'unknown')}")
        return True

    except Exception as e:
        print(f"❌ Fel: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Daglig nyhetssammanfattning för solenergi och batterilagring"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Skicka ett test-mail för att verifiera konfigurationen"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hämta nyheter utan att skicka mail (för debugging)"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Hämta nyheter och spara HTML lokalt för förhandsgranskning"
    )

    args = parser.parse_args()

    if args.test:
        success = run_test()
    elif args.dry_run:
        success = run_dry_run()
    elif args.preview:
        success = run_preview()
    else:
        success = run_full_pipeline()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
