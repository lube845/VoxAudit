"""
数据库迁移脚本 - 添加 is_enabled 列
运行方式: python -m backend.migrations.migrate_add_is_enabled
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """添加 is_enabled 列到 scoring_rules 表"""
    async with engine.begin() as conn:
        # 检查 is_enabled 列是否存在
        result = await conn.execute(text("SHOW COLUMNS FROM scoring_rules LIKE 'is_enabled'"))
        if not result.fetchone():
            print("添加 is_enabled 列...")
            await conn.execute(text(
                "ALTER TABLE scoring_rules ADD COLUMN is_enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用（启用且最新才参与评分）'"
            ))
            print("is_enabled 列添加成功")
        else:
            print("is_enabled 列已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())