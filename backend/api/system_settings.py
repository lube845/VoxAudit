"""
系统设置API - 仅超级管理员可用
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select
import httpx
from backend.core.database import AsyncSessionLocal
from backend.core.config import settings
from backend.models.system_settings import SystemSettings
from backend.api.auth import get_current_user_required
from backend.services.config_service import DEFAULT_PROMPTS

router = APIRouter(prefix="/system-settings", tags=["系统设置"])


def require_admin(current_user: dict = Depends(get_current_user_required)) -> dict:
    """检查是否为超级管理员"""
    if current_user.get("loginid") != settings.ADMIN_USER:
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")
    return current_user


class LLMConfig(BaseModel):
    """大模型配置"""
    api_key: Optional[str] = None
    model: Optional[str] = None
    api_endpoint: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    json_retry_count: Optional[int] = None
    enable_thinking: Optional[bool] = None


class ASRConfig(BaseModel):
    """ASR配置"""
    api_url: Optional[str] = None
    api_key: Optional[str] = None


class SystemConfig(BaseModel):
    """系统配置"""
    llm: LLMConfig
    asr: ASRConfig


class TestResult(BaseModel):
    """测试结果"""
    success: bool
    message: str


class PromptItem(BaseModel):
    """单个Prompt配置"""
    system: Optional[str] = Field(default=None)
    user: Optional[str] = Field(default=None)


class PromptConfig(BaseModel):
    """Prompt配置"""
    speaker_detection: Optional[PromptItem] = None
    rule_refine: Optional[PromptItem] = None
    bonus_judgment: Optional[PromptItem] = None
    deduction_judgment: Optional[PromptItem] = None


async def get_setting(session: AsyncSessionLocal, key: str) -> Optional[str]:
    """获取单个配置"""
    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_setting(session: AsyncSessionLocal, key: str, value: str, description: str = "", is_secret: bool = False):
    """设置单个配置"""
    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
        setting.description = description
        setting.is_secret = is_secret
    else:
        setting = SystemSettings(key=key, value=value, description=description, is_secret=is_secret)
        session.add(setting)
    await session.flush()
    return setting


@router.get("/config", response_model=SystemConfig)
async def get_system_config(current_user: dict = Depends(require_admin)):
    """
    获取系统配置（LLM和ASR）
    注意：敏感信息（api_key）不会返回实际值
    """
    async with AsyncSessionLocal() as session:
        llm_api_key = await get_setting(session, "LLM_API_KEY")
        llm_model = await get_setting(session, "LLM_MODEL")
        llm_api_endpoint = await get_setting(session, "LLM_API_ENDPOINT")
        llm_temperature = await get_setting(session, "LLM_TEMPERATURE")
        llm_max_tokens = await get_setting(session, "LLM_MAX_TOKENS")
        llm_json_retry_count = await get_setting(session, "LLM_JSON_RETRY_COUNT")
        llm_enable_thinking = await get_setting(session, "LLM_ENABLE_THINKING")

        asr_api_url = await get_setting(session, "ASR_API_URL")
        asr_api_key = await get_setting(session, "ASR_API_KEY")

        return SystemConfig(
            llm=LLMConfig(
                api_key="***已设置***" if llm_api_key else None,
                model=llm_model or settings.LLM_MODEL,
                api_endpoint=llm_api_endpoint or settings.LLM_API_ENDPOINT,
                temperature=float(llm_temperature) if llm_temperature else settings.LLM_TEMPERATURE,
                max_tokens=int(llm_max_tokens) if llm_max_tokens else settings.LLM_MAX_TOKENS,
                json_retry_count=int(llm_json_retry_count) if llm_json_retry_count else settings.LLM_JSON_RETRY_COUNT,
                enable_thinking=llm_enable_thinking.lower() == "true" if llm_enable_thinking else False,
            ),
            asr=ASRConfig(
                api_url=asr_api_url or settings.ASR_API_URL,
                api_key="***已设置***" if asr_api_key else None,
            )
        )


@router.put("/config/llm")
async def update_llm_config(
    config: LLMConfig,
    current_user: dict = Depends(require_admin)
):
    """
    更新LLM配置
    """
    async with AsyncSessionLocal() as session:
        if config.api_key is not None:
            await set_setting(session, "LLM_API_KEY", config.api_key, "大模型API密钥", is_secret=True)
        if config.model is not None:
            await set_setting(session, "LLM_MODEL", config.model, "大模型名称")
        if config.api_endpoint is not None:
            await set_setting(session, "LLM_API_ENDPOINT", config.api_endpoint, "大模型API地址")
        if config.temperature is not None:
            await set_setting(session, "LLM_TEMPERATURE", str(config.temperature), "大模型温度参数")
        if config.max_tokens is not None:
            await set_setting(session, "LLM_MAX_TOKENS", str(config.max_tokens), "大模型最大Token数")
        if config.json_retry_count is not None:
            await set_setting(session, "LLM_JSON_RETRY_COUNT", str(config.json_retry_count), "LLM JSON解析失败重试次数")
        if config.enable_thinking is not None:
            await set_setting(session, "LLM_ENABLE_THINKING", str(config.enable_thinking).lower(), "大模型深度思考开关")

        await session.commit()
        return {"message": "LLM配置更新成功"}


@router.put("/config/asr")
async def update_asr_config(
    config: ASRConfig,
    current_user: dict = Depends(require_admin)
):
    """
    更新ASR配置
    """
    async with AsyncSessionLocal() as session:
        if config.api_url is not None:
            await set_setting(session, "ASR_API_URL", config.api_url, "ASR API地址")
        if config.api_key is not None:
            await set_setting(session, "ASR_API_KEY", config.api_key, "ASR API密钥", is_secret=True)

        await session.commit()
        return {"message": "ASR配置更新成功"}


@router.post("/config/llm/test", response_model=TestResult)
async def test_llm_config(
    config: LLMConfig,
    current_user: dict = Depends(require_admin)
):
    """
    测试LLM配置连通性
    """
    api_key = config.api_key if config.api_key else settings.LLM_API_KEY
    model = config.model if config.model else settings.LLM_MODEL
    api_endpoint = config.api_endpoint if config.api_endpoint else settings.LLM_API_ENDPOINT

    if not api_endpoint:
        return TestResult(success=False, message="API地址未配置")

    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "你好，请回复OK"},
            ],
            "temperature": 0.1,
            "max_tokens": 10,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(api_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("choices") and len(result.get("choices", [])) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                if content:
                    return TestResult(success=True, message="连接成功")
            return TestResult(success=False, message="响应格式异常")

    except httpx.TimeoutException:
        return TestResult(success=False, message="连接超时")
    except httpx.HTTPStatusError as e:
        return TestResult(success=False, message=f"HTTP错误: {e.response.status_code}")
    except Exception as e:
        return TestResult(success=False, message=f"连接失败: {str(e)}")


@router.post("/config/asr/test", response_model=TestResult)
async def test_asr_config(
    config: ASRConfig,
    current_user: dict = Depends(require_admin)
):
    """
    测试ASR配置连通性
    """
    api_url = config.api_url if config.api_url else settings.ASR_API_URL

    if not api_url:
        return TestResult(success=False, message="API地址未配置")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{api_url}/health")
            response.raise_for_status()
            return TestResult(success=True, message="连接成功")
    except Exception as e:
        # ASR服务可能没有health接口，尝试其他方式检测
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(api_url)
                return TestResult(success=True, message="连接成功")
        except Exception:
            return TestResult(success=False, message=f"连接失败: {str(e)}")


@router.get("/config/llm")
async def get_llm_config(current_user: dict = Depends(require_admin)):
    """
    获取当前生效的LLM配置（包含默认值）
    """
    async with AsyncSessionLocal() as session:
        llm_api_key = await get_setting(session, "LLM_API_KEY")
        llm_model = await get_setting(session, "LLM_MODEL")
        llm_api_endpoint = await get_setting(session, "LLM_API_ENDPOINT")
        llm_temperature = await get_setting(session, "LLM_TEMPERATURE")
        llm_max_tokens = await get_setting(session, "LLM_MAX_TOKENS")
        llm_json_retry_count = await get_setting(session, "LLM_JSON_RETRY_COUNT")
        llm_enable_thinking = await get_setting(session, "LLM_ENABLE_THINKING")

        return {
            "api_key": llm_api_key,
            "model": llm_model or settings.LLM_MODEL,
            "api_endpoint": llm_api_endpoint or settings.LLM_API_ENDPOINT,
            "temperature": float(llm_temperature) if llm_temperature else settings.LLM_TEMPERATURE,
            "max_tokens": int(llm_max_tokens) if llm_max_tokens else settings.LLM_MAX_TOKENS,
            "json_retry_count": int(llm_json_retry_count) if llm_json_retry_count else settings.LLM_JSON_RETRY_COUNT,
            "enable_thinking": llm_enable_thinking.lower() == "true" if llm_enable_thinking else False,
        }


@router.get("/prompts", response_model=PromptConfig)
async def get_prompts(current_user: dict = Depends(require_admin)):
    """
    获取所有Prompt配置
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(SystemSettings))
        settings_dict = {s.key: s.value for s in result.scalars().all()}

        def get_prompt_item(key: str, default: dict) -> PromptItem:
            system = settings_dict.get(key + "_system") or default.get("system_prompt", "")
            user = settings_dict.get(key + "_user") or default.get("user_prompt", "")
            return PromptItem(system=system, user=user)

        return PromptConfig(
            speaker_detection=get_prompt_item("prompt_speaker_detection", DEFAULT_PROMPTS["prompt_speaker_detection"]),
            rule_refine=get_prompt_item("prompt_rule_refine", DEFAULT_PROMPTS["prompt_rule_refine"]),
            bonus_judgment=get_prompt_item("prompt_bonus_judgment", DEFAULT_PROMPTS["prompt_bonus_judgment"]),
            deduction_judgment=get_prompt_item("prompt_deduction_judgment", DEFAULT_PROMPTS["prompt_deduction_judgment"]),
        )


@router.put("/prompts")
async def update_prompts(
    config: PromptConfig,
    current_user: dict = Depends(require_admin)
):
    """
    更新Prompt配置
    """
    async with AsyncSessionLocal() as session:
        if config.speaker_detection is not None:
            await set_setting(session, "prompt_speaker_detection_system", config.speaker_detection.system, "客服/客户区分System Prompt")
            await set_setting(session, "prompt_speaker_detection_user", config.speaker_detection.user, "客服/客户区分User Prompt")
        if config.rule_refine is not None:
            await set_setting(session, "prompt_rule_refine_system", config.rule_refine.system, "规则细化System Prompt")
            await set_setting(session, "prompt_rule_refine_user", config.rule_refine.user, "规则细化User Prompt")
        if config.bonus_judgment is not None:
            await set_setting(session, "prompt_bonus_judgment_system", config.bonus_judgment.system, "加分规则判定System Prompt")
            await set_setting(session, "prompt_bonus_judgment_user", config.bonus_judgment.user, "加分规则判定User Prompt")
        if config.deduction_judgment is not None:
            await set_setting(session, "prompt_deduction_judgment_system", config.deduction_judgment.system, "减分规则判定System Prompt")
            await set_setting(session, "prompt_deduction_judgment_user", config.deduction_judgment.user, "减分规则判定User Prompt")

        await session.commit()
        return {"message": "Prompt配置更新成功"}


@router.post("/prompts/reset")
async def reset_prompts(current_user: dict = Depends(require_admin)):
    """
    重置所有Prompt为默认值
    """
    async with AsyncSessionLocal() as session:
        for key, value in DEFAULT_PROMPTS.items():
            await set_setting(session, key + "_system", value["system_prompt"], f"{key}默认System模板")
            await set_setting(session, key + "_user", value["user_prompt"], f"{key}默认User模板")
        await session.commit()
        return {"message": "Prompt配置已重置为默认值"}
