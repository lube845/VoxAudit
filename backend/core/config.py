"""
应用配置模块
"""
import urllib.parse
from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    APP_NAME: str = "VoxAudit 规则管理服务"
    APP_VERSION: str = "1.0.0"
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

    # JWT配置
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

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
    LLM_MAX_TOKENS: int = 2000

    # 超级管理员配置
    ADMIN_USER: str = ""
    ADMIN_PASSWORD: str = ""

    # OA配置
    OA_BASE_URL: str = ""
    OA_SECRET_KEY: str = ""
    OA_API_IDENTIFIER: str = ""
    OA_TOKEN_EXPIRE_MINUTES: int = 5
    OA_TIME_OFFSET_SECONDS: int = 0

    # ASR配置
    ASR_API_URL: str = ""
    ASR_API_KEY: str = ""

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
        if not self.SECRET_KEY:
            missing.append("SECRET_KEY")
        if not self.ADMIN_PASSWORD:
            missing.append("ADMIN_PASSWORD")
        if missing:
            raise ValueError(f"缺少必填配置: {', '.join(missing)}，请检查 .env 文件")
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()