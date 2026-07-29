"""
API路由汇总
"""
from .rule import router as rule_router, history_router
from .recording import router as recording_router
from .statistics import router as statistics_router
from .export import router as export_router
from .auth import router as auth_router
from .storage import router as storage_router
from .user_stats import router as user_stats_router
from .system_settings import router as system_settings_router

__all__ = ["rule_router", "history_router", "recording_router", "statistics_router", "export_router", "auth_router", "storage_router", "user_stats_router", "system_settings_router"]