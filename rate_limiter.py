import time
from collections import deque
from datetime import datetime, timedelta


class RateLimiter:
    def __init__(self, max_requests=2, time_window=1):
        """
        Initialize rate limiter
        max_requests: maximum number of requests allowed in the time window
        time_window: time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()

    def can_make_request(self) -> bool:
        """Check if a request can be made within rate limits"""
        now = datetime.now()

        # Remove old requests from the window
        while self.requests and self.requests[0] < now - timedelta(seconds=self.time_window):
            self.requests.popleft()

        # Check if we can make a new request
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        return False

    def wait_if_needed(self):
        """Wait until a request can be made"""
        while not self.can_make_request():
            time.sleep(0.1)  # Sleep for 100ms
        return True
