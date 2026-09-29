"""Thread-safe bounded ring frame buffer with stale frame dropping policy."""
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional, Tuple, Any
import numpy as np


class BoundedFrameBuffer:
    """Thread-safe bounded ring buffer.
    
    When full, the oldest unconsumed frame is discarded so real-time processing
    never falls behind wall-clock video feed.
    """

    def __init__(self, maxsize: int = 30) -> None:
        if maxsize < 1:
            raise ValueError("Buffer maxsize must be >= 1")
        self.maxsize = maxsize
        self._queue: deque = deque(maxlen=maxsize)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._closed = False

        # Telemetry metrics
        self.total_enqueued: int = 0
        self.total_dropped: int = 0
        self.total_dequeued: int = 0

    def put(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Pushes a frame to the buffer. If full, drops the oldest frame.
        
        Returns:
            True if frame was enqueued without dropping; False if oldest frame was dropped.
        """
        ts = timestamp or datetime.now(timezone.utc)
        item = (frame_index, ts, frame)

        with self._lock:
            if self._closed:
                return False

            was_full = len(self._queue) >= self.maxsize
            if was_full:
                # deque(maxlen=maxsize) automatically discards the leftmost item on append,
                # but we track drops explicitly
                self.total_dropped += 1

            self._queue.append(item)
            self.total_enqueued += 1
            self._not_empty.notify()
            return not was_full

    def get(
        self, timeout: Optional[float] = None
    ) -> Optional[Tuple[int, datetime, np.ndarray]]:
        """Retrieves the next oldest frame.
        
        Blocks up to timeout seconds. Returns None if timed out or closed.
        """
        with self._not_empty:
            while not self._queue:
                if self._closed:
                    return None
                if timeout is not None and timeout <= 0:
                    return None
                if not self._not_empty.wait(timeout=timeout):
                    return None  # Timed out

            if self._closed and not self._queue:
                return None

            item = self._queue.popleft()
            self.total_dequeued += 1
            return item

    def get_latest(self) -> Optional[Tuple[int, datetime, np.ndarray]]:
        """Retrieves and clears all queued frames, returning only the most recent one.
        
        Useful when skipping all buffered latency directly to live frame.
        """
        with self._lock:
            if not self._queue or self._closed:
                return None
            dropped_in_flush = len(self._queue) - 1
            self.total_dropped += dropped_in_flush
            latest_item = self._queue[-1]
            self._queue.clear()
            self.total_dequeued += 1
            return latest_item

    def clear(self) -> None:
        """Empties all buffered frames."""
        with self._lock:
            self._queue.clear()

    def close(self) -> None:
        """Closes the buffer and unblocks waiting consumers."""
        with self._lock:
            self._closed = True
            self._not_empty.notify_all()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def is_full(self) -> bool:
        with self._lock:
            return len(self._queue) >= self.maxsize

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0
