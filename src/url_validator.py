"""Validerar URL:er med async HTTP requests innan mail skickas."""

import asyncio
import aiohttp
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class ValidationResult:
    """Resultat från URL-validering."""
    url: str
    is_valid: bool
    status_code: Optional[int]
    final_url: Optional[str]  # URL efter eventuella redirects
    error: Optional[str]


async def validate_url(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int = 10
) -> ValidationResult:
    """
    Validerar en URL med HTTP HEAD request.

    Args:
        session: aiohttp ClientSession
        url: URL att validera
        timeout: Max antal sekunder att vänta

    Returns:
        ValidationResult med status
    """
    # Hoppa över kända problematiska URL-mönster
    if "vertexaisearch.cloud.google.com" in url:
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            final_url=None,
            error="Google redirect-länk (ej direkt URL)"
        )

    if not url.startswith(("http://", "https://")):
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            final_url=None,
            error="Ogiltig URL-format"
        )

    try:
        async with session.head(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            allow_redirects=True,
            ssl=False  # Vissa sajter har SSL-problem
        ) as response:
            # 2xx och 3xx är OK, 4xx och 5xx är fel
            is_valid = response.status < 400

            return ValidationResult(
                url=url,
                is_valid=is_valid,
                status_code=response.status,
                final_url=str(response.url) if response.url != url else None,
                error=None if is_valid else f"HTTP {response.status}"
            )

    except asyncio.TimeoutError:
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            final_url=None,
            error="Timeout"
        )
    except aiohttp.ClientError as e:
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            final_url=None,
            error=f"Nätverksfel: {type(e).__name__}"
        )
    except Exception as e:
        return ValidationResult(
            url=url,
            is_valid=False,
            status_code=None,
            final_url=None,
            error=f"Oväntat fel: {str(e)[:50]}"
        )


async def validate_urls_batch(
    urls: List[str],
    max_concurrent: int = 10,
    timeout: int = 10
) -> Dict[str, ValidationResult]:
    """
    Validerar flera URL:er parallellt.

    Args:
        urls: Lista med URL:er att validera
        max_concurrent: Max antal samtidiga requests
        timeout: Timeout per request i sekunder

    Returns:
        Dict med URL -> ValidationResult
    """
    if not urls:
        return {}

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def validate_with_semaphore(url: str) -> ValidationResult:
        async with semaphore:
            return await validate_url(session, url, timeout)

    # Använd en gemensam session med rimliga headers
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0; +https://sveasolar.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    connector = aiohttp.TCPConnector(limit=max_concurrent, ssl=False)

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = [validate_with_semaphore(url) for url in urls]
        validation_results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, result in zip(urls, validation_results):
            if isinstance(result, Exception):
                results[url] = ValidationResult(
                    url=url,
                    is_valid=False,
                    status_code=None,
                    final_url=None,
                    error=f"Exception: {str(result)[:50]}"
                )
            else:
                results[url] = result

    return results


def create_google_search_url(title: str, source: str = None) -> str:
    """
    Skapar en Google-söklänk baserat på artikelns titel.

    Args:
        title: Artikelns titel
        source: Källans namn (optional, läggs till i sökningen)

    Returns:
        Google sök-URL
    """
    from urllib.parse import quote

    search_query = title
    if source and source.lower() not in title.lower():
        search_query = f"{title} {source}"

    return f"https://www.google.com/search?q={quote(search_query)}"


def filter_valid_news(
    news_items: List[Dict],
    validation_results: Dict[str, ValidationResult],
    replace_broken_with_search: bool = True
) -> Tuple[List[Dict], List[Dict]]:
    """
    Filtrerar nyheter baserat på URL-validering.

    Om replace_broken_with_search=True, ersätts brutna URL:er med Google-sökning
    istället för att ta bort artikeln.

    Args:
        news_items: Lista med nyhetsartiklar
        validation_results: Dict med URL -> ValidationResult
        replace_broken_with_search: Ersätt brutna länkar med Google-sökning

    Returns:
        Tuple med (giltiga nyheter, nyheter med ersatta/brutna länkar)
    """
    valid = []
    fixed = []  # Artiklar där URL ersatts med söklänk

    for item in news_items:
        url = item.get("url", "")

        if not url:
            if replace_broken_with_search and item.get("title"):
                # Ingen URL - skapa Google-sökning baserat på titel
                item["url"] = create_google_search_url(
                    item["title"],
                    item.get("source")
                )
                item["url_is_search"] = True
                item["url_verified"] = False
                item["url_error"] = "Ingen original-URL, söklänk skapad"
                valid.append(item)
                fixed.append(item)
            continue

        result = validation_results.get(url)

        if result and result.is_valid:
            # Uppdatera URL om vi fick en redirect
            if result.final_url and result.final_url != url:
                item["url"] = result.final_url
                item["original_url"] = url
            item["url_verified"] = True
            item["url_status"] = result.status_code
            valid.append(item)
        else:
            # Bruten länk
            if replace_broken_with_search and item.get("title"):
                # Ersätt med Google-sökning
                item["original_url"] = url
                item["url"] = create_google_search_url(
                    item["title"],
                    item.get("source")
                )
                item["url_is_search"] = True
                item["url_verified"] = False
                item["url_error"] = result.error if result else "Ej validerad"
                valid.append(item)
                fixed.append(item)
            else:
                item["url_verified"] = False
                item["url_error"] = result.error if result else "Ej validerad"
                # Artikeln tas bort (läggs inte i valid)

    return valid, fixed


def run_validation(urls: List[str]) -> Dict[str, ValidationResult]:
    """
    Synkron wrapper för att köra async validering.

    Args:
        urls: Lista med URL:er att validera

    Returns:
        Dict med URL -> ValidationResult
    """
    return asyncio.run(validate_urls_batch(urls))


if __name__ == "__main__":
    # Test
    test_urls = [
        "https://www.pv-magazine.com/",
        "https://www.solenerginyheter.se/",
        "https://invalid-url-that-does-not-exist.com/",
        "vertexaisearch.cloud.google.com/grounding-api-redirect/test",
        "https://www.google.com/",
    ]

    print("Testar URL-validering...\n")
    results = run_validation(test_urls)

    for url, result in results.items():
        status = "OK" if result.is_valid else "FEL"
        print(f"[{status}] {url[:50]}")
        if result.error:
            print(f"      Fel: {result.error}")
        if result.final_url:
            print(f"      Redirect till: {result.final_url[:50]}")
