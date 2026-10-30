"""
应用配置模块
"""
import urllib.parse
from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    APP_NAME: str = "VoxAudit 语音管理系统"
    APP_VERSION: str = "1.3.0"
    DEBUG: bool = False

    # 数据库配置
    DB_HOST: str = ""
    DB_PORT: int = 3306
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_PASSWORD_ENCRYPTED: str = ""
    DB_SECRET_KEY: str = ""
    DB_NAME: str = ""

    @property
    def DATABASE_URL(self) -> str:
        encoded_password = urllib.parse.quote_plus(self.DB_PASSWORD)
        return f"mysql+aiomysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        encoded_password = urllib.parse.quote_plus(self.DB_PASSWORD)
        return f"mysql+pymysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # OSS配置
    OSS_ENDPOINT: str = ""
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_BUCKET: str = "voxaudit-recordings"
    OSS_SECURE: bool = False

    # LLM配置
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "MiniMax-M2-7"
    LLM_API_ENDPOINT: str = ""
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 20000

    # 超级管理员配置
    ADMIN_USER: str = ""
    ADMIN_PASSWORD: str = ""

    # k 前缀本地账号的默认密码（首次登录后强制改密）
    K_USER_DEFAULT_PASSWORD: str = "kefu123456"
    # k 账号改密后多少天再次强制改密
    K_USER_PASSWORD_EXPIRE_DAYS: int = 90

    # OA配置
    OA_BASE_URL: str = ""
    OA_SECRET_KEY: str = ""
    OA_API_IDENTIFIER: str = ""
    OA_TOKEN_EXPIRE_MINUTES: int = 5
    OA_TIME_OFFSET_SECONDS: int = 0

    # 会话配置
    SESSION_EXPIRE_HOURS: int = 8  # 登录后8小时要求重新登录

    # ASR配置
    ASR_API_URL: str = ""
    ASR_API_KEY: str = ""

    # ICP 上游接口（催记管理数据源；完整 URL，含 /v1/icp/ICP1100010 路径）
    # 形如 http://escterminal:10306/v1/icp/ICP1100010
    ICP_API_BASE_URL: str = ""
    ICP_API_TIMEOUT: int = 15
    ICP_API_TOKEN: str = ""

    # —— 上游 CSP 适配器（MAC / verify / decrypt 的统一网关）——
    # CSP_ADAPTER_BASE_URL：形如 http://csp-adapter:8081（不含 /v1/* 后缀）
    CSP_ADAPTER_BASE_URL: str = ""
    CSP_ADAPTER_TIMEOUT: int = 10

    # —— 链路上行固定标识（不同环境可改）——
    # X_CSP_GLOBAL_SERVICE_NO：同一逻辑请求（一次刷新）的所有 HTTP 调用共享
    # X_CSP_SOURCE_JOURNAL_NO：同一逻辑请求共享；留空则每次刷新自动生成
    #                         （DEMO{yyyyMMdd}{9 位毫秒序号}，与上游样例同形）
    CSP_KEY_NAME: str = "GZYH.LMDA_node.zek"
    X_CSP_GLOBAL_SERVICE_NO: str = "G202610130000000001"
    X_CSP_SOURCE_JOURNAL_NO: str = ""
    # 节点名：generate 调 ICPA 侧、verify 调 LMDA 侧（与上游样例一致）
    X_CSP_NODE_NAME_GENERATE: str = "ICPA"
    X_CSP_NODE_NAME_VERIFY: str = "LMDA"
    # GZB 流向：我们是 LMD 侧，调用 ICP 侧（与上游样例一致）
    X_GZB_SOURCE_SYSTEM_CODE: str = "LMD"
    X_GZB_SINK_SYSTEM_CODE: str = "ICP"
    X_GZB_ACTION_ID: str = "ICP1100010"
    X_GZB_MAC_ENCRYPT_TYPE: int = 4

    # —— 催记刷新窗口（[明天00:00 - N天, 明天00:00)；N=1 只覆盖今天，N=2 覆盖昨天+今天）——
    RECORDING_REQUEST_DURATION_DAYS: int = 2

    # 催记管理 - 后台处理并发度 & 启动恢复阈值
    COLLECTION_NOTE_PROCESS_CONCURRENCY: int = 3
    COLLECTION_NOTE_STUCK_MINUTES: int = 10

    # 催记管理 - 刷新频控（同一 loginid 在此秒数内只允许一次刷新；<=0 表示关闭）
    COLLECTION_NOTE_REFRESH_COOLDOWN_SECONDS: int = 5

    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # 批量重试并发控制（按用户）
    MAX_RETRY_CONCURRENCY: int = 5
    MAX_LLM_CONCURRENCY: int = 3

    # 批量重试并发控制（全局）
    MAX_GLOBAL_ASR_CONCURRENCY: int = 20
    MAX_GLOBAL_LLM_CONCURRENCY: int = 10

    # LLM JSON解析失败重试次数
    LLM_JSON_RETRY_COUNT: int = 3

    # CORS配置
    CORS_ORIGINS: str = "http://localhost:8888,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list:
        """将CORS_ORIGINS字符串解析为列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_required(self) -> "Settings":
        """启动时校验必填配置，并对密文密码进行解密"""
        # DB_PASSWORD_ENCRYPTED 以 "enc:" 开头则视为密文，使用 Fernet 解密；
        # 否则视为明文，直接使用。
        raw = self.DB_PASSWORD_ENCRYPTED or ""
        if raw.startswith("enc:"):
            if not self.DB_SECRET_KEY:
                raise ValueError(
                    "DB_PASSWORD_ENCRYPTED 以 'enc:' 开头时必须同时设置 DB_SECRET_KEY"
                )
            try:
                from cryptography.fernet import Fernet, InvalidToken
                fernet = Fernet(self.DB_SECRET_KEY.encode("utf-8"))
                self.DB_PASSWORD = fernet.decrypt(
                    raw[4:].encode("utf-8")
                ).decode("utf-8")
            except InvalidToken:
                raise ValueError(
                    "DB_PASSWORD_ENCRYPTED 解密失败：DB_SECRET_KEY 不正确或密文已损坏"
                )
        elif raw:
            self.DB_PASSWORD = raw
        # else: DB_PASSWORD 已通过字段默认值或环境变量设置，保持不变

        missing = []
        if not self.DB_PASSWORD:
            missing.append("DB_PASSWORD_ENCRYPTED")
        if not self.ADMIN_PASSWORD:
            missing.append("ADMIN_PASSWORD")
        # 上游 CSP / ICP 链路必填（催记刷新依赖）
        for name, val in (
            ("CSP_ADAPTER_BASE_URL", self.CSP_ADAPTER_BASE_URL),
            ("ICP_API_BASE_URL", self.ICP_API_BASE_URL),
        ):
            if not val:
                missing.append(name)
        if missing:
            raise ValueError(f"缺少必填配置: {', '.join(missing)}，请检查 .env 文件")

        # 数值约束
        if self.RECORDING_REQUEST_DURATION_DAYS < 1:
            raise ValueError(
                f"RECORDING_REQUEST_DURATION_DAYS 必须 ≥ 1，当前={self.RECORDING_REQUEST_DURATION_DAYS}"
            )
        if self.X_GZB_MAC_ENCRYPT_TYPE not in (1, 2, 3, 4):
            raise ValueError("X_GZB_MAC_ENCRYPT_TYPE 必须是 1/2/3/4")
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()