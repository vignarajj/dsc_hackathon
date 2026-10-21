class PipelineError(Exception):
    """A request failed with an HTTP status the API should return as-is."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
