from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class BillRequest(BaseModel):
    """Bill fetch request validation."""
    reference_no: str = Field(..., min_length=14, max_length=14)
    disco: str = Field(default="fesco")

    @field_validator("reference_no")
    @classmethod
    def validate_reference_no(cls, v: str) -> str:
        # Sirf digits allowed
        if not re.match(r"^\d{14}$", v):
            raise ValueError("Reference number must be exactly 14 digits")
        return v

    @field_validator("disco")
    @classmethod
    def validate_disco(cls, v: str) -> str:
        allowed = {"fesco", "lesco", "gepco", "mepco", "iesco",
                   "pesco", "hesca", "qesco", "sepco", "tesco"}
        v = v.lower()
        if v not in allowed:
            raise ValueError(f"DISCO must be one of: {', '.join(allowed)}")
        return v


class EmailAlertRequest(BaseModel):
    """Email alert request."""
    email: str = Field(..., min_length=5, max_length=100)
    ref_no: str = Field(..., min_length=14, max_length=14)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", v):
            raise ValueError("Invalid email format")
        return v.lower()