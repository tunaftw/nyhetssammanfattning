"""Retry-logik med exponential backoff för API-anrop."""

import time
import functools
from typing import Callable, TypeVar, Tuple, Type

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] = None
) -> Callable:
    """
    Decorator för retry med exponential backoff.

    Args:
        max_retries: Max antal försök (default 3)
        base_delay: Bas-fördröjning i sekunder (default 1.0)
        max_delay: Max fördröjning i sekunder (default 30.0)
        exceptions: Tuple med exception-typer att fånga
        on_retry: Callback som körs vid varje retry (exception, attempt)

    Returns:
        Decorated function

    Example:
        @retry_with_backoff(max_retries=3, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        # Beräkna delay med exponential backoff
                        delay = min(base_delay * (2 ** attempt), max_delay)

                        # Kör callback om den finns
                        if on_retry:
                            on_retry(e, attempt + 1)
                        else:
                            print(f"  Retry {attempt + 1}/{max_retries} efter {delay:.1f}s ({type(e).__name__})")

                        time.sleep(delay)

            # Alla försök misslyckades
            raise last_exception

        return wrapper
    return decorator


def log_retry(exception: Exception, attempt: int) -> None:
    """Standard callback för retry-loggning."""
    print(f"  ⚠️  Försök {attempt} misslyckades: {type(exception).__name__}")


if __name__ == "__main__":
    # Test
    call_count = 0

    @retry_with_backoff(max_retries=3, base_delay=0.1, exceptions=(ValueError,))
    def flaky_function():
        global call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Simulated error")
        return "Success!"

    result = flaky_function()
    print(f"Resultat: {result}")
    print(f"Antal anrop: {call_count}")
