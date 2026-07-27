class CLIError(Exception):
    def __init__(self, message: str, stderr: str = ""):
        self.message = message
        self.stderr = stderr
        super().__init__(self.message)


class CLITimeoutError(CLIError):
    def __init__(self, timeout: int, stderr: str = ""):
        self.timeout = timeout
        super().__init__(f"CLI execution timed out after {timeout}s", stderr)


class CLIParseError(CLIError):
    def __init__(self, message: str, raw_output: str = ""):
        self.raw_output = raw_output
        super().__init__(message)


class CLINotFoundError(CLIError):
    def __init__(self, command: str):
        super().__init__(f"CLI command not found: {command}")
