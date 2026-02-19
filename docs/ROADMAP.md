# Roadmap

Future enhancements organized by priority for production readiness.

## High Priority (1-3 months)

- **Account lockout after failed attempts**: Lock accounts after 5 consecutive failed login attempts. Configurable lockout duration and reset mechanism.
- **Rate limiting**: Per-IP and per-user rate limits via middleware or API gateway to prevent brute force and abuse.
- **Admin fraud/security dashboard**: Real-time view of failed login attempts, declined transactions, and suspicious activity patterns across the organization.
- **Refresh tokens**: Refresh token rotation for long-lived sessions without extending JWT expiry.
- **PostgreSQL migration**: Replace SQLite with PostgreSQL + asyncpg. Enables row-level locking (`FOR UPDATE`), concurrent writes, and horizontal scaling. Only `DATABASE_URL` needs to change.
- **Alembic migrations**: Version-controlled schema changes instead of `create_all()` at startup. Migration files already scaffolded.
- **Credit card model**: Separate card balance with credit limits, minimum payments, interest calculation, and statement cycles. Currently only debit cards are supported.
- **External transfers (ACH/wire)**: Outbound and inbound transfers to/from external bank accounts. Includes pending states for settlement, routing number validation, and hold periods.

## Medium Priority (3-6 months)

- **Two-factor authentication (2FA)**: TOTP-based second factor for login and high-value operations.
- **Redis caching**: Cache account balances and frequently-accessed data. Reduces database load for read-heavy operations.
- **Webhook/event system**: Publish transaction events for external integrations (notifications, fraud detection, analytics).
- **Multi-currency support**: Exchange rate service, cross-currency transfers, per-account currency.
- **Audit log service**: Immutable append-only log of all state changes for compliance and forensics.
- **Scheduled payments**: Recurring transfers, bill pay, standing orders.

## Low Priority (6+ months)

- **PCI DSS compliance**: HSM/KMS for card encryption keys, tokenization service, network segmentation.
- **Account interest calculation**: Daily accrual, monthly compounding for savings accounts.
- **Admin dashboard enhancements**: User management, account freezing, transaction reversal tools.
- **Mobile API optimizations**: Push notification hooks, biometric auth integration, offline-first patterns.
