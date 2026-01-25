# TabSis (表姐) - 智能财务数据中台

TabSis 是一个模块化的财务数据处理平台，旨在填补传统 ERP 与外部非结构化数据（发票、银行流水）之间的空白。它集成了先进的 AI Agent，提供从数据清洗、存储到智能分析的一站式解决方案。

## 🚀 核心特性

- **多租户架构**: 按“项目 -> 企业”层级管理数据，支持数据隔离。
- **发票分析**: 一键上传 Excel，自动生成销项/进项多维度分析报表。
- **银行流水**: 强大的 PDF 解析引擎，结合 OCR 与 AI 视觉模型，将非结构化流水转化为标准数据。
- **AI Agent "表姐"**: 上下文感知的智能助手，支持自然语言查询，并能直接渲染数据图表 (MCP)。
- **高性能存储**: 基于 Apache Doris，轻松应对亿级数据分析。

## 🛠️ 快速启动

### 1. 环境要求
- Docker & Docker Compose

### 2. 启动服务
```bash
# 进入项目目录
cd "e:\doris - caicai"

# 启动所有服务 (后端、前端、数据库)
docker-compose up -d
```

### 3. 访问应用
- **Web 界面**: http://localhost:5173
- **API 文档**: http://localhost:8018/docs
- **Doris 控制台**: http://localhost:18030 (User: root, Pass: empty)

## 📂 目录结构

```
e:\doris - caicai\
├── tabsis-backend/       # Python FastAPI 后端
├── tabsis-frontend/      # Vue 3 前端
├── docker-compose.yml    # 部署配置
└── # 交接说明书.md        # 详细技术文档
```

## 🔧 配置

在 `docker-compose.yml` 中配置 AI 密钥：
```yaml
environment:
  - OPENROUTER_API_KEY=sk-your-key
  - MODEL_NAME=google/gemini-2.0-flash-exp
```

## 📄 许可证
MIT License
