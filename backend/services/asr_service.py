"""
ASR转写服务 - 基于 FunASR API
"""
import json
import re
import io
import httpx
from typing import List, Dict

from backend.core.config import settings
from backend.services.config_service import config_service
from backend.services.llm_service import llm_service


class ASRService:
    """ASR转写服务 - FunASR API"""

    def __init__(self):
        self.api_url = None
        self.api_key = None
        self.timeout = 600  # 10分钟超时

    async def _load_config(self):
        """从数据库加载配置"""
        config = await config_service.get_asr_config()
        self.api_url = config["api_url"]
        self.api_key = config["api_key"]

        # 声道模式配置
        self.channel_mode = config.get("channel_mode", "channel")  # "channel" | "llm"
        self.left_channel_role = config.get("left_channel_role", "agent")
        self.right_channel_role = config.get("right_channel_role", "customer")

        # 加载LLM配置（用于角色检测）
        llm_config = await config_service.get_llm_config()
        self.llm_api_url = llm_config["api_endpoint"]
        self.llm_api_key = llm_config["api_key"]
        self.llm_model = llm_config["model"]

        # 加载Prompt模板
        prompts = await config_service.get_all_prompts()
        self.prompt_speaker_system = prompts["prompt_speaker_detection"].get("system_prompt", "")
        self.prompt_speaker_user = prompts["prompt_speaker_detection"].get("user_prompt", "")

    async def transcribe(
        self,
        file_content: bytes,
        filename: str = "audio.wav",
    ) -> Dict:
        """
        调用ASR接口进行转写（文件上传方式）

        Args:
            file_content: 音频文件内容（bytes）
            filename: 文件名（用于识别格式）

        Returns:
            转写结果，包含全文和分片段
        """
        await self._load_config()
        if not self.api_url:
            raise Exception("ASR API URL 未配置")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                files = {
                    "upload_file": (filename, file_content, self._get_content_type(filename))
                }

                response = await client.post(
                    f"{self.api_url}/transcribe_upload/",
                    headers=self._get_headers(),
                    files=files,
                )
                response.raise_for_status()
                result = response.json()
                return self._parse_transcript_result(result)
        except httpx.TimeoutException:
            raise Exception("ASR转写超时")
        except httpx.HTTPStatusError as e:
            raise Exception(f"ASR转写失败: {e.response.text}")
        except Exception as e:
            raise Exception(f"ASR转写异常: {str(e)}")

    async def transcribe_with_role(
        self,
        file_content: bytes,
        filename: str = "audio.wav",
        force_method: str = None,
        left_channel_role: str = None,
        right_channel_role: str = None,
    ) -> Dict:
        """转写并判断说话人角色（根据配置自动选择方式）

        Args:
            file_content: 音频文件内容
            filename: 文件名
            force_method: 强制使用的方法 "channel" | "llm"，默认为None（根据配置）
            left_channel_role: 左声道角色覆盖（可选）
            right_channel_role: 右声道角色覆盖（可选）
        """
        await self._load_config()

        if force_method is None:
            method = self.channel_mode
        else:
            method = force_method

        # 使用传入的覆盖值，否则使用配置值
        left_role = left_channel_role or self.left_channel_role
        right_role = right_channel_role or self.right_channel_role

        if method == "llm":
            return await self._transcribe_with_role_llm(file_content, filename)
        else:
            return await self._transcribe_with_channel(file_content, filename, left_role, right_role)

    async def _transcribe_with_channel(
        self,
        file_content: bytes,
        filename: str = "audio.wav",
        left_channel_role: str = "agent",
        right_channel_role: str = "customer",
    ) -> Dict:
        """使用声道分离进行转写（不依赖LLM判断角色）"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 1. 分离左右声道
            left_audio, right_audio, is_mono = await self._split_stereo_channels(file_content, filename)
            logger.info(f"[ASR] 声道分离完成，左声道: {len(left_audio)} bytes，右声道: {len(right_audio)} bytes")
        except Exception as e:
            logger.warning(f"[ASR] 声道分离失败，降级到LLM模式: {e}")
            return await self._transcribe_with_role_llm(file_content, filename)

        # 单声道音频无法使用声道分离，降级到LLM模式
        if is_mono:
            logger.warning(f"[ASR] 检测到单声道音频，无法使用声道分离，降级到LLM模式")
            result = await self._transcribe_with_role_llm(file_content, filename)
            result["mono_warn"] = True
            return result

        # 2. 分别转写
        try:
            left_result = await self._transcribe_single_channel(left_audio, "left.wav")
            right_result = await self._transcribe_single_channel(right_audio, "right.wav")
        except Exception as e:
            logger.warning(f"[ASR] 声道转写失败，降级到LLM模式: {e}")
            return await self._transcribe_with_role_llm(file_content, filename)

        # 3. 合并结果，按时间排序
        segments = self._merge_channel_segments(
            left_result, right_result,
            left_channel_role, right_channel_role
        )

        full_text = "\n".join([
            seg["speaker_name"] + ": " + seg["text"]
            for seg in segments
        ])

        return {
            "full_text": full_text,
            "segments": segments,
            "speaker_cnt": 2,
            "channel_mode": True,
            "mono_warn": False,
        }

    async def _split_stereo_channels(self, file_content: bytes, filename: str) -> tuple:
        """分离立体声音频的左右声道

        Returns:
            (left_audio, right_audio, is_mono): 左右声道音频数据，是否为单声道
        """
        from pydub import AudioSegment

        audio = AudioSegment.from_file(io.BytesIO(file_content))

        if audio.channels < 2:
            # 单声道音频，左右声道使用相同音频
            return file_content, file_content, True

        # 分离声道
        channels = audio.split_to_mono()
        left = channels[0]
        right = channels[1]

        # 导出为bytes
        left_io = io.BytesIO()
        right_io = io.BytesIO()
        left.export(left_io, format="wav")
        right.export(right_io, format="wav")

        return left_io.getvalue(), right_io.getvalue(), False

    async def _transcribe_single_channel(self, audio_content: bytes, filename: str) -> Dict:
        """转写单个声道音频"""
        result = await self.transcribe(audio_content, filename)
        return result

    def _merge_channel_segments(
        self,
        left_result: Dict,
        right_result: Dict,
        left_role: str,
        right_role: str
    ) -> List[Dict]:
        """合并左右声道转写结果，按时间排序"""
        segments = []

        left_segments = left_result.get("segments", [])
        right_segments = right_result.get("segments", [])

        # 角色映射
        role_map = {
            "agent": ("agent", "坐席"),
            "customer": ("customer", "客户"),
        }
        left_speaker, left_name = role_map.get(left_role, ("unknown", f"未知-{left_role}"))
        right_speaker, right_name = role_map.get(right_role, ("unknown", f"未知-{right_role}"))

        # 为左声道片段设置角色
        for seg in left_segments:
            seg["speaker"] = left_speaker
            seg["speaker_name"] = left_name

        # 为右声道片段设置角色
        for seg in right_segments:
            seg["speaker"] = right_speaker
            seg["speaker_name"] = right_name

        # 合并并按开始时间排序
        all_segments = left_segments + right_segments
        all_segments.sort(key=lambda x: x.get("start_time", 0))

        return all_segments

    async def _transcribe_with_role_llm(
        self,
        file_content: bytes,
        filename: str = "audio.wav",
    ) -> Dict:
        """使用LLM判断说话人角色（原有逻辑）"""
        result = await self.transcribe(file_content, filename)
        result["segments"] = await self._detect_speaker_roles(result["segments"])
        result["full_text"] = "\n".join([
            seg["speaker_name"] + ": " + seg["text"]
            for seg in result["segments"]
        ])
        result["channel_mode"] = False
        return result

    async def _detect_speaker_roles(self, segments, db=None):
        """使用LLM判断说话人角色"""
        if not segments:
            return segments
        speakers = {}
        for seg in segments:
            speaker = seg.get("speaker", "unknown")
            if speaker not in speakers:
                speakers[speaker] = []
            speakers[speaker].append(seg.get("text", "")[:100])
        if len(speakers) == 1:
            for seg in segments:
                seg["speaker"] = "agent"
                seg["speaker_name"] = "坐席"
            return segments
        dialogue_lines = []
        for seg in segments:
            speaker = seg.get("speaker", "?")
            text = seg.get("text", "")
            dialogue_lines.append("[" + speaker + "]: " + text)
        dialogue_text = "\n".join(dialogue_lines)
        prompt = self.prompt_speaker_user.format(
            speaker_count=len(speakers),
            dialogue_text=dialogue_text,
        )
        system_message = self.prompt_speaker_system
        def _try_parse_json(text: str):
            """尝试解析JSON，自动修复常见格式错误"""
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # 尝试修复常见格式错误
                # 1. 移除尾随逗号
                text = re.sub(r',(\s*[}\]])', r'\1', text)
                # 2. 修复中文引号
                text = text.replace('""', '"')
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return None

        try:
            role_result = await llm_service.call(
                prompt=prompt, 
                system_message=system_message
            )
            role_info = _try_parse_json(role_result)
            if role_info is None:
                raise Exception("JSON解析失败")
            speaker_roles = role_info.get("speaker_roles", {})
            customer_map = {}
            customer_counter = 0
            unknown_map = {}
            unknown_counter = 0
            for seg in segments:
                original_speaker = seg.get("speaker", "unknown")
                role = speaker_roles.get(original_speaker, "customer")
                if role == "agent":
                    seg["speaker"] = "agent"
                    seg["speaker_name"] = "坐席"
                elif role == "unknown":
                    if original_speaker not in unknown_map:
                        unknown_counter += 1
                        unknown_map[original_speaker] = unknown_counter
                    unknown_num = unknown_map[original_speaker]
                    seg["speaker"] = "unknown_" + str(unknown_num)
                    seg["speaker_name"] = "未知" + str(unknown_num)
                else:
                    if original_speaker not in customer_map:
                        customer_counter += 1
                        customer_map[original_speaker] = customer_counter
                    customer_num = customer_map[original_speaker]
                    seg["speaker"] = "customer_" + str(customer_num)
                    seg["speaker_name"] = "客户" + str(customer_num)
            return segments
        except Exception as e:
            import logging
            # 区分不同错误类型，提供更详细的调试信息
            error_msg = str(e)
            error_type = type(e).__name__
            if "LLM API Endpoint 未配置" in error_msg:
                logging.warning(f"LLM角色判断跳过：LLM API未配置 ({error_type}: {error_msg})")
            elif "LLM返回内容为空" in error_msg:
                logging.warning(f"LLM角色判断失败：LLM返回内容为空 ({error_type}: {error_msg})")
            elif isinstance(e, httpx.HTTPStatusError):
                logging.warning(f"LLM角色判断失败：HTTP错误 {e.response.status_code} ({error_type}: {error_msg})")
            elif isinstance(e, httpx.TimeoutException):
                logging.warning(f"LLM角色判断失败：LLM请求超时 ({error_type}: {error_msg})")
            elif isinstance(e, json.JSONDecodeError) or "JSON解析失败" in error_msg:
                logging.warning(f"LLM角色判断失败：LLM返回格式无效JSON ({error_type}: {error_msg})")
            else:
                logging.warning(f"LLM角色判断失败：{error_type}: {error_msg}")
            # Fallback: speaker_0 -> 坐席，其余 -> 客户
            logging.info(f"Speaker role fallback applied: speaker_0=agent, others numbered as customers")
            customer_map = {}
            customer_counter = 0
            unknown_map = {}
            unknown_counter = 0
            for seg in segments:
                if seg.get("speaker") == "speaker_0":
                    seg["speaker"] = "agent"
                    seg["speaker_name"] = "坐席"
                else:
                    original_speaker = seg.get("speaker", "unknown")
                    if original_speaker not in customer_map:
                        customer_counter += 1
                        customer_map[original_speaker] = customer_counter
                    customer_num = customer_map[original_speaker]
                    seg["speaker"] = "customer_" + str(customer_num)
                    seg["speaker_name"] = "客户" + str(customer_num)
            return segments

    def _parse_transcript_result(self, result: Dict) -> Dict:
        """解析ASR返回的Markdown结果"""
        import logging
        logger = logging.getLogger(__name__)
        markdown_text = result.get("markdown", "")
        speaker_cnt = result.get("speaker_cnt", 0)

        if not markdown_text:
            logger.warning(f"[ASR] API响应中无markdown字段，完整响应: {result}")

        segments = self._parse_markdown(markdown_text)
        full_text = "\n".join([seg["text"] for seg in segments])

        return {
            "full_text": full_text,
            "segments": segments,
            "speaker_cnt": speaker_cnt,
        }

    def _parse_markdown(self, markdown: str) -> List[Dict]:
        """解析Markdown格式的转写结果"""
        import logging
        logger = logging.getLogger(__name__)
        segments = []
        markdown = re.sub(r"^#.*$", "", markdown, flags=re.MULTILINE)

        # 匹配 **说话人0** `00:00 - 00:08` 文本内容
        pattern = r"\*\*说话人(\d+)\*\*\s+`(\d{2}:\d{2})\s+-\s+(\d{2}:\d{2})`\s*(.+?)(?=\*\*说话人|$)"

        matches = re.findall(pattern, markdown, re.DOTALL)

        if not matches:
            logger.warning(f"[ASR] markdown解析无匹配结果，原始内容: {markdown[:500]}")

        for match in matches:
            speaker_id = f"speaker_{match[0]}"
            start_time = self._parse_time(match[1])
            end_time = self._parse_time(match[2])
            text = match[3].strip()

            segments.append({
                "speaker": speaker_id,
                "speaker_name": speaker_id,
                "start_time": start_time,
                "end_time": end_time,
                "text": text,
                "confidence": 0.95,
            })
        
        return segments

    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串 (mm:ss) 为秒数"""
        parts = time_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0.0

    def _get_headers(self) -> dict:
        """获取请求头"""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_content_type(self, filename: str) -> str:
        """根据文件名获取Content-Type"""
        ext = filename.lower().split(".")[-1]
        content_types = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "mp4": "audio/mp4",
            "m4a": "audio/mp4",
            "flac": "audio/flac",
            "ogg": "audio/ogg",
            "webm": "audio/webm",
            "amr": "audio/amr",
        }
        return content_types.get(ext, "audio/wav")


# 始终使用ASRService，当ASR_API_URL未配置时会显式报错
asr_service = ASRService()
