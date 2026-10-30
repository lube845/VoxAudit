"""
数据库迁移脚本 - 给 call_records 增加 call_url_inner / call_url_decrypted 两列
运行方式: python -m backend.migrations.migrate_add_call_record_url_inner

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

        if not await column_exists("call_url_inner"):
            print("添加 call_url_inner 列...")
            await conn.execute(text(
                "ALTER TABLE call_records ADD COLUMN call_url_inner TEXT NULL "
                "COMMENT '通话录音地址密文（上游原值）'"
            ))
        else:
            print("call_url_inner 已存在")

        if not await column_exists("call_url_decrypted"):
            print("添加 call_url_decrypted 列...")
            await conn.execute(text(
                "ALTER TABLE call_records ADD COLUMN call_url_decrypted TEXT NULL "
                "COMMENT '通话录音地址明文（已解密）'"
            ))
        else:
            print("call_url_decrypted 已存在")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())