"""
数据库迁移脚本 - 创建 audit_logs 表
运行方式: python -m backend.migrations.migrate_add_audit_logs

幂等：表已存在则跳过。
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """创建 audit_logs 表（含必要的索引）"""
    async with engine.begin() as conn:
        # 1. 建表（如果不存在）
        result = await conn.execute(text("SHOW TABLES LIKE 'audit_logs'"))
        if not result.fetchone():
            print("创建 audit_logs 表...")
            await conn.execute(text("""
                CREATE TABLE `audit_logs` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT,
                    `created_at` DATETIME NOT NULL COMMENT '操作时间',
                    `actor_loginid` VARCHAR(50) NOT NULL COMMENT '谁（loginid）',
                    `actor_name` VARCHAR(100) NULL COMMENT '姓名',
                    `actor_role` VARCHAR(20) NULL COMMENT 'admin/k_user/oa_user',
                    `action` VARCHAR(50) NOT NULL COMMENT '事件类型',
                    `target_type` VARCHAR(50) NULL COMMENT '对象类型',
                    `target_id` VARCHAR(100) NULL COMMENT '对象ID',
                    `target_label` VARCHAR(255) NULL COMMENT '对象描述',
                    `ip` VARCHAR(64) NULL COMMENT '客户端 IP',
                    `user_agent` VARCHAR(255) NULL,
                    `result` VARCHAR(20) NOT NULL DEFAULT 'success' COMMENT 'success/fail',
                    `detail` JSON NULL COMMENT '业务上下文',
                    PRIMARY KEY (`id`),
                    KEY `idx_created_at` (`created_at`),
                    KEY `idx_actor_loginid` (`actor_loginid`),
                    KEY `idx_action` (`action`),
                    KEY `idx_target_type` (`target_type`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                  COMMENT='审计日志表'
            """))
            print("audit_logs 表创建成功")
        else:
            print("audit_logs 表已存在，跳过建表")

        # 2. 兜底补索引（如果表是老版本建出来的，索引可能不全）
        for idx_name, col in (
            ("idx_created_at", "created_at"),
            ("idx_actor_loginid", "actor_loginid"),
            ("idx_action", "action"),
            ("idx_target_type", "target_type"),
        ):
            r = await conn.execute(text(f"SHOW INDEX FROM audit_logs WHERE Key_name = '{idx_name}'"))
            if not r.fetchone():
                print(f"补建索引 {idx_name} ({col})...")
                await conn.execute(text(f"ALTER TABLE audit_logs ADD INDEX `{idx_name}` (`{col}`)"))
            else:
                print(f"索引 {idx_name} 已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())