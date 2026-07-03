"""
数据库迁移脚本 - 添加缺失的列
运行方式: python -m backend.migrations.migrate_add_columns
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """添加缺失的列到 recordings 表"""
    async with engine.begin() as conn:
        # 检查并添加 agent_name 列
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'agent_name'"))
        if not result.fetchone():
            print("添加 agent_name 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN agent_name VARCHAR(100) NULL COMMENT '坐席姓名'"
            ))
            print("agent_name 列添加成功")
        else:
            print("agent_name 列已存在")

        # 检查并添加 rule_version 列
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'rule_version'"))
        if not result.fetchone():
            print("添加 rule_version 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN rule_version VARCHAR(20) NULL COMMENT '规则版本'"
            ))
            print("rule_version 列添加成功")
        else:
            print("rule_version 列已存在")

        # 检查 bonus_score 列类型
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'bonus_score'"))
        row = result.fetchone()
        if row:
            if 'float' not in row[1].lower() and 'double' not in row[1].lower() and 'decimal' not in row[1].lower():
                print(f"bonus_score 列类型可能不正确: {row[1]}")
        else:
            print("添加 bonus_score 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN bonus_score FLOAT DEFAULT 0 COMMENT '加分总分'"
            ))
            print("bonus_score 列添加成功")

        # 检查 deduction_score 列类型
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'deduction_score'"))
        row = result.fetchone()
        if row:
            if 'float' not in row[1].lower() and 'double' not in row[1].lower() and 'decimal' not in row[1].lower():
                print(f"deduction_score 列类型可能不正确: {row[1]}")
        else:
            print("添加 deduction_score 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN deduction_score FLOAT DEFAULT 0 COMMENT '扣分总分'"
            ))
            print("deduction_score 列添加成功")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())