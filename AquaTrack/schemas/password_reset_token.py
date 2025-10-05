from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PasswordResetTokenBase(BaseModel):
    usuario_id: int
    expira_at: datetime


class PasswordResetTokenCreate(PasswordResetTokenBase):
    pass


class PasswordResetTokenOut(PasswordResetTokenBase):
    token_id: int
    token_hash: str = Field(..., min_length=64, max_length=64)
    used_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
