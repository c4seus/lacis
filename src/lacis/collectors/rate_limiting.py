import threading
import time
from collections import deque
from collections.abc import Callable, Mapping

from lacis.storage.responses import ResponseSource

REQUESTS_PER_SECOND = {
    ResponseSource.COMPANY_REGISTER: 6,
    ResponseSource.BODACC: 5,
}
WINDOW_SECONDS = 1.0

Clock = Callable[[], float]
Sleep = Callable[[float], None]


class RateLimiter:
    def __init__(
        self, requests_per_second: int, clock: Clock = time.monotonic, sleep: Sleep = time.sleep
    ) -> None:
        self.requests_per_second = requests_per_second
        self.clock = clock
        self.sleep = sleep
        self.recent_request_times: deque[float] = deque(maxlen=requests_per_second)
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = self.clock()
            if len(self.recent_request_times) == self.requests_per_second:
                window_end = self.recent_request_times[0] + WINDOW_SECONDS
                if now < window_end:
                    self.sleep(window_end - now)
                    now = window_end
            self.recent_request_times.append(now)


class RateLimiters:
    def __init__(
        self,
        requests_per_second: Mapping[ResponseSource, int] = REQUESTS_PER_SECOND,
        clock: Clock = time.monotonic,
        sleep: Sleep = time.sleep,
    ) -> None:
        self.limiters = {
            source: RateLimiter(rate, clock, sleep) for source, rate in requests_per_second.items()
        }

    def wait_for(self, source: ResponseSource) -> None:
        self.limiters[source].wait()


SHARED_RATE_LIMITERS = RateLimiters()
