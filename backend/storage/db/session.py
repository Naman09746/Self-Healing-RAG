from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# PostgreSQL is required. No SQLite fallback.
# Application will fail to start if database is unreachable.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from backend.storage.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)