"""MongoDB connection lifecycle and small repository helpers."""

from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .core import get_settings


class Database:
    client: AsyncIOMotorClient | None = None

    async def connect(self) -> None:
        settings = get_settings()
        self.client = AsyncIOMotorClient(settings.mongodb_url, serverSelectionTimeoutMS=3000)
        await self.client.admin.command("ping")
        db = self.database
        await db.audits.create_index([("created_at", -1)])
        await db.audits.create_index([("store_id", 1), ("shelf_id", 1), ("created_at", -1)])
        await db.alerts.create_index([("status", 1), ("created_at", -1)])
        await db.audit_events.create_index([("audit_id", 1), ("created_at", -1)])
        await db.planograms.create_index([("store_id", 1), ("shelf_id", 1)], unique=True)
        await db.products.create_index("sku", unique=True)

    async def disconnect(self) -> None:
        if self.client:
            self.client.close()
            self.client = None

    @property
    def database(self) -> AsyncIOMotorDatabase:
        if self.client is None:
            raise RuntimeError("Database client is not connected")
        return self.client[get_settings().mongodb_database]


database = Database()


@asynccontextmanager
async def database_lifespan():
    await database.connect()
    try:
        yield
    finally:
        await database.disconnect()
