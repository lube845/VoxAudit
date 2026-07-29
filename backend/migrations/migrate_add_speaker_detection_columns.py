"""
数据库迁移脚本 - 添加说话人检测方式列
运行方式: python -m backend.migrations.migrate_add_speaker_detection_columns
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """添加说话人检测方式列到 recordings 表"""
    async with engine.begin() as conn:
        # 检查并添加 speaker_detection_method 列
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'speaker_detection_method'"))
        if not result.fetchone():
            print("添加 speaker_detection_method 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN speaker_detection_method VARCHAR(20) NULL DEFAULT 'channel' COMMENT '说话人检测方式: channel=声道分离, llm=大模型'"
            ))
            print("speaker_detection_method 列添加成功")
        else:
            print("speaker_detection_method 列已存在")

        # 检查并添加 left_channel_role 列
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'left_channel_role'"))
        if not result.fetchone():
            print("添加 left_channel_role 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN left_channel_role VARCHAR(20) NULL DEFAULT 'agent' COMMENT '左声道角色: agent=坐席, customer=客户'"
            ))
            print("left_channel_role 列添加成功")
        else:
            print("left_channel_role 列已存在")

        # 检查并添加 right_channel_role 列
        result = await conn.execute(text("SHOW COLUMNS FROM recordings LIKE 'right_channel_role'"))
        if not result.fetchone():
            print("添加 right_channel_role 列...")
            await conn.execute(text(
                "ALTER TABLE recordings ADD COLUMN right_channel_role VARCHAR(20) NULL DEFAULT 'customer' COMMENT '右声道角色: agent=坐席, customer=客户'"
            ))
            print("right_channel_role 列添加成功")
        else:
            print("right_channel_role 列已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
