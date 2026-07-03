"""
存储清理API - 仅超级管理员可用
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from backend.api.auth import get_current_user_required
from backend.services.oss_service import oss_service
from backend.core.config import settings
import asyncio

router = APIRouter(prefix="/storage", tags=["存储管理"])


def require_admin(current_user: dict = Depends(get_current_user_required)) -> dict:
    """检查是否为超级管理员"""
    if current_user.get("loginid") != settings.ADMIN_USER:
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")
    return current_user


class StorageInfo(BaseModel):
    """存储信息"""
    total_size: int  # bytes
    total_count: int
    recordings_size: int
    recordings_count: int
    other_size: int
    other_count: int


class StorageObject(BaseModel):
    """存储对象"""
    object_key: str
    size: int
    last_modified: str


class StorageListResponse(BaseModel):
    """存储列表响应"""
    objects: List[StorageObject]
    total_count: int
    total_size: int
    prefix: Optional[str] = None


class DeleteRequest(BaseModel):
    """删除请求"""
    object_keys: Optional[List[str]] = None  # 指定删除的文件
    prefix: Optional[str] = None  # 按前缀删除
    before_date: Optional[str] = None  # 删除此日期之前的文件


class DeleteResponse(BaseModel):
    """删除响应"""
    deleted_count: int
    deleted_size: int
    message: str


@router.get("/info", response_model=StorageInfo)
async def get_storage_info(current_user: dict = Depends(require_admin)):
    """
    获取存储概览信息
    """
    try:
        def _list_objects():
            objects = list(oss_service.client.list_objects(settings.OSS_BUCKET, recursive=True))
            return objects

        objects = await asyncio.to_thread(_list_objects)

        total_size = 0
        total_count = 0
        recordings_size = 0
        recordings_count = 0
        other_size = 0
        other_count = 0

        for obj in objects:
            size = obj.size or 0
            total_size += size
            total_count += 1

            if obj.object_name and obj.object_name.startswith("recordings/"):
                recordings_size += size
                recordings_count += 1
            else:
                other_size += size
                other_count += 1

        return StorageInfo(
            total_size=total_size,
            total_count=total_count,
            recordings_size=recordings_size,
            recordings_count=recordings_count,
            other_size=other_size,
            other_count=other_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取存储信息失败: {str(e)}")


@router.get("/objects", response_model=StorageListResponse)
async def list_objects(
    prefix: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(require_admin)
):
    """
    列出存储对象
    """
    try:
        def _list_objects():
            objects = list(oss_service.client.list_objects(
                settings.OSS_BUCKET,
                prefix=prefix or "",
                recursive=True
            ))
            return objects

        objects = await asyncio.to_thread(_list_objects)

        result_objects = []
        total_size = 0

        for obj in objects[:limit]:
            size = obj.size or 0
            total_size += size
            result_objects.append(StorageObject(
                object_key=obj.object_name,
                size=size,
                last_modified=str(obj.last_modified) if obj.last_modified else ""
            ))

        return StorageListResponse(
            objects=result_objects,
            total_count=len(objects),
            total_size=total_size,
            prefix=prefix,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出对象失败: {str(e)}")


@router.post("/delete", response_model=DeleteResponse)
async def delete_objects(
    request: DeleteRequest,
    current_user: dict = Depends(require_admin)
):
    """
    删除存储对象
    支持三种模式:
    1. 指定object_keys列表删除
    2. 按prefix前缀删除
    3. 按before_date日期之前的录音删除
    """
    try:
        deleted_count = 0
        deleted_size = 0

        def _do_delete():
            nonlocal deleted_count, deleted_size

            # 列出所有对象
            all_objects = list(oss_service.client.list_objects(settings.OSS_BUCKET, recursive=True))

            to_delete = []

            if request.object_keys:
                # 模式1: 指定删除
                to_delete = [obj for obj in all_objects if obj.object_name in request.object_keys]
            elif request.prefix:
                # 模式2: 前缀删除
                to_delete = [obj for obj in all_objects if obj.object_name.startswith(request.prefix)]
            elif request.before_date:
                # 模式3: 按日期删除 (只删录音文件)
                try:
                    before_dt = datetime.fromisoformat(request.before_date.replace("Z", "+00:00"))
                    to_delete = []
                    for obj in all_objects:
                        if obj.object_name and obj.object_name.startswith("recordings/"):
                            if obj.last_modified and obj.last_modified.replace(tzinfo=None) < before_dt:
                                to_delete.append(obj)
                except ValueError:
                    raise Exception("日期格式错误，请使用ISO格式")
            else:
                raise Exception("请指定删除条件")

            # 执行删除
            for obj in to_delete:
                try:
                    oss_service.client.remove_object(settings.OSS_BUCKET, obj.object_name)
                    deleted_count += 1
                    deleted_size += obj.size or 0
                except Exception as e:
                    print(f"删除对象失败 {obj.object_name}: {e}")

        await asyncio.to_thread(_do_delete)

        return DeleteResponse(
            deleted_count=deleted_count,
            deleted_size=deleted_size,
            message=f"成功删除 {deleted_count} 个对象，释放 {deleted_size} 字节"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


class CacheInfo(BaseModel):
    """缓存信息"""
    cache_type: str
    size: int
    count: int
    description: str


@router.get("/cache", response_model=List[CacheInfo])
async def get_cache_info(current_user: dict = Depends(require_admin)):
    """
    获取缓存信息
    """
    cache_info = []

    # 检查临时上传文件
    import os
    import tempfile

    temp_dir = tempfile.gettempdir()
    temp_files = []
    temp_size = 0

    try:
        for f in os.listdir(temp_dir):
            if f.startswith("voxaudit_") or f.startswith("upload_"):
                path = os.path.join(temp_dir, f)
                if os.path.isfile(path):
                    temp_size += os.path.getsize(path)
                    temp_files.append(f)
        cache_info.append(CacheInfo(
            cache_type="temp_files",
            size=temp_size,
            count=len(temp_files),
            description=f"临时上传文件 ({len(temp_files)} 个)"
        ))
    except PermissionError:
        pass

    # 检查缓存目录
    cache_dirs = [
        "/tmp/voxaudit_cache",
        "/tmp/voxaudit_uploads",
    ]

    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            total_size = 0
            file_count = 0
            try:
                for root, dirs, files in os.walk(cache_dir):
                    for f in files:
                        path = os.path.join(root, f)
                        try:
                            total_size += os.path.getsize(path)
                            file_count += 1
                        except:
                            pass
                cache_info.append(CacheInfo(
                    cache_type=cache_dir.replace("/", "_"),
                    size=total_size,
                    count=file_count,
                    description=f"缓存目录 ({file_count} 个文件)"
                ))
            except PermissionError:
                pass

    return cache_info


@router.post("/cache/clear", response_model=DeleteResponse)
async def clear_cache(
    cache_type: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """
    清理缓存
    """
    import os
    import tempfile

    deleted_count = 0
    deleted_size = 0

    def _clear():
        nonlocal deleted_count, deleted_size

        # 清理临时文件
        temp_dir = tempfile.gettempdir()

        if cache_type is None or cache_type == "temp_files":
            try:
                for f in os.listdir(temp_dir):
                    if f.startswith("voxaudit_") or f.startswith("upload_"):
                        path = os.path.join(temp_dir, f)
                        if os.path.isfile(path):
                            try:
                                size = os.path.getsize(path)
                                os.remove(path)
                                deleted_count += 1
                                deleted_size += size
                            except:
                                pass
            except PermissionError:
                pass

        # 清理缓存目录
        cache_dirs = ["/tmp/voxaudit_cache", "/tmp/voxaudit_uploads"]

        if cache_type is None:
            target_dirs = cache_dirs
        else:
            target_dirs = [f"/tmp/{cache_type}"]

        for cache_dir in target_dirs:
            if os.path.exists(cache_dir):
                try:
                    for root, dirs, files in os.walk(cache_dir):
                        for f in files:
                            path = os.path.join(root, f)
                            try:
                                size = os.path.getsize(path)
                                os.remove(path)
                                deleted_count += 1
                                deleted_size += size
                            except:
                                pass
                except PermissionError:
                    pass

    await asyncio.to_thread(_clear)

    return DeleteResponse(
        deleted_count=deleted_count,
        deleted_size=deleted_size,
        message=f"成功清理 {deleted_count} 个缓存文件，释放 {deleted_size} 字节"
    )