"""
数据库迁移脚本 - 给 k_users 表加 password_changed_at 列
运行方式: python -m backend.migrations.migrate_add_password_changed_at
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """k_users.password_changed_at 列（nullable，首次落库与默认密码期间为 NULL）"""
    async with engine.begin() as conn:
        result = await conn.execute(text("SHOW COLUMNS FROM k_users LIKE 'password_changed_at'"))
        if not result.fetchone():
            print("添加 k_users.password_changed_at 列...")
            await conn.execute(text(
                "ALTER TABLE k_users ADD COLUMN password_changed_at DATETIME NULL "
                "COMMENT '最近一次改密时间；NULL 表示仍在用默认密码'"
            ))
            print("k_users.password_changed_at 列添加成功")
        else:
            print("k_users.password_changed_at 列已存在")
        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())