"""
ASR转写服务 - 基于 FunASR API
"""
import json
import re
import httpx
from typing import List, Dict

from backend.core.config import settings


class ASRService:
    """ASR转写服务 - FunASR API"""

    def __init__(self):
        self.api_url = settings.ASR_API_URL
        self.api_key = settings.ASR_API_KEY
        self.timeout = 600  # 10分钟超时

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
    ) -> Dict:
        """转写并使用LLM判断说话人角色"""
        result = await self.transcribe(file_content, filename)
        result["segments"] = await self._detect_speaker_roles(result["segments"])
        result["full_text"] = "\n".join([
            seg["speaker_name"] + ": " + seg["text"]
            for seg in result["segments"]
        ])
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
        prompt = f"""以下是一段客服通话录音转写，已识别出{len(speakers)}个说话人。
转写内容：
{dialogue_text}
判断哪个是坐席哪个是客户，只返回JSON格式：
{{"speaker_roles": {{"speaker_0": "agent"或"customer", ...}}}}"""
        try:
            role_result = await self._call_llm(prompt)
            role_info = json.loads(role_result)
            speaker_roles = role_info.get("speaker_roles", {})
            customer_map = {}
            customer_counter = 0
            for seg in segments:
                original_speaker = seg.get("speaker", "unknown")
                role = speaker_roles.get(original_speaker, "customer")
                if role == "agent":
                    seg["speaker"] = "agent"
                    seg["speaker_name"] = "坐席"
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
            logging.warning("LLM角色判断失败: " + str(e))
            customer_counter = 0
            for seg in segments:
                if seg.get("speaker") == "speaker_0":
                    seg["speaker"] = "agent"
                    seg["speaker_name"] = "坐席"
                else:
                    customer_counter += 1
                    seg["speaker"] = "customer_" + str(customer_counter)
                    seg["speaker_name"] = "客户" + str(customer_counter)
            return segments

    async def _call_llm(self, prompt):
        """调用LLM API"""
        if not settings.LLM_API_ENDPOINT:
            raise Exception("LLM API Endpoint 未配置")
        headers = {"Authorization": "Bearer " + settings.LLM_API_KEY, "Content-Type": "application/json"} if settings.LLM_API_KEY else {"Content-Type": "application/json"}
        payload = {"model": settings.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(settings.LLM_API_ENDPOINT, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            text = result["choices"][0]["message"].get("content") or ""
            if not text:
                raise Exception("LLM返回内容为空")
            text = re.sub(r'<think>.*?\n\n', '', text, flags=re.DOTALL).strip()
            json_start = text.rfind("{")
            if json_start >= 0:
                text = text[json_start:]
            return text

    def _parse_transcript_result(self, result: Dict) -> Dict:
        """解析ASR返回的Markdown结果"""
        markdown_text = result.get("markdown", "")
        speaker_cnt = result.get("speaker_cnt", 0)
        
        segments = self._parse_markdown(markdown_text)
        full_text = "\n".join([seg["text"] for seg in segments])
        
        return {
            "full_text": full_text,
            "segments": segments,
            "speaker_cnt": speaker_cnt,
        }

    def _parse_markdown(self, markdown: str) -> List[Dict]:
        """解析Markdown格式的转写结果"""
        segments = []
        markdown = re.sub(r"^#.*$", "", markdown, flags=re.MULTILINE)
        
        # 匹配 **说话人0** `00:00 - 00:08` 文本内容
        pattern = r"\*\*说话人(\d+)\*\*\s+`(\d{2}:\d{2})\s+-\s+(\d{2}:\d{2})`\s*(.+?)(?=\*\*说话人|$)"
        
        matches = re.findall(pattern, markdown, re.DOTALL)
        
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
