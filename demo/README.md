# Demo Scripts

**These scripts are for local demos and development ONLY. Do not use in production.**

## Seed Script

Populates the database with sample users, accounts, cards, and 2-3 months of transaction history.

```bash
# Start the API server first
uvicorn app.main:app --reload

# In another terminal, run the seed script
python demo/seed.py
```

### Reset and Re-seed

```bash
# Delete the database
python demo/seed.py --reset

# Restart the server (recreates empty tables), then re-seed
python demo/seed.py
```

## Login Credentials

| Email                        | Password          | Role   |
|------------------------------|--------------------|--------|
| admin@bankdemo.com           | AdminDemo123!      | ADMIN  |
| alice.chen@example.com       | AliceDemo123!      | MEMBER |
| bob.martinez@example.com     | BobDemo123!        | MEMBER |
| carol.nguyen@example.com     | CarolDemo123!      | MEMBER |
| dave.johnson@example.com     | DaveDemo123!       | MEMBER |
| erin.patel@example.com       | ErinDemo123!       | MEMBER |
