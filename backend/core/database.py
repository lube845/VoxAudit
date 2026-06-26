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
        finally:
            await session.close()


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
    """初始化数据库结构"""
    await ensure_database_exists()

    async with engine.begin() as conn:
        # 先创建表结构
        await conn.run_sync(Base.metadata.create_all)

        # 检查并添加 is_veto 列（如果不存在）
        result = await conn.execute(text("SHOW COLUMNS FROM scoring_rules LIKE 'is_veto'"))
        if not result.fetchone():
            await conn.execute(text(
                "ALTER TABLE scoring_rules ADD COLUMN is_veto BOOLEAN DEFAULT FALSE COMMENT '是否否决项'"
            ))

        # 检查并添加 is_enabled 列（如果不存在）
        result = await conn.execute(text("SHOW COLUMNS FROM scoring_rules LIKE 'is_enabled'"))
        if not result.fetchone():
            await conn.execute(text(
                "ALTER TABLE scoring_rules ADD COLUMN is_enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用（启用且最新才参与评分）'"
            ))