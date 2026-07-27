class GPSError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class GPSNotFoundError(GPSError):
    def __init__(self, device: str = ""):
        self.device = device
        super().__init__(f"GPS device not found: {device}")


class GPSReadError(GPSError):
    def __init__(self, message: str = "Failed to read GPS data"):
        super().__init__(message)


class GPSTimeoutError(GPSError):
    def __init__(self, timeout: int = 0):
        self.timeout = timeout
        super().__init__(f"GPS read timed out after {timeout}s")
