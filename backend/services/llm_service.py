"""
LLM 调用服务 - 统一封装
"""
import httpx
from loguru import logger
from typing import Optional, Dict, Any

from backend.services.config_service import config_service
import re

def strip_think(content: str) -> str:
    """去除大模型输出中的思考过程标签及内容"""
    if not content:
        return content
    # re.DOTALL 让 . 匹配换行符，避免思考过程跨多行时漏删
    cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
    return cleaned.strip()

class LLMService:
    """统一的 LLM 调用服务"""

    def __init__(self, timeout: float = 60):
        self.timeout = timeout
        self._config: Optional[Dict[str, Any]] = None

    async def _ensure_config(self):
        """确保配置已加载"""
        if self._config is None:
            self._config = await config_service.get_llm_config()

    async def refresh_config(self):
        """强制刷新配置（用于配置更新后立即生效）"""
        self._config = await config_service.get_llm_config()

    async def call(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_retries: int = 3,
    ) -> str:
        """
        调用 LLM API

        Args:
            prompt: 用户 prompt
            system_message: 系统消息，可选
            max_tokens: 最大 token 数，默认使用配置值
            temperature: 温度参数，默认使用配置值
            max_retries: 最大重试次数，默认 3

        Returns:
            LLM 返回的文本内容
        """
        await self._ensure_config()

        headers = {"Content-Type": "application/json"}
        if self._config.get("api_key"):
            headers["Authorization"] = f"Bearer {self._config['api_key']}"

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._config["model"],
            "messages": messages,
            "temperature": self._config.get("temperature", 0.1),
            "max_tokens": self._config.get("max_tokens", 32768),
            "chat_template_kwargs": {
                "enable_thinking": self._config.get("enable_thinking", False),
                "thinking": self._config.get("enable_thinking", False),
            },
            "stream": False,
        }

        endpoint = self._config["api_endpoint"]
        if not endpoint:
            raise Exception("LLM API URL 未配置")

        logger.info(f"调用 LLM API: {endpoint}, Model: {self._config['model']}")

        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    result = response.json()

                    if result.get("choices") is None or len(result.get("choices", [])) == 0:
                        error_msg = result.get("base_resp", {}).get("status_msg", "unknown error")
                        raise Exception(f"LLM API 错误: {error_msg}")

                    message = result["choices"][0].get("message", {})
                    content = message.get("content", "")

                    # 提取正式内容，删除思考过程
                    content = strip_think(content)
                    if not content:
                        raise Exception("LLM 返回内容为空")

                    logger.info(f"LLM 返回内容: {content[:200]}...")
                    return content

            except httpx.TimeoutException:
                last_error = Exception("LLM 请求超时")
                logger.warning(f"LLM 超时 (尝试 {attempt + 1}/{max_retries})")
            except httpx.HTTPStatusError as e:
                last_error = Exception(f"LLM HTTP 错误: {e.response.status_code} - {e.response.text}")
                logger.warning(f"LLM HTTP 错误 (尝试 {attempt + 1}/{max_retries}): {last_error}")
            except Exception as e:
                last_error = e
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")

            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2)

        raise last_error

    async def call_json(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        调用 LLM 并返回 JSON 解析后的结果

        Returns:
            解析后的 JSON dict
        """
        import json
        content = await self.call(
            prompt=prompt,
            system_message=system_message,
            max_tokens=max_tokens or 2000,
            temperature=temperature,
            max_retries=max_retries,
        )
        return self._extract_json(content)

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """从文本中提取 JSON"""
        import json
        content = content.strip()
        if not content:
            raise json.JSONDecodeError("内容为空", content, 0)

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 提取 {...} 部分
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            # 清理常见问题
            json_str = json_str.replace(",}", "}")
            json_str = json_str.replace(",]", "]")
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError(f"无法从内容中提取 JSON: {content[:200]}", content, 0)


llm_service = LLMService()
