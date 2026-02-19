#!/usr/bin/env python3
"""One-time script to promote admin user. Run on the server."""
import asyncio
import os
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.user import User, UserType

async def promote():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = async_sessionmaker(engine, class_=AsyncSession)
    async with sf() as s:
        r = await s.execute(
            update(User)
            .where(User.email == "admin@bankdemo.com")
            .values(user_type=UserType.ADMIN)
        )
        await s.commit()
        print(f"Rows updated: {r.rowcount}")
    await engine.dispose()

asyncio.run(promote())
