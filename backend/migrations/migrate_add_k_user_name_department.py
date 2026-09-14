"""
数据库迁移脚本 - 给 k_users 表加 name（姓名）和 department（部门）列
运行方式: python -m backend.migrations.migrate_add_k_user_name_department
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """k_users.name 与 k_users.department 列（nullable，白名单元数据）"""
    async with engine.begin() as conn:
        for col, comment in (
            ("name", "姓名（白名单元数据）"),
            ("department", "部门（白名单元数据）"),
        ):
            result = await conn.execute(text(f"SHOW COLUMNS FROM k_users LIKE '{col}'"))
            if not result.fetchone():
                print(f"添加 k_users.{col} 列...")
                await conn.execute(text(
                    f"ALTER TABLE k_users ADD COLUMN `{col}` VARCHAR(64) NULL "
                    f"COMMENT '{comment}'"
                ))
                print(f"k_users.{col} 列添加成功")
            else:
                print(f"k_users.{col} 列已存在")
        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
