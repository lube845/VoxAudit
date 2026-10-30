"""
数据库连接和会话管理
"""
import urllib.parse
import datetime as _dt
from loguru import logger
from sqlalchemy import text, update
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

    # 必须先 import 所有 model，Base.metadata 才能 create_all 出全部表
    # 否则后续迁移脚本里裸 SQL 引用的表会不存在
    from backend.models import k_user, recording, rule, system_settings, audit_log, call_record, call_note  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 全部幂等；数据迁移放最后
    # 注意：逐个迁移独立捕获错误 —— 某个迁移失败不能连带跳过后面的迁移，
    # 否则会出现「建表没建、列没加」的半迁移库，接口全 500 而根因只在日志里。
    # 所有失败项收集齐后统一抛出，让服务启动失败（fail fast）。
    from backend.migrations import ALL_MIGRATIONS
    failures: list[str] = []
    for mod in ALL_MIGRATIONS:
        try:
            await mod.migrate()
        except Exception as e:
            logger.error(f"迁移 {mod.__name__} 失败: {e!r}")
            failures.append(f"{mod.__name__}: {e}")
    if failures:
        raise RuntimeError("数据库迁移失败：" + "；".join(failures))

    # 启动恢复：催记后台处理卡死（processing 超过阈值）的行，重置为 pending
    try:
        await _recover_stuck_collection_notes()
    except Exception as e:
        logger.error(f"催记卡死记录恢复失败（忽略，不影响启动）: {e}")


async def _recover_stuck_collection_notes() -> None:
    """启动时把 processing 状态超过 COLLECTION_NOTE_STUCK_MINUTES 的字段重置为 pending

    多 worker 场景：worker A 启动后台循环，认领 3 行标为 processing 后崩溃。
    worker B 重启后看到这些行卡在 processing，会在这里被重置为 pending，
    由 worker B 的新一轮后台循环接手。
    """
    # call_notes 表由迁移创建；但若 init_db 走到这里时迁移还没建表，跳过恢复
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("SELECT 1 FROM call_notes LIMIT 0"))
        except Exception:
            return  # 表还没建好，跳过

    # 延迟导入：避免循环引用 + 表可能尚未存在
    from backend.models.call_note import CallNote

    threshold = _dt.datetime.now() - _dt.timedelta(
        minutes=max(1, int(settings.COLLECTION_NOTE_STUCK_MINUTES or 10))
    )
    status_cols = ("asr_status", "structured_status", "unstructured_status")

    async with AsyncSessionLocal() as db:
        recovered = 0
        for col in status_cols:
            stmt = (
                update(CallNote)
                .where(getattr(CallNote, col) == "processing")
                .where(
                    (CallNote.last_processed_at < threshold) | (CallNote.last_processed_at.is_(None))
                )
                .values(**{col: "pending"})
            )
            result = await db.execute(stmt)
            recovered += result.rowcount or 0
        await db.commit()
        if recovered:
            logger.info(f"催记启动恢复：重置 {recovered} 个卡死的 processing 字段为 pending")