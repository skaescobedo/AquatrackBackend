from datetime import datetime
from pydantic import BaseModel, Field


class PasswordResetTokenBase(BaseModel):
    usuario_id: int
    token_hash: str = Field(..., max_length=64)
    expira_at: datetime


class PasswordResetTokenCreate(PasswordResetTokenBase):
    pass


class PasswordResetTokenOut(PasswordResetTokenBase):
    token_id: int
    used_at: datetime | None = None
    created_at: datetime

    class Config:
        orm_mode = True
