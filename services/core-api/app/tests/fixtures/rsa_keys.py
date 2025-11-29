import pytest

try:  # pragma: no cover - optional dependency
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    serialization = None
    rsa = None


@pytest.fixture(scope="session")
def rsa_keys() -> dict:
    if rsa and serialization:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
    else:
        import rsa as pure_rsa

        public_key, private_key = pure_rsa.newkeys(2048)
        private_pem = private_key.save_pkcs1().decode("utf-8")
        public_pem = public_key.save_pkcs1().decode("utf-8")

    return {"private": private_pem, "public": public_pem}
