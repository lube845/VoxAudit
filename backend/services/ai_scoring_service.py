"""
AI评分服务 - 简化版
只用 scoring_rules 表的 total_score 和 description
"""
import json
import httpx
from loguru import logger
from typing import List, Dict, Optional, Any
from datetime import datetime

from backend.core.config import settings
from backend.models.rule import ScoringRule


class AIScoringService:
    """AI评分服务"""

    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.timeout = 120  # 2分钟超时

    async def score(
        self,
        transcript: str,
        segments: List[Dict],
        rule: "ScoringRule",
    ) -> Dict:
        """
        使用LLM进行智能评分
        直接使用 scoring_rules 表的 total_score 和 description

        Args:
            transcript: 转写文本
            segments: 转写片段（带时间戳）
            rule: 评分规则（scoring_rules表的记录）

        Returns:
            评分结果
        """
        if not settings.LLM_API_ENDPOINT:
            raise Exception("LLM API URL未配置")

        # 直接使用 scoring_rules 的字段构建规则信息
        rule_info = [{
            "id": rule.id,
            "name": rule.name,
            "code": rule.code,
            "max_score": rule.total_score,
            "description": rule.description or "",
            "rule_type": getattr(rule, "rule_type", "bonus"),
            "is_veto": getattr(rule, "is_veto", False),
        }]

        # 根据规则类型决定是加分还是扣分
        if rule_info[0]["rule_type"] == "deduction":
            result = await self._score_deduction_rules(transcript, segments, rule_info)
            # 否决项逻辑：如果是否决项且命中，直接 is_rejected = True
            is_veto_rule = rule_info[0].get("is_veto", False)
            has_matched = any(d["status"] == "matched" for d in result["details"])
            is_rejected = is_veto_rule and has_matched
            return {
                "total_score": 0,
                "bonus_score": 0,
                "deduction_score": result["total_score"],
                "total_max_score": result["total_max_score"],
                "passed": result["total_score"] <= 0 and not is_rejected,
                "is_rejected": is_rejected,
                "details": result["details"],
                "warnings": result["warnings"],
            }
        else:
            result = await self._score_bonus_rules(transcript, segments, rule_info)
            pass_score = getattr(rule, 'pass_score', 60)
            return {
                "total_score": result["total_score"],
                "bonus_score": result["total_score"],
                "deduction_score": 0,
                "total_max_score": result["total_max_score"],
                "passed": result["total_score"] >= pass_score,
                "is_rejected": False,
                "details": result["details"],
                "warnings": result["warnings"],
            }

    async def _score_bonus_rules(
        self,
        transcript: str,
        segments: List[Dict],
        bonus_items: List[Dict],
    ) -> Dict:
        """对加分规则进行评分，JSON解析失败时自动重试LLM"""
        if not bonus_items:
            return {"total_score": 0, "total_max_score": 0, "details": [], "warnings": []}

        prompt = self._build_bonus_prompt(transcript, segments, bonus_items)
        retry_count = settings.LLM_JSON_RETRY_COUNT
        last_error = None

        for attempt in range(retry_count):
            try:
                content = await self._call_llm(prompt)
                return self._parse_bonus_result(content, bonus_items)
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    logger.warning(f"JSON解析失败 (尝试 {attempt + 1}/{retry_count}): {str(e)}, 重新调用LLM...")
                    import asyncio
                    await asyncio.sleep(1)  # 等待1秒后重试
                    continue

        raise last_error

    async def _score_deduction_rules(
        self,
        transcript: str,
        segments: List[Dict],
        deduction_items: List[Dict],
    ) -> Dict:
        """对减分规则进行评分，JSON解析失败时自动重试LLM"""
        if not deduction_items:
            return {"total_score": 0, "total_max_score": 0, "details": [], "warnings": []}

        prompt = self._build_deduction_prompt(transcript, segments, deduction_items)
        retry_count = settings.LLM_JSON_RETRY_COUNT
        last_error = None

        for attempt in range(retry_count):
            try:
                content = await self._call_llm(prompt)
                return self._parse_deduction_result(content, deduction_items)
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    logger.warning(f"JSON解析失败 (尝试 {attempt + 1}/{retry_count}): {str(e)}, 重新调用LLM...")
                    import asyncio
                    await asyncio.sleep(1)  # 等待1秒后重试
                    continue

        raise last_error

    async def _call_llm(self, prompt: str, max_retries: int = 3) -> str:
        """调用LLM API，带自动重试机制"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个专业的金融催收录音质检专家，负责对催收对话进行评分。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }

        endpoint = settings.LLM_API_ENDPOINT
        logger.info(f"调用LLM评分 API: {endpoint}, Model: {self.model}, Temperature: {settings.LLM_TEMPERATURE}, MaxTokens: {settings.LLM_MAX_TOKENS}")

        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    logger.info(f"LLM API原始响应: {result}")
                    # 检查API返回是否有效
                    if result.get("choices") is None or len(result.get("choices", [])) == 0:
                        error_msg = result.get("base_resp", {}).get("status_msg", "unknown error")
                        raise Exception(f"AI评分失败: {error_msg}")
                    message = result["choices"][0].get("message", {})
                    # MiniMax 推理模型返回的内容可能在 reasoning_content 中
                    content = message.get("content", "") or message.get("reasoning_content", "")
                    if not content:
                        raise Exception("AI评分返回内容为空")
                    logger.info(f"LLM返回内容: {content}")
                    return content
            except httpx.TimeoutException:
                raise Exception("AI评分超时")
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM HTTP错误: {e.response.status_code} - {e.response.text}")
                raise Exception(f"AI评分失败: {e.response.text}")
            except Exception as e:
                last_error = e
                logger.warning(f"LLM调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2)  # 等待2秒后重试
                    continue

        # 所有重试都失败
        logger.error(f"LLM评分失败，已重试{max_retries}次: {str(last_error)}")
        raise Exception(f"AI评分失败，已重试{max_retries}次: {str(last_error)}")

    def _build_bonus_prompt(
        self,
        transcript: str,
        segments: List[Dict],
        bonus_items: List[Dict],
    ) -> str:
        """构建加分规则评分提示词"""
        rules_json = json.dumps(bonus_items, ensure_ascii=False, indent=2)

        return f"""## 录音转写文本
{transcript}

## 对话片段详情（带时间戳）
{json.dumps(segments, ensure_ascii=False, indent=2)}

## 加分规则
{rules_json}

## 评分要求
请仔细阅读转写文本和对话片段，判断坐席的表现是否匹配加分规则。
- 如果坐席的表现符合某条加分规则的description描述，则标记为"matched"，该规则得满分
- 如果坐席的表现不符合某条加分规则，则标记为"not_matched"，不得分（但不扣分）

## 输出格式要求（JSON）：
{{
    "items": [
        {{
            "code": "规则代码",
            "status": "matched/not_matched",
            "score": 得分（匹配则得满分，否则得0分）,
            "matched_text": "匹配到的文本（未匹配则为空字符串）",
            "reason": "评分理由"
        }}
    ],
    "warnings": ["风险预警列表，如有则填入，否则为空数组"]
}}

请严格按照上述JSON格式输出，不要包含其他内容。"""

    def _build_deduction_prompt(
        self,
        transcript: str,
        segments: List[Dict],
        deduction_items: List[Dict],
    ) -> str:
        """构建减分规则评分提示词"""
        rules_json = json.dumps(deduction_items, ensure_ascii=False, indent=2)

        return f"""## 录音转写文本
{transcript}

## 对话片段详情（带时间戳）
{json.dumps(segments, ensure_ascii=False, indent=2)}

## 减分规则
{rules_json}

## 评分要求
请仔细阅读转写文本和对话片段，判断坐席的表现是否触犯减分规则。
- 如果坐席的行为违反了某条减分规则的description描述，则标记为"matched"，按该规则扣分
- 如果坐席的行为没有违反某条减分规则，则标记为"not_matched"，不扣分

注意：扣分不超过规则设定的max_score。

## 输出格式要求（JSON）：
{{
    "items": [
        {{
            "code": "规则代码",
            "status": "matched/not_matched",
            "score": 扣分数（匹配则扣除相应分数，否则得0分）,
            "matched_text": "违规的文本（未违规则为空字符串）",
            "reason": "扣分理由"
        }}
    ],
    "warnings": ["风险预警列表，如有则填入，否则为空数组"]
}}

请严格按照上述JSON格式输出，不要包含其他内容。"""

    def _parse_bonus_result(
        self,
        content: str,
        bonus_items: List[Dict],
    ) -> Dict:
        """解析加分规则评分结果"""
        try:
            logger.info(f"[LLM原始输出] bonus: {content[:2000] if content else '空内容'}")
            result = self._extract_json(content)
            items_result = result.get("items", [])
            warnings = result.get("warnings", [])

            details = []
            total_score = 0
            total_max_score = 0

            for item in bonus_items:
                total_max_score += item["max_score"]
                item_result = next(
                    (i for i in items_result if i.get("code") == item["code"]),
                    None
                )

                if item_result and item_result.get("status") == "matched":
                    score = item["max_score"]
                    matched_text = item_result.get("matched_text", "")
                else:
                    score = 0
                    matched_text = ""

                total_score += score
                details.append({
                    "rule_item_id": item["id"],
                    "item_name": item["name"],
                    "item_type": "bonus",
                    "status": "matched" if score > 0 else "not_matched",
                    "score": score,
                    "max_score": item["max_score"],
                    "matched_text": matched_text,
                    "is_veto": item.get("is_veto", False),
                })

            return {
                "total_score": total_score,
                "total_max_score": total_max_score,
                "details": details,
                "warnings": warnings,
            }

        except json.JSONDecodeError as e:
            logger.error(f"解析加分评分结果失败: {str(e)}, content={content[:500]}")
            raise Exception(f"解析加分评分结果失败: {str(e)}")

    def _parse_deduction_result(
        self,
        content: str,
        deduction_items: List[Dict],
    ) -> Dict:
        """解析减分规则评分结果"""
        try:
            logger.info(f"[LLM原始输出] deduction: {content[:2000] if content else '空内容'}")
            result = self._extract_json(content)
            items_result = result.get("items", [])
            warnings = result.get("warnings", [])

            details = []
            total_score = 0
            total_max_score = 0

            for item in deduction_items:
                total_max_score += item["max_score"]
                item_result = next(
                    (i for i in items_result if i.get("code") == item["code"]),
                    None
                )

                if item_result and item_result.get("status") == "matched":
                    deduction = abs(item_result.get("score", item["max_score"]))
                    deduction = min(deduction, item["max_score"])
                else:
                    deduction = 0

                total_score += deduction
                details.append({
                    "rule_item_id": item["id"],
                    "item_name": item["name"],
                    "item_type": "deduction",
                    "status": "matched" if deduction > 0 else "not_matched",
                    "score": -deduction,
                    "max_score": item["max_score"],
                    "matched_text": item_result.get("matched_text", "") if item_result else "",
                    "is_veto": item.get("is_veto", False),
                })

            return {
                "total_score": total_score,
                "total_max_score": total_max_score,
                "details": details,
                "warnings": warnings,
            }

        except json.JSONDecodeError as e:
            logger.error(f"解析减分评分结果失败: {str(e)}, content={content[:500]}")
            raise Exception(f"解析减分评分结果失败: {str(e)}")

    def _fix_unescaped_commas(self, json_str: str) -> str:
        """修复JSON字符串中未转义的字符"""
        # 替换中文标点和单引号为英文标点（仅在字符串外）
        result = []
        in_string = False
        i = 0
        while i < len(json_str):
            char = json_str[i]
            if char == '"' and (i == 0 or json_str[i-1] != '\\'):
                in_string = not in_string
                result.append(char)
            elif not in_string:
                # 不在字符串内，替换中文标点和单引号
                if char == '，':
                    result.append(',')
                elif char == '：':
                    result.append(':')
                elif char == "'":
                    # 单引号替换为双引号（处理LLM返回的单引号JSON）
                    result.append('"')
                elif char == '"':
                    # 不在字符串内的引号，可能是多余的
                    result.append('"')
                else:
                    result.append(char)
            else:
                # 在字符串内
                if char == '\\' and i + 1 < len(json_str):
                    if json_str[i+1] == 'n':
                        result.append('\\n')
                        i += 2
                        continue
                    elif json_str[i+1] == '"':
                        result.append('\\"')
                        i += 2
                        continue
                    elif json_str[i+1] == "'":
                        # 处理字符串内的单引号
                        result.append("\\'")
                        i += 2
                        continue
                result.append(char)
            i += 1
        return ''.join(result)

    def _try_fix_truncated_json(self, json_str: str) -> Optional[Dict]:
        """尝试修复被截断的JSON，返回修复后的结果或None"""
        original = json_str
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                pos = e.pos
                # 尝试修复：截断位置在字符串内部导致的不完整
                if pos is not None and pos > 0:
                    # 检查截断位置是否在字符串内（引号未闭合）
                    in_string = False
                    last_unescaped_quote = -1
                    i = 0
                    while i < pos and i < len(json_str):
                        char = json_str[i]
                        if char == '"' and (i == 0 or json_str[i-1] != '\\'):
                            in_string = not in_string
                            if in_string:
                                last_unescaped_quote = i
                        i += 1

                    # 如果截断时正在字符串内，尝试闭合它
                    if in_string and last_unescaped_quote >= 0:
                        # 找到最后一个未闭合的字符串，闭合它
                        json_str = json_str[:pos] + '"' + json_str[pos:]
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            pass

                # 尝试移除末尾的不完整内容（数组/对象元素）
                truncated = json_str.rstrip()
                for suffix in ["},", "],", "]", "}"]:
                    if truncated.endswith(suffix):
                        break
                    # 找到最后一个完整的数组/对象元素
                    last_delim = max(
                        truncated.rfind("},"),
                        truncated.rfind("],"),
                        truncated.rfind('"}'),
                    )
                    if last_delim > 0:
                        truncated = truncated[:last_delim + 1]
                        try:
                            return json.loads(truncated)
                        except json.JSONDecodeError:
                            pass

                # 尝试移除末尾不完整的 key-value 对
                last_comma = truncated.rfind(",")
                if last_comma > 0:
                    truncated = truncated[:last_comma] + "}"
                    try:
                        return json.loads(truncated)
                    except json.JSONDecodeError:
                        pass

                # 尝试移除末尾不完整的字符串
                if last_unescaped_quote >= 0:
                    truncated = json_str[:last_unescaped_quote] + '"}'
                    try:
                        return json.loads(truncated)
                    except json.JSONDecodeError:
                        pass

                # 尝试在末尾补全常见的闭合
                for closer in ['"]}', "}]}", "]}"]:
                    if truncated.endswith('"') or truncated.endswith('{') or truncated.endswith('['):
                        candidate = truncated + closer
                        try:
                            result = json.loads(candidate)
                            logger.warning(f"JSON被截断，已自动修复: {original[:50]}... -> {candidate[:50]}...")
                            return result
                        except json.JSONDecodeError:
                            pass

                # 如果本次尝试没有改变json_str，跳出循环避免死循环
                if json_str == original:
                    break
                original = json_str

        return None

    def _extract_json(self, content: str) -> Dict:
        """从LLM返回的内容中提取JSON"""
        try:
            # 清理空白字符
            content = content.strip()
            if not content:
                raise json.JSONDecodeError("LLM返回内容为空", content, 0)

            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                # 清理常见的JSON格式问题
                json_str = json_str.replace(",}", "}")  # 移除尾随逗号
                json_str = json_str.replace(",]", "]")  # 移除数组尾随逗号
                # 首先尝试直接解析
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
                # 尝试修复未转义逗号的问题
                json_str = self._fix_unescaped_commas(json_str)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
                # 尝试修复被截断的JSON
                fixed = self._try_fix_truncated_json(json_str)
                if fixed is not None:
                    return fixed
                # 所有修复都失败，抛出原始错误
                raise json.JSONDecodeError("无法解析JSON", json_str, 0)
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败 content={content[:200]}, error={e}")
            raise Exception(f"解析评分结果失败: {str(e)}")


ai_scoring_service = AIScoringService()
