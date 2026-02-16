from __future__ import annotations

from app.services.invitations.invitation_tokens import generate_invitation_token, hash_invitation_token, invite_expiration


def test_token_hash_is_not_plain() -> None:
    token, token_hash = generate_invitation_token()
    assert token
    assert token_hash
    assert token_hash != token
    assert token_hash == hash_invitation_token(token)


def test_invitation_expiration_future() -> None:
    expires_at = invite_expiration()
    assert expires_at.tzinfo is not None
