"""
规则管理路由 - 含规则历史
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List

from backend.core.database import get_db
from backend.core.datetime_utils import get_current_time
from backend.models.rule import ScoringRule
from backend.schemas.rule import ScoringRuleCreate, ScoringRuleUpdate, ScoringRuleResponse, RuleRefineRequest, RuleRefineResponse
from backend.api.auth import get_current_user_required

router = APIRouter(prefix="/rules", tags=["规则管理"])


def generate_version():
    """生成版本号：v_年月日时分秒"""
    now = get_current_time()
    return f"v_{now.strftime('%y%m%d%H%M%S')}"


@router.get("/generate-code/{rule_type}")
async def generate_code(
    rule_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """生成新的规则代码（自增，按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    # 查找该类型规则中最大的code编号（只查当前用户的）
    result = await db.execute(
        select(ScoringRule.code).where(
            ScoringRule.rule_type == rule_type,
            ScoringRule.user_id == user_id
        )
    )
    codes = result.scalars().all()

    max_num = 0
    for code in codes:
        # code格式: bonus_001, deduction_001
        if '_' in code:
            try:
                num = int(code.split('_')[-1])
                if num > max_num:
                    max_num = num
            except:
                pass

    new_num = max_num + 1
    return f"{rule_type}_{new_num:03d}"


@router.post("", response_model=ScoringRuleResponse)
async def create_rule(
    rule_data: ScoringRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """创建评分规则"""
    user_id = current_user.get("loginid", "admin")
    rule = ScoringRule(
        name=rule_data.name,
        code=rule_data.code,
        version=rule_data.version if rule_data.version else generate_version(),
        description=rule_data.description,
        total_score=rule_data.total_score,
        rule_type=rule_data.rule_type,
        is_veto=rule_data.is_veto if rule_data.rule_type == 'deduction' else False,
        is_latest=True,
        is_enabled=rule_data.is_enabled if hasattr(rule_data, 'is_enabled') else True,
        published_at=get_current_time(),
        user_id=user_id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return rule


@router.get("", response_model=List[ScoringRuleResponse])
async def list_rules(
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取规则列表（仅最新版本，按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    query = select(ScoringRule).where(
        ScoringRule.is_latest == True,
        ScoringRule.user_id == user_id
    )

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (ScoringRule.name.ilike(search_pattern)) |
            (ScoringRule.code.ilike(search_pattern))
        )

    query = query.order_by(ScoringRule.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/ruleexport")
async def export_rules_json(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """导出所有规则为JSON文件（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")

    result = await db.execute(
        select(ScoringRule)
        .where(
            ScoringRule.is_latest == True,
            ScoringRule.user_id == user_id
        )
        .order_by(ScoringRule.rule_type, ScoringRule.code)
    )
    rules = result.scalars().all()

    data = []
    for rule in rules:
        data.append({
            "规则名称": rule.name,
            "规则类型": "加分" if rule.rule_type == "bonus" else "扣分",
            "分值": rule.total_score,
            "否决项": "是" if rule.is_veto else "否",
            "描述": rule.description or "",
        })

    return {
        "rules": data,
        "total": len(data),
        "export_time": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
    }


@router.post("/ruleimport")
async def import_rules(
    rules_data: List[dict],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """导入规则（按用户隔离）"""
    user_id = current_user.get("loginid", "admin")
    imported = []
    errors = []
    batch_counter = {}  # 同批次导入计数器，避免生成相同编号

    for idx, item in enumerate(rules_data):
        try:
            # 自动识别规则类型
            rule_type_map = {"加分": "bonus", "扣分": "deduction"}
            rule_type = rule_type_map.get(item.get("规则类型", ""))
            if not rule_type:
                errors.append(f"第{idx + 1}条：规则类型无效，必须为'加分'或'扣分'")
                continue

            # 自动生成规则代码（动态累加，避免同批次导入生成相同编号）
            code_result = await db.execute(
                select(ScoringRule.code).where(
                    ScoringRule.rule_type == rule_type,
                    ScoringRule.user_id == user_id
                )
            )
            codes = code_result.scalars().all()
            max_num = 0
            for code in codes:
                if '_' in code:
                    try:
                        num = int(code.split('_')[-1])
                        if num > max_num:
                            max_num = num
                    except:
                        pass
            # 本批次同类型规则累加计数
            batch_counter[rule_type] = batch_counter.get(rule_type, 0) + 1
            new_code = f"{rule_type}_{max_num + batch_counter[rule_type]:03d}"

            # 自动生成版本号
            version = generate_version()

            # 解析否决项
            is_veto = item.get("否决项") in ["是", True, "true", "True", 1]

            rule = ScoringRule(
                name=item.get("规则名称", ""),
                code=new_code,
                version=version,
                description=item.get("描述", ""),
                total_score=float(item.get("分值", 0)),
                rule_type=rule_type,
                is_veto=is_veto if rule_type == "deduction" else False,
                is_latest=True,
                published_at=get_current_time(),
                user_id=user_id,
            )
            db.add(rule)
            imported.append(new_code)
        except Exception as e:
            errors.append(f"第{idx + 1}条：{str(e)}")

    await db.commit()

    return {
        "imported": len(imported),
        "codes": imported,
        "errors": errors,
        "total": len(rules_data)
    }


@router.get("/{rule_id}", response_model=ScoringRuleResponse)
async def get_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取规则详情"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(ScoringRule).where(
            ScoringRule.id == rule_id,
            ScoringRule.user_id == user_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.put("/{rule_id}", response_model=ScoringRuleResponse)
async def update_rule(
    rule_id: int,
    rule_data: ScoringRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """更新规则（创建新版本）"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(ScoringRule).where(
            ScoringRule.id == rule_id,
            ScoringRule.user_id == user_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    update_data = rule_data.model_dump(exclude_unset=True)

    # 如果没有更新内容，直接返回
    if not update_data:
        return rule

    # 将当前版本标记为非最新
    rule.is_latest = False
    await db.flush()

    # 创建新版本
    new_rule = ScoringRule(
        name=update_data.get('name', rule.name),
        code=rule.code,
        version=generate_version(),
        description=update_data.get('description', rule.description),
        total_score=update_data.get('total_score', rule.total_score),
        rule_type=rule.rule_type,
        is_veto=update_data.get('is_veto', rule.is_veto) if rule.rule_type == 'deduction' else False,
        is_latest=True,
        is_enabled=rule.is_enabled,  # 继承启用状态
        parent_id=rule.id,
        published_at=get_current_time(),
        user_id=user_id,
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)

    return new_rule


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """删除规则"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(ScoringRule).where(
            ScoringRule.id == rule_id,
            ScoringRule.user_id == user_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    await db.delete(rule)
    await db.commit()

    return {"message": "删除成功"}


@router.patch("/{rule_id}/toggle-enabled")
async def toggle_rule_enabled(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """切换规则启用状态（仅限最新版本）"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(ScoringRule).where(
            ScoringRule.id == rule_id,
            ScoringRule.user_id == user_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    if not rule.is_latest:
        raise HTTPException(status_code=400, detail="只能操作最新版本")

    rule.is_enabled = not rule.is_enabled
    await db.commit()
    await db.refresh(rule)

    return {"message": "操作成功", "is_enabled": rule.is_enabled}


# ========== 规则历史管理 ==========
history_router = APIRouter(prefix="/rules", tags=["规则历史"])


@history_router.get("/{rule_id}/history")
async def get_rule_history(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """获取规则历史版本"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(ScoringRule).where(
            ScoringRule.id == rule_id,
            ScoringRule.user_id == user_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    # 查找同代码的所有版本
    history_result = await db.execute(
        select(ScoringRule)
        .where(ScoringRule.code == rule.code, ScoringRule.user_id == user_id)
        .order_by(ScoringRule.created_at.desc())
    )
    history = history_result.scalars().all()

    return history


@history_router.get("/version/{version_id}")
async def get_rule_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """查看规则历史版本详情"""
    user_id = current_user.get("loginid", "admin")
    result = await db.execute(
        select(ScoringRule).where(
            ScoringRule.id == version_id,
            ScoringRule.user_id == user_id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则版本不存在")
    return rule


@history_router.post("/{rule_id}/rollback/{version_id}")
async def rollback_rule(
    rule_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """回溯规则到指定历史版本"""
    user_id = current_user.get("loginid", "admin")
    # 获取当前规则
    result = await db.execute(select(ScoringRule).where(
        ScoringRule.id == rule_id,
        ScoringRule.user_id == user_id
    ))
    current_rule = result.scalar_one_or_none()
    if not current_rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    # 获取要回溯的版本
    result = await db.execute(select(ScoringRule).where(
        ScoringRule.id == version_id,
        ScoringRule.user_id == user_id
    ))
    old_version = result.scalar_one_or_none()
    if not old_version:
        raise HTTPException(status_code=404, detail="历史版本不存在")

    if old_version.code != current_rule.code:
        raise HTTPException(status_code=400, detail="只能回溯同一规则的不同版本")

    # 将当前版本标记为非最新
    await db.execute(
        update(ScoringRule).where(
            ScoringRule.code == current_rule.code,
            ScoringRule.is_latest == True,
            ScoringRule.user_id == user_id,
        ).values(is_latest=False)
    )

    # 创建新版本（复制旧版本内容，自动生成版本号）
    new_rule = ScoringRule(
        name=old_version.name,
        code=current_rule.code,
        version=generate_version(),
        description=old_version.description,
        total_score=old_version.total_score,
        rule_type=old_version.rule_type,
        is_veto=old_version.is_veto if old_version.rule_type == 'deduction' else False,
        is_latest=True,
        parent_id=current_rule.id,
        published_at=get_current_time(),
        user_id=user_id,
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)

    return {"message": "回溯成功", "new_rule_id": new_rule.id, "new_version": new_rule.version}


@history_router.delete("/{rule_id}/history/{version_id}")
async def delete_rule_version(
    rule_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_required)
):
    """删除规则历史版本"""
    user_id = current_user.get("loginid", "admin")
    # 获取当前规则
    result = await db.execute(select(ScoringRule).where(
        ScoringRule.id == rule_id,
        ScoringRule.user_id == user_id
    ))
    current_rule = result.scalar_one_or_none()
    if not current_rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    # 获取要删除的版本
    result = await db.execute(select(ScoringRule).where(
        ScoringRule.id == version_id,
        ScoringRule.user_id == user_id
    ))
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="历史版本不存在")

    if version.code != current_rule.code:
        raise HTTPException(status_code=400, detail="只能删除同一规则的历史版本")

    if version.is_latest:
        raise HTTPException(status_code=400, detail="不能删除最新版本，请先回溯到其他版本")

    await db.delete(version)
    await db.commit()

    return {"message": "历史版本删除成功"}


@router.post("/refine-description", response_model=RuleRefineResponse)
async def refine_rule_description(
    request: RuleRefineRequest,
    current_user: dict = Depends(get_current_user_required)
):
    """使用AI细化规则描述，使其更加清晰、具体、结构化"""
    import httpx
    from backend.services.config_service import config_service

    llm_config = await config_service.get_llm_config()
    prompt_template = await config_service.get_prompt("prompt_rule_refine")

    if not llm_config["api_endpoint"]:
        raise HTTPException(status_code=500, detail="LLM API未配置")

    prompt = prompt_template.format(original_description=request.description)

    headers = {"Content-Type": "application/json"}
    if llm_config["api_key"]:
        headers["Authorization"] = f"Bearer {llm_config['api_key']}"

    payload = {
        "model": llm_config["model"],
        "messages": [
            {"role": "system", "content": "你是一个专业的金融催收录音质检专家，负责将粗略的质检规则细化为清晰、具体的评分标准。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": llm_config["temperature"],
        "max_tokens": 2000,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(llm_config["api_endpoint"], headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("choices") is None or len(result.get("choices", [])) == 0:
                error_msg = result.get("base_resp", {}).get("status_msg", "unknown error")
                raise HTTPException(status_code=500, detail=f"AI细化失败: {error_msg}")

            message = result["choices"][0].get("message", {})
            content = message.get("content", "") or message.get("reasoning_content", "")
            if not content:
                raise HTTPException(status_code=500, detail="AI返回内容为空")

            return RuleRefineResponse(refined_description=content.strip())

    except httpx.TimeoutException:
        raise HTTPException(status_code=500, detail="AI细化请求超时")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"AI细化失败: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI细化失败: {str(e)}")