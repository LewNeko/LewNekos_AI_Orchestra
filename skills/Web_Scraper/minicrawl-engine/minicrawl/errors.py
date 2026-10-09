"""Typed errors. Everything that can go wrong while acquiring content has a class."""


class MiniCrawlError(Exception):
    retryable = False


class FetchError(MiniCrawlError):
    def __init__(self, message, url=None, status=None):
        super().__init__(message)
        self.url, self.status = url, status


class RateLimitError(FetchError):
    retryable = True

    def __init__(self, message, url=None, status=429, retry_after=None):
        super().__init__(message, url, status)
        self.retry_after = retry_after


class FetchTimeout(FetchError):
    retryable = True


class ServerError(FetchError):
    retryable = True


class BlockedError(FetchError):
    """401/403/451 or a bot-wall. Not retried over HTTP; the strategy may escalate to a browser."""

    def __init__(self, message, url=None, status=403, response=None):
        super().__init__(message, url, status)
        self.response = response


class HTTPStatusError(FetchError):
    """Non-retryable 4xx (404, 410, ...)."""


class BrowserUnavailable(MiniCrawlError):
    pass


class SearchUnavailable(MiniCrawlError):
    pass


class ExtractionError(MiniCrawlError):
    pass
