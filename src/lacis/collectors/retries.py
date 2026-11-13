from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

TOO_MANY_REQUESTS = 429
SERVER_ERRORS = range(500, 600)
RETRY_AFTER_HEADER = "Retry-After"


def is_retryable_status(http_status: int) -> bool:
    return http_status == TOO_MANY_REQUESTS or http_status in SERVER_ERRORS


@dataclass(frozen=True)
class RetryPolicy:
    maximum_attempts: int = 4
    first_delay: timedelta = timedelta(seconds=0.5)
    maximum_delay: timedelta = timedelta(seconds=60)

    def backoff_delay(self, failed_attempts: int) -> timedelta:
        return min(self.first_delay * (1 << (failed_attempts - 1)), self.maximum_delay)

    def delay_before_retry(
        self, failed_attempts: int, retry_after: str | None, now: datetime
    ) -> timedelta:
        requested_delay = parse_retry_after(retry_after, now) if retry_after else None
        if requested_delay is None:
            return self.backoff_delay(failed_attempts)
        return min(requested_delay, self.maximum_delay)


DEFAULT_RETRY_POLICY = RetryPolicy()


def parse_retry_after(retry_after: str, now: datetime) -> timedelta | None:
    value = retry_after.strip()
    if value.isdigit():
        return timedelta(seconds=int(value))
    try:
        retry_time = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_time.tzinfo is None:
        retry_time = retry_time.replace(tzinfo=UTC)
    return max(retry_time - now, timedelta(0))
