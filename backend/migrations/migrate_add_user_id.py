"""
数据库迁移脚本 - 添加 user_id 列到所有表
运行方式: python -m backend.migrations.migrate_add_user_id
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """添加 user_id 列到所有需要的表"""
    async with engine.begin() as conn:
        # 检查 recordings 表
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'user_id'"))
        if not result.fetchone():
            print("添加 recordings.user_id 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN user_id VARCHAR(50) NULL COMMENT '所属用户loginid'"
            ))
            print("recordings.user_id 列添加成功")
        else:
            print("recordings.user_id 列已存在")

        # 检查 scoring_rules 表
        result = await conn.execute(text("SHOW COLUMNS FROM scoring_rules LIKE 'user_id'"))
        if not result.fetchone():
            print("添加 scoring_rules.user_id 列...")
            await conn.execute(text(
                "ALTER TABLE scoring_rules ADD COLUMN user_id VARCHAR(50) NULL COMMENT '所属用户loginid'"
            ))
            print("scoring_rules.user_id 列添加成功")
        else:
            print("scoring_rules.user_id 列已存在")

        # 检查 scoring_results 表
        result = await conn.execute(text("SHOW COLUMNS FROM scoring_results LIKE 'user_id'"))
        if not result.fetchone():
            print("添加 scoring_results.user_id 列...")
            await conn.execute(text(
                "ALTER TABLE scoring_results ADD COLUMN user_id VARCHAR(50) NULL COMMENT '所属用户loginid'"
            ))
            print("scoring_results.user_id 列添加成功")
        else:
            print("scoring_results.user_id 列已存在")

        # 为已有的 admin 用户数据设置默认 user_id
        print("\n为现有数据设置 user_id='admin'...")
        await conn.execute(text("UPDATE recordings SET user_id='admin' WHERE user_id IS NULL"))
        await conn.execute(text("UPDATE scoring_rules SET user_id='admin' WHERE user_id IS NULL"))
        await conn.execute(text("UPDATE scoring_results SET user_id='admin' WHERE user_id IS NULL"))
        print("现有数据已更新")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())