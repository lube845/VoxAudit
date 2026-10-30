"""
数据库迁移脚本 - 创建 call_records 表（催记管理数据源）
运行方式: python -m backend.migrations.migrate_add_call_records

幂等：表已存在则跳过。
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def _has_unique_index(conn, table: str, col: str) -> bool:
    """列上是否已存在**任意**唯一索引（不按索引名判断）。

    为什么不能按名字查：create_all 建表时模型里的 unique=True 生成的是匿名 UNIQUE 约束，
    InnoDB 会把它命名成列名本身（call_id），而不是 uk_call_id。
    按名字查会永远查不到 → 每次启动都重建一个多余的普通索引（而且名字带 uk_ 却不是唯一键）。
    """
    r = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t "
            "AND COLUMN_NAME = :c AND NON_UNIQUE = 0 LIMIT 1"
        ),
        {"t": table, "c": col},
    )
    return r.fetchone() is not None


async def _ensure_unique_key(conn, table: str, col: str, uk_name: str) -> None:
    """确保 (table, col) 上有唯一键；没有就补建（有重复值时跳过并明确报出来）"""
    # 该列上所有索引：名字 + 是否唯一
    rows = (await conn.execute(
        text(
            "SELECT INDEX_NAME, NON_UNIQUE FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": col},
    )).fetchall()
    unique_names = {r[0] for r in rows if r[1] == 0}
    plain_names = {r[0] for r in rows if r[1] != 0}

    if unique_names:
        print(f"{table}.{col} 已有唯一索引 {sorted(unique_names)}，无需新建")
        # 清理老迁移留下的垃圾：uk_ 开头却不是唯一键的索引
        if uk_name in plain_names:
            print(f"  清理历史遗留的非唯一索引 {uk_name}")
            await conn.execute(text(f"ALTER TABLE `{table}` DROP INDEX `{uk_name}`"))
        return

    # 有重复值时加唯一键会失败 —— 先查出来报清楚，别静默跳过
    dup = await conn.execute(
        text(
            f"SELECT `{col}`, COUNT(*) AS c FROM `{table}` "
            f"GROUP BY `{col}` HAVING c > 1 LIMIT 5"
        )
    )
    dups = dup.fetchall()
    if dups:
        print(f"⚠ {table}.{col} 存在重复值，无法添加唯一键 {uk_name}，需人工清理：{dups}")
        return

    # 可能之前误补过同名的**普通**索引（uk_ 开头却不是唯一键）→ 先删再建唯一键
    if uk_name in plain_names:
        print(f"删除同名非唯一索引 {uk_name}")
        await conn.execute(text(f"ALTER TABLE `{table}` DROP INDEX `{uk_name}`"))

    print(f"补建唯一键 {uk_name} ({col})...")
    await conn.execute(text(f"ALTER TABLE `{table}` ADD UNIQUE KEY `{uk_name}` (`{col}`)"))


async def migrate():
    """创建 call_records 表（含必要的索引）"""
    async with engine.begin() as conn:
        # 1) 建表（如果不存在）
        result = await conn.execute(text("SHOW TABLES LIKE 'call_records'"))
        if not result.fetchone():
            print("创建 call_records 表...")
            await conn.execute(text("""
                CREATE TABLE `call_records` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT,
                    `call_id` VARCHAR(64) NOT NULL COMMENT '通话ID（业务主键）',
                    `agent_id` VARCHAR(50) NOT NULL COMMENT '座席工号',
                    `agent_name` VARCHAR(100) NULL COMMENT '座席姓名',
                    `dn_id` VARCHAR(50) NULL COMMENT '分机号',
                    `phone_number` VARCHAR(50) NULL COMMENT '呼叫号码',
                    `established_time` DATETIME NULL COMMENT '通话开始时间',
                    `released_times` DATETIME NULL COMMENT '通话挂断时间',
                    `handle_times` INT NULL COMMENT '通话时长（秒）',
                    `call_url` TEXT NULL COMMENT '通话录音地址（上游加密，原样存）',
                    `reserve1` VARCHAR(255) NULL,
                    `reserve2` VARCHAR(255) NULL,
                    `reserve3` VARCHAR(255) NULL,
                    `reserve4` VARCHAR(255) NULL,
                    `reserve5` VARCHAR(255) NULL,
                    `fetched_at` DATETIME NOT NULL COMMENT '入库时间',
                    `fetched_by` VARCHAR(50) NOT NULL COMMENT '触发刷新的 loginid',
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uk_call_id` (`call_id`),
                    KEY `idx_call_records_agent_id` (`agent_id`),
                    KEY `idx_call_records_established_time` (`established_time`),
                    KEY `idx_call_records_phone` (`phone_number`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                  COMMENT='催记管理 - 通话记录表（来源：ICP1100010）'
            """))
            print("call_records 表创建成功")
        else:
            print("call_records 表已存在，跳过建表")

        # 2) 唯一键（call_id 必须唯一：否则同一通话会重复入库，查询接口直接 500）
        await _ensure_unique_key(conn, "call_records", "call_id", "uk_call_id")

        # 3) 兜底补普通索引（如果表是老版本建出来的，索引可能不全）
        for idx_name, col in (
            ("idx_call_records_agent_id", "agent_id"),
            ("idx_call_records_established_time", "established_time"),
            ("idx_call_records_phone", "phone_number"),
        ):
            r = await conn.execute(text(f"SHOW INDEX FROM call_records WHERE Key_name = '{idx_name}'"))
            if not r.fetchone():
                print(f"补建索引 {idx_name} ({col})...")
                await conn.execute(text(f"ALTER TABLE call_records ADD INDEX `{idx_name}` (`{col}`)"))
            else:
                print(f"索引 {idx_name} 已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
