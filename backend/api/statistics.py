"""
统计路由
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, Date
from typing import Optional

from backend.core.database import get_db
from backend.models.recording import Recording, RecordingStatus, ScoringResult
from backend.models.rule import ScoringRule
from backend.api.auth import get_current_user_required

router = APIRouter(prefix="/statistics", tags=["统计"])


@router.get("/overview")
async def get_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取统计数据概览（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    # 构建基础查询 - 已评分的录音
    base_conditions = [
        Recording.status == RecordingStatus.SCORED,
        Recording.total_score.isnot(None),
        Recording.user_id == user_id
    ]

    # 时间筛选
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            base_conditions.append(Recording.created_at >= start_dt)
        except:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
            base_conditions.append(Recording.created_at <= end_dt)
        except:
            pass

    # 总录音数（已评分的）
    total_result = await db.execute(
        select(func.count()).where(and_(*base_conditions))
    )
    total_recordings = total_result.scalar() or 0

    # 已评分数
    scored_count = total_recordings

    # 有加分的录音
    bonus_conditions = base_conditions + [
        Recording.bonus_score.isnot(None),
        Recording.bonus_score > 0
    ]
    bonus_result = await db.execute(
        select(func.count()).where(and_(*bonus_conditions))
    )
    recordings_with_bonus = bonus_result.scalar() or 0

    # 有扣分的录音
    deduction_conditions = base_conditions + [
        Recording.deduction_score.isnot(None),
        Recording.deduction_score > 0
    ]
    deduction_result = await db.execute(
        select(func.count()).where(and_(*deduction_conditions))
    )
    recordings_with_deduction = deduction_result.scalar() or 0

    # 有否决的录音（通过ScoringResult表关联）
    rejection_result = await db.execute(
        select(func.count(Recording.id))
        .join(ScoringResult, ScoringResult.recording_id == Recording.id)
        .where(and_(*base_conditions), ScoringResult.is_rejected == True)
    )
    recordings_with_rejection = rejection_result.scalar() or 0

    # 总加分
    total_bonus_result = await db.execute(
        select(func.coalesce(func.sum(Recording.bonus_score), 0))
        .where(and_(*base_conditions))
    )
    total_bonus = total_bonus_result.scalar() or 0

    # 总扣分
    total_deduction_result = await db.execute(
        select(func.coalesce(func.sum(Recording.deduction_score), 0))
        .where(and_(*base_conditions))
    )
    total_deduction = total_deduction_result.scalar() or 0

    # 平均加分（只统计有加分的录音）
    avg_bonus_result = await db.execute(
        select(func.avg(Recording.bonus_score))
        .where(and_(*bonus_conditions))
    )
    avg_bonus = avg_bonus_result.scalar() or 0

    # 平均扣分（只统计有扣分的录音）
    avg_deduction_result = await db.execute(
        select(func.avg(Recording.deduction_score))
        .where(and_(*deduction_conditions))
    )
    avg_deduction = avg_deduction_result.scalar() or 0

    # 最高加分
    max_bonus_result = await db.execute(
        select(func.max(Recording.bonus_score))
        .where(and_(*bonus_conditions))
    )
    max_bonus = max_bonus_result.scalar() or 0

    # 最高扣分
    max_deduction_result = await db.execute(
        select(func.max(Recording.deduction_score))
        .where(and_(*deduction_conditions))
    )
    max_deduction = max_deduction_result.scalar() or 0

    # 平均总分
    avg_total_result = await db.execute(
        select(func.avg(Recording.total_score))
        .where(and_(*base_conditions))
    )
    avg_total = avg_total_result.scalar() or 0

    return {
        "total_recordings": total_recordings,
        "scored_count": scored_count,
        "recordings_with_rejection": recordings_with_rejection,
        "recordings_with_bonus": recordings_with_bonus,
        "recordings_with_deduction": recordings_with_deduction,
        "total_bonus": round(total_bonus, 1),
        "total_deduction": round(total_deduction, 1),
        "avg_bonus": round(avg_bonus, 1) if avg_bonus else 0,
        "avg_deduction": round(avg_deduction, 1) if avg_deduction else 0,
        "max_bonus": round(max_bonus, 1) if max_bonus else 0,
        "max_deduction": round(max_deduction, 1) if max_deduction else 0,
        "avg_total_score": round(avg_total, 1) if avg_total else 0,
    }


@router.get("/trend")
async def get_trend(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取每日趋势数据（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days - 1)

    # 获取每日统计数据
    daily_stats = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)

        conditions = [
            Recording.status == RecordingStatus.SCORED,
            Recording.total_score.isnot(None),
            Recording.created_at >= day_start,
            Recording.created_at < day_end,
            Recording.user_id == user_id
        ]

        # 当日录音数
        count_result = await db.execute(
            select(func.count()).where(and_(*conditions))
        )
        count = count_result.scalar() or 0

        # 当日平均分
        avg_result = await db.execute(
            select(func.avg(Recording.total_score)).where(and_(*conditions))
        )
        avg_score = avg_result.scalar() or 0

        # 当日平均加分
        bonus_cond = conditions + [Recording.bonus_score.isnot(None), Recording.bonus_score > 0]
        bonus_result = await db.execute(
            select(func.avg(Recording.bonus_score)).where(and_(*bonus_cond))
        )
        avg_bonus = bonus_result.scalar() or 0

        # 当日平均扣分
        deduct_cond = conditions + [Recording.deduction_score.isnot(None), Recording.deduction_score > 0]
        deduct_result = await db.execute(
            select(func.avg(Recording.deduction_score)).where(and_(*deduct_cond))
        )
        avg_deduction = deduct_result.scalar() or 0

        # 违规率（有扣分的占比）
        deduct_count_result = await db.execute(
            select(func.count()).where(and_(*deduct_cond))
        )
        deduct_count = deduct_count_result.scalar() or 0
        violation_rate = round((deduct_count / count * 100), 1) if count > 0 else 0

        # 否决率（有否决项命中的占比）
        rejection_count_result = await db.execute(
            select(func.count(Recording.id))
            .join(ScoringResult, ScoringResult.recording_id == Recording.id)
            .where(and_(*conditions), ScoringResult.is_rejected == True)
        )
        rejection_count = rejection_count_result.scalar() or 0
        rejection_rate = round((rejection_count / count * 100), 1) if count > 0 else 0

        daily_stats.append({
            "date": day.strftime("%Y-%m-%d"),
            "count": count,
            "avg_score": round(avg_score, 1) if avg_score else 0,
            "avg_bonus": round(avg_bonus, 1) if avg_bonus else 0,
            "avg_deduction": round(avg_deduction, 1) if avg_deduction else 0,
            "violation_rate": violation_rate,
            "rejection_rate": rejection_rate
        })

    return daily_stats


@router.get("/agent-stats")
async def get_agent_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取坐席统计数据（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    conditions = [
        Recording.status == RecordingStatus.SCORED,
        Recording.total_score.isnot(None),
        Recording.agent_name.isnot(None),
        Recording.user_id == user_id
    ]

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            conditions.append(Recording.created_at >= start_dt)
        except:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
            conditions.append(Recording.created_at <= end_dt)
        except:
            pass

    # 按坐席分组统计
    query = select(
        Recording.agent_name,
        func.count().label("count"),
        func.avg(Recording.total_score).label("avg_score"),
        func.avg(Recording.bonus_score).label("avg_bonus"),
        func.avg(Recording.deduction_score).label("avg_deduction")
    ).where(and_(*conditions)).group_by(
        Recording.agent_name
    ).order_by(func.count().desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "agent_name": r.agent_name or "未知",
            "count": r.count,
            "avg_score": round(r.avg_score, 1) if r.avg_score else 0,
            "avg_bonus": round(r.avg_bonus, 1) if r.avg_bonus else 0,
            "avg_deduction": round(r.avg_deduction, 1) if r.avg_deduction else 0
        }
        for r in rows
    ]


@router.get("/rule-stats")
async def get_rule_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取规则使用统计（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    # 先获取当前用户的规则信息（id -> rule 映射）
    rules_result = await db.execute(
        select(ScoringRule.id, ScoringRule.name, ScoringRule.code).where(ScoringRule.user_id == user_id)
    )
    rules_map = {}
    for row in rules_result.fetchall():
        rules_map[row[0]] = {"name": row[1], "code": row[2]}
    user_rule_ids = list(rules_map.keys())

    # 构建基础查询条件
    conditions = [
        ScoringResult.recording_id.isnot(None),
    ]

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            conditions.append(ScoringResult.created_at >= start_dt)
        except:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
            conditions.append(ScoringResult.created_at <= end_dt)
        except:
            pass

    # 查询所有评分结果
    query = select(ScoringResult).where(and_(*conditions))
    result = await db.execute(query)
    all_results = result.scalars().all()

    # 统计每个规则的命中情况
    rule_stats = {}
    for scoring in all_results:
        # rule_ids 是 JSON 数组格式
        scoring_rule_ids = scoring.rule_ids if scoring.rule_ids else []
        if not isinstance(scoring_rule_ids, list):
            scoring_rule_ids = [scoring_rule_ids] if scoring_rule_ids else []
        for rule_id in scoring_rule_ids:
            if rule_id not in user_rule_ids:
                continue
            if rule_id not in rule_stats:
                rule_stats[rule_id] = {
                    "rule_id": rule_id,
                    "rule_name": rules_map[rule_id]["name"],
                    "rule_code": rules_map[rule_id]["code"],
                    "hit_count": 0,
                    "total_bonus": 0.0,
                    "total_deduction": 0.0,
                }
            rule_stats[rule_id]["hit_count"] += 1
            rule_stats[rule_id]["total_bonus"] += scoring.bonus_score or 0
            rule_stats[rule_id]["total_deduction"] += scoring.deduction_score or 0

    # 转换为列表并按命中次数排序
    stats_list = list(rule_stats.values())
    stats_list.sort(key=lambda x: x["hit_count"], reverse=True)

    # 格式化输出
    return [
        {
            "rule_id": s["rule_id"],
            "rule_name": s["rule_name"],
            "rule_code": s["rule_code"],
            "hit_count": s["hit_count"],
            "total_bonus": round(s["total_bonus"], 1),
            "total_deduction": round(s["total_deduction"], 1)
        }
        for s in stats_list
    ]
