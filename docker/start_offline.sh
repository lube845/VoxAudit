#!/bin/bash
# VoxAudit 离线启动脚本 (配合 docker-compose.yml.bak 使用)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== VoxAudit 离线启动脚本 ==="
echo ""

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker 未运行，请先启动 Docker"
    exit 1
fi

# 停止已有容器
echo "[1/4] 停止已有容器..."
docker compose -f docker-compose.yml.bak down 2>/dev/null || true

# 加载镜像
echo "[2/4] 加载 Docker 镜像..."
if [ -f "voxaudit_mysql.tar" ]; then
    docker load < voxaudit_mysql.tar
else
    echo "警告: voxaudit_mysql.tar 未找到"
fi

if [ -f "voxaudit_redis.tar" ]; then
    docker load < voxaudit_redis.tar
else
    echo "警告: voxaudit_redis.tar 未找到"
fi

if [ -f "voxaudit_backend.tar" ]; then
    docker load < voxaudit_backend.tar
else
    echo "警告: voxaudit_backend.tar 未找到"
fi

if [ -f "voxaudit_minio.tar" ]; then
    docker load < voxaudit_minio.tar
else
    echo "警告: voxaudit_minio.tar 未找到"
fi

if [ -f "voxaudit_frontend.tar" ]; then
    docker load < voxaudit_frontend.tar
else
    echo "警告: voxaudit_frontend.tar 未找到"
fi

# 启动服务
echo "[3/4] 启动 Docker 服务..."
docker compose -f docker-compose.yml.bak up -d

# 等待 MySQL 和 Redis 启动
echo "[4/4] 等待服务就绪..."
for i in {1..30}; do
    if docker exec voxaudit_mysql mysqladmin ping -h localhost -u root -proaxacaudit_root_2024 > /dev/null 2>&1; then
        echo "MySQL 已就绪"
        break
    fi
    echo "等待 MySQL 启动... ($i/30)"
    sleep 2
done

# 手动启动后端服务（离线镜像没有启动命令）
echo "启动后端服务..."
docker exec voxaudit_backend bash -c "cd /workspace && python -c 'import asyncio; from backend.core.database import init_db; from backend.core.seed import seed_data; asyncio.run(init_db()); asyncio.run(seed_data())' && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000" &
BACKEND_PID=$!

# 等待后端启动
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "后端服务已就绪"
        break
    fi
    echo "等待后端启动... ($i/30)"
    sleep 2
done

# 显示状态
echo ""
echo "=== Docker 容器状态 ==="
docker compose -f docker-compose.yml.bak ps

echo ""
echo "=== 访问地址 ==="
echo "前端页面: http://localhost:8888"
echo "后端API:  http://localhost:8000"
echo "API文档:  http://localhost:8000/docs"
echo "MinIO:    http://localhost:9001"
echo ""
echo "MySQL:    localhost:3307"
echo "Redis:    localhost:6379"
echo ""

echo "=== 启动完成! ==="
echo ""
echo "停止服务: docker compose -f docker-compose.yml.bak down"