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

from news_fetcher import fetch_all_news, generate_weekly_insights
from email_sender import send_email, send_test_email, render_email_html, send_deep_email
from config import RECIPIENT_EMAIL, GEMINI_API_KEY, RESEND_API_KEY
from url_validator import validate_urls_batch, filter_valid_news, run_validation
from database import save_report, get_reports, get_articles, get_monthly_summary, get_database_stats


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
    Kör hela pipelinen: hämta nyheter, validera länkar och skicka mail.

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

        # Steg 2: Validera URL:er
        print("\n🔗 Validerar länkar...")
        all_urls = [
            item["url"]
            for cat in news_data["news_by_category"].values()
            for item in cat["news_items"]
            if item.get("url")
        ]

        validation_results = run_validation(all_urls)

        # Validera och fixa brutna länkar (ersätt med Google-sökning)
        total_fixed = 0
        for cat_key, cat_data in news_data["news_by_category"].items():
            valid, fixed = filter_valid_news(cat_data["news_items"], validation_results)
            cat_data["news_items"] = valid

            if fixed:
                total_fixed += len(fixed)
                print(f"   🔧 {cat_data['name']}: {len(fixed)} länkar ersatta med Google-sökning")

        # Uppdatera total efter filtrering
        total_after = sum(
            len(cat["news_items"])
            for cat in news_data["news_by_category"].values()
        )

        if total_fixed > 0:
            print(f"   ✅ {total_after} artiklar totalt ({total_fixed} med söklänkar)")

        if total_after == 0:
            print("⚠️  Inga nyheter med giltiga länkar. Avbryter.")
            return False

        # Visa sammanfattning per kategori
        print("\n📊 Sammanfattning:")
        for cat_key, cat_data in news_data["news_by_category"].items():
            count = len(cat_data["news_items"])
            print(f"   {cat_data['emoji']} {cat_data['name']}: {count} nyheter")

        # Steg 3: Skicka mail
        print(f"\n📧 Skickar mail till {RECIPIENT_EMAIL}...")
        result = send_email(news_data)

        # Steg 4: Spara till historik
        print("\n💾 Sparar till historik...")
        report_id = save_report(news_data, report_type="daily")
        print(f"   Rapport #{report_id} sparad")

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

        # Validera URL:er (samma som i full pipeline)
        print("\n🔗 Validerar länkar...")
        all_urls = [
            item["url"]
            for cat in news_data["news_by_category"].values()
            for item in cat["news_items"]
            if item.get("url")
        ]

        validation_results = run_validation(all_urls)

        # Validera och fixa brutna länkar (ersätt med Google-sökning)
        total_fixed = 0
        for cat_key, cat_data in news_data["news_by_category"].items():
            valid, fixed = filter_valid_news(cat_data["news_items"], validation_results)
            cat_data["news_items"] = valid

            if fixed:
                total_fixed += len(fixed)
                print(f"   🔧 {cat_data['name']}: {len(fixed)} länkar ersatta med Google-sökning")

        total_after = sum(
            len(cat["news_items"])
            for cat in news_data["news_by_category"].values()
        )

        if total_fixed > 0:
            print(f"   ✅ {total_after} artiklar totalt ({total_fixed} med söklänkar)")

        html = render_email_html(news_data)

        # Spara till fil
        output_path = Path(__file__).parent.parent / "preview.html"
        output_path.write_text(html, encoding="utf-8")

        print(f"\n✅ HTML sparad till: {output_path}")
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


def run_weekly_analysis(days_back: int = 7) -> bool:
    """
    Kör veckoanalys med djupare AI-insikter.

    Args:
        days_back: Antal dagar att analysera (default 7)

    Returns:
        True om lyckad, False vid fel
    """
    print("=" * 60)
    print(f"📊 Veckoanalys - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Analyserar senaste {days_back} dagarna")
    print("=" * 60)

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

        # Steg 2: Validera URL:er
        print("\n🔗 Validerar länkar...")
        all_urls = [
            item["url"]
            for cat in news_data["news_by_category"].values()
            for item in cat["news_items"]
            if item.get("url")
        ]

        validation_results = run_validation(all_urls)

        # Validera och fixa brutna länkar (ersätt med Google-sökning)
        total_fixed = 0
        for cat_key, cat_data in news_data["news_by_category"].items():
            valid, fixed = filter_valid_news(cat_data["news_items"], validation_results)
            cat_data["news_items"] = valid

            if fixed:
                total_fixed += len(fixed)
                print(f"   🔧 {cat_data['name']}: {len(fixed)} länkar ersatta med söklänk")

        total_after = sum(
            len(cat["news_items"])
            for cat in news_data["news_by_category"].values()
        )

        if total_after == 0:
            print("⚠️  Inga nyheter hittades. Avbryter.")
            return False

        print(f"   ✅ {total_after} artiklar totalt ({total_fixed} med söklänkar)")

        # Steg 3: Generera AI-insikter
        print("\n🧠 Genererar AI-analys...")
        insights = generate_weekly_insights(news_data)
        news_data["ai_insights"] = insights
        news_data["report_type"] = "weekly"

        print(f"   ✅ {len(insights.get('trends', []))} trender identifierade")
        print(f"   ✅ {len(insights.get('company_context', []))} företagsrelevanta insikter")
        print(f"   ✅ {len(insights.get('predictions', []))} marknadsprognoser")

        # Visa sammanfattning
        print("\n📊 Sammanfattning:")
        for cat_key, cat_data in news_data["news_by_category"].items():
            count = len(cat_data["news_items"])
            if count > 0:
                print(f"   {cat_data['emoji']} {cat_data['name']}: {count} nyheter")

        # Steg 4: Skicka deep email
        print(f"\n📧 Skickar veckorapport till {RECIPIENT_EMAIL}...")
        result = send_deep_email(news_data)

        # Steg 5: Spara till historik
        print("\n💾 Sparar till historik...")
        report_id = save_report(news_data, report_type="weekly")
        print(f"   Veckorapport #{report_id} sparad")

        print("\n✅ Veckorapport skickad!")
        print(f"   Mail-ID: {result.get('id', 'unknown')}")

        return True

    except Exception as e:
        print(f"\n❌ Fel: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_history(month: str = None, search: str = None) -> bool:
    """
    Visar historik över tidigare rapporter.

    Args:
        month: YYYY-MM för att filtrera på månad
        search: Sökterm för att hitta artiklar
    """
    print("📚 Nyhetshistorik")
    print("=" * 60)

    if month:
        # Visa månadssammanfattning
        try:
            year, mon = month.split("-")
            summary = get_monthly_summary(int(year), int(mon))

            print(f"\n📅 {month}")
            print(f"   Rapporter: {summary['stats']['total_reports']}")
            print(f"   Artiklar: {summary['stats']['total_articles']}")

            if summary['stats']['avg_relevance']:
                print(f"   Snitt relevans: {summary['stats']['avg_relevance']:.1f}/10")

            if summary['by_category']:
                print("\n📊 Per kategori:")
                for cat in summary['by_category']:
                    print(f"   {cat['category_name']}: {cat['count']} artiklar")

            if summary['top_articles']:
                print("\n🏆 Top 10 artiklar:")
                for i, art in enumerate(summary['top_articles'], 1):
                    score = art.get('relevance_score', '?')
                    print(f"   {i}. [{score}] {art['title'][:60]}...")
                    print(f"      {art['source']} - {art['report_date']}")

            return True

        except ValueError:
            print(f"❌ Ogiltigt datumformat: {month}")
            print("   Använd format: YYYY-MM (t.ex. 2025-08)")
            return False

    elif search:
        # Sök i artiklar
        articles = get_articles(search=search, limit=20)

        if not articles:
            print(f"\n🔍 Inga artiklar matchade: '{search}'")
            return True

        print(f"\n🔍 Sökresultat för '{search}': {len(articles)} träffar\n")

        for art in articles:
            score = art.get('relevance_score', '?')
            print(f"[{score}] {art['title'][:65]}")
            print(f"    {art['source']} - {art['report_date']}")
            print(f"    {art['url'][:70]}...")
            print()

        return True

    else:
        # Visa övergripande statistik
        stats = get_database_stats()

        if stats['total_reports'] == 0:
            print("\n📭 Ingen historik ännu.")
            print("   Kör 'python main.py' för att generera första rapporten.")
            return True

        print(f"\n📈 Övergripande statistik:")
        print(f"   Totalt rapporter: {stats['total_reports']}")
        print(f"   Totalt artiklar: {stats['total_articles']}")

        if stats['date_range']['first']:
            print(f"   Första rapport: {stats['date_range']['first']}")
            print(f"   Senaste rapport: {stats['date_range']['last']}")

        if stats['by_category']:
            print("\n📊 Artiklar per kategori:")
            for cat in stats['by_category']:
                name = cat.get('category_name') or 'Okänd'
                print(f"   {name}: {cat['count']}")

        # Visa senaste rapporter
        recent = get_reports(limit=5)
        if recent:
            print("\n📅 Senaste rapporter:")
            for rep in recent:
                rtype = "📊" if rep['report_type'] == 'weekly' else "📰"
                print(f"   {rtype} {rep['report_date']}: {rep['total_articles']} artiklar")

        print("\n💡 Tips:")
        print("   --history --month 2025-08    Visa augusti 2025")
        print("   --history --search 'batteri' Sök efter 'batteri'")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Nyhetssammanfattning för solenergi och batterilagring"
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
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Kör veckoanalys med AI-insikter (djupare analys)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Antal dagar att analysera (endast för --weekly, default 7)"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Visa historik över tidigare rapporter"
    )
    parser.add_argument(
        "--month",
        type=str,
        help="Filtrera på månad (format: YYYY-MM, t.ex. 2025-08)"
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Sök i historiska artiklar"
    )

    args = parser.parse_args()

    if args.test:
        success = run_test()
    elif args.dry_run:
        success = run_dry_run()
    elif args.preview:
        success = run_preview()
    elif args.weekly:
        success = run_weekly_analysis(days_back=args.days)
    elif args.history:
        success = run_history(month=args.month, search=args.search)
    else:
        success = run_full_pipeline()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
