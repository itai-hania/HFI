"""Auth API request/response schemas."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Password-based login request."""
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT bearer token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
