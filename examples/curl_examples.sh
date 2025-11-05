#!/bin/bash

# Doris Agent - cURL 调用示例
# 
# 这是一个完整的 Shell 脚本示例,展示如何使用 curl 与 Doris 数据中台交互。
# 
# 使用前请确保:
# 1. Doris 服务已启动: docker-compose up -d
# 2. 已安装 curl 和 jq (用于格式化 JSON 输出)

BASE_URL="http://localhost:8018"
API_KEY="sk-748638f482f74b7392a6dafd89bdd307"  # 替换为你的 API Key

echo "============================================================"
echo "Doris Agent - cURL 调用示例"
echo "============================================================"

# 1. 健康检查
echo -e "\n1. 健康检查..."
curl -s "${BASE_URL}/api/health" | jq '.'

# 2. 获取所有表
echo -e "\n2. 获取所有表..."
curl -s "${BASE_URL}/api/tables" | jq '.'

# 3. 自然语言查询 (使用默认 API Key)
echo -e "\n3. 自然语言查询 (使用默认 API Key)..."
curl -s -X POST "${BASE_URL}/api/query/natural" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "有哪些表?"
  }' | jq '.'

# 4. 自然语言查询 (使用自定义 API Key)
echo -e "\n4. 自然语言查询 (使用自定义 API Key)..."
curl -s -X POST "${BASE_URL}/api/query/natural" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"统计每个表的记录数\",
    \"api_key\": \"${API_KEY}\",
    \"model\": \"deepseek-chat\"
  }" | jq '.'

# 5. 执行 SQL 查询
echo -e "\n5. 执行 SQL 查询..."
curl -s -X POST "${BASE_URL}/api/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "query",
    "params": {
      "sql": "SHOW DATABASES"
    }
  }' | jq '.'

# 6. 获取表结构 (如果表存在)
echo -e "\n6. 获取表结构示例..."
echo "curl -s \"${BASE_URL}/api/tables/your_table_name/schema\" | jq '.'"

# 7. 上传 Excel 文件 (需要准备文件)
echo -e "\n7. 上传 Excel 文件示例..."
echo "curl -X POST \"${BASE_URL}/api/upload\" \\"
echo "  -F \"file=@data.xlsx\" \\"
echo "  -F \"table_name=my_table\" \\"
echo "  -F \"create_table=true\" | jq '.'"

# 8. 预览 Excel 文件
echo -e "\n8. 预览 Excel 文件示例..."
echo "curl -X POST \"${BASE_URL}/api/upload/preview\" \\"
echo "  -F \"file=@data.xlsx\" \\"
echo "  -F \"rows=10\" | jq '.'"

# 9. 创建 LLM 配置
echo -e "\n9. 创建 LLM 配置..."
curl -s -X POST "${BASE_URL}/api/llm/config" \
  -H "Content-Type: application/json" \
  -d "{
    \"resource_name\": \"my_deepseek\",
    \"provider_type\": \"deepseek\",
    \"endpoint\": \"https://api.deepseek.com/chat/completions\",
    \"model_name\": \"deepseek-chat\",
    \"api_key\": \"${API_KEY}\"
  }" | jq '.'

# 10. 获取所有 LLM 配置
echo -e "\n10. 获取所有 LLM 配置..."
curl -s "${BASE_URL}/api/llm/config" | jq '.'

echo -e "\n============================================================"
echo "✅ 示例完成!"
echo "============================================================"

