"""
用户使用情况统计API - 仅超级管理员可用
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.config import settings
from backend.models.recording import Recording, RecordingStatus, ScoringResult
from backend.models.rule import ScoringRule
from backend.api.auth import get_current_user_required

router = APIRouter(prefix="/statistics/users", tags=["用户统计"])


def require_admin(current_user: dict = Depends(get_current_user_required)) -> dict:
    """检查是否为超级管理员"""
    if current_user.get("loginid") != settings.ADMIN_USER:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")
    return current_user


class UserStats(BaseModel):
    """用户统计数据"""
    loginid: str
    name: str  # 姓名
    department: str  # 部门
    total_recordings: int  # 总录音数
    total_duration: float  # 总录音时长(秒)
    avg_score: float  # 平均分
    total_storage_bytes: int  # 总占用存储(字节)
    score_distribution: dict  # 分数分布 {0-60: count, 60-70: count, ...}
    recordings_by_status: dict  # 各状态录音数
    recent_activity: list  # 近30天活动


class ScoreRangeItem(BaseModel):
    label: str
    count: int
    percentage: float


class UserDetailStats(BaseModel):
    """用户详细统计"""
    loginid: str
    name: str
    department: str

    # 规则统计
    total_rules: int
    active_rules: int
    latest_rule_version: Optional[str]

    # 录音统计
    total_recordings: int
    uploaded_recordings: int
    transcribed_recordings: int
    scored_recordings: int
    failed_recordings: int
    total_duration: float  # 秒
    avg_duration: float  # 秒
    total_storage_bytes: int

    # 评分统计
    avg_total_score: float
    avg_bonus_score: float
    avg_deduction_score: float
    pass_rate: float  # 60分以上比例
    reject_rate: float  # 否决率
    score_distribution: List[ScoreRangeItem]

    # 时间分布
    recordings_timeline: List[dict]  # 每日录音数


class UsersOverview(BaseModel):
    """用户概览"""
    total_users: int
    active_users: int  # 30天内有活动的用户
    total_recordings: int
    total_storage_bytes: int
    avg_score_all: float


@router.get("/overview", response_model=UsersOverview)
async def get_users_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """
    获取所有用户的概览统计
    """
    db: AsyncSession = await get_db().__anext__()

    # 默认时间范围：全部
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        except ValueError:
            pass

    # 获取不同时区用户数
    all_users_result = await db.execute(
        select(func.count(distinct(Recording.user_id)))
    )
    total_users = all_users_result.scalar() or 0

    # 获取活跃用户数（30天内有活动）
    active_date = datetime.now() - timedelta(days=30)
    active_users_result = await db.execute(
        select(func.count(distinct(Recording.user_id)))
        .where(Recording.created_at >= active_date)
    )
    active_users = active_users_result.scalar() or 0

    # 录音总数
    recordings_count_result = await db.execute(select(func.count(Recording.id)))
    total_recordings = recordings_count_result.scalar() or 0

    # 总存储
    storage_result = await db.execute(
        select(func.sum(Recording.file_size))
    )
    total_storage_bytes = storage_result.scalar() or 0

    # 平均分
    avg_score_result = await db.execute(
        select(func.avg(ScoringResult.total_score))
        .where(ScoringResult.total_score.isnot(None))
    )
    avg_score_all = avg_score_result.scalar() or 0.0

    await db.close()

    return UsersOverview(
        total_users=total_users,
        active_users=active_users,
        total_recordings=total_recordings,
        total_storage_bytes=total_storage_bytes,
        avg_score_all=round(avg_score_all, 2) if avg_score_all else 0.0
    )


@router.get("/list", response_model=List[UserStats])
async def get_users_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_recordings: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin)
):
    """
    获取所有用户的统计数据列表
    """
    db: AsyncSession = await get_db().__anext__()

    # 时间范围
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        except ValueError:
            pass

    # 获取所有用户列表
    users_result = await db.execute(
        select(Recording.user_id, func.count(Recording.id).label('recording_count'))
        .group_by(Recording.user_id)
        .having(func.count(Recording.id) >= min_recordings)
    )
    user_groups = users_result.fetchall()

    results = []
    for user_row in user_groups:
        user_id = user_row.user_id or "unknown"

        # 获取该用户的录音列表（带时间筛选）
        query = select(Recording).where(Recording.user_id == user_id)
        if start_dt:
            query = query.where(Recording.created_at >= start_dt)
        if end_dt:
            query = query.where(Recording.created_at < end_dt)

        recordings_result = await db.execute(query)
        recordings = recordings_result.scalars().all()

        if not recordings:
            continue

        # 获取该用户的规则数
        rules_count_result = await db.execute(
            select(func.count(ScoringRule.id)).where(ScoringRule.user_id == user_id)
        )
        total_rules = rules_count_result.scalar() or 0

        # 计算统计数据
        total_recordings = len(recordings)
        total_duration = sum(r.duration or 0 for r in recordings)
        total_size = sum(r.file_size or 0 for r in recordings)

        # 评分统计
        scored_recordings = [r for r in recordings if r.total_score is not None]
        avg_score = sum(r.total_score or 0 for r in scored_recordings) / len(scored_recordings) if scored_recordings else 0

        # 分数分布
        score_dist = {"0-60": 0, "60-70": 0, "70-80": 0, "80-90": 0, "90-100": 0}
        for r in scored_recordings:
            score = r.total_score or 0
            if score < 60:
                score_dist["0-60"] += 1
            elif score < 70:
                score_dist["60-70"] += 1
            elif score < 80:
                score_dist["70-80"] += 1
            elif score < 90:
                score_dist["80-90"] += 1
            else:
                score_dist["90-100"] += 1

        # 状态分布
        status_dist = {}
        for r in recordings:
            status = r.status.value if hasattr(r.status, 'value') else str(r.status)
            status_dist[status] = status_dist.get(status, 0) + 1

        # 近30天活动
        recent_date = datetime.now() - timedelta(days=30)
        recent_recordings = [r for r in recordings if r.created_at and r.created_at >= recent_date]
        recent_activity_count = len(recent_recordings)

        # 获取用户名信息（从OA获取，简化处理）
        name = user_id  # 默认用工号作姓名
        department = ""

        results.append(UserStats(
            loginid=user_id,
            name=name,
            department=department,
            total_recordings=total_recordings,
            total_duration=round(total_duration, 2),
            avg_score=round(avg_score, 2),
            total_storage_bytes=total_size,
            score_distribution=score_dist,
            recordings_by_status=status_dist,
            recent_activity=[{"date": str(datetime.now().date()), "count": recent_activity_count}]
        ))

    await db.close()
    return results


@router.get("/{loginid}/detail", response_model=UserDetailStats)
async def get_user_detail_stats(
    loginid: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """
    获取指定用户的详细统计数据
    """
    db: AsyncSession = await get_db().__anext__()

    # 时间范围
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        except ValueError:
            pass

    # 获取规则统计
    rules_result = await db.execute(
        select(ScoringRule).where(ScoringRule.user_id == loginid)
    )
    rules = list(rules_result.scalars().all())
    total_rules = len(rules)
    active_rules = len([r for r in rules if r.is_latest])
    latest_rule = max((r for r in rules if r.is_latest), key=lambda r: r.version, default=None)
    latest_rule_version = latest_rule.version if latest_rule else None

    # 获取录音统计
    query = select(Recording).where(Recording.user_id == loginid)
    if start_dt:
        query = query.where(Recording.created_at >= start_dt)
    if end_dt:
        query = query.where(Recording.created_at < end_dt)

    recordings_result = await db.execute(query)
    recordings = list(recordings_result.scalars().all())

    total_recordings = len(recordings)
    uploaded_recordings = len([r for r in recordings if r.status == RecordingStatus.UPLOADED])
    transcribed_recordings = len([r for r in recordings if r.status in [RecordingStatus.TRANSCRIBED, RecordingStatus.SCORING, RecordingStatus.SCORED]])
    scored_recordings = len([r for r in recordings if r.status == RecordingStatus.SCORED])
    failed_recordings = len([r for r in recordings if r.status in [RecordingStatus.UPLOAD_FAILED, RecordingStatus.TRANSCRIBE_FAILED, RecordingStatus.SCORE_FAILED]])

    durations = [r.duration for r in recordings if r.duration]
    total_duration = sum(durations)
    avg_duration = total_duration / len(durations) if durations else 0
    total_storage_bytes = sum(r.file_size or 0 for r in recordings)

    # 评分统计（只统计已评分的）
    scored = [r for r in recordings if r.total_score is not None]
    avg_total_score = sum(r.total_score or 0 for r in scored) / len(scored) if scored else 0
    avg_bonus_score = sum(r.bonus_score or 0 for r in scored) / len(scored) if scored else 0
    avg_deduction_score = sum(r.deduction_score or 0 for r in scored) / len(scored) if scored else 0

    # 通过率（60分以上）
    passed = len([r for r in scored if (r.total_score or 0) >= 60])
    pass_rate = (passed / len(scored) * 100) if scored else 0

    # 否决率
    # 获取该用户录音的评分结果中的否决标记
    recording_ids = [r.id for r in recordings]
    rejected_count = 0
    if recording_ids:
        reject_result = await db.execute(
            select(func.count(ScoringResult.id))
            .where(ScoringResult.recording_id.in_(recording_ids))
            .where(ScoringResult.is_rejected == True)
        )
        rejected_count = reject_result.scalar() or 0
    reject_rate = (rejected_count / len(scored) * 100) if scored else 0

    # 分数分布
    score_dist_list = []
    score_ranges = [("0-60", 0, 60), ("60-70", 60, 70), ("70-80", 70, 80), ("80-90", 80, 90), ("90-100", 90, 101)]
    for label, low, high in score_ranges:
        count = len([r for r in scored if low <= (r.total_score or 0) < high])
        percentage = (count / len(scored) * 100) if scored else 0
        score_dist_list.append(ScoreRangeItem(
            label=label,
            count=count,
            percentage=round(percentage, 1)
        ))

    # 每日录音数时间线
    timeline = {}
    for r in recordings:
        if r.created_at:
            date_key = r.created_at.strftime('%Y-%m-%d')
            timeline[date_key] = timeline.get(date_key, 0) + 1

    recordings_timeline = [{"date": k, "count": v} for k, v in sorted(timeline.items())]

    # 获取用户姓名（从最近一条录音的agent_name或用loginid）
    name = loginid

    await db.close()

    return UserDetailStats(
        loginid=loginid,
        name=name,
        department="",
        total_rules=total_rules,
        active_rules=active_rules,
        latest_rule_version=latest_rule_version,
        total_recordings=total_recordings,
        uploaded_recordings=uploaded_recordings,
        transcribed_recordings=transcribed_recordings,
        scored_recordings=scored_recordings,
        failed_recordings=failed_recordings,
        total_duration=round(total_duration, 2),
        avg_duration=round(avg_duration, 2),
        total_storage_bytes=total_storage_bytes,
        avg_total_score=round(avg_total_score, 2),
        avg_bonus_score=round(avg_bonus_score, 2),
        avg_deduction_score=round(avg_deduction_score, 2),
        pass_rate=round(pass_rate, 1),
        reject_rate=round(reject_rate, 1),
        score_distribution=score_dist_list,
        recordings_timeline=recordings_timeline
    )


@router.get("/leaderboard", response_model=List[dict])
async def get_users_leaderboard(
    limit: int = Query(10, ge=1, le=50),
    sort_by: str = Query("total_score", regex="^(total_score|total_recordings|avg_score)$"),
    current_user: dict = Depends(require_admin)
):
    """
    获取用户排行榜（按平均分/录音数/总分）
    """
    db: AsyncSession = await get_db().__anext__()

    # 获取所有用户及其统计数据
    users_result = await db.execute(
        select(Recording.user_id, func.count(Recording.id).label('recording_count'))
        .group_by(Recording.user_id)
    )
    user_groups = users_result.fetchall()

    leaderboard = []

    for user_row in user_groups:
        user_id = user_row.user_id or "unknown"

        recordings_result = await db.execute(
            select(Recording).where(Recording.user_id == user_id)
        )
        recordings = list(recordings_result.scalars().all())

        if not recordings:
            continue

        scored = [r for r in recordings if r.total_score is not None]
        total_recordings = len(recordings)
        avg_score = sum(r.total_score or 0 for r in scored) / len(scored) if scored else 0
        total_score_sum = sum(r.total_score or 0 for r in scored)

        leaderboard.append({
            "loginid": user_id,
            "name": user_id,
            "total_recordings": total_recordings,
            "scored_recordings": len(scored),
            "avg_score": round(avg_score, 2),
            "total_score": round(total_score_sum, 2),
        })

    await db.close()

    # 排序
    if sort_by == "total_score":
        leaderboard.sort(key=lambda x: x["total_score"], reverse=True)
    elif sort_by == "avg_score":
        leaderboard.sort(key=lambda x: x["avg_score"], reverse=True)
    else:  # total_recordings
        leaderboard.sort(key=lambda x: x["total_recordings"], reverse=True)

    return leaderboard[:limit]