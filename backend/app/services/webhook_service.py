import structlog
import httpx
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

log = structlog.get_logger()


async def send_webhook(
    url: str,
    payload: dict,
    max_retries: int = 3,
) -> bool:
    """POST payload to url with exponential-backoff retry. Never raises; returns success bool."""

    def _on_retry(retry_state) -> None:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        log.warning(
            "webhook_retry",
            url=url,
            attempt=retry_state.attempt_number,
            error=str(exc) if exc else "unknown",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                before_sleep=_on_retry,
            ):
                with attempt:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
        except RetryError as exc:
            last = exc.last_attempt.exception() if exc.last_attempt else None
            log.error(
                "webhook_exhausted",
                url=url,
                max_retries=max_retries,
                last_error=str(last) if last else "unknown",
            )
            return False
        except Exception as exc:
            log.error("webhook_unexpected_error", url=url, error=str(exc))
            return False
        else:
            log.info("webhook_delivered", url=url)
            return True

    return False  # unreachable; satisfies type checker
