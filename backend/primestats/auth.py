"""Passwort-Hashing und Zufalls-Tokens (nur Standardbibliothek)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

# scrypt-Parameter (OWASP-Empfehlung: N=2^17 bei r=8, p=1; hier 2^15 für ~50 ms)
_N, _R, _P = 2 ** 15, 8, 1
_MAXMEM = 128 * _N * _R * 2

#: Alphabet für Verknüpfungscodes ohne verwechselbare Zeichen (0/O, 1/I/L)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                                   maxmem=128 * int(n) * int(r) * 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest)


def new_token() -> str:
    """Zufälliges Geheimnis für Session-Cookies und Geräteschlüssel."""
    return secrets.token_urlsafe(32)


def new_link_code() -> str:
    """Kurzer, abtippbarer Code wie ``K7QX-M2PA``."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(code: str) -> str:
    cleaned = "".join(ch for ch in code.upper() if ch in CODE_ALPHABET)
    return f"{cleaned[:4]}-{cleaned[4:]}" if len(cleaned) == 8 else cleaned


def token_hash(token: str) -> str:
    """Tokens/Codes werden nur gehasht gespeichert."""
    return hashlib.sha256(token.encode()).hexdigest()
