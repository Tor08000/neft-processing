from __future__ import annotations

from app.domains.client.repo import ClientRepository
from app.domains.client.schemas import ClientDTO, ClientMeResponse, UserDTO


def build_client_me_response(token: dict, repo: ClientRepository) -> ClientMeResponse:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = token.get("role")
    if role and role not in roles:
        roles.append(role)

    client_payload = None
    client = repo.get_client_by_id(token.get("client_id"))
    if client is not None:
        client_payload = ClientDTO(id=str(client.id), name=str(client.name))

    return ClientMeResponse(
        user=UserDTO(
            id=str(token.get("user_id") or token.get("sub") or ""),
            email=token.get("email"),
            full_name=token.get("full_name"),
        ),
        client=client_payload,
        roles=[str(item) for item in roles],
    )
