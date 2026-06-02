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

    # CORS配置
    CORS_ORIGINS: str = "http://localhost:8888,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list:
        """将CORS_ORIGINS字符串解析为列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_required(self) -> "Settings":
        """启动时校验必填配置"""
        missing = []
        if not self.DB_PASSWORD:
            missing.append("DB_PASSWORD")
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