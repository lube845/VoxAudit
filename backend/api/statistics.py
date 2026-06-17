"""
统计路由
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, cast, Date, Integer
from typing import Optional

from backend.core.database import get_db
from backend.core.datetime_utils import get_current_time, get_timezone
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

    # 构建时间筛选条件
    time_conditions = []
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            time_conditions.append(Recording.created_at >= start_dt)
        except:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S') + timedelta(days=1)
            time_conditions.append(Recording.created_at < end_dt)
        except:
            pass

    # 总录音数（所有上传的录音，不限状态）
    total_conditions = [Recording.user_id == user_id] + time_conditions
    total_result = await db.execute(
        select(func.count()).where(and_(*total_conditions))
    )
    total_recordings = total_result.scalar() or 0

    # 已评分数（只统计已评分的录音）
    base_conditions = [
        Recording.status == RecordingStatus.SCORED,
        Recording.total_score.isnot(None),
        Recording.user_id == user_id
    ] + time_conditions

    scored_count_result = await db.execute(
        select(func.count()).where(and_(*base_conditions))
    )
    scored_count = scored_count_result.scalar() or 0

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
    now = get_current_time()
    end_date = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start_date = end_date - timedelta(days=days)

    # 每日分组查询（包含违规计数）
    daily_query = select(
        cast(Recording.created_at, Date).label("stat_date"),
        func.count().label("count"),
        func.avg(Recording.total_score).label("avg_score"),
        func.avg(func.coalesce(Recording.bonus_score, 0)).label("avg_bonus"),
        func.avg(func.coalesce(Recording.deduction_score, 0)).label("avg_deduction"),
        func.sum(
            func.cast(Recording.deduction_score > 0, Integer)
        ).label("violation_count"),
    ).where(
        and_(
            Recording.status == RecordingStatus.SCORED,
            Recording.total_score.isnot(None),
            Recording.created_at >= start_date,
            Recording.created_at < end_date,
            Recording.user_id == user_id
        )
    ).group_by(cast(Recording.created_at, Date)).order_by(cast(Recording.created_at, Date))

    daily_result = await db.execute(daily_query)
    daily_rows = daily_result.all()

    # 否决数据按日查询
    rejection_query = select(
        cast(Recording.created_at, Date).label("stat_date"),
        func.count(func.distinct(Recording.id)).label("rejection_count"),
    ).join(
        ScoringResult, ScoringResult.recording_id == Recording.id
    ).where(
        and_(
            Recording.status == RecordingStatus.SCORED,
            Recording.total_score.isnot(None),
            Recording.created_at >= start_date,
            Recording.created_at < end_date,
            Recording.user_id == user_id,
            ScoringResult.is_rejected == True
        )
    ).group_by(cast(Recording.created_at, Date))

    rejection_result = await db.execute(rejection_query)
    rejection_rows = rejection_result.all()
    rejection_map = {r.stat_date: r.rejection_count for r in rejection_rows}

    date_count_map = {r.stat_date: r.count for r in daily_rows}
    date_violation_map = {r.stat_date: r.violation_count or 0 for r in daily_rows}

    result = []
    current_date = start_date.date()
    while current_date < end_date.date():
        count = date_count_map.get(current_date, 0)
        violation_count = date_violation_map.get(current_date, 0)
        rejection_count = rejection_map.get(current_date, 0)
        violation_rate = round((violation_count / count * 100), 1) if count > 0 else 0
        rejection_rate = round((rejection_count / count * 100), 1) if count > 0 else 0

        row = next((r for r in daily_rows if r.stat_date == current_date), None)
        result.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "count": count,
            "avg_score": round(row.avg_score, 1) if row and row.avg_score else 0,
            "avg_bonus": round(row.avg_bonus, 1) if row and row.avg_bonus else 0,
            "avg_deduction": round(row.avg_deduction, 1) if row and row.avg_deduction else 0,
            "violation_rate": violation_rate,
            "rejection_rate": rejection_rate,
        })
        current_date += timedelta(days=1)

    return result


@router.get("/agent-stats")
async def get_agent_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="count", pattern="^(count|avg_score|violation_rate|rejection_rate|total_score)$"),
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
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S') + timedelta(days=1)
            conditions.append(Recording.created_at < end_dt)
        except:
            pass

    # 构建基础时间条件（用户隔离 + 时间范围）
    base_time_conditions = []
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            base_time_conditions.append(Recording.created_at >= start_dt)
        except:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S') + timedelta(days=1)
            base_time_conditions.append(Recording.created_at < end_dt)
        except:
            pass

    # 1. 获取所有有录音的坐席及其总录音数（不受评分状态限制）
    base_conditions = [
        Recording.agent_name.isnot(None),
        Recording.user_id == user_id
    ] + base_time_conditions

    total_query = select(
        Recording.agent_name,
        func.count().label("total_count")
    ).where(and_(*base_conditions)).group_by(Recording.agent_name)
    total_result = await db.execute(total_query)
    agent_total_map = {r.agent_name: r.total_count for r in total_result.fetchall()}

    # 2. 在已评分的录音上统计各项指标
    scored_conditions = [
        Recording.status == RecordingStatus.SCORED,
        Recording.total_score.isnot(None),
        Recording.agent_name.isnot(None),
        Recording.user_id == user_id
    ] + base_time_conditions

    scored_query = select(
        Recording.agent_name,
        func.count().label("count"),
        func.avg(Recording.total_score).label("avg_score"),
        func.avg(Recording.bonus_score).label("avg_bonus"),
        func.avg(Recording.deduction_score).label("avg_deduction"),
        func.sum(
            func.cast(Recording.deduction_score > 0, Integer)
        ).label("violation_count"),
    ).where(and_(*scored_conditions)).group_by(Recording.agent_name)

    scored_result = await db.execute(scored_query)
    scored_rows = scored_result.all()
    scored_map = {r.agent_name: r for r in scored_rows}

    # 3. 按坐席统计未评分数
    unscored_query = select(
        Recording.agent_name,
        func.count().label("unscored_count")
    ).where(and_(*base_conditions),
        or_(
            Recording.status != RecordingStatus.SCORED,
            Recording.total_score.is_(None)
        )
    ).group_by(Recording.agent_name)
    unscored_result = await db.execute(unscored_query)
    unscored_count_map = {r.agent_name: r.unscored_count for r in unscored_result.fetchall()}

    # 4. 按坐席统计否决数
    rejection_query = select(
        Recording.agent_name,
        func.count(func.distinct(ScoringResult.recording_id)).label("rejection_count")
    ).join(
        ScoringResult, ScoringResult.recording_id == Recording.id
    ).where(
        and_(*scored_conditions), ScoringResult.is_rejected == True
    ).group_by(Recording.agent_name)
    rejection_result = await db.execute(rejection_query)
    rejection_map = {r.agent_name: r.rejection_count for r in rejection_result.fetchall()}

    # 5. 构建完整坐席数据（所有坐席，没有评分的指标为0）
    all_agent_data = []
    for agent_name in agent_total_map:
        scored = scored_map.get(agent_name)
        total_count = agent_total_map[agent_name]
        unscored_count = unscored_count_map.get(agent_name, 0)
        rejection_count = rejection_map.get(agent_name, 0)

        if scored:
            count = scored.count
            avg_score = scored.avg_score
            avg_bonus = scored.avg_bonus
            avg_deduction = scored.avg_deduction
            violation_count = scored.violation_count or 0
        else:
            count = 0
            avg_score = None
            avg_bonus = None
            avg_deduction = None
            violation_count = 0

        all_agent_data.append({
            "agent_name": agent_name or "未知",
            "total_count": total_count,
            "count": count,
            "unscored_count": unscored_count,
            "avg_score": round(avg_score, 1) if avg_score else 0,
            "avg_bonus": round(avg_bonus, 1) if avg_bonus else 0,
            "avg_deduction": round(avg_deduction, 1) if avg_deduction else 0,
            "violation_count": violation_count,
            "violation_rate": round(violation_count / count * 100, 1) if count > 0 else 0,
            "rejection_count": rejection_count,
            "rejection_rate": round(rejection_count / count * 100, 1) if count > 0 else 0,
        })

    # 6. 按指定维度排序
    sort_map = {
        "count": lambda r: r["total_count"],  # 按总录音数排序
        "avg_score": lambda r: r["avg_score"] or 0,
        "violation_rate": lambda r: r["violation_rate"] or 0,
        "rejection_rate": lambda r: r["rejection_rate"] or 0,
        "total_score": lambda r: (r["avg_score"] or 0) * r["count"],
    }
    sorted_data = sorted(all_agent_data, key=sort_map[sort_by], reverse=True)[:limit]

    return sorted_data


@router.get("/rule-stats")
async def get_rule_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rule_type: str = Query(default="bonus", pattern="^(bonus|deduction)$"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取规则使用统计（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    # 先获取当前用户指定类型的规则信息（id -> rule 映射）
    rules_result = await db.execute(
        select(ScoringRule.id, ScoringRule.name, ScoringRule.code).where(
            and_(ScoringRule.user_id == user_id, ScoringRule.rule_type == rule_type)
        )
    )
    rules_map = {}
    for row in rules_result.fetchall():
        rules_map[row[0]] = {"name": row[1], "code": row[2], "rule_type": row[3]}
    user_rule_ids = list(rules_map.keys())

    # 构建基础查询条件（通过Recording表进行用户隔离）
    conditions = [
        ScoringResult.recording_id.isnot(None),
        Recording.user_id == user_id,
    ]

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            conditions.append(Recording.created_at >= start_dt)
        except:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S') + timedelta(days=1)
            conditions.append(Recording.created_at < end_dt)
        except:
            pass

    # 查询所有评分结果（join Recording进行用户隔离）
    query = select(ScoringResult).join(Recording, Recording.id == ScoringResult.recording_id).where(and_(*conditions))
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
                }
            rule_stats[rule_id]["hit_count"] += 1

    # 按命中次数排序，取 top10
    stats_list = sorted(rule_stats.values(), key=lambda x: x["hit_count"], reverse=True)[:10]

    return [
        {
            "rule_id": s["rule_id"],
            "rule_name": s["rule_name"],
            "rule_code": s["rule_code"],
            "hit_count": s["hit_count"],
        }
        for s in stats_list
    ]


@router.get("/rule-hit-stats")
async def get_rule_hit_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    item_type: str = Query(default="bonus", pattern="^(bonus|deduction)$"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取规则命中统计（按item_name分组，取top10）"""
    user_id = current_user.get("loginid", "admin")

    # 构建时间筛选条件（通过Recording表进行用户隔离）
    conditions = [
        ScoringResult.recording_id.isnot(None),
        Recording.user_id == user_id,
    ]

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            conditions.append(Recording.created_at >= start_dt)
        except:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S') + timedelta(days=1)
            conditions.append(Recording.created_at < end_dt)
        except:
            pass

    # 查询所有评分结果（join Recording进行用户隔离）
    query = select(ScoringResult).join(Recording, Recording.id == ScoringResult.recording_id).where(and_(*conditions))
    result = await db.execute(query)
    all_results = result.scalars().all()

    # 统计每个item_name的命中次数（只统计status=matched且item_type匹配的项目）
    item_stats = {}
    for scoring in all_results:
        details = scoring.scoring_details if scoring.scoring_details else []
        if not isinstance(details, list):
            details = [details] if details else []
        for item in details:
            if item.get("status") != "matched":
                continue
            if item.get("item_type") != item_type:
                continue
            item_name = item.get("item_name") or "未知"
            if item_name not in item_stats:
                item_stats[item_name] = {
                    "item_name": item_name,
                    "hit_count": 0,
                }
            item_stats[item_name]["hit_count"] += 1

    # 按命中次数排序，取 top10
    stats_list = sorted(item_stats.values(), key=lambda x: x["hit_count"], reverse=True)[:10]

    return [
        {
            "item_name": s["item_name"],
            "hit_count": s["hit_count"],
        }
        for s in stats_list
    ]
