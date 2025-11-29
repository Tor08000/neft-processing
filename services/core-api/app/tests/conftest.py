import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

ROOT_DIR = Path(__file__).resolve().parents[4]
SHARED_PATH = ROOT_DIR / "shared" / "python"

if SHARED_PATH.exists():
    sys.path.append(str(SHARED_PATH))

# Use in-memory SQLite for tests to avoid coupling to external Postgres.
os.environ.setdefault("NEFT_DB_URL", "sqlite+pysqlite:///:memory:")


PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDQJdz1t9IfZZIu
Mo/NRIn/DWrKUDv3/8NEdTVTxy8Nu3UzInRldZZm4psF+nf0fBOwvofeYR4ey7CC
uimK+iONPDAxuorhcBygjA6SLWCuEw7A9iNTOua7DG8XGPJPEPh/zNpB2VU16wFH
wgVQV6bcruTPou8FEaem2sRX8bTwiUPWJ7KvE8d2zhGqzjUVFABb32hdVgDONZf4
nU2IQP5HxIK3ib4sS6apg+vBr+EKCZSc2lX+d4cSOVQYq6CXUbkCkBHgi5OVZKl+
IHCXj3QC1SkTP66eqZiaUAdKIoxfVpJPcDlkTocVvh4h/YrZVl8iw70Avn2E7P+h
3VEPHpzJAgMBAAECggEAWS2nthUMLwx27VkXWFRBpWdrtgNbNh073YQ0FVFU/Raw
F3jvEpsnFayHy69snnBchVCUaLgGTh5p4RB+hP83pSbA5UVthDni4fwvr/xGHD6p
Bw5NwzaMrV4d6HD1O9/i/+pWJnlFc0Tc9xAO88WiBZHfEYDW1D6krC21ipJRue3n
q6FkbnTMRDAoOe5ALeL4/o37n3bYiGsP8sfKRf7lmWXg6NYmvDWFETtBCTAjrZgs
ZGw/4MrgoEM6O6qc3FtmUFUJT/mF4TVo+ZdQ0tPQA/gUjPngcgnErZE01gslDxxI
kfJEQp9LtGmQkjwb+j3uogzSXjjBzo2AsgqzYnCf4wKBgQDr85rZ9LxCMADI7gx3
ThuE+apCSXJ+jpUvgbBdEt8avf9gqGhZEp4vx8fBM41PulXr+jRNYcm3NPHB4oxJ
oFuRgm2qOSx07NL0ubjqx6TQ4nolRcb6yPcfj+Xwc4TRDvBbR2ioWnrqTem0spA2
gatUeVMeh3fRirokqUzHrop8FwKBgQDh1Xm0SsDRnHt9NOHHS2AL4iadORZqTK+u
RcbOQvGmRGo8QEpUt8FpFu537f9LRSeI/i4sx6tS3W5srlgwu0lVmsWd6k/vrMiE
g489CV9c4lkRcQuqNlRVsvCHeJzIVfZW6+wjzO6CkQObkYwB2btThwgaiXVHdfxl
PlOXvYLaHwKBgQDGoKIhDRdWGJbwjwTLgmNEQ/CCMNZDl8Aa5/ARygsqtfs/4UVG
hpfH3URZbg5tqY0fQ9e3tLRcmCNUdmRmrqmnCsdK3yp/m8XS4m26pyol9iGhMuZY
w8jVNwv4qSaL3ymTjb+ayeBjUgeFaDRizjHuwNup/ZxuN3yP1D2gc1x9LQKBgBCe
nDlHcw85++CH/sGi62uUdhEF/X9PK3Kg0fOl+5Cn4kWS2aWIbGRmeqA61Jneef1b
71v+Sb5sa072OalEby4smLR5ZO6XgZ427FiqkukMA1AESL57BxPTel4N40PfB6T3
8cXks/zJ3UEaofoU4vNPsan6SbY7mZp9zrsRCEszAoGAexFT0Z9qHnC9ilvzlxq4
2HoVlr44eB3fdtibmuJrMIYxFwBjmuvtyWBunIl6bVy5SwcCUItsTbUzV9Y0fzyA
NailaUkqcG5FOM61sOIXDPBRJeQrObwG1yMX8KGrssB8hkVIZ6ooKaEOAacOPTcr
HHY98GAH4Vn/SLHqp6Mfuqw=
-----END PRIVATE KEY-----"""

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0CXc9bfSH2WSLjKPzUSJ
/w1qylA79//DRHU1U8cvDbt1MyJ0ZXWWZuKbBfp39HwTsL6H3mEeHsuwgropivoj
jTwwMbqK4XAcoIwOki1grhMOwPYjUzrmuwxvFxjyTxD4f8zaQdlVNesBR8IFUFem
3K7kz6LvBRGnptrEV/G08IlD1ieyrxPHds4Rqs41FRQAW99oXVYAzjWX+J1NiED+
R8SCt4m+LEumqYPrwa/hCgmUnNpV/neHEjlUGKugl1G5ApAR4IuTlWSpfiBwl490
AtUpEz+unqmYmlAHSiKMX1aST3A5ZE6HFb4eIf2K2VZfIsO9AL59hOz/od1RDx6c
yQIDAQAB
-----END PUBLIC KEY-----"""


@pytest.fixture(scope="session")
def rsa_keys() -> dict:
    return {"private": PRIVATE_KEY, "public": PUBLIC_KEY}


@pytest.fixture(autouse=True)
def _mock_admin_public_key(monkeypatch: pytest.MonkeyPatch, rsa_keys: dict):
    try:
        from app.security import admin_auth
    except ModuleNotFoundError:
        return

    monkeypatch.setattr(admin_auth, "_cached_public_key", None, raising=False)
    monkeypatch.setattr(admin_auth, "_public_key_cached_at", 0.0, raising=False)
    monkeypatch.setattr(admin_auth, "get_public_key", lambda: rsa_keys["public"])


@pytest.fixture
def make_jwt(rsa_keys: dict):
    def _make_jwt(role: str = "ADMIN", minutes_valid: int = 60, sub: str = "user-1"):
        payload = {
            "sub": sub,
            "role": role,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes_valid),
        }
        return jwt.encode(payload, rsa_keys["private"], algorithm="RS256")

    return _make_jwt


@pytest.fixture
def admin_token(make_jwt):
    return make_jwt(role="ADMIN")


@pytest.fixture
def user_token(make_jwt):
    return make_jwt(role="USER")


@pytest.fixture
def admin_auth_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}
