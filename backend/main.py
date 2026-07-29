"""
VoxAudit 规则管理服务 - 主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
import os
from loguru import logger

from backend.core.config import settings
from backend.core.database import init_db
from backend.services.oss_service import oss_service
from backend.api import rule_router, history_router, recording_router, statistics_router, export_router, auth_router, storage_router, user_stats_router, system_settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在启动应用...")
    try:
        await init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    # 初始化MinIO存储桶
    try:
        await oss_service.init_buckets()
        logger.info("MinIO存储桶初始化完成")
    except Exception as e:
        logger.warning(f"MinIO存储桶初始化失败（桶可能已存在）: {e}")

    yield
    logger.info("正在关闭应用...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="VoxAudit 评分规则管理服务",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "message": str(exc)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """把 Pydantic 验证错误转成中文友好提示"""
    field_names = {
        "speaker_detection": "客服/客户区分",
        "rule_refine": "规则细化",
        "bonus_judgment": "加分规则判定",
        "deduction_judgment": "减分规则判定",
    }
    errors = []
    for err in exc.errors():
        loc = err.get("loc")
        if loc and len(loc) > 1:
            field_key = str(loc[1])
            field_label = field_names.get(field_key, field_key)
            errors.append(f"{field_label}的prompt过短（最少10个字）")
        else:
            errors.append(err.get("msg", "验证失败"))

    message = "；".join(errors) if errors else "验证失败"
    return JSONResponse(
        status_code=422,
        content={"detail": message},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


# 注册路由
app.include_router(rule_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")
app.include_router(recording_router, prefix="/api/v1")
app.include_router(statistics_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(storage_router, prefix="/api/v1")
app.include_router(user_stats_router, prefix="/api/v1")
app.include_router(system_settings_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/upload_rules_template.json")
async def get_template():
    """下载导入规则模板"""
    template_path = os.path.join(os.path.dirname(__file__), "upload_rules_template.json")
    return FileResponse(template_path, media_type="application/json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )