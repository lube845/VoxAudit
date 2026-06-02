"""
对象存储服务 (MinIO)
"""
import uuid
from datetime import timedelta
from typing import Optional
from minio import Minio
from minio.error import S3Error

from backend.core.config import settings


class OSSService:
    """对象存储服务"""

    def __init__(self):
        self.client = Minio(
            settings.OSS_ENDPOINT.replace("http://", "").replace("https://", ""),
            access_key=settings.OSS_ACCESS_KEY,
            secret_key=settings.OSS_SECRET_KEY,
            secure=settings.OSS_SECURE,
        )
        self.bucket = settings.OSS_BUCKET

    async def init_buckets(self):
        """初始化存储桶（如果不存在则创建）"""
        import asyncio
        def _do_init():
            if self.client.bucket_exists(self.bucket):
                return  # 桶已存在
            self.client.make_bucket(self.bucket)  # 不存在则创建
        try:
            await asyncio.to_thread(_do_init)
        except S3Error as e:
            if e.code == "NoSuchKey":
                return  # COS 返回 NoSuchKey 表示桶不存在但已创建（并发安全），忽略即可
            raise Exception(f"初始化存储桶失败: {str(e)}")

    def generate_object_key(self, filename: str) -> str:
        """生成对象存储键"""
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        unique_id = uuid.uuid4().hex
        return f"recordings/{unique_id}.{ext}"

    async def upload_file(
        self,
        file_data: bytes,
        object_key: str,
        content_type: str = "audio/mpeg",
    ) -> bool:
        """上传文件（异步）"""
        import asyncio

        def _do_upload():
            try:
                from io import BytesIO
                data_stream = BytesIO(file_data)
                self.client.put_object(
                    self.bucket,
                    object_key,
                    data_stream,
                    length=len(file_data),
                    content_type=content_type,
                )
                return True
            except S3Error as e:
                raise Exception(f"上传文件失败: {str(e)}")

        return await asyncio.to_thread(_do_upload)

    async def get_presigned_url(
        self,
        object_key: str,
        bucket: str = None,
        expires: int = 3600,
    ) -> str:
        """获取预签名URL（用于安全播放，异步）"""
        import asyncio

        def _do_get_url():
            try:
                bucket = bucket or self.bucket
                url = self.client.presigned_get_object(
                    bucket,
                    object_key,
                    expires=timedelta(seconds=expires),
                )
                return url
            except Exception as e:
                raise Exception(f"生成预签名URL失败: {str(e)}")

        return await asyncio.to_thread(_do_get_url)

    def get_stream_url(self, object_key: str, bucket: str = None) -> str:
        """获取流式播放URL"""
        return self.get_presigned_url(object_key, bucket, expires=3600)

    async def delete_file(self, object_key: str, bucket: str = None) -> bool:
        """删除文件（异步）"""
        import asyncio

        def _do_delete():
            try:
                _bucket = bucket if bucket is not None else self.bucket
                self.client.remove_object(_bucket, object_key)
                return True
            except S3Error as e:
                raise Exception(f"删除文件失败: {str(e)}")

        return await asyncio.to_thread(_do_delete)

    def get_file_info(self, object_key: str, bucket: str = None) -> dict:
        """获取文件信息（同步）"""
        try:
            bucket = bucket or self.bucket
            stat = self.client.stat_object(bucket, object_key)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
            }
        except S3Error as e:
            raise Exception(f"获取文件信息失败: {str(e)}")

    def check_file_exists(self, object_key: str, bucket: str = None) -> bool:
        """检查文件是否存在（同步）"""
        try:
            bucket = bucket or self.bucket
            self.client.stat_object(bucket, object_key)
            return True
        except S3Error:
            return False

    async def get_file(self, object_key: str, bucket: str = None) -> bytes:
        """下载文件内容（异步）"""
        import asyncio

        def _do_get():
            try:
                _bucket = bucket if bucket is not None else self.bucket
                response = self.client.get_object(_bucket, object_key)
                return response.read()
            except S3Error as e:
                raise Exception(f"下载文件失败: {str(e)}")

        return await asyncio.to_thread(_do_get)


oss_service = OSSService()