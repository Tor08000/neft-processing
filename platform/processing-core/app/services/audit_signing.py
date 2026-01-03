from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import boto3
import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa

from neft_shared.settings import get_settings

from app.models.audit_signing_keys import AuditSigningKeyRecord


SUPPORTED_ALGS = {"ed25519", "rsa_pss_sha256", "ecdsa_p256_sha256"}
KMS_ALG_MAP = {
    "ed25519": "ED25519",
    "rsa_pss_sha256": "RSA_PSS_SHA_256",
    "ecdsa_p256_sha256": "ECDSA_SHA_256",
}

VAULT_ALG_MAP = {
    "ed25519": "ed25519",
    "rsa_pss_sha256": "rsa-pss",
    "ecdsa_p256_sha256": "ecdsa-p256",
}

_AUDIT_SIGNING_HEALTH: str | None = None


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


class AwsKmsSigner:
    def __init__(
        self,
        *,
        alg: str,
        key_id: str,
        client=None,
        verify_mode: str = "local",
        public_key_cache_seconds: int = 3600,
    ) -> None:
        if alg not in KMS_ALG_MAP:
            raise AuditSigningError(f"Unsupported KMS signing algorithm: {alg}")
        self.alg = alg
        self.key_id = key_id
        self.verify_mode = verify_mode
        self._client = client or boto3.client("kms")
        self._public_key_pem: str | None = None
        self._public_key_expires_at: float | None = None
        self._public_key_cache_seconds = public_key_cache_seconds

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
        if self.verify_mode == "local":
            try:
                verifier = PublicKeyVerifier(alg=self.alg, key_id=self.key_id, public_key_pem=self.public_key_pem)
                return verifier.verify(message, signature_b64)
            except Exception:  # noqa: BLE001
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
        if self._public_key_pem and self._public_key_expires_at:
            if time.time() < self._public_key_expires_at:
                return self._public_key_pem
        if self._public_key_pem and self._public_key_expires_at is None:
            return self._public_key_pem
        response = self._client.get_public_key(KeyId=self.key_id)
        public_key = serialization.load_der_public_key(response["PublicKey"])
        self._public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        self._public_key_expires_at = time.time() + self._public_key_cache_seconds
        return self._public_key_pem


class VaultTransitSigner:
    def __init__(
        self,
        *,
        alg: str,
        key_id: str,
        vault_addr: str,
        vault_token: str,
        mount: str = "transit",
        verify_mode: str = "vault",
        namespace: str | None = None,
        public_key_cache_seconds: int = 3600,
        session: requests.Session | None = None,
    ) -> None:
        if alg not in VAULT_ALG_MAP:
            raise AuditSigningError(f"Unsupported Vault signing algorithm: {alg}")
        self.alg = alg
        self.key_id = key_id
        self._vault_addr = vault_addr.rstrip("/")
        self._vault_token = vault_token
        self._mount = mount
        self.verify_mode = verify_mode
        self._namespace = namespace
        self._session = session or requests.Session()
        self._public_key_pem: str | None = None
        self._public_key_expires_at: float | None = None
        self._public_key_cache_seconds = public_key_cache_seconds

    def sign(self, message: bytes) -> str:
        payload = {"input": base64.b64encode(message).decode("utf-8"), "algorithm": VAULT_ALG_MAP[self.alg]}
        response = self._request("POST", f"/v1/{self._mount}/sign/{self.key_id}", json=payload)
        signature = response.get("data", {}).get("signature")
        if not signature:
            raise AuditSigningError("Vault signing response missing signature")
        return self._unwrap_signature(signature)

    def verify(self, message: bytes, signature_b64: str) -> bool:
        if self.verify_mode == "local":
            try:
                verifier = PublicKeyVerifier(alg=self.alg, key_id=self.key_id, public_key_pem=self.public_key_pem)
                return verifier.verify(message, signature_b64)
            except Exception:  # noqa: BLE001
                return False
        payload = {
            "input": base64.b64encode(message).decode("utf-8"),
            "signature": self._wrap_signature(signature_b64),
        }
        response = self._request("POST", f"/v1/{self._mount}/verify/{self.key_id}", json=payload)
        return bool(response.get("data", {}).get("valid"))

    @property
    def public_key_pem(self) -> str:
        if self._public_key_pem and self._public_key_expires_at:
            if time.time() < self._public_key_expires_at:
                return self._public_key_pem
        response = self._request("GET", f"/v1/{self._mount}/keys/{self.key_id}")
        keys = response.get("data", {}).get("keys", {})
        if not keys:
            raise AuditSigningError("Vault transit key does not expose public key")
        latest = keys.get("1") or next(iter(keys.values()))
        public_key = latest.get("public_key") if isinstance(latest, dict) else None
        if not public_key:
            raise AuditSigningError("Vault transit public key missing")
        self._public_key_pem = public_key
        self._public_key_expires_at = time.time() + self._public_key_cache_seconds
        return public_key

    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        url = f"{self._vault_addr}{path}"
        headers = {"X-Vault-Token": self._vault_token}
        if self._namespace:
            headers["X-Vault-Namespace"] = self._namespace
        response = self._session.request(method, url, json=json, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise AuditSigningError("Invalid Vault response")
        return data

    @staticmethod
    def _unwrap_signature(signature: str) -> str:
        if signature.startswith("vault:"):
            parts = signature.split(":", 2)
            if len(parts) == 3:
                return parts[2]
        return signature

    @staticmethod
    def _wrap_signature(signature: str) -> str:
        if signature.startswith("vault:"):
            return signature
        return f"vault:v1:{signature}"


class AuditSigningService:
    def __init__(self) -> None:
        settings = get_settings()
        self.mode = (os.getenv("AUDIT_SIGNING_MODE") or settings.AUDIT_SIGNING_MODE or "local").lower()
        required_env = os.getenv("AUDIT_SIGNING_REQUIRED")
        if required_env is None:
            self.required = settings.AUDIT_SIGNING_REQUIRED
        else:
            self.required = required_env.lower() in {"1", "true", "yes"}
        self.alg = os.getenv("AUDIT_SIGNING_ALG", settings.AUDIT_SIGNING_ALG)
        self.key_id = os.getenv("AUDIT_SIGNING_KEY_ID", settings.AUDIT_SIGNING_KEY_ID)
        self._private_key_b64 = os.getenv(
            "AUDIT_SIGNING_PRIVATE_KEY_B64",
            settings.AUDIT_SIGNING_PRIVATE_KEY_B64,
        )
        self._public_keys_json = os.getenv(
            "AUDIT_SIGNING_PUBLIC_KEYS_JSON",
            settings.AUDIT_SIGNING_PUBLIC_KEYS_JSON,
        )
        cache_env = os.getenv("AUDIT_SIGNING_PUBLIC_KEYS_CACHE_SECONDS")
        if cache_env is None:
            self._public_key_cache_seconds = settings.AUDIT_SIGNING_PUBLIC_KEYS_CACHE_SECONDS
        else:
            self._public_key_cache_seconds = int(cache_env)
        self._aws_region = os.getenv("AWS_REGION", settings.AWS_REGION or "")
        self._aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", settings.AWS_ACCESS_KEY_ID or "")
        self._aws_secret_access_key = os.getenv(
            "AWS_SECRET_ACCESS_KEY",
            settings.AWS_SECRET_ACCESS_KEY or "",
        )
        self._aws_kms_endpoint = os.getenv("AWS_KMS_ENDPOINT", settings.AWS_KMS_ENDPOINT or "")
        self._aws_verify_mode = os.getenv(
            "AWS_KMS_VERIFY_MODE",
            settings.AWS_KMS_VERIFY_MODE,
        ).lower()
        self._vault_addr = os.getenv("VAULT_ADDR", settings.VAULT_ADDR or "")
        self._vault_token = os.getenv("VAULT_TOKEN", settings.VAULT_TOKEN or "")
        self._vault_namespace = os.getenv("VAULT_NAMESPACE", settings.VAULT_NAMESPACE or "")
        self._vault_mount = os.getenv("VAULT_TRANSIT_MOUNT", settings.VAULT_TRANSIT_MOUNT)
        self._vault_key = os.getenv(
            "VAULT_TRANSIT_KEY",
            settings.VAULT_TRANSIT_KEY or settings.AUDIT_SIGNING_KEY_ID,
        )
        self._vault_verify_mode = os.getenv("VAULT_VERIFY_MODE", settings.VAULT_VERIFY_MODE).lower()
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

    def list_keys(self, *, db=None) -> list[AuditSigningKey]:
        keys: list[AuditSigningKey] = []
        if db is not None:
            keys = self._load_db_keys(db)
            if keys:
                return keys
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

    def _load_db_keys(self, db) -> list[AuditSigningKey]:
        records = db.query(AuditSigningKeyRecord).order_by(AuditSigningKeyRecord.created_at.desc()).all()
        return [
            AuditSigningKey(
                key_id=record.key_id,
                alg=record.alg,
                public_key_pem=record.public_key_pem or "",
                status=record.status,
                created_at=record.created_at,
            )
            for record in records
        ]

    def _get_current_signer(self) -> AuditSigner | None:
        if self._current_signer is not None:
            return self._current_signer
        if self.mode in {"disabled", "none"}:
            return None
        if self.mode == "local":
            private_key_pem = self._load_private_key()
            if not private_key_pem:
                return None
            self._current_signer = LocalSigner(alg=self.alg, key_id=self.key_id, private_key_pem=private_key_pem)
            return self._current_signer
        if self.mode in {"kms", "aws_kms"}:
            client_params = {}
            if self._aws_region:
                client_params["region_name"] = self._aws_region
            if self._aws_access_key_id and self._aws_secret_access_key:
                client_params["aws_access_key_id"] = self._aws_access_key_id
                client_params["aws_secret_access_key"] = self._aws_secret_access_key
            if self._aws_kms_endpoint:
                client_params["endpoint_url"] = self._aws_kms_endpoint
            client = boto3.client("kms", **client_params)
            self._current_signer = AwsKmsSigner(
                alg=self.alg,
                key_id=self.key_id,
                client=client,
                verify_mode=self._aws_verify_mode,
                public_key_cache_seconds=self._public_key_cache_seconds,
            )
            return self._current_signer
        if self.mode == "vault_transit":
            if not self._vault_addr or not self._vault_token:
                return None
            self._current_signer = VaultTransitSigner(
                alg=self.alg,
                key_id=self._vault_key,
                vault_addr=self._vault_addr,
                vault_token=self._vault_token,
                mount=self._vault_mount,
                verify_mode=self._vault_verify_mode,
                namespace=self._vault_namespace,
                public_key_cache_seconds=self._public_key_cache_seconds,
            )
            return self._current_signer
        raise AuditSigningError(f"Unsupported signing mode: {self.mode}")

    def _get_signer_for_key(self, *, key_id: str, alg: str) -> AuditSigner | None:
        if self.mode in {"disabled", "none"}:
            return None
        if self.mode == "local":
            current = self._get_current_signer()
            if current and current.key_id == key_id and current.alg == alg:
                return current
            verifier = self._public_verifiers.get(key_id)
            if verifier and verifier.alg == alg:
                return verifier
            return None
        if self.mode in {"kms", "aws_kms"}:
            client_params = {}
            if self._aws_region:
                client_params["region_name"] = self._aws_region
            if self._aws_access_key_id and self._aws_secret_access_key:
                client_params["aws_access_key_id"] = self._aws_access_key_id
                client_params["aws_secret_access_key"] = self._aws_secret_access_key
            if self._aws_kms_endpoint:
                client_params["endpoint_url"] = self._aws_kms_endpoint
            client = boto3.client("kms", **client_params)
            return AwsKmsSigner(
                alg=alg,
                key_id=key_id,
                client=client,
                verify_mode=self._aws_verify_mode,
                public_key_cache_seconds=self._public_key_cache_seconds,
            )
        if self.mode == "vault_transit":
            if not self._vault_addr or not self._vault_token:
                return None
            return VaultTransitSigner(
                alg=alg,
                key_id=key_id,
                vault_addr=self._vault_addr,
                vault_token=self._vault_token,
                mount=self._vault_mount,
                verify_mode=self._vault_verify_mode,
                namespace=self._vault_namespace,
                public_key_cache_seconds=self._public_key_cache_seconds,
            )
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

    def self_check(self) -> bool:
        if not self.required:
            return True
        signer = self._get_current_signer()
        if not signer:
            return False
        message = b"audit-signing-healthcheck"
        try:
            signature = signer.sign(message)
            return signer.verify(message, signature)
        except Exception:  # noqa: BLE001
            return False


def set_audit_signing_health(status: str) -> None:
    global _AUDIT_SIGNING_HEALTH
    _AUDIT_SIGNING_HEALTH = status


def get_audit_signing_health() -> str:
    return _AUDIT_SIGNING_HEALTH or "unknown"


def get_audit_signer() -> AuditSigner | None:
    return AuditSigningService()._get_current_signer()


__all__ = [
    "AuditSignature",
    "AuditSigningError",
    "AuditSigningKey",
    "AuditSigningService",
    "AwsKmsSigner",
    "VaultTransitSigner",
    "get_audit_signer",
    "get_audit_signing_health",
    "set_audit_signing_health",
]
