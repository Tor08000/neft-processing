from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import boto3
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa



SUPPORTED_ALGS = {"ed25519", "rsa_pss_sha256", "ecdsa_p256_sha256"}
KMS_ALG_MAP = {
    "ed25519": "ED25519",
    "rsa_pss_sha256": "RSA_PSS_SHA_256",
    "ecdsa_p256_sha256": "ECDSA_SHA_256",
}


class AuditSigningError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuditSignature:
    signature: str
    alg: str
    key_id: str
    signed_at: datetime


@dataclass(frozen=True)
class AuditSigningKey:
    key_id: str
    alg: str
    public_key_pem: str
    status: str
    created_at: datetime | None = None


class AuditSigner(Protocol):
    alg: str
    key_id: str

    def sign(self, message: bytes) -> str:
        ...

    def verify(self, message: bytes, signature_b64: str) -> bool:
        ...

    @property
    def public_key_pem(self) -> str:
        ...


class LocalSigner:
    def __init__(self, *, alg: str, key_id: str, private_key_pem: bytes) -> None:
        if alg not in SUPPORTED_ALGS:
            raise AuditSigningError(f"Unsupported signing algorithm: {alg}")
        self.alg = alg
        self.key_id = key_id
        self._private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        self._public_key = self._private_key.public_key()

    def sign(self, message: bytes) -> str:
        signature = self._sign_raw(message)
        return base64.b64encode(signature).decode("utf-8")

    def verify(self, message: bytes, signature_b64: str) -> bool:
        try:
            signature = base64.b64decode(signature_b64)
        except ValueError:
            return False
        try:
            self._verify_raw(message, signature)
        except InvalidSignature:
            return False
        return True

    @property
    def public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def _sign_raw(self, message: bytes) -> bytes:
        if self.alg == "ed25519":
            if not isinstance(self._private_key, ed25519.Ed25519PrivateKey):
                raise AuditSigningError("Invalid Ed25519 private key")
            return self._private_key.sign(message)
        if self.alg == "rsa_pss_sha256":
            if not isinstance(self._private_key, rsa.RSAPrivateKey):
                raise AuditSigningError("Invalid RSA private key")
            return self._private_key.sign(
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
        if self.alg == "ecdsa_p256_sha256":
            if not isinstance(self._private_key, ec.EllipticCurvePrivateKey):
                raise AuditSigningError("Invalid ECDSA private key")
            return self._private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        raise AuditSigningError(f"Unsupported signing algorithm: {self.alg}")

    def _verify_raw(self, message: bytes, signature: bytes) -> None:
        if self.alg == "ed25519":
            if not isinstance(self._public_key, ed25519.Ed25519PublicKey):
                raise AuditSigningError("Invalid Ed25519 public key")
            self._public_key.verify(signature, message)
            return
        if self.alg == "rsa_pss_sha256":
            if not isinstance(self._public_key, rsa.RSAPublicKey):
                raise AuditSigningError("Invalid RSA public key")
            self._public_key.verify(
                signature,
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return
        if self.alg == "ecdsa_p256_sha256":
            if not isinstance(self._public_key, ec.EllipticCurvePublicKey):
                raise AuditSigningError("Invalid ECDSA public key")
            self._public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            return
        raise AuditSigningError(f"Unsupported signing algorithm: {self.alg}")


class PublicKeyVerifier:
    def __init__(self, *, alg: str, key_id: str, public_key_pem: str) -> None:
        if alg not in SUPPORTED_ALGS:
            raise AuditSigningError(f"Unsupported signing algorithm: {alg}")
        self.alg = alg
        self.key_id = key_id
        self._public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        self._public_key_pem = public_key_pem

    def sign(self, message: bytes) -> str:
        raise AuditSigningError("Signing not supported for public key verifier")

    def verify(self, message: bytes, signature_b64: str) -> bool:
        try:
            signature = base64.b64decode(signature_b64)
        except ValueError:
            return False
        try:
            self._verify_raw(message, signature)
        except AuditSigningError:
            return False
        except InvalidSignature:
            return False
        return True

    @property
    def public_key_pem(self) -> str:
        return self._public_key_pem

    def _verify_raw(self, message: bytes, signature: bytes) -> None:
        if self.alg == "ed25519":
            if not isinstance(self._public_key, ed25519.Ed25519PublicKey):
                raise AuditSigningError("Invalid Ed25519 public key")
            self._public_key.verify(signature, message)
            return
        if self.alg == "rsa_pss_sha256":
            if not isinstance(self._public_key, rsa.RSAPublicKey):
                raise AuditSigningError("Invalid RSA public key")
            self._public_key.verify(
                signature,
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return
        if self.alg == "ecdsa_p256_sha256":
            if not isinstance(self._public_key, ec.EllipticCurvePublicKey):
                raise AuditSigningError("Invalid ECDSA public key")
            self._public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            return
        raise AuditSigningError(f"Unsupported signing algorithm: {self.alg}")


class KmsSigner:
    def __init__(self, *, alg: str, key_id: str, client=None) -> None:
        if alg not in KMS_ALG_MAP:
            raise AuditSigningError(f"Unsupported KMS signing algorithm: {alg}")
        self.alg = alg
        self.key_id = key_id
        self._client = client or boto3.client("kms")
        self._public_key_pem: str | None = None

    def sign(self, message: bytes) -> str:
        response = self._client.sign(
            KeyId=self.key_id,
            Message=message,
            MessageType="RAW",
            SigningAlgorithm=KMS_ALG_MAP[self.alg],
        )
        signature = response.get("Signature", b"")
        return base64.b64encode(signature).decode("utf-8")

    def verify(self, message: bytes, signature_b64: str) -> bool:
        try:
            signature = base64.b64decode(signature_b64)
        except ValueError:
            return False
        response = self._client.verify(
            KeyId=self.key_id,
            Message=message,
            MessageType="RAW",
            Signature=signature,
            SigningAlgorithm=KMS_ALG_MAP[self.alg],
        )
        return bool(response.get("SignatureValid"))

    @property
    def public_key_pem(self) -> str:
        if self._public_key_pem:
            return self._public_key_pem
        response = self._client.get_public_key(KeyId=self.key_id)
        public_key = serialization.load_der_public_key(response["PublicKey"])
        self._public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return self._public_key_pem


class AuditSigningService:
    def __init__(self) -> None:
        self.mode = (os.getenv("AUDIT_SIGNING_MODE", "local") or "").lower()
        self.required = os.getenv("AUDIT_SIGNING_REQUIRED", "false").lower() in {"1", "true", "yes"}
        self.alg = os.getenv("AUDIT_SIGNING_ALG", "ed25519")
        self.key_id = os.getenv("AUDIT_SIGNING_KEY_ID", "local-dev-key-v1")
        self._private_key_b64 = os.getenv("AUDIT_SIGNING_PRIVATE_KEY_B64", "")
        self._public_keys_json = os.getenv("AUDIT_SIGNING_PUBLIC_KEYS_JSON", "")
        self._current_signer: AuditSigner | None = None
        self._public_verifiers: dict[str, AuditSigner] = {}
        self._load_local_verifiers()

    def sign(self, message: bytes) -> AuditSignature | None:
        signer = self._get_current_signer()
        if not signer:
            if self.required:
                raise AuditSigningError("Audit signing is required but no signer is configured")
            return None
        try:
            signature = signer.sign(message)
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise AuditSigningError("Audit signing failed") from exc
            return None
        return AuditSignature(
            signature=signature,
            alg=signer.alg,
            key_id=signer.key_id,
            signed_at=datetime.now(timezone.utc),
        )

    def verify(self, *, message: bytes, signature_b64: str, alg: str, key_id: str) -> bool:
        signer = self._get_signer_for_key(key_id=key_id, alg=alg)
        if not signer:
            return False
        return signer.verify(message, signature_b64)

    def list_keys(self) -> list[AuditSigningKey]:
        keys: list[AuditSigningKey] = []
        current = self._get_current_signer()
        if current:
            keys.append(
                AuditSigningKey(
                    key_id=current.key_id,
                    alg=current.alg,
                    public_key_pem=current.public_key_pem,
                    status="active",
                )
            )
        for key_id, verifier in self._public_verifiers.items():
            if current and key_id == current.key_id:
                continue
            keys.append(
                AuditSigningKey(
                    key_id=key_id,
                    alg=verifier.alg,
                    public_key_pem=verifier.public_key_pem,
                    status="retired",
                )
            )
        return keys

    def _get_current_signer(self) -> AuditSigner | None:
        if self._current_signer is not None:
            return self._current_signer
        if self.mode == "disabled":
            return None
        if self.mode == "local":
            private_key_pem = self._load_private_key()
            if not private_key_pem:
                return None
            self._current_signer = LocalSigner(alg=self.alg, key_id=self.key_id, private_key_pem=private_key_pem)
            return self._current_signer
        if self.mode == "kms":
            self._current_signer = KmsSigner(alg=self.alg, key_id=self.key_id)
            return self._current_signer
        raise AuditSigningError(f"Unsupported signing mode: {self.mode}")

    def _get_signer_for_key(self, *, key_id: str, alg: str) -> AuditSigner | None:
        if self.mode == "disabled":
            return None
        if self.mode == "local":
            current = self._get_current_signer()
            if current and current.key_id == key_id and current.alg == alg:
                return current
            verifier = self._public_verifiers.get(key_id)
            if verifier and verifier.alg == alg:
                return verifier
            return None
        if self.mode == "kms":
            return KmsSigner(alg=alg, key_id=key_id)
        return None

    def _load_private_key(self) -> bytes | None:
        value = self._private_key_b64 or ""
        if not value:
            return None
        try:
            return base64.b64decode(value)
        except ValueError as exc:
            raise AuditSigningError("Invalid audit signing private key encoding") from exc

    def _load_local_verifiers(self) -> None:
        raw = self._public_keys_json or ""
        if not raw:
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AuditSigningError("Invalid AUDIT_SIGNING_PUBLIC_KEYS_JSON") from exc
        if not isinstance(data, dict):
            raise AuditSigningError("AUDIT_SIGNING_PUBLIC_KEYS_JSON must be a JSON object")
        for key_id, value in data.items():
            if not isinstance(value, dict):
                continue
            alg = value.get("alg")
            public_key = value.get("public_key_pem") or value.get("public_key_b64")
            if not alg or not public_key:
                continue
            pem = self._resolve_public_key(public_key)
            self._public_verifiers[str(key_id)] = PublicKeyVerifier(alg=alg, key_id=str(key_id), public_key_pem=pem)

    @staticmethod
    def _resolve_public_key(value: str) -> str:
        if "BEGIN PUBLIC KEY" in value:
            return value
        try:
            return base64.b64decode(value).decode("utf-8")
        except ValueError:
            raise AuditSigningError("Invalid public key encoding")


__all__ = [
    "AuditSignature",
    "AuditSigningError",
    "AuditSigningKey",
    "AuditSigningService",
]
