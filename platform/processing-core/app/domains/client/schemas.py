from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email: str | None = None
    full_name: str | None = None


class ClientDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class ClientMeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: UserDTO
    client: ClientDTO | None = None
    roles: list[str]
