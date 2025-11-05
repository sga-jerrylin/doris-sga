# Doris API Gateway - HTTP 调用范例

本文档提供外部 Agent 通过 HTTP 访问 Doris 数据中台的完整示例。

**API 基础地址**: `http://localhost:8018`

---

## 📋 目录

1. [健康检查](#1-健康检查)
2. [自然语言查询 (AI Agent)](#2-自然语言查询-ai-agent)
3. [Excel 数据上传](#3-excel-数据上传)
4. [数据查询](#4-数据查询)
5. [表管理](#5-表管理)
6. [LLM 配置管理](#6-llm-配置管理)

---

## 1. 健康检查

### 1.1 基础健康检查

```bash
curl http://localhost:8018/
```

**响应:**
```json
{
  "service": "Doris API Gateway",
  "status": "running",
  "version": "1.0.0"
}
```

### 1.2 Doris 连接检查

```bash
curl http://localhost:8018/api/health
```

**响应:**
```json
{
  "success": true,
  "doris_connected": true
}
```

---

## 2. 自然语言查询 (AI Agent)

**这是最核心的 Agent-to-Agent 接口!**

### 2.1 使用默认 API Key (环境变量配置)

```bash
curl -X POST http://localhost:8018/api/query/natural \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2022年的机构中来自于广东的有多少个?"
  }'
```

### 2.2 使用自定义 API Key

```bash
curl -X POST http://localhost:8018/api/query/natural \
  -H "Content-Type: application/json" \
  -d '{
    "query": "每个城市的机构数量占比是多少?",
    "api_key": "sk-your-deepseek-api-key",
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com"
  }'
```

### 2.3 Python 示例

```python
import requests

url = "http://localhost:8018/api/query/natural"

# 方式 1: 使用默认配置
response = requests.post(url, json={
    "query": "统计每个省份的机构数量"
})

# 方式 2: 使用自定义 API Key
response = requests.post(url, json={
    "query": "统计每个省份的机构数量",
    "api_key": "sk-your-deepseek-api-key",
    "model": "deepseek-chat"
})

result = response.json()
print(f"生成的 SQL: {result['sql']}")
print(f"查询结果: {result['data']}")
print(f"记录数: {result['count']}")
```

### 2.4 JavaScript 示例

```javascript
// 使用 fetch API
const response = await fetch('http://localhost:8018/api/query/natural', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: '2022年的机构中来自于广东的有多少个?',
    api_key: 'sk-your-deepseek-api-key'  // 可选
  })
});

const result = await response.json();
console.log('生成的 SQL:', result.sql);
console.log('查询结果:', result.data);
console.log('记录数:', result.count);
```

### 2.5 响应示例

```json
{
  "success": true,
  "query": "2022年的机构中来自于广东的有多少个?",
  "sql": "SELECT COUNT(*) as count FROM institutions WHERE year = 2022 AND province = '广东'",
  "data": [
    {
      "count": 156
    }
  ],
  "count": 1
}
```

---

## 3. Excel 数据上传

### 3.1 预览 Excel 文件

```bash
curl -X POST http://localhost:8018/api/upload/preview \
  -F "file=@/path/to/your/data.xlsx" \
  -F "rows=10"
```

### 3.2 上传并创建表

```bash
curl -X POST http://localhost:8018/api/upload \
  -F "file=@/path/to/your/data.xlsx" \
  -F "table_name=my_table" \
  -F "create_table=true"
```

### 3.3 Python 示例

```python
import requests

url = "http://localhost:8018/api/upload"

# 上传 Excel 文件
with open('data.xlsx', 'rb') as f:
    files = {'file': ('data.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    data = {
        'table_name': 'institutions',
        'create_table': 'true'
    }
    response = requests.post(url, files=files, data=data)

result = response.json()
print(f"上传成功: {result['success']}")
print(f"表名: {result['table_name']}")
print(f"导入行数: {result['rows_imported']}")
```

### 3.4 JavaScript 示例 (Node.js)

```javascript
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('data.xlsx'));
form.append('table_name', 'institutions');
form.append('create_table', 'true');

const response = await fetch('http://localhost:8018/api/upload', {
  method: 'POST',
  body: form
});

const result = await response.json();
console.log('上传结果:', result);
```

### 3.5 响应示例

```json
{
  "success": true,
  "message": "数据上传成功",
  "table_name": "institutions",
  "rows_imported": 1500,
  "columns": ["id", "name", "province", "city", "year"]
}
```

---

## 4. 数据查询

### 4.1 执行 SQL 查询

```bash
curl -X POST http://localhost:8018/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action": "query",
    "params": {
      "sql": "SELECT * FROM institutions LIMIT 10"
    }
  }'
```

### 4.2 Python 示例

```python
import requests

url = "http://localhost:8018/api/execute"

# 执行查询
response = requests.post(url, json={
    "action": "query",
    "params": {
        "sql": "SELECT province, COUNT(*) as count FROM institutions GROUP BY province"
    }
})

result = response.json()
print(result['data'])
```

### 4.3 响应示例

```json
{
  "success": true,
  "action": "query",
  "data": [
    {"province": "广东", "count": 156},
    {"province": "北京", "count": 89},
    {"province": "上海", "count": 72}
  ],
  "count": 3
}
```

---

## 5. 表管理

### 5.1 获取所有表

```bash
curl http://localhost:8018/api/tables
```

**Python:**
```python
response = requests.get("http://localhost:8018/api/tables")
tables = response.json()['tables']
print(tables)
```

**响应:**
```json
{
  "success": true,
  "tables": ["institutions", "customers", "orders"]
}
```

### 5.2 获取表结构

```bash
curl http://localhost:8018/api/tables/institutions/schema
```

**Python:**
```python
response = requests.get("http://localhost:8018/api/tables/institutions/schema")
schema = response.json()['schema']
for col in schema:
    print(f"{col['Field']}: {col['Type']}")
```

**响应:**
```json
{
  "success": true,
  "table": "institutions",
  "schema": [
    {"Field": "id", "Type": "INT", "Null": "NO", "Key": "PRI"},
    {"Field": "name", "Type": "VARCHAR(255)", "Null": "YES", "Key": ""},
    {"Field": "province", "Type": "VARCHAR(50)", "Null": "YES", "Key": ""},
    {"Field": "city", "Type": "VARCHAR(50)", "Null": "YES", "Key": ""}
  ]
}
```

---

## 6. LLM 配置管理

### 6.1 创建 LLM 配置

```bash
curl -X POST http://localhost:8018/api/llm/config \
  -H "Content-Type: application/json" \
  -d '{
    "resource_name": "my_deepseek",
    "provider_type": "deepseek",
    "endpoint": "https://api.deepseek.com/chat/completions",
    "model_name": "deepseek-chat",
    "api_key": "sk-your-api-key"
  }'
```

### 6.2 获取所有 LLM 配置

```bash
curl http://localhost:8018/api/llm/config
```

### 6.3 测试 LLM 配置

```bash
curl -X POST http://localhost:8018/api/llm/config/my_deepseek/test
```

### 6.4 删除 LLM 配置

```bash
curl -X DELETE http://localhost:8018/api/llm/config/my_deepseek
```

---

## 🚀 完整 Agent 调用示例

### Python Agent 示例

```python
import requests

class DorisAgent:
    def __init__(self, base_url="http://localhost:8018", api_key=None):
        self.base_url = base_url
        self.api_key = api_key
    
    def ask(self, question: str):
        """使用自然语言提问"""
        url = f"{self.base_url}/api/query/natural"
        payload = {"query": question}
        if self.api_key:
            payload["api_key"] = self.api_key
        
        response = requests.post(url, json=payload)
        return response.json()
    
    def upload_data(self, file_path: str, table_name: str):
        """上传 Excel 数据"""
        url = f"{self.base_url}/api/upload"
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'table_name': table_name, 'create_table': 'true'}
            response = requests.post(url, files=files, data=data)
        return response.json()
    
    def query(self, sql: str):
        """执行 SQL 查询"""
        url = f"{self.base_url}/api/execute"
        response = requests.post(url, json={
            "action": "query",
            "params": {"sql": sql}
        })
        return response.json()

# 使用示例
agent = DorisAgent(api_key="sk-your-deepseek-api-key")

# 1. 上传数据
result = agent.upload_data("institutions.xlsx", "institutions")
print(f"上传成功: {result['rows_imported']} 行")

# 2. 自然语言查询
result = agent.ask("2022年广东省有多少个机构?")
print(f"SQL: {result['sql']}")
print(f"结果: {result['data']}")

# 3. 直接 SQL 查询
result = agent.query("SELECT * FROM institutions LIMIT 5")
print(f"查询结果: {result['data']}")
```

---

## 📝 错误处理

所有 API 在出错时返回标准错误格式:

```json
{
  "detail": {
    "error": "错误信息",
    "traceback": "详细堆栈信息"
  }
}
```

**Python 错误处理示例:**

```python
try:
    response = requests.post(url, json=payload)
    response.raise_for_status()
    result = response.json()
except requests.exceptions.HTTPError as e:
    error_detail = e.response.json().get('detail', {})
    print(f"错误: {error_detail.get('error', str(e))}")
```

---

## 🔐 认证 (可选)

当前版本不需要认证。如果需要添加认证,可以在请求头中添加:

```bash
curl -H "Authorization: Bearer your-token" \
  http://localhost:8018/api/query/natural
```

---

## 📖 API 文档

完整的交互式 API 文档:
- **Swagger UI**: http://localhost:8018/docs
- **ReDoc**: http://localhost:8018/redoc

