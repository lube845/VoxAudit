"""
数据库迁移脚本 - 创建 call_notes 表（催记处理结果）
运行方式: python -m backend.migrations.migrate_add_call_notes

幂等：表已存在则跳过。
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine
from backend.migrations.migrate_add_call_records import _ensure_unique_key


async def migrate():
    """创建 call_notes 表（含必要的索引）"""
    async with engine.begin() as conn:
        # 1) 建表（如果不存在）
        result = await conn.execute(text("SHOW TABLES LIKE 'call_notes'"))
        if not result.fetchone():
            print("创建 call_notes 表...")
            await conn.execute(text("""
                CREATE TABLE `call_notes` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT,
                    `call_id` VARCHAR(64) NOT NULL COMMENT '业务主键（对应 call_records.call_id）',
                    `transcript` TEXT NULL COMMENT '录音转写原文',
                    `transcript_segments` JSON NULL COMMENT '转写片段',
                    `structured_note` TEXT NULL COMMENT '原始结构化催记',
                    `unstructured_note` TEXT NULL COMMENT '原始非结构化催记',
                    `edited_structured_note` TEXT NULL COMMENT '校对结构化催记',
                    `edited_unstructured_note` TEXT NULL COMMENT '校对非结构化催记',
                    `asr_status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/processing/done/failed',
                    `structured_status` VARCHAR(20) NOT NULL DEFAULT 'pending',
                    `unstructured_status` VARCHAR(20) NOT NULL DEFAULT 'pending',
                    `asr_error` TEXT NULL,
                    `structured_error` TEXT NULL,
                    `unstructured_error` TEXT NULL,
                    `last_processed_at` DATETIME NULL,
                    `created_at` DATETIME NOT NULL,
                    `updated_at` DATETIME NOT NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uk_call_notes_call_id` (`call_id`),
                    KEY `idx_call_notes_asr_status` (`asr_status`),
                    KEY `idx_call_notes_structured_status` (`structured_status`),
                    KEY `idx_call_notes_unstructured_status` (`unstructured_status`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                  COMMENT='催记管理 - 通话处理结果（转写+催记）'
            """))
            print("call_notes 表创建成功")
        else:
            print("call_notes 表已存在，跳过建表")

        # 2) 唯一键（call_id 必须唯一：否则同一通话会有多条 note，查询接口直接 500）
        await _ensure_unique_key(conn, "call_notes", "call_id", "uk_call_notes_call_id")

        # 3) 兜底补普通索引
        for idx_name, col in (
            ("idx_call_notes_asr_status", "asr_status"),
            ("idx_call_notes_structured_status", "structured_status"),
            ("idx_call_notes_unstructured_status", "unstructured_status"),
        ):
            r = await conn.execute(text(f"SHOW INDEX FROM call_notes WHERE Key_name = '{idx_name}'"))
            if not r.fetchone():
                print(f"补建索引 {idx_name} ({col})...")
                await conn.execute(text(f"ALTER TABLE call_notes ADD INDEX `{idx_name}` (`{col}`)"))
            else:
                print(f"索引 {idx_name} 已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
