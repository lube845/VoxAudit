"""
数据库迁移脚本 - 添加 prompt system/user 列
运行方式: python -m backend.migrations.migrate_add_prompt_columns
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """添加 prompt system/user 列到 system_settings 表"""
    async with engine.begin() as conn:
        # 新列定义
        new_columns = [
            ('prompt_speaker_detection_system', 'TEXT'),
            ('prompt_speaker_detection_user', 'TEXT'),
            ('prompt_rule_refine_system', 'TEXT'),
            ('prompt_rule_refine_user', 'TEXT'),
            ('prompt_bonus_judgment_system', 'TEXT'),
            ('prompt_bonus_judgment_user', 'TEXT'),
            ('prompt_deduction_judgment_system', 'TEXT'),
            ('prompt_deduction_judgment_user', 'TEXT'),
        ]

        for col_name, col_type in new_columns:
            result = await conn.execute(text(f"SHOW COLUMNS FROM system_settings LIKE '{col_name}'"))
            if not result.fetchone():
                print(f"添加 {col_name} 列...")
                await conn.execute(text(
                    f"ALTER TABLE system_settings ADD COLUMN {col_name} {col_type}"
                ))
                print(f"{col_name} 列添加成功")
            else:
                print(f"{col_name} 列已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
