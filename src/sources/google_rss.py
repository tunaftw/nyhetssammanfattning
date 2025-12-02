"""Google News RSS-integration för att hämta nyheter."""

import re
import html
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote, unquote
import httpx
import feedparser


class GoogleNewsRSS:
    """
    Hämtar nyheter via Google News RSS-feed.

    Fördelar:
    - Gratis, ingen API-nyckel
    - Extraherar faktiska URL:er (inte Google redirect)
    - Kompletterar Gemini med fler resultat
    """

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self, timeout: int = 15):
        """
        Args:
            timeout: HTTP timeout i sekunder
        """
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)",
                "Accept": "application/rss+xml, application/xml, text/xml",
            }
        )

    def fetch_news(
        self,
        query: str,
        language: str = "sv",
        country: str = "SE",
        max_results: int = 5
    ) -> List[Dict]:
        """
        Hämtar nyheter från Google News RSS.

        Args:
            query: Sökfråga
            language: Språkkod (sv, en, etc.)
            country: Landskod (SE, US, etc.)
            max_results: Max antal resultat

        Returns:
            Lista med nyheter som dicts
        """
        url = f"{self.BASE_URL}?q={quote(query)}&hl={language}&gl={country}&ceid={country}:{language}"

        try:
            response = self.client.get(url)
            response.raise_for_status()

            feed = feedparser.parse(response.text)

            articles = []
            for entry in feed.entries[:max_results]:
                # Extrahera faktisk URL från Google redirect
                real_url = self._extract_real_url(entry.link)

                # Extrahera källans namn
                source = self._extract_source(entry)

                # Parsa datum
                published_date = self._parse_date(entry.get("published"))

                # Rensa HTML från sammanfattning
                summary = self._clean_html(entry.get("summary", ""))

                articles.append({
                    "title": entry.title,
                    "summary": summary[:300] if summary else "",
                    "url": real_url,
                    "source": source,
                    "published_date": published_date,
                    "api_source": "google_rss",
                    "relevance_score": 5,  # Default, kan justeras senare
                })

            return articles

        except httpx.HTTPError as e:
            print(f"  Google RSS-fel för '{query[:30]}': {e}")
            return []
        except Exception as e:
            print(f"  Oväntat fel vid Google RSS: {e}")
            return []

    def _extract_real_url(self, google_url: str) -> str:
        """
        Extraherar faktisk URL från Google News redirect.

        Google News använder format:
        https://news.google.com/rss/articles/CBMi...

        Vi behöver följa redirecten eller parsa base64-kodad URL.
        """
        if not google_url:
            return ""

        # Om det inte är en Google-länk, returnera direkt
        if "news.google.com" not in google_url:
            return google_url

        try:
            # Försök följa redirecten
            response = self.client.head(google_url, follow_redirects=True)
            final_url = str(response.url)

            # Om vi fortfarande är på Google, returnera original
            if "google.com" in final_url:
                return google_url

            return final_url

        except Exception:
            # Om redirect misslyckas, returnera original
            return google_url

    def _extract_source(self, entry) -> str:
        """Extraherar källans namn från RSS-entry."""
        # Google News inkluderar ofta källan i source-taggen
        if hasattr(entry, 'source') and entry.source:
            if hasattr(entry.source, 'title'):
                return entry.source.title

        # Alternativt, försök extrahera från titeln
        # Format: "Rubrik - Källa"
        if " - " in entry.title:
            parts = entry.title.rsplit(" - ", 1)
            if len(parts) == 2:
                return parts[1].strip()

        return "Google News"

    def _parse_date(self, date_str: Optional[str]) -> str:
        """Parsar datum från RSS till YYYY-MM-DD format."""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")

        try:
            # feedparser ger ofta en time.struct_time
            if hasattr(date_str, 'tm_year'):
                return datetime(*date_str[:6]).strftime("%Y-%m-%d")

            # Försök parsa olika format
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%SZ",
            ]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        except Exception:
            pass

        return datetime.now().strftime("%Y-%m-%d")

    def _clean_html(self, text: str) -> str:
        """Tar bort HTML-taggar och dekodar entities."""
        if not text:
            return ""

        # Ta bort HTML-taggar
        clean = re.sub(r'<[^>]+>', '', text)

        # Dekoda HTML entities
        clean = html.unescape(clean)

        # Normalisera whitespace
        clean = ' '.join(clean.split())

        return clean

    def __del__(self):
        """Stäng HTTP-klienten."""
        if hasattr(self, 'client'):
            self.client.close()


def fetch_from_google_rss(
    queries: List[str],
    language: str = "sv",
    max_per_query: int = 3
) -> List[Dict]:
    """
    Convenience-funktion för att hämta nyheter från flera sökfrågor.

    Args:
        queries: Lista med sökfrågor
        language: Språkkod
        max_per_query: Max resultat per fråga

    Returns:
        Aggregerad lista med nyheter (deduplikerad)
    """
    rss = GoogleNewsRSS()
    all_news = []
    seen_titles = set()

    for query in queries:
        news = rss.fetch_news(query, language=language, max_results=max_per_query)

        for item in news:
            # Enkel deduplikation baserat på titel
            title_lower = item["title"].lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                all_news.append(item)

    return all_news


if __name__ == "__main__":
    # Test
    print("Testar Google News RSS...\n")

    rss = GoogleNewsRSS()

    queries = [
        "solcellspark Sverige",
        "batterilagring energi",
    ]

    for query in queries:
        print(f"Söker: {query}")
        print("-" * 40)

        news = rss.fetch_news(query, max_results=3)

        for item in news:
            print(f"  {item['title'][:60]}...")
            print(f"  Källa: {item['source']}")
            print(f"  URL: {item['url'][:60]}...")
            print()
