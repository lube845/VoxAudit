#!/bin/bash
# VoxAudit 规则管理服务启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== VoxAudit 启动脚本 ==="
echo ""

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker 未运行，请先启动 Docker"
    exit 1
fi

# 停止已有容器
echo "[1/5] 停止已有容器..."
cd "$PROJECT_DIR"
docker compose -f docker-compose.yml.test down 2>/dev/null || true

# 启动 Docker 服务（MySQL、Redis、Backend、MinIO）
echo "[2/5] 启动 Docker 服务..."
cd "$PROJECT_DIR/docker"
# 加载 .env 文件并启动 Docker
set -a
. "$PROJECT_DIR/docker/.env"
set +a
docker compose -f docker-compose.yml.test up -d

echo "[3/5] 等待 MySQL 和 Redis 启动..."
for i in {1..30}; do
    if docker exec voxaudit_mysql mysqladmin ping -h localhost -u root -proaxacaudit_root_2024 > /dev/null 2>&1; then
        echo "MySQL 已就绪"
        break
    fi
    echo "等待 MySQL 启动... ($i/30)"
    sleep 2
done

# 检查后端健康状态
echo "[4/5] 检查后端服务..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "后端服务已就绪"
        break
    fi
    echo "等待后端启动... ($i/30)"
    sleep 2
done

# 启动前端开发服务器
echo "[5/5] 启动前端开发服务器..."
cd "$PROJECT_DIR/frontend"
nohup npm run dev > /tmp/voxaudit-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端服务 PID: $FRONTEND_PID"

# 等待前端启动
sleep 5

# 显示状态
echo ""
echo "=== Docker 容器状态 ==="
cd "$PROJECT_DIR/docker"
docker compose ps

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

# 最终健康检查
echo "=== 最终状态检查 ==="
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 后端服务:  运行中"
else
    echo "❌ 后端服务:  未响应"
fi

if curl -s http://localhost:8888 > /dev/null 2>&1; then
    echo "✅ 前端服务:  运行中"
else
    echo "⚠️  前端服务:  可能未就绪，请稍后刷新"
fi

echo ""
echo "=== 启动完成! ==="
echo ""
echo "停止服务:"
echo "  - Docker: docker compose -f docker-compose.yml.test down"
echo "  - 前端:   kill $FRONTEND_PID"
echo ""
echo "查看前端日志: tail -f /tmp/voxaudit-frontend.log"