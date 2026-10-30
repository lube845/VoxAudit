"""
催记管理 - 通话处理服务

负责把 call_records 里的通话记录变成 call_notes 里的转写 + 催记：
  ① 解密 call_url_inner 指向的录音并下载
  ② ASR 转写（声道分离：左=坐席，右=客户）
  ③ LLM 并行生成结构化/非结构化催记
  ④ 写入 call_notes

并发模型：
  - 后台循环处理"还有 pending 步骤"的行，原子认领（只把 pending 的那几步标 processing）
  - 单步重试由用户触发（API 路由直接调用对应方法）
  - 进程内 _running 标志防多协程同时跑
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import mimetypes
import os
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from sqlalchemy import select, update, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.core.datetime_utils import get_current_time
from backend.models.call_note import CallNote
from backend.models.call_record import CallRecord
from backend.services.asr_service import asr_service
from backend.services.config_service import config_service
from backend.services.csp_service import decrypt_call_url
from backend.services.llm_service import llm_service


# —— 字段级状态枚举 ——
ASR_PENDING = "pending"
ASR_PROCESSING = "processing"
ASR_DONE = "done"
ASR_FAILED = "failed"

ALL_STEP_KEYS = ("asr", "structured", "unstructured")
STEP_TO_STATUS_COL = {
    "asr": "asr_status",
    "structured": "structured_status",
    "unstructured": "unstructured_status",
}
STEP_TO_ERROR_COL = {
    "asr": "asr_error",
    "structured": "structured_error",
    "unstructured": "unstructured_error",
}
STEP_TO_NOTE_COL = {
    "asr": "transcript",
    "structured": "structured_note",
    "unstructured": "unstructured_note",
}
STEP_TO_SEGMENTS_COL = {
    "asr": "transcript_segments",
}


# —— 状态判断工具 ——

def _is_terminal(status: str) -> bool:
    return status in (ASR_DONE, ASR_FAILED)


def _row_all_pending(row: CallNote) -> bool:
    return (
        row.asr_status == ASR_PENDING
        and row.structured_status == ASR_PENDING
        and row.unstructured_status == ASR_PENDING
    )


def _row_has_processing(row: CallNote) -> bool:
    return (
        row.asr_status == ASR_PROCESSING
        or row.structured_status == ASR_PROCESSING
        or row.unstructured_status == ASR_PROCESSING
    )


def _row_fully_done(row: CallNote) -> bool:
    return (
        row.asr_status == ASR_DONE
        and row.structured_status == ASR_DONE
        and row.unstructured_status == ASR_DONE
    )


# —— 主服务 ——

class CollectionNoteService:
    """催记处理服务（单例）"""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    # ———————— 公开 API：批量后台 ——————————

    async def trigger_background_processing(self) -> None:
        """幂等地启动后台循环。仅在同一进程内有意义；多进程靠原子认领避免重复。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop(), name="collection-note-bg")
        logger.info("[催记] 后台处理循环已启动")

    async def stop_background_processing(self) -> None:
        """停止后台循环（用于测试/优雅关闭）"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def _process_loop(self) -> None:
        """后台循环：拉一批 → 认领 → 并发处理 → 循环"""
        concurrency = max(1, int(settings.COLLECTION_NOTE_PROCESS_CONCURRENCY or 3))
        try:
            while True:
                claimed = await self._claim_pending_batch(limit=concurrency)
                if not claimed:
                    logger.info("[催记] 没有 pending 记录，后台循环退出")
                    break
                logger.info(f"[催记] 后台认领 {len(claimed)} 条：{claimed}")
                await asyncio.gather(
                    *[self._run_full_pipeline(cid) for cid in claimed],
                    return_exceptions=True,
                )
        except asyncio.CancelledError:
            logger.info("[催记] 后台循环被取消")
            raise
        except Exception as e:
            logger.error(f"[催记] 后台循环异常: {e!r}")
        finally:
            self._running = False

    async def _claim_pending_batch(self, limit: int) -> list[str]:
        """原子认领 N 条"还有 pending 步骤"的行。返回 call_id 列表。

        策略：先 SELECT 候选，再 UPDATE WHERE 仍有 pending 步骤。
        只把 UPDATE 真正影响到的行算作"认领到"（多 worker 不会重复）。

        注意：这里认领的是"还有 pending 步骤"的行，而不是"三步全 pending"的行。
        转写已完成（asr=done）、催记还是 pending 的行同样要能被认领 ——
        否则服务重启把卡死的 processing 重置回 pending 之后，这类行永远没人接手，
        前端就一直转圈又没有重试入口（重试按钮只在 failed 时出现）。
        只把 pending 的那几步标成 processing，已完成的步骤保持 done，避免重跑 ASR。
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CallNote.call_id)
                .where(
                    or_(
                        CallNote.asr_status == ASR_PENDING,
                        CallNote.structured_status == ASR_PENDING,
                        CallNote.unstructured_status == ASR_PENDING,
                    )
                )
                .limit(limit)
            )
            candidates = [r[0] for r in result.all() if r[0]]
            if not candidates:
                return []

            claimed: list[str] = []
            for cid in candidates:
                # 每个候选单独 UPDATE，UPDATE 影响 0 行 → 被其他 worker 抢先了
                upd = (
                    update(CallNote)
                    .where(
                        CallNote.call_id == cid,
                        or_(
                            CallNote.asr_status == ASR_PENDING,
                            CallNote.structured_status == ASR_PENDING,
                            CallNote.unstructured_status == ASR_PENDING,
                        ),
                    )
                    .values(
                        asr_status=case(
                            (CallNote.asr_status == ASR_PENDING, ASR_PROCESSING),
                            else_=CallNote.asr_status,
                        ),
                        structured_status=case(
                            (CallNote.structured_status == ASR_PENDING, ASR_PROCESSING),
                            else_=CallNote.structured_status,
                        ),
                        unstructured_status=case(
                            (CallNote.unstructured_status == ASR_PENDING, ASR_PROCESSING),
                            else_=CallNote.unstructured_status,
                        ),
                    )
                )
                r = await db.execute(upd)
                if r.rowcount:
                    claimed.append(cid)
            await db.commit()
            return claimed

    async def _run_full_pipeline(self, call_id: str) -> None:
        """完整流程：ASR → 写 transcript → 并行两份 LLM → 写催记"""
        try:
            # 1) 下载 + ASR
            await self._step_transcribe(call_id)
            # 2) 取 transcript 后并行两份 LLM
            async with AsyncSessionLocal() as db:
                row = await self._get_note(db, call_id)
                if not row or not row.transcript:
                    logger.warning(f"[催记] {call_id} ASR 完成后无 transcript，跳过 LLM")
                    return
            await asyncio.gather(
                self._step_generate_note(call_id, "structured"),
                self._step_generate_note(call_id, "unstructured"),
                return_exceptions=True,
            )
        except Exception as e:
            logger.error(f"[催记] {call_id} pipeline 异常: {e!r}")
            # 不再整体标 failed（_step_* 已经分别标过）

    # ———————— 公开 API：单步重试 ——————————

    async def retry_transcribe(self, call_id: str, *, force: bool = False) -> dict:
        """ASR 重试：默认仅当 transcript 为空时才跑；force=True 时强制覆盖"""
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                return {"success": False, "message": f"call_note({call_id}) 不存在"}
            if not force and row.transcript and row.asr_status == ASR_DONE:
                return {"success": True, "message": "转写已存在，未重跑", "skipped": True}

        await self._step_transcribe(call_id, force=force)
        return await self._get_note_status_dict(call_id)

    async def retry_structured_note(self, call_id: str, *, force: bool = False) -> dict:
        """结构化催记重试：需要 transcript 存在；默认仅当 structured_note 为空时才跑"""
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                return {"success": False, "message": f"call_note({call_id}) 不存在"}
            if not row.transcript:
                return {"success": False, "message": "尚未转写，无法生成结构化催记", "skipped": True}
            if not force and row.structured_note and row.structured_status == ASR_DONE:
                return {"success": True, "message": "结构化催记已存在，未重跑", "skipped": True}

        await self._step_generate_note(call_id, "structured", force=force)
        return await self._get_note_status_dict(call_id)

    async def retry_unstructured_note(self, call_id: str, *, force: bool = False) -> dict:
        """非结构化催记重试：需要 transcript 存在；默认仅当 unstructured_note 为空时才跑"""
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                return {"success": False, "message": f"call_note({call_id}) 不存在"}
            if not row.transcript:
                return {"success": False, "message": "尚未转写，无法生成非结构化催记", "skipped": True}
            if not force and row.unstructured_note and row.unstructured_status == ASR_DONE:
                return {"success": True, "message": "非结构化催记已存在，未重跑", "skipped": True}

        await self._step_generate_note(call_id, "unstructured", force=force)
        return await self._get_note_status_dict(call_id)

    async def reset_and_reprocess(self, call_id: str) -> dict:
        """整体重试：三步全标 pending，清空内容（保留 edited_*），完整跑一遍"""
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                return {"success": False, "message": f"call_note({call_id}) 不存在"}
            row.asr_status = ASR_PENDING
            row.structured_status = ASR_PENDING
            row.unstructured_status = ASR_PENDING
            row.asr_error = None
            row.structured_error = None
            row.unstructured_error = None
            row.transcript = None
            row.transcript_segments = None
            row.structured_note = None
            row.unstructured_note = None
            row.last_processed_at = None
            await db.commit()

        await self._run_full_pipeline(call_id)
        return await self._get_note_status_dict(call_id)

    # ———————— 内部步骤 ——————————

    async def _step_transcribe(self, call_id: str, *, force: bool = False) -> None:
        """ASR 步骤：解密录音地址 → 下载音频 → 转写 → 写 transcript

        录音地址只认 call_url_inner（上游 ICP1100010 返回的密文），
        调 csp-adapter /v1/password/decrypt 解密成明文 URL 后再下载；出错直接失败。
        """
        # 标 processing
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                logger.warning(f"[催记] ASR 跳过：call_note({call_id}) 不存在")
                return
            if not force and row.asr_status == ASR_DONE and row.transcript:
                return
            row.asr_status = ASR_PROCESSING
            row.asr_error = None
            await db.commit()

        try:
            # 1) 取 call_url_inner 密文
            async with AsyncSessionLocal() as db:
                rec = await self._get_record(db, call_id)
            if not rec:
                raise RuntimeError("call_records 中找不到对应记录")
            cipher = (getattr(rec, "call_url_inner", None) or "").strip()
            if not cipher:
                raise RuntimeError("call_url_inner 为空，无法下载录音")
            # 2) 解密 → 明文可下载 URL
            download_url = await decrypt_call_url(cipher)
            # 3) 下载
            audio_bytes, filename = await self._download_audio(download_url)
            # 4) ASR
            asr_result = await asr_service.transcribe_with_role(
                file_content=audio_bytes,
                filename=filename,
                force_method="channel",
                left_channel_role="agent",
                right_channel_role="customer",
            )
            transcript = asr_result.get("full_text") or ""
            segments = asr_result.get("segments")
            if not transcript:
                raise RuntimeError("ASR 返回转写为空")
            # 5) 写库
            await self._mark_step_done(call_id, "asr", {
                STEP_TO_NOTE_COL["asr"]: transcript,
                STEP_TO_SEGMENTS_COL["asr"]: segments,
            })
        except Exception as e:
            logger.error(f"[催记] {call_id} ASR 失败: {e!r}")
            await self._mark_step_failed(call_id, "asr", str(e))

    async def _step_generate_note(self, call_id: str, kind: str, *, force: bool = False) -> None:
        """单份 LLM 催记生成：kind = 'structured' | 'unstructured'"""
        # 标 processing
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                logger.warning(f"[催记] {kind} 跳过：call_note({call_id}) 不存在")
                return
            status_col = STEP_TO_STATUS_COL[kind]
            if not force and getattr(row, status_col) == ASR_DONE:
                return
            if not row.transcript:
                await self._mark_step_failed(call_id, kind, "无 transcript，无法生成催记")
                return
            setattr(row, status_col, ASR_PROCESSING)
            setattr(row, STEP_TO_ERROR_COL[kind], None)
            transcript = row.transcript
            await db.commit()

        try:
            text = await self._call_llm_note(kind, transcript)
            if not text:
                raise RuntimeError("LLM 返回空")
            await self._mark_step_done(call_id, kind, {STEP_TO_NOTE_COL[kind]: text})
        except Exception as e:
            logger.error(f"[催记] {call_id} {kind} 失败: {e!r}")
            await self._mark_step_failed(call_id, kind, str(e))

    async def _call_llm_note(self, kind: str, transcript: str) -> str:
        """调 LLM 生成指定类型的催记"""
        from backend.services.config_service import ConfigService
        prompts = await ConfigService.get_all_prompts()
        prompt_cfg = prompts.get(f"prompt_{kind}_note") or {
            "system_prompt": "你是一名催收质检专家。",
            "user_prompt": "请根据以下转写生成催记：\n{transcript}",
        }
        sys_p = prompt_cfg.get("system_prompt") or ""
        usr_p = (prompt_cfg.get("user_prompt") or "").format(transcript=transcript)
        result = await llm_service.call(prompt=usr_p, system_message=sys_p)
        return (result or "").strip()

    # ———————— 状态写回 ——————————

    async def _mark_step_done(self, call_id: str, step: str, fields: dict) -> None:
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                return
            for k, v in fields.items():
                setattr(row, k, v)
            setattr(row, STEP_TO_STATUS_COL[step], ASR_DONE)
            setattr(row, STEP_TO_ERROR_COL[step], None)
            row.last_processed_at = get_current_time()
            await db.commit()

    async def _mark_step_failed(self, call_id: str, step: str, error: str) -> None:
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                return
            setattr(row, STEP_TO_STATUS_COL[step], ASR_FAILED)
            setattr(row, STEP_TO_ERROR_COL[step], (error or "")[:4000])
            row.last_processed_at = get_current_time()
            await db.commit()

    async def _get_note(self, db: AsyncSession, call_id: str) -> CallNote | None:
        r = await db.execute(select(CallNote).where(CallNote.call_id == call_id))
        return r.scalar_one_or_none()

    async def _get_record(self, db: AsyncSession, call_id: str) -> CallRecord | None:
        r = await db.execute(select(CallRecord).where(CallRecord.call_id == call_id))
        return r.scalar_one_or_none()

    async def _get_note_status_dict(self, call_id: str) -> dict:
        async with AsyncSessionLocal() as db:
            row = await self._get_note(db, call_id)
            if not row:
                return {"success": False, "message": f"call_note({call_id}) 不存在"}
            return {
                "success": True,
                "asr_status": row.asr_status,
                "structured_status": row.structured_status,
                "unstructured_status": row.unstructured_status,
                "asr_error": row.asr_error,
                "structured_error": row.structured_error,
                "unstructured_error": row.unstructured_error,
                "transcript": row.transcript,
                "structured_note": row.structured_note,
                "unstructured_note": row.unstructured_note,
            }

    # ———————— 音频下载 ——————————

    async def _download_audio(self, url: str) -> tuple[bytes, str]:
        """下载录音；返回 (bytes, filename)"""
        if not url:
            raise RuntimeError("录音下载地址为空")
        timeout = 30
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content = resp.content
                if not content:
                    raise RuntimeError("下载内容为空")
                filename = self._guess_filename(url, resp.headers.get("content-type"))
                return content, filename
        except httpx.TimeoutException as e:
            raise RuntimeError(f"下载超时（>{timeout}s）") from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"下载失败: {e!s}") from e

    @staticmethod
    def _guess_filename(url: str, content_type: str | None) -> str:
        # 1) URL 末段
        path = urlparse(url).path
        base = os.path.basename(path) if path else ""
        if base and "." in base:
            return base
        # 2) Content-Type
        if content_type:
            ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
            if ext:
                return f"audio{ext}"
        # 3) 默认
        return "audio.wav"


# 模块级单例
collection_note_service = CollectionNoteService()
