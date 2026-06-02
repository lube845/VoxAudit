"""
录音管理路由
"""
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import Optional, List
import logging

from backend.core.database import get_db, AsyncSessionLocal
from backend.core.config import settings
from backend.models.recording import Recording, RecordingStatus, TranscriptSegment, ScoringResult
from backend.models.rule import ScoringRule
from backend.schemas.recording import (
    RecordingInitUpload, RecordingUploadResponse, RecordingResponse,
    RecordingDetailResponse, ScoringResultResponse, RecordingListResponse,
)
from backend.services.oss_service import oss_service
from backend.services.asr_service import asr_service
from backend.services.ai_scoring_service import ai_scoring_service
from backend.api.auth import get_current_user_required

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recordings", tags=["录音管理"])


@router.post("/init-upload")
async def init_upload(
    data: RecordingInitUpload,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """初始化上传（秒传检查）"""
    user_id = current_user.get("loginid", "admin")
    # 检查MD5是否已存在（秒传），并且是当前用户的
    if data.file_md5:
        result = await db.execute(
            select(Recording).where(
                Recording.file_md5 == data.file_md5,
                Recording.user_id == user_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return {
                "exists": True,
                "recording_id": existing.id,
                "message": "文件已存在",
            }

    # 生成对象存储键
    object_key = oss_service.generate_object_key(data.file_name)

    # 创建录音记录
    recording = Recording(
        file_name=data.file_name,
        file_size=data.file_size,
        file_md5=data.file_md5,
        file_type=data.file_type,
        oss_object_key=object_key,
        oss_bucket=settings.OSS_BUCKET,
        status=RecordingStatus.UPLOADING,
        agent_name=data.agent_name,
        user_id=user_id,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    return {
        "exists": False,
        "recording_id": recording.id,
        "upload_url": f"/api/v1/recordings/{recording.id}/upload",
        "object_key": object_key,
    }


@router.post("/{recording_id}/upload")
async def upload_file(
    recording_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """上传录音文件"""
    user_id = current_user.get("loginid", "admin")
    # 获取录音记录（只能操作当前用户的）
    result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="录音记录不存在")

    # 读取文件内容
    content = await file.read()

    # 上传到OSS
    try:
        content_type = f"audio/{recording.file_type}" if recording.file_type in ["mp3", "wav", "amr", "m4a"] else "application/octet-stream"
        await oss_service.upload_file(
            file_data=content,
            object_key=recording.oss_object_key,
            content_type=content_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

    # 更新录音状态
    recording.status = RecordingStatus.UPLOADED
    await db.commit()

    # 触发异步转写
    asyncio.create_task(transcribe_recording_bg(recording_id))

    return {"message": "上传成功", "recording_id": recording_id}


async def transcribe_recording_bg(recording_id: int):
    """后台转写录音"""
    async with AsyncSessionLocal() as db:
        await _transcribe_impl(recording_id, db)


async def _transcribe_impl(recording_id: int, db: AsyncSession):
    """转写录音实现"""
    result = await db.execute(select(Recording).where(Recording.id == recording_id))
    recording = result.scalar_one_or_none()
    if not recording:
        return

    recording.status = RecordingStatus.TRANSCRIBING
    await db.commit()

    try:
        # 从OSS获取文件内容
        file_content = await oss_service.get_file(recording.oss_object_key)

        # 调用ASR转写
        transcript_result = await asr_service.transcribe_with_role(
            file_content, recording.file_name
        )

        # 保存转写结果
        recording.transcript = transcript_result.get("full_text", "")

        # 保存转写片段到 TranscriptSegment 表
        segments_data = transcript_result.get("segments", [])
        for seg in segments_data:
            segment = TranscriptSegment(
                recording_id=recording_id,
                speaker=seg.get("speaker"),
                speaker_name=seg.get("speaker_name"),
                start_time=seg.get("start_time"),
                end_time=seg.get("end_time"),
                text=seg.get("text"),
                confidence=seg.get("confidence"),
            )
            db.add(segment)

        # 同时保留 JSON 格式（兼容旧数据）
        recording.transcript_segments = segments_data

        # 估算时长
        if transcript_result.get("segments"):
            last_seg = transcript_result["segments"][-1]
            recording.duration = last_seg.get("end_time")

        recording.status = RecordingStatus.TRANSCRIBED
        await db.commit()

        # 转写完成后自动触发评分
        asyncio.create_task(auto_score_recording(recording_id))

    except Exception as e:
        logger.error(f"转写失败: {e}")
        recording.status = RecordingStatus.TRANSCRIBE_FAILED
        await db.commit()


async def auto_score_recording(recording_id: int):
    """自动评分录音"""
    logger.info(f"[评分] 开始自动评分 recording_id={recording_id}")
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Recording).where(Recording.id == recording_id))
            recording = result.scalar_one_or_none()
            if not recording:
                logger.warning(f"[评分] 录音不存在 recording_id={recording_id}")
                return

            logger.info(f"[评分] 录音状态={recording.status}, 转写文本长度={len(recording.transcript or '')}")

            # 获取该用户所有最新版本的规则
            rules_result = await db.execute(
                select(ScoringRule).where(
                    ScoringRule.is_latest == True,
                    ScoringRule.user_id == recording.user_id,
                )
            )
            rules = list(rules_result.scalars().all())

            logger.info(f"[评分] 找到 {len(rules)} 条规则")

            if not rules:
                logger.warning(f"[评分] 没有找到规则，跳过评分: recording_id={recording_id}")
                return

            recording.status = RecordingStatus.SCORING
            await db.commit()
            logger.info(f"[评分] 已更新状态为 SCORING")

            # 分别对每个规则进行评分
            total_bonus = 0
            total_deduction = 0
            all_details = []
            has_veto = False  # 初始化否决标记

            for rule in rules:
                logger.info(f"[评分] 开始评分规则 id={rule.id}, name={rule.name}, code={rule.code}")
                # 调用AI评分
                scoring_result = await ai_scoring_service.score(
                    transcript=recording.transcript or "",
                    segments=recording.transcript_segments or [],
                    rule=rule,
                )
                logger.info(f"[评分] 规则评分完成 id={rule.id}, bonus={scoring_result.get('bonus_score', 0)}, deduction={scoring_result.get('deduction_score', 0)}, is_rejected={scoring_result.get('is_rejected', False)}")
                total_bonus += scoring_result.get("bonus_score", 0)
                total_deduction += scoring_result.get("deduction_score", 0)
                all_details.extend(scoring_result.get("details", []))
                # 追踪是否有否决项被命中
                if scoring_result.get("is_rejected", False):
                    has_veto = True

            # 计算总分
            final_score = max(0, total_bonus - total_deduction)

            # 保存评分结果
            result_record = ScoringResult(
                recording_id=recording.id,
                rule_ids=[rule.id for rule in rules],  # 存储所有参与评分的规则ID
                total_score=final_score,
                bonus_score=total_bonus,
                deduction_score=total_deduction,
                scoring_details=all_details,
                is_auto_scored=True,
                is_rejected=has_veto,
            )
            db.add(result_record)

            # 更新录音评分信息
            recording.total_score = final_score
            recording.bonus_score = total_bonus
            recording.deduction_score = total_deduction
            recording.rule_version = rules[0].version if rules else None
            recording.status = RecordingStatus.SCORED

            await db.commit()

        except Exception as e:
            logger.error(f"[评分] 自动评分失败: recording_id={recording_id}, error={e}")
            import traceback
            traceback.print_exc()
            try:
                # 重新获取recording对象
                result = await db.execute(select(Recording).where(Recording.id == recording_id))
                recording = result.scalar_one_or_none()
                if recording:
                    recording.status = RecordingStatus.SCORE_FAILED
                    recording.remark = f"评分失败: {str(e)}"
                    await db.commit()
                    logger.info(f"[评分] 已更新状态为 SCORE_FAILED, remark={recording.remark}")
            except Exception as commit_err:
                logger.error(f"[评分] 更新状态失败: {commit_err}")


@router.delete("/{recording_id}")
async def delete_recording(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """删除录音"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")

    # 删除转写片段
    await db.execute(delete(TranscriptSegment).where(TranscriptSegment.recording_id == recording_id))
    # 删除评分结果
    await db.execute(delete(ScoringResult).where(ScoringResult.recording_id == recording_id))
    # 删除录音记录
    await db.delete(recording)
    await db.commit()

    # 后台删除OSS文件
    object_key = recording.oss_object_key
    asyncio.create_task(_delete_oss_file_bg(object_key))

    return {"message": "删除成功"}


async def _delete_oss_file_bg(object_key: str):
    """后台删除OSS文件"""
    try:
        await oss_service.delete_file(object_key)
        logger.info(f"OSS文件删除成功: {object_key}")
    except Exception as e:
        logger.error(f"OSS文件删除失败: object_key={object_key}, error={e}")


@router.get("", response_model=RecordingListResponse)
async def list_recordings(
    status: Optional[str] = None,
    agent_name: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取录音列表（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    query = select(Recording).where(Recording.user_id == user_id)

    if status:
        try:
            status_enum = RecordingStatus(status)
            query = query.where(Recording.status == status_enum)
        except ValueError:
            pass  # ignore invalid status values
    if agent_name:
        query = query.where(Recording.agent_name.ilike(f"%{agent_name}%"))
    if keyword:
        query = query.where(
            Recording.file_name.ilike(f"%{keyword}%")
        )
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            query = query.where(Recording.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
            query = query.where(Recording.created_at <= end_dt)
        except ValueError:
            pass

    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(Recording.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    recordings = result.scalars().all()

    # 获取每个录音的评分结果中的 is_rejected 标记
    recording_ids = [r.id for r in recordings]
    is_rejected_map = {}
    if recording_ids:
        score_result = await db.execute(
            select(ScoringResult.recording_id, ScoringResult.is_rejected)
            .where(ScoringResult.recording_id.in_(recording_ids))
        )
        is_rejected_map = {r.recording_id: r.is_rejected for r in score_result.fetchall()}

    # 构建响应列表
    items = []
    for r in recordings:
        items.append({
            "id": r.id,
            "file_name": r.file_name,
            "file_size": r.file_size,
            "file_type": r.file_type,
            "status": r.status.value if hasattr(r.status, 'value') else r.status,
            "duration": r.duration,
            "transcript": r.transcript,
            "total_score": r.total_score,
            "bonus_score": r.bonus_score or 0,
            "deduction_score": r.deduction_score or 0,
            "agent_id": r.agent_id,
            "agent_name": r.agent_name,
            "customer_phone": r.customer_phone,
            "remark": r.remark,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "is_rejected": is_rejected_map.get(r.id, False),
        })

    return RecordingListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{recording_id}", response_model=RecordingDetailResponse)
async def get_recording(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取录音详情"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")

    # 获取转写片段
    segments_result = await db.execute(
        select(TranscriptSegment).where(TranscriptSegment.recording_id == recording_id)
    )
    segments = segments_result.scalars().all()

    # 获取评分结果
    score_result = await db.execute(
        select(ScoringResult).where(ScoringResult.recording_id == recording_id)
    )
    scoring = score_result.scalar_one_or_none()

    # 构建评分结果响应
    scoring_results = []
    if scoring:
        details_list = []
        if scoring.scoring_details:
            for i, d in enumerate(scoring.scoring_details):
                details_list.append({
                    "id": d.get("rule_item_id", i + 1),
                    "item_name": d.get("item_name", ""),
                    "item_type": d.get("item_type", ""),
                    "status": d.get("status", ""),
                    "score": d.get("score", 0),
                    "max_score": d.get("max_score", 0),
                    "matched_text": d.get("matched_text"),
                })

        scoring_results.append({
            "id": scoring.id,
            "total_score": scoring.total_score,
            "bonus_score": scoring.bonus_score or 0,
            "deduction_score": scoring.deduction_score or 0,
            "passed": scoring.total_score >= 60,
            "is_rejected": getattr(scoring, 'is_rejected', False),
            "is_auto_scored": scoring.is_auto_scored,
            "ai_model": scoring.ai_model,
            "scored_by": getattr(scoring, 'scored_by', None),
            "scored_at": getattr(scoring, 'scored_at', None),
            "remark": getattr(scoring, 'remark', None),
            "rule_ids": getattr(scoring, 'rule_ids', None),  # 参与评分的规则ID列表
            "details": details_list,
            "created_at": scoring.created_at,
        })

    # 获取是否被否决（是否命中否决规则）
    is_rejected = getattr(scoring, 'is_rejected', False) if scoring else False

    return {
        **recording.__dict__,
        "transcript_segments": recording.transcript_segments or [],
        "scoring_results": scoring_results,
        "is_rejected": is_rejected,
    }


@router.get("/{recording_id}/score")
async def get_scoring_result(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取录音评分结果"""
    user_id = current_user.get("loginid", "admin")
    # 先验证录音属于当前用户
    rec_result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id
        )
    )
    if not rec_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="录音不存在")

    result = await db.execute(select(ScoringResult).where(ScoringResult.recording_id == recording_id))
    scoring = result.scalars().first()
    if not scoring:
        raise HTTPException(status_code=404, detail="评分结果不存在")

    # 构建响应数据，处理 JSON 字段
    return {
        "id": scoring.id,
        "recording_id": scoring.recording_id,
        "total_score": scoring.total_score,
        "bonus_score": scoring.bonus_score or 0,
        "deduction_score": scoring.deduction_score or 0,
        "scoring_details": scoring.scoring_details,
        "matched_text": scoring.matched_text,
        "is_auto_scored": scoring.is_auto_scored,
        "is_rejected": scoring.is_rejected,
        "ai_model": scoring.ai_model,
        "scored_by": scoring.scored_by,
        "scored_at": scoring.scored_at,
        "remark": scoring.remark,
        "rule_ids": scoring.rule_ids,  # JSON 字段直接返回
        "user_id": scoring.user_id,
        "created_at": scoring.created_at,
    }


@router.post("/{recording_id}/transcribe")
async def trigger_transcribe(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """手动触发转写"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")

    if recording.status != RecordingStatus.UPLOADED:
        raise HTTPException(status_code=400, detail="录音状态不正确")

    asyncio.create_task(transcribe_recording_bg(recording_id))
    return {"message": "转写任务已触发"}


@router.post("/{recording_id}/score")
async def trigger_scoring(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """手动触发评分"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")

    if recording.status not in [RecordingStatus.TRANSCRIBED, RecordingStatus.SCORE_FAILED]:
        raise HTTPException(status_code=400, detail="录音未完成转写")

    asyncio.create_task(auto_score_recording(recording_id))
    return {"message": "评分任务已触发"}


@router.get("/{recording_id}/play")
async def play_recording(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取录音播放URL"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id
        )
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="录音不存在")

    try:
        url = await oss_service.get_presigned_url(recording.oss_object_key)
        return {"play_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成播放URL失败: {str(e)}")
