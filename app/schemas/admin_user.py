from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

RoleCode = Literal["SUPER_ADMIN", "INTEGRATION_ADMIN", "FINANCE", "AUDITOR"]


class UserChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


class UserFields(UserChange):
    display_name: str = Field(min_length=1, max_length=200)
    role: RoleCode
    active: bool

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class CreateAdminUser(UserFields):
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=15, max_length=128)


class UpdateAdminUser(UserFields):
    expected_version: int = Field(strict=True, ge=1)


class RevokeUserSessions(UserChange):
    expected_version: int = Field(strict=True, ge=1)


class PasswordChange(UserChange):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=15, max_length=128)


class InviteAdmin(UserChange):
    email: EmailStr = Field(max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    role: RoleCode
    expires_hours: int = Field(default=24, ge=1, le=168)


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=200)
    new_password: SecretStr = Field(min_length=15, max_length=128)


class InvitationAccept(PasswordResetConfirm):
    pass
