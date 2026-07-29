# VoxAudit 智能语音质检系统

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-2496ed.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.4+-brightgreen.svg)](https://vuejs.org/)

基于 ASR 语音转写 + LLM AI 评分的自动化催收通话质检平台，支持录音上传、自动转写、智能评分与报告导出。

## 核心功能

- 🎙️ **自动转写**：FunASR 语音识别，支持说话人分离与时间戳，新增通过不同声道区分说话人身份
- 🤖 **AI 评分**：LLM 智能分析，根据规则描述自动打分
- 📋 **规则管理**：版本化管理，支持历史回滚与复合评分
- 📊 **统计分析**：多维度评分统计与可视化报表
- 📄 **报告导出**：一键生成 Word 格式评分报告
- ☁️ **对象存储**：MinIO / 腾讯云 COS 录音文件管理
- ⚙️ **系统设置**：支持在界面配置 ASR、LLM、OSS 等全部参数，无需手动修改配置文件

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| 后端 | FastAPI + SQLAlchemy 2.0 (async) |
| 前端 | Vue 3 + Element Plus + ECharts |
| 数据库 | MySQL (TDSQL) |
| 对象存储 | MinIO / 腾讯云 COS |
| 语音转写 | FunASR API |
| AI评分 | LLM API (MiniMax 等) |
| 部署 | Docker + Docker Compose + Nginx |

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    客户端层                              │
│              Vue 3 + Element Plus + ECharts             │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     Nginx 网关层                         │
│              (负载均衡 / 静态资源 / SSL)                  │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  后端服务     │  │  ASR 服务     │  │  数据库       │
│ FastAPI      │  │  FunASR API  │  │  MySQL/TDSQL │
│ + SQLAlchemy │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
                          │
                          ▼
                ┌──────────────────┐
                │   对象存储        │
                │  MinIO / COS     │
                └──────────────────┘
```

## 快速开始

### 环境要求

- Docker & Docker Compose
- MySQL 8.0+
- Python 3.11+ (本地开发)

### 部署

```bash
# 1. 复制环境配置
cp docker/.env.example docker/.env
# 编辑 docker/.env 填入实际配置

# 2. 启动服务
cd docker
docker-compose up -d

# 3. 访问系统
# 前端: http://localhost:8888
# 后端API: http://localhost:8000
```

### 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

## 项目结构

```
VoxAudit/
├── backend/                 # 后端服务
│   ├── api/                 # API 路由
│   ├── core/                # 核心模块（配置/数据库/初始化）
│   ├── models/              # 数据模型
│   ├── schemas/             # Pydantic 模型
│   ├── services/            # 业务服务（AI评分/ASR/OSS）
│   └── main.py              # 应用入口
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── api/             # Axios 封装
│   │   ├── views/           # 页面组件
│   │   └── router/           # 路由配置
│   └── package.json
├── docker/                  # Docker 配置
│   ├── docker-compose.yml   # 编排配置
│   ├── Dockerfile.backend   # 后端镜像
│   ├── Dockerfile.frontend  # 前端镜像
│   └── nginx.conf           # Nginx 配置
└── docs/                    # 设计文档
```

## 主要流程

### 录音质检流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 上传录音  │───▶│ 存储录音  │───▶│ ASR转写  │───▶│ AI评分   │───▶│ 完成存档  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
   │                │               │               │               │
   ▼                ▼               ▼               ▼               ▼
uploading       uploaded      transcribing       scoring          scored
                                    │
                                    ▼
                               transcribed
```

### 评分规则版本管理

```
┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐
│  创建规则v1  │───▶│ 创建规则v2   │───▶│ 旧录音自动用v1，新录音用v2    │
└─────────────┘    └─────────────┘    └─────────────────────────────┘
       │                  │
       ▼                  ▼
 is_latest=false    is_latest=true
```

## API 文档

启动服务后访问: `http://localhost:8000/docs` (Swagger UI)

## 配置说明

核心配置项（详见 `docker/.env.example`）：

| 变量 | 说明 |
|------|------|
| `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD` | 数据库连接 |
| `OSS_ENDPOINT/OSS_ACCESS_KEY/OSS_SECRET_KEY` | 对象存储 |
| `LLM_API_ENDPOINT/LLM_API_KEY/LLM_MODEL` | 大模型 API |
| `ASR_API_URL` | 语音转写服务地址 |
| `OA_BASE_URL/OA_SECRET_KEY` | OA 认证配置 |

## 常见问题

**Q: ASR 转写失败怎么排查？**
A: 检查 `ASR_API_URL` 配置是否可达，确认录音文件格式为 WAV/MP3 且编码正确。

**Q: AI 评分返回空结果？**
A: 检查 `LLM_API_KEY` 是否有效，确认规则描述是否清晰完整。

**Q: 前端无法上传录音？**
A: 检查 Nginx 配置的 `client_max_body_size`，默认最大支持 100MB 文件上传。

## License

本项目采用 [MIT License](LICENSE) 开源。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request
