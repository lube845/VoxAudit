"""
数据库连接和会话管理
"""
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


async def init_db():
    """初始化数据库结构"""
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