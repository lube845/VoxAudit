"""
数据库迁移脚本 - 给 call_records 增加 calling_number 列

背景：上游 ICP1100010 的返回里有两个号码字段：
  - calling_number：对端客户号码（上游已脱敏，形如 135****9752）
  - phone_number  ：主叫号码，实为分机号（与 dn_id 相同）
之前只落了 phone_number，导致列表里看不到客户号码。

运行方式: python -m backend.migrations.migrate_add_call_record_calling_number

依赖：call_records 表必须已存在（即 migrate_add_call_records 已运行）。
幂等：列已存在则跳过。
"""
import asyncio
from sqlalchemy import text
from backend.core.database import engine


async def migrate():
    """幂等 ALTER TABLE — 缺啥补啥"""
    async with engine.begin() as conn:
        # 1) 校验表存在
        tbl = await conn.execute(text("SHOW TABLES LIKE 'call_records'"))
        if not tbl.fetchone():
            print("call_records 表不存在，请先运行 migrate_add_call_records")
            return

        # 2) 缺啥补啥
        async def column_exists(name: str) -> bool:
            r = await conn.execute(text(f"SHOW COLUMNS FROM call_records LIKE '{name}'"))
            return r.fetchone() is not None

        if not await column_exists("calling_number"):
            print("添加 calling_number 列...")
            await conn.execute(text(
                "ALTER TABLE call_records ADD COLUMN calling_number VARCHAR(50) NULL "
                "COMMENT '对端客户号码（上游 calling_number，已脱敏）' AFTER phone_number"
            ))
        else:
            print("calling_number 已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
