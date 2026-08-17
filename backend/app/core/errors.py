class UserFacingError(Exception):
    """Exception with a safe message that can be shown in the web UI."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

