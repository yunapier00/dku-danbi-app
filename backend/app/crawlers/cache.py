import threading
import time
from typing import Any, Callable, Dict, Hashable, Tuple


class TTLCache:
    """성공한 결과만 ttl 동안 보관하는 스레드 안전 캐시.

    - loader 가 예외를 내면 아무것도 저장하지 않는다.
    - 락을 잡은 채 loader 를 실행하므로 같은 요청이 동시에 들어와도 크롤링(Chrome 기동 등)은 한 번만 일어난다.
    - ttl_seconds <= 0 이면 캐시를 쓰지 않는다.
    """

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._items: Dict[Hashable, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_load(self, key: Hashable, loader: Callable[[], Any]) -> Any:
        if self._ttl <= 0:
            return loader()

        with self._lock:
            hit = self._items.get(key)
            if hit is not None and hit[0] > self._clock():
                return hit[1]

            value = loader()
            now = self._clock()
            self._items = {k: v for k, v in self._items.items() if v[0] > now}
            self._items[key] = (now + self._ttl, value)
            return value
