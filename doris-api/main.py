"""
Doris API Gateway - 主程序
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uvicorn
import traceback
import os

from config import API_HOST, API_PORT, DORIS_CONFIG
from handlers import action_handler
from db import doris_client
from upload_handler import excel_handler
from vanna_doris import VannaDorisOpenAI

app = FastAPI(
    title="Doris API Gateway",
    description="极简的 HTTP API Gateway for Apache Doris",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 启动事件 ============

@app.on_event("startup")
async def startup_event():
    """
    应用启动时初始化数据库
    """
    import time
    import pymysql

    max_retries = 30
    retry_interval = 2

    print("=" * 60)
    print("🚀 Doris API Gateway 启动中...")
    print("=" * 60)

    # 等待 Doris FE 就绪
    for i in range(max_retries):
        try:
            print(f"⏳ 等待 Doris FE 就绪... ({i+1}/{max_retries})")

            # 尝试连接到 Doris (不指定数据库)
            conn = pymysql.connect(
                host=DORIS_CONFIG['host'],
                port=DORIS_CONFIG['port'],
                user=DORIS_CONFIG['user'],
                password=DORIS_CONFIG['password'],
                connect_timeout=5
            )

            cursor = conn.cursor()

            # 创建数据库
            db_name = DORIS_CONFIG['database']
            print(f"📦 创建数据库: {db_name}")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")

            # 验证数据库创建成功
            cursor.execute("SHOW DATABASES")
            databases = [row[0] for row in cursor.fetchall()]

            if db_name in databases:
                print(f"✅ 数据库 '{db_name}' 已就绪")
            else:
                print(f"⚠️  数据库 '{db_name}' 创建失败")

            cursor.close()
            conn.close()

            print("=" * 60)
            print("✅ Doris API Gateway 启动成功!")
            print(f"📊 数据库: {db_name}")
            print(f"🌐 API 地址: http://{API_HOST}:{API_PORT}")
            print(f"📖 API 文档: http://{API_HOST}:{API_PORT}/docs")
            print("=" * 60)
            break

        except Exception as e:
            if i < max_retries - 1:
                print(f"❌ 连接失败: {str(e)}")
                print(f"⏳ {retry_interval} 秒后重试...")
                time.sleep(retry_interval)
            else:
                print("=" * 60)
                print("❌ 无法连接到 Doris FE,请检查配置")
                print(f"错误: {str(e)}")
                print("=" * 60)
                raise


# ============ 数据模型 ============

class ExecuteRequest(BaseModel):
    """统一执行请求"""
    action: str = Field(..., description="操作类型: query/sentiment/classify/extract/stats/similarity/translate/summarize/mask/fixgrammar/generate/filter")
    table: Optional[str] = Field(None, description="表名")
    column: Optional[str] = Field(None, description="列名")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="其他参数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "sentiment",
                "table": "customer_feedback",
                "column": "feedback_text",
                "params": {
                    "limit": 50
                }
            }
        }


class LLMConfigRequest(BaseModel):
    """LLM 配置请求"""
    resource_name: str = Field(..., description="资源名称")
    provider_type: str = Field(..., description="厂商类型: openai/deepseek/qwen/zhipu/local等")
    endpoint: str = Field(..., description="API 端点")
    model_name: str = Field(..., description="模型名称")
    api_key: Optional[str] = Field(None, description="API 密钥")
    temperature: Optional[float] = Field(None, description="温度参数 0-1")
    max_tokens: Optional[int] = Field(None, description="最大 token 数")

    class Config:
        json_schema_extra = {
            "example": {
                "resource_name": "my_openai",
                "provider_type": "openai",
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "model_name": "gpt-4",
                "api_key": "sk-xxxxx"
            }
        }


class NLQueryRequest(BaseModel):
    """自然语言查询请求"""
    question: str = Field(..., description="自然语言问题")
    table_name: str = Field(..., description="目标表名")
    resource_name: Optional[str] = Field(None, description="LLM 资源名称,不指定则使用第一个可用资源")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "2022年的机构中来自于广东的有多少个?分别是来自于广东那几个城市每个城市的占比是多少?",
                "table_name": "中国环保公益组织现状调研数据2022.",
                "resource_name": "my_deepseek"
            }
        }


# ============ API 路由 ============

@app.get("/")
async def root():
    """健康检查"""
    return {
        "service": "Doris API Gateway",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """检查 Doris 连接状态"""
    try:
        result = doris_client.execute_query("SELECT 1 AS health")
        return {
            "success": True,
            "doris_connected": True,
            "message": "Doris connection OK"
        }
    except Exception as e:
        return {
            "success": False,
            "doris_connected": False,
            "error": str(e)
        }


@app.post("/api/execute")
async def execute_action(req: ExecuteRequest):
    """
    统一执行接口
    
    支持的 action:
    - query: 普通查询
    - sentiment: 情感分析
    - classify: 文本分类
    - extract: 信息提取
    - stats: 统计分析
    - similarity: 语义相似度
    - translate: 文本翻译
    - summarize: 文本摘要
    - mask: 敏感信息脱敏
    - fixgrammar: 语法纠错
    - generate: 内容生成
    - filter: 布尔过滤
    """
    try:
        # 合并参数
        params = req.params or {}
        if req.table:
            params['table'] = req.table
        if req.column:
            params['column'] = req.column
        
        # 执行操作
        result = action_handler.execute(req.action, params)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )


@app.get("/api/tables")
async def list_tables():
    """获取所有表"""
    try:
        tables = doris_client.get_tables()
        return {
            "success": True,
            "tables": tables,
            "count": len(tables)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tables/{table_name}/schema")
async def get_table_schema(table_name: str):
    """获取表结构"""
    try:
        schema = doris_client.get_table_schema(table_name)
        return {
            "success": True,
            "table": table_name,
            "schema": schema
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm/config")
async def create_llm_config(req: LLMConfigRequest):
    """创建 LLM 配置"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"=== Received request: provider={req.provider_type}, endpoint={req.endpoint}, model={req.model_name}")

        # 构造 CREATE RESOURCE SQL (Doris 4.0 使用 'ai' 类型和 'ai.' 前缀)
        properties = [
            "'type' = 'ai'",
            f"'ai.provider_type' = '{req.provider_type}'",
            f"'ai.endpoint' = '{req.endpoint}'",
            f"'ai.model_name' = '{req.model_name}'"
        ]

        if req.api_key:
            properties.append(f"'ai.api_key' = '{req.api_key}'")
        if req.temperature is not None:
            properties.append(f"'ai.temperature' = {req.temperature}")
        if req.max_tokens is not None:
            properties.append(f"'ai.max_tokens' = {req.max_tokens}")
        
        properties_str = ',\n    '.join(properties)
        
        sql = f"""
        CREATE RESOURCE '{req.resource_name}'
        PROPERTIES (
            {properties_str}
        )
        """

        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"=== Creating LLM Resource SQL: {sql}")

        doris_client.execute_update(sql)
        
        return {
            "success": True,
            "message": f"LLM resource '{req.resource_name}' created successfully",
            "sql": sql
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )


@app.get("/api/llm/config")
async def list_llm_configs():
    """获取所有 LLM 配置"""
    try:
        # Doris 4.0 的 SHOW RESOURCES 语法,使用 NAME LIKE 获取所有资源
        sql = 'SHOW RESOURCES WHERE NAME LIKE "%"'
        all_resources = doris_client.execute_query(sql)

        # SHOW RESOURCES 返回的是每个资源的每个属性作为一行
        # 需要按资源名称分组,并过滤出 AI 类型的资源
        resources_dict = {}
        for row in all_resources:
            name = row.get('Name')
            resource_type = row.get('ResourceType')

            # 只处理 AI 类型的资源
            if resource_type != 'ai':
                continue

            # 初始化资源对象 (使用前端期望的字段名)
            if name not in resources_dict:
                resources_dict[name] = {
                    'ResourceName': name,
                    'ResourceType': resource_type,
                    'properties': {}
                }

            # 收集属性
            item = row.get('Item')
            value = row.get('Value')
            if item and value:
                resources_dict[name]['properties'][item] = value

        # 转换为列表
        llm_resources = list(resources_dict.values())

        return {
            "success": True,
            "resources": llm_resources,
            "count": len(llm_resources)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm/config/{resource_name}/test")
async def test_llm_config(resource_name: str):
    """测试 LLM 配置"""
    try:
        # 使用简单的测试查询 (Doris 4.0 使用 AI_GENERATE 函数)
        sql = f"SELECT AI_GENERATE('{resource_name}', 'Hello') AS test_result"
        result = doris_client.execute_query(sql)
        
        return {
            "success": True,
            "message": "LLM resource is working",
            "test_result": result[0] if result else None
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e)
            }
        )


@app.delete("/api/llm/config/{resource_name}")
async def delete_llm_config(resource_name: str):
    """删除 LLM 配置"""
    try:
        sql = f"DROP RESOURCE '{resource_name}'"
        doris_client.execute_update(sql)

        return {
            "success": True,
            "message": f"LLM resource '{resource_name}' deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query/natural")
async def natural_language_query(request: Dict[str, Any]):
    """
    自然语言查询接口 (Agent-to-Agent) - 使用 Vanna.AI

    前端 Agent 传入自然语言问题,系统使用 Vanna.AI 生成 SQL 并执行查询

    Request Body:
        {
            "query": "2022年的机构中来自于广东的有多少个?分别是来自于广东那几个城市每个城市的占比是多少?",
            "api_key": "sk-xxx",  // 可选,默认从环境变量读取
            "model": "deepseek-chat",  // 可选,默认 deepseek-chat
            "base_url": "https://api.deepseek.com"  // 可选,默认 DeepSeek API
        }

    Response:
        {
            "success": true,
            "query": "原始问题",
            "sql": "生成的 SQL",
            "data": [...],
            "count": 数据行数
        }
    """
    try:
        query = request.get('query')
        if not query:
            raise HTTPException(status_code=400, detail="Missing 'query' parameter")

        # 获取 API 配置
        api_key = request.get('api_key') or os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')
        model = request.get('model') or os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        base_url = request.get('base_url') or os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')

        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="API key not provided. Please provide 'api_key' in request or set DEEPSEEK_API_KEY/OPENAI_API_KEY environment variable"
            )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Natural language query: {query}")
        logger.info(f"=== Using model: {model} at {base_url}")

        # 初始化 Vanna
        vanna = VannaDorisOpenAI(
            doris_client=doris_client,
            api_key=api_key,
            model=model,
            base_url=base_url,
            config={'temperature': 0.1}  # 低温度以获得更确定的结果
        )

        # 使用 Vanna 生成 SQL
        logger.info("=== Generating SQL with Vanna.AI...")
        generated_sql = vanna.generate_sql(question=query)

        logger.info(f"=== Generated SQL: {generated_sql}")

        # 执行生成的 SQL
        query_result = vanna.run_sql(generated_sql)

        logger.info(f"=== Query executed successfully, returned {len(query_result)} rows")

        return {
            "success": True,
            "query": query,
            "sql": generated_sql,
            "data": query_result,
            "count": len(query_result)
        }

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"=== Error in natural language query: {str(e)}")
        logger.error(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )


@app.post("/api/upload/preview")
async def preview_excel_file(file: UploadFile = File(...), rows: int = 10):
    """预览 Excel 文件"""
    try:
        content = await file.read()
        result = excel_handler.preview_excel(content, rows)

        return {
            "success": True,
            "filename": file.filename,
            **result
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )


@app.post("/api/upload")
async def upload_excel(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    column_mapping: Optional[str] = Form(None),
    create_table: str = Form("true")
):
    """
    上传 Excel 文件并导入到 Doris

    Args:
        file: Excel 文件
        table_name: 目标表名
        column_mapping: 列映射 JSON 字符串 (可选)
        create_table: 如果表不存在是否创建 (字符串 "true"/"false")
    """
    try:
        import json

        content = await file.read()

        # 解析列映射
        mapping = None
        if column_mapping:
            mapping = json.loads(column_mapping)

        # 转换 create_table 字符串为布尔值
        create_table_bool = create_table.lower() in ('true', '1', 'yes')

        result = excel_handler.import_excel(
            file_content=content,
            table_name=table_name,
            column_mapping=mapping,
            create_table_if_not_exists=create_table_bool
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True
    )

