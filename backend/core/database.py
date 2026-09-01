"""
数据库连接和会话管理
"""
import urllib.parse
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from .config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ensure_database_exists():
    """检查目标数据库是否存在，不存在则自动创建"""
    encoded_password = urllib.parse.quote_plus(settings.DB_PASSWORD)
    server_url = (
        f"mysql+aiomysql://{settings.DB_USER}:{encoded_password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/"
    )
    server_engine = create_async_engine(server_url, echo=False, poolclass=NullPool)
    try:
        async with server_engine.begin() as conn:
            result = await conn.execute(
                text("SHOW DATABASES LIKE :db_name"),
                {"db_name": settings.DB_NAME},
            )
            if not result.fetchone():
                logger.info(f"目标数据库 {settings.DB_NAME} 不存在，正在自动创建...")
                await conn.execute(text(
                    f"CREATE DATABASE `{settings.DB_NAME}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
                logger.info(f"目标数据库 {settings.DB_NAME} 创建成功")
            else:
                logger.info(f"目标数据库 {settings.DB_NAME} 已存在")
    finally:
        await server_engine.dispose()


async def init_db():
    """初始化数据库结构 + 自动迁移。

    新建项目：create_all 建表，迁移全部 no-op。
    升级项目：表已存在，迁移按 SHOW COLUMNS / 旧列存在性检查后增量 ALTER，已存数据不动。
    """
    await ensure_database_exists()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 全部幂等；数据迁移放最后
    from backend.migrations import ALL_MIGRATIONS
    for mod in ALL_MIGRATIONS:
        await mod.migrate()