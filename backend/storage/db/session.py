from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# NullPool is used for asyncpg with FastAPI/Starlette to prevent
# "Future attached to a different loop" errors across requests and lifespan background tasks.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from backend.storage.db.models import Base, User
    from backend.core.security import get_password_hash
    from backend.core.rbac import Role
    from sqlalchemy import select
    import uuid

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default admin user if no users exist
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).limit(1))
            if not result.scalar_one_or_none():
                admin_uuid = str(uuid.uuid4())
                admin_user = User(
                    email="admin@self-healing-rag.local",
                    hashed_password=get_password_hash("Admin12345!"),
                    full_name="System Administrator",
                    user_uuid=admin_uuid,
                    tenant_id="default",
                    role=Role.ADMIN.value,
                    is_active=True,
                )
                session.add(admin_user)
                await session.commit()
                logger.info("Seeded initial admin user: admin@self-healing-rag.local")
        except Exception as e:
            logger.warning("Could not seed default admin user", error=str(e))