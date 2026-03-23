from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    """Acepta `store_name` o `storeName` en JSON (evita 422 si el front manda camelCase)."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str
    store_name: str = Field(
        ...,
        validation_alias=AliasChoices("store_name", "storeName"),
    )

    @field_validator("store_name")
    @classmethod
    def validate_store_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("El nombre de la tienda debe tener al menos 2 caracteres")
        if len(v) > 150:
            raise ValueError("El nombre de la tienda no puede superar 150 caracteres")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    store_id: int
    role: str
    store_name: Optional[str] = None
    tiendanube_user_id: Optional[str] = None
    needs_tiendanube: bool = True
