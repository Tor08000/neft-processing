from pydantic import BaseModel

class ClientCreate(BaseModel):
    name: str
    inn: str | None = None
