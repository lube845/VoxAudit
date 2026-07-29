"""
数据库迁移脚本 - 删除 LLM_COMPATIBILITY_MODE 列
运行方式: python -m backend.migrations.migrate_drop_compatibility_mode
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """删除 system_settings 表中的 LLM_COMPATIBILITY_MODE 列"""
    async with engine.begin() as conn:
        # 检查列是否存在
        result = await conn.execute(text("SHOW COLUMNS FROM system_settings LIKE 'LLM_COMPATIBILITY_MODE'"))
        if result.fetchone():
            print("删除 LLM_COMPATIBILITY_MODE 列...")
            await conn.execute(text("ALTER TABLE system_settings DROP COLUMN LLM_COMPATIBILITY_MODE"))
            print("LLM_COMPATIBILITY_MODE 列已删除")
        else:
            print("LLM_COMPATIBILITY_MODE 列不存在，跳过")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
