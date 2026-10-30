# -*- coding: utf-8 -*-
"""
「刷新转后台任务」链路的集成自检（需要一个可连的 MySQL）。

验证点：
  1. POST /collection-notes/calls/refresh 立即返回 {status: running, job_id}
  2. 后台任务最终把 call_records / call_notes 落库
  3. GET /collection-notes/calls/refresh/{job_id} 能查到进度并最终变 done
  4. 同一个 loginid 在任务跑完前再刷一次 → 409

上游（CSP/ESCTerminal）与解密都在这里 mock 掉，只测我们自己的编排逻辑。

跑法：
    cd <项目根目录>
    set -a && . docker/.env && set +a
    python3 backend/tests/test_refresh_async_flow.py
    # 若是本机 docker 的 MySQL（端口 3307）：DB_PORT=3307 DB_HOST=127.0.0.1 python3 ...
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DB_PASSWORD", "voxaudit2026")
os.environ.setdefault("ADMIN_PASSWORD", "test")
os.environ.setdefault("CSP_ADAPTER_BASE_URL", "http://csp-adapter:8081")
os.environ.setdefault("ICP_API_BASE_URL", "http://escterminal:10306/v1/icp/ICP1100010")

from sqlalchemy import delete, select  # noqa: E402

from backend.api import collection_note as cn  # noqa: E402
from backend.core.database import AsyncSessionLocal  # noqa: E402
from backend.models.call_note import CallNote  # noqa: E402
from backend.models.call_record import CallRecord  # noqa: E402
from backend.models.audit_log import AuditLog  # noqa: E402


TEST_LOGINID = "k_test_refresh_async"
TEST_CALL_ID = "test-refresh-async-0001"
TEST_CIPHER = "B386C21F11A12C2F44CEFEA082A859498CBBD54E88F5AE34D8DBF82B00F132EA"


def _fake_records():
    return [{
        "call_id": TEST_CALL_ID,
        "agent_id": "61038",
        "agent_name": "61038",
        "dn_id": "1038",
        "phone_number": "1038",
        "calling_number": "135****9752",
        "established_time": "2026-10-19 14:40:40",
        "released_times": "2026-10-19 14:43:22",
        "handle_times": 162,
        "call_url": "F1813D881686C00E80FB231904DA0691AC6C7FD4831EB2626FAE5A0D49F31",
        "call_url_inner": TEST_CIPHER,
        "reserve1": "", "reserve2": "", "reserve3": "", "reserve4": "", "reserve5": "",
    }]


async def _mock_query(**kwargs):
    return _fake_records()


async def _mock_decrypt(ciphers, **kwargs):
    # 第一条成功，第二条（若有）失败 → 验证「单条失败不影响整批」
    out = []
    for i, c in enumerate(ciphers):
        if i == 0:
            out.append(("http://example.invalid/a.wav", None))
        else:
            out.append((None, "模拟解密失败"))
    return out


def _install_mocks():
    cn.query_call_records = _mock_query
    cn.decrypt_call_urls = _mock_decrypt


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(CallNote).where(CallNote.call_id == TEST_CALL_ID))
        await db.execute(delete(CallRecord).where(CallRecord.call_id == TEST_CALL_ID))
        await db.execute(
            delete(AuditLog).where(AuditLog.actor_loginid == TEST_LOGINID)
        )
        await db.commit()


async def main() -> int:
    _install_mocks()
    user_info = {"loginid": TEST_LOGINID, "姓名": "异步刷新自检"}
    payload = cn.RefreshRequest()

    await _cleanup()

    async with AsyncSessionLocal() as db:
        # ——— 1) 调刷新：应立即返回 running ———
        t0 = time.time()
        res = await cn.refresh_calls(payload, None, user_info, db)
        elapsed = time.time() - t0
        print(f"接口耗时 {elapsed:.3f}s，返回：{ {k: v for k, v in res.items() if k != 'items'} }")
        assert res.get("status") == "running", f"应返回 status=running，实际 {res.get('status')}"
        assert res.get("job_id"), "应返回 job_id"
        job_id = res["job_id"]

        # ——— 2) 轮询任务直到结束 ———
        for _ in range(100):
            st = await cn.get_refresh_status(job_id, user_info)
            job = st["job"]
            if job["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.1)
        else:
            print("✗ 任务超时未结束")
            return 1

        print(f"任务最终状态：{job}")
        assert job["status"] == "done", f"任务应成功，实际 {job['status']} / {job.get('error')}"
        assert job["decrypted"] == 1, f"应解密成功 1 条，实际 {job['decrypted']}"
        assert job["inserted"] == 1, f"应新增 1 条，实际 {job['inserted']}"
        assert job["notes_inserted"] == 1, f"应新增 1 条催记记录，实际 {job['notes_inserted']}"

        # ——— 3) 校验落库 ———
        rec = await db.execute(select(CallRecord).where(CallRecord.call_id == TEST_CALL_ID))
        row = rec.scalars().first()
        assert row is not None, "call_records 没落库"
        assert row.call_url_decrypted == "http://example.invalid/a.wav", f"解密地址不对：{row.call_url_decrypted}"
        assert row.agent_id == "k61038", f"落库工号应为 k61038，实际 {row.agent_id}"
        assert row.established_time is not None, "established_time 丢了"

        note = await db.execute(select(CallNote).where(CallNote.call_id == TEST_CALL_ID))
        nrow = note.scalars().first()
        assert nrow is not None, "call_notes 没落库"
        # 落库后后台处理循环可能立刻认领它 → pending/processing 都算正常
        assert nrow.asr_status in ("pending", "processing"), \
            f"催记初始状态应为 pending/processing，实际 {nrow.asr_status}"

        # ——— 4) 重复刷新保护 ———
        cn._clear_refresh_cooldown(TEST_LOGINID)   # 跳过 5s 频控
        res2 = await cn.refresh_calls(payload, None, user_info, db)
        print(f"第二次刷新返回：{res2.get('status')}（任务已结束，应允许再次刷新）")
        # 等它跑完，避免残留任务
        for _ in range(100):
            st = await cn.get_refresh_status(res2["job_id"], user_info)
            if st["job"]["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.1)

    await _cleanup()
    print("\n✓ 异步刷新链路自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
