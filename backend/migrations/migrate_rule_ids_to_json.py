"""
数据库迁移脚本 - rule_id 改为 rule_ids (JSON数组)
运行方式: python -m backend.migrations.migrate_rule_ids_to_json

此迁移将 scoring_results 表的 rule_id (INT) 列改为 rule_ids (JSON) 列，
存储所有参与评分的规则ID列表。
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """迁移 rule_id -> rule_ids"""
    async with engine.begin() as conn:
        # 1. 检查旧列 rule_id 是否存在
        result = await conn.execute(text("SHOW COLUMNS FROM scoring_results LIKE 'rule_id'"))
        old_column_exists = result.fetchone() is not None

        if not old_column_exists:
            print("rule_id 列不存在，可能是全新环境，跳过迁移")
            return

        # 2. 检查新列 rule_ids 是否已存在
        result = await conn.execute(text("SHOW COLUMNS FROM scoring_results LIKE 'rule_ids'"))
        new_column_exists = result.fetchone() is not None

        if new_column_exists:
            print("rule_ids 列已存在，跳过迁移")
            return

        # 3. 添加新列 rule_ids (JSON类型)
        print("添加 rule_ids 列 (JSON类型)...")
        await conn.execute(text(
            "ALTER TABLE scoring_results ADD COLUMN rule_ids JSON COMMENT '参与评分的规则ID列表'"
        ))
        print("rule_ids 列添加成功")

        # 4. 迁移数据：将 rule_id 值转为 JSON 数组格式
        print("迁移数据: rule_id -> rule_ids...")
        await conn.execute(text(
            "UPDATE scoring_results SET rule_ids = CONCAT('[', rule_id, ']') WHERE rule_id IS NOT NULL"
        ))
        print("数据迁移完成")

        # 5. 删除旧列 rule_id (可选，保留以便回滚)
        # 如果需要保留旧列进行回滚，可以注释掉下面这行
        print("尝试删除旧列 rule_id...")
        try:
            await conn.execute(text("ALTER TABLE scoring_results DROP COLUMN rule_id"))
            print("旧列 rule_id 已删除")
        except Exception as e:
            print(f"删除旧列失败 (可能有外键约束)，跳过: {e}")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
