"""
Security utilities: password hashing, JWT tokens, and Fernet encryption.

This module centralizes all cryptographic operations so they're easy to
audit and update. Three concerns are handled here:

1. PASSWORD HASHING (Argon2)
   - Passwords are never stored in plaintext
   - Argon2 is the winner of the Password Hashing Competition (2015) and is
     considered the state-of-the-art for password hashing. It is resistant to
     GPU-based and side-channel attacks because it is both memory-hard and
     time-hard, unlike bcrypt which is only time-hard.
   - We use passlib's CryptContext for safe, high-level Argon2 operations

2. JWT TOKENS (JSON Web Tokens)
   - After login, the user receives a signed JWT containing their user ID
   - The token is signed with SECRET_KEY using HS256 (HMAC-SHA256)
   - Tokens expire after ACCESS_TOKEN_EXPIRE_MINUTES (default: 30 min)
   - The server is stateless: no session storage needed

3. FERNET ENCRYPTION (AES-128-CBC + HMAC-SHA256)
   - Used for encrypting sensitive card data at rest (card numbers, CVVs)
   - Fernet provides authenticated encryption: data is both encrypted and
     integrity-checked, preventing tampering
   - The encryption key is loaded from environment variables, never hardcoded

Enterprise note:
  In a production environment, you'd use a Hardware Security Module (HSM)
  or a secrets manager (AWS KMS, HashiCorp Vault) instead of env-var keys.
  This implementation is structured to make that migration straightforward.
"""

from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings


# ---------------------------------------------------------------------------
# 1. Password Hashing (Argon2)
# ---------------------------------------------------------------------------

# CryptContext manages hashing schemes. "argon2" is the active scheme.
# Argon2id (the default variant) is recommended for password hashing because
# it combines Argon2i's resistance to side-channel attacks with Argon2d's
# resistance to GPU cracking.
#
# If we ever need to migrate from argon2 to a future scheme, passlib handles
# the transition automatically: old hashes are verified with the original
# scheme, and new passwords use the new one ("deprecated='auto'").
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password using Argon2id.

    Args:
        plain_password: The user's raw password input.

    Returns:
        An Argon2 hash string (e.g., "$argon2id$v=19$m=65536,t=3,p=4$...").
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored Argon2 hash.

    This is a constant-time comparison to prevent timing attacks.

    Args:
        plain_password: The password the user just typed.
        hashed_password: The hash stored in the database.

    Returns:
        True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# 2. JWT Tokens
# ---------------------------------------------------------------------------


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT access token.

    The token payload contains:
      - "sub": The subject (user ID as string) — standard JWT claim
      - "exp": Expiration timestamp — after this, the token is rejected

    Args:
        data: Dictionary of claims to encode (must include "sub").
        expires_delta: Optional custom expiration time. Defaults to
                       ACCESS_TOKEN_EXPIRE_MINUTES from settings.

    Returns:
        An encoded JWT string.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.

    Raises:
        JWTError: If the token is expired, tampered with, or invalid.

    Returns:
        The decoded payload dictionary (contains "sub", "exp", etc.).
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ---------------------------------------------------------------------------
# 3. Fernet Encryption (for card data at rest)
# ---------------------------------------------------------------------------

# Initialize the Fernet cipher with the key from environment.
# Fernet keys are URL-safe base64-encoded 32-byte keys.
_fernet = Fernet(settings.CARD_ENCRYPTION_KEY.encode())


def encrypt_value(plaintext: str) -> bytes:
    """
    Encrypt a string value using Fernet (AES-128-CBC + HMAC-SHA256).

    Used for encrypting card numbers and CVVs before storing in the database.

    Args:
        plaintext: The sensitive value to encrypt (e.g., "4111111111111111").

    Returns:
        Encrypted bytes suitable for storing in a LargeBinary column.
    """
    return _fernet.encrypt(plaintext.encode())


def decrypt_value(ciphertext: bytes) -> str:
    """
    Decrypt a Fernet-encrypted value back to plaintext.

    Args:
        ciphertext: The encrypted bytes from the database.

    Returns:
        The original plaintext string.

    Raises:
        cryptography.fernet.InvalidToken: If the data is corrupted or
            the encryption key doesn't match.
    """
    return _fernet.decrypt(ciphertext).decode()
