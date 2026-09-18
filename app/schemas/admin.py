from pydantic import BaseModel, EmailStr, Field, SecretStr


class AdminLogin(BaseModel):
    identifier: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)
