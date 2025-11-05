# Doris 数据中台 (Doris Data Platform)

基于 Apache Doris 4.0 的智能数据中台,集成 Vanna.AI Text-to-SQL 功能,支持自然语言查询。

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 8GB 可用内存

### 一键部署

```bash
# 克隆仓库
git clone https://github.com/sga-jerrylin/doris-sga.git
cd doris-sga

# 启动所有服务
docker-compose up -d

# 查看启动日志
docker-compose logs -f
```

**就这么简单!** 🎉

等待 2-3 分钟后,所有服务将自动启动并初始化。

### 访问地址

- **前端界面**: http://localhost:5173
- **API 文档**: http://localhost:8018/docs
- **Doris Web UI**: http://localhost:18030 (用户名: root, 密码: 空)

---

## 📦 系统架构

```
┌─────────────────┐
│  前端 (Vue 3)   │  ← http://localhost:5173
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API Gateway    │  ← http://localhost:8018
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Apache Doris 4.0 Cluster   │
│  ┌──────┐      ┌──────┐     │
│  │  FE  │◄────►│  BE  │     │
│  └──────┘      └──────┘     │
└─────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Vanna.AI       │  ← Text-to-SQL
│  (DeepSeek)     │
└─────────────────┘
```

---

## 🎯 核心功能

### 1. Excel 数据上传
- 拖拽上传 Excel 文件
- 自动创建表结构
- 批量导入数据

### 2. AI 自然语言查询
- 输入中文问题,自动生成 SQL
- 支持复杂统计分析
- 实时返回查询结果

### 3. LLM 配置管理
- 支持多种 AI 提供商 (OpenAI, DeepSeek, Gemini 等)
- 灵活配置 API Key 和模型
- 动态切换 AI 资源

### 4. 数据查询
- 可视化表结构浏览
- SQL 查询执行
- 结果导出

---

## 🔧 配置说明

### 环境变量

所有配置都在 `docker-compose.yml` 中:

```yaml
environment:
  # Doris 数据库配置
  - DORIS_HOST=doris-fe
  - DORIS_PORT=9030
  - DORIS_DATABASE=doris_db        # 数据库名称
  
  # DeepSeek API 配置 (可选)
  - DEEPSEEK_API_KEY=sk-your-key   # 替换为你的 API Key
  - DEEPSEEK_MODEL=deepseek-chat
  - DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 网络配置

如果遇到网络冲突错误:
```
Error: Pool overlaps with other one on this address space
```

修改 `docker-compose.yml` 中的网络段:

```yaml
networks:
  doris-network:
    ipam:
      config:
        - subnet: 192.168.88.0/24    # 改成其他未占用的网段
          gateway: 192.168.88.1
```

同时修改对应的 IP 地址:
- `FE_SERVERS=fe1:192.168.88.2:9010`
- `BE_ADDR=192.168.88.3:9050`
- `ipv4_address: 192.168.88.2` 和 `192.168.88.3`

---

## 📊 使用示例

### 1. 上传 Excel 数据

1. 打开前端界面 http://localhost:5173
2. 点击 "Excel 上传"
3. 拖拽或选择 Excel 文件
4. 输入表名,点击上传

### 2. AI 自然语言查询

1. 点击 "AI 问答"
2. 输入问题,例如:
   - "2022年的机构中来自于广东的有多少个?"
   - "每个城市的机构数量占比是多少?"
3. 点击 "执行查询"
4. 查看生成的 SQL 和结果

### 3. 配置 AI 资源

1. 点击 "LLM 配置"
2. 填写配置信息:
   - 资源名称: `my_deepseek`
   - 提供商: `deepseek`
   - API Key: `sk-your-key`
   - 模型: `deepseek-chat`
3. 点击 "创建资源"

---

## 🛠️ 常用命令

```bash
# 查看所有容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 完全清理 (包括数据卷)
docker-compose down -v

# 重新构建并启动
docker-compose up -d --build
```

---

## 🔍 故障排查

### 问题 1: BE 节点不健康

**症状**: `dependency failed to start: container doris-be is unhealthy`

**解决**:
```bash
# 查看 BE 日志
docker logs doris-be

# 手动注册 BE 节点
docker exec -it doris-fe mysql -h127.0.0.1 -P9030 -uroot -e "ALTER SYSTEM ADD BACKEND '192.168.88.3:9050';"
```

### 问题 2: 数据库不存在

**症状**: `Unknown database 'doris_db'`

**解决**: API 会在启动时自动创建数据库,如果失败,手动创建:
```bash
docker exec -it doris-fe mysql -h127.0.0.1 -P9030 -uroot -e "CREATE DATABASE IF NOT EXISTS doris_db;"
```

### 问题 3: 网络冲突

**症状**: `Pool overlaps with other one on this address space`

**解决**: 参考上面的 "网络配置" 部分修改网络段。

---

## 📝 技术栈

- **前端**: Vue 3.5 + TypeScript + Vite + Ant Design Vue
- **后端**: Python 3.11 + FastAPI + Uvicorn
- **数据库**: Apache Doris 4.0 (1 FE + 1 BE)
- **AI**: Vanna.AI + DeepSeek / OpenAI
- **部署**: Docker + Docker Compose

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

---

## 📧 联系方式

- GitHub: https://github.com/sga-jerrylin/doris-sga
- Email: jerrylin@sologenai.com

