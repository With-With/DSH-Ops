"""
AI 配置的密钥加密工具（ADR#6：密钥 Fernet 加密落库，API 只回掩码）。

Fernet key 由平台 SECRET_KEY 派生（sha256 -> base64），
生产环境换 DSHOPS_SECRET_KEY 即轮换（旧密文需重新录入）。
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    secret = os.environ.get("DSHOPS_SECRET_KEY", "dev-insecure-key")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_key(plain: str) -> str:
    """明文 -> Fernet 密文（str）。空串原样返回。"""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_key(enc: str) -> str:
    """密文 -> 明文。空串/解密失败返回空串。"""
    if not enc:
        return ""
    try:
        return _fernet().decrypt(enc.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_key(plain: str) -> str:
    """明文 -> 掩码：保留前缀与后 4 位，如 sk-****abcd。"""
    if not plain:
        return ""
    if len(plain) <= 8:
        return "****"
    prefix = plain[:3] if plain[:3] in ("sk-", "ak-") else plain[:2]
    return f"{prefix}****{plain[-4:]}"
