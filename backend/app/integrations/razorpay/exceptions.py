class RazorpayBaseError(Exception):
    """Base exception for all Razorpay integration errors."""
    pass

class RazorpayAuthError(RazorpayBaseError):
    """Raised when Razorpay credentials (KEY_ID / KEY_SECRET) are invalid or unauthorized."""
    pass

class RazorpayNotFoundError(RazorpayBaseError):
    """Raised when the requested Razorpay resource (Payment/Order/Refund) is not found."""
    pass

class RazorpayRateLimitError(RazorpayBaseError):
    """Raised when Razorpay API rate limit is exceeded."""
    pass

class RazorpaySignatureVerificationError(RazorpayBaseError):
    """Raised when Razorpay webhook HMAC-SHA256 signature verification fails."""
    pass

class RazorpayAPIError(RazorpayBaseError):
    """Raised when Razorpay API returns an unexpected error response."""
    def __init__(self, status_code: int, message: str, error_data: dict = None):
        super().__init__(f"Razorpay API Error [{status_code}]: {message}")
        self.status_code = status_code
        self.message = message
        self.error_data = error_data or {}
