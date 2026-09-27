from pydantic import BaseModel, EmailStr, Field, SecretStr


class AdminLogin(BaseModel):
    identifier: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)
    otp: str | None = Field(default=None, min_length=6, max_length=20)


class MfaCode(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class Reauthenticate(BaseModel):
    password: SecretStr = Field(min_length=1, max_length=128)
