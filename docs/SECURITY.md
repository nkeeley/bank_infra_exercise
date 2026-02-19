# Security Considerations

## Authentication

- **Password hashing**: Argon2id (winner of the Password Hashing Competition). Memory-hard and time-hard, resistant to GPU and side-channel attacks.
- **JWT tokens**: HS256-signed, 30-minute expiry, stateless. User ID stored in `sub` claim.
- **User enumeration prevention**: Login returns the same error for "wrong password" and "email not found".

## Authorization

- **Role-based access**: MEMBER (own data only) and ADMIN (read-only organization-wide).
- **Ownership enforcement**: Every member endpoint verifies the authenticated user owns the requested resource via JWT → User → AccountHolder chain.
- **Admin isolation**: Admin users are blocked from all member banking endpoints (403). Admin provisioning is an operator action, not self-service.

## Data Protection

- **Card encryption**: Card numbers and CVVs encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256). Only last four digits stored in plaintext for display.
- **No sensitive data in logs**: SQL echo disabled in production. Uvicorn logs method/path/status only, not request bodies. JWT tokens and passwords never logged.
- **Integer cents**: All monetary amounts stored as integers to prevent floating-point rounding errors.

## Transport

- **CORS**: Locked to specific frontend origins. Wildcard (`*`) is never used in production.
- **HTTPS**: Required in production. TLS termination at load balancer/reverse proxy level.

## Known Limitations (MVP)

- No rate limiting (add via middleware or API gateway)
- No refresh tokens (JWT expiry is the only session control)
- No IP-based brute force protection
- SQLite does not support row-level locking (`FOR UPDATE` is a no-op)
- Encryption key stored in environment variable (use HSM/KMS in production)

## OWASP Top 10 Coverage

| Risk | Mitigation |
|------|-----------|
| Injection | SQLAlchemy ORM parameterized queries |
| Broken Authentication | Argon2id, JWT, enumeration prevention |
| Sensitive Data Exposure | Fernet encryption, no plaintext secrets in logs |
| Broken Access Control | Role-based gates, ownership verification on every endpoint |
| Security Misconfiguration | Strict CORS, DEBUG=false in production, non-root Docker user |
| XSS | API-only backend (no HTML rendering); React frontend escapes by default |
| CSRF | JWT Bearer tokens (not cookies), CORS enforcement |
