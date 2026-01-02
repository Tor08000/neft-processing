import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.services.audit_signing import AwsKmsSigner


class _FakeKmsClient:
    def __init__(self, signature: bytes, public_key_der: bytes, signature_valid: bool = True) -> None:
        self._signature = signature
        self._public_key_der = public_key_der
        self._signature_valid = signature_valid

    def sign(self, **_kwargs):
        return {"Signature": self._signature}

    def verify(self, **_kwargs):
        return {"SignatureValid": self._signature_valid}

    def get_public_key(self, **_kwargs):
        return {"PublicKey": self._public_key_der}


def test_kms_signer_sign_and_verify_local() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    message = b"kms-signing"
    signature = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
    public_key_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    client = _FakeKmsClient(signature=signature, public_key_der=public_key_der)
    signer = AwsKmsSigner(
        alg="ecdsa_p256_sha256",
        key_id="kms-key",
        client=client,
        verify_mode="local",
        public_key_cache_seconds=60,
    )
    signature_b64 = signer.sign(message)
    assert base64.b64decode(signature_b64) == signature
    assert signer.verify(message, signature_b64) is True


def test_kms_signer_verify_via_kms() -> None:
    client = _FakeKmsClient(signature=b"sig", public_key_der=b"pub", signature_valid=True)
    signer = AwsKmsSigner(
        alg="rsa_pss_sha256",
        key_id="kms-key",
        client=client,
        verify_mode="kms",
        public_key_cache_seconds=60,
    )
    assert signer.verify(b"msg", base64.b64encode(b"sig").decode("utf-8")) is True
