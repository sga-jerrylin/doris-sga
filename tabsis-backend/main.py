"""
Doris API Gateway - 主程序
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uvicorn
import traceback
import os
import json
from io import BytesIO
from datetime import datetime, timedelta
from pymysql.err import OperationalError

from config import API_HOST, API_PORT, DORIS_CONFIG
from handlers import action_handler
from db import doris_client, project_db_name, ensure_project_db
from upload_handler import excel_handler
from invoice_handler import invoice_handler
from bank_handler import bank_handler
from agent_handler import agent_handler
from vanna_doris import VannaDorisOpenAI



from metadata_db import init_metadata_db, close_metadata_db
from metadata_models import (
    Project,
    Company,
    InvoiceProject,
    InvoiceUpload,
    ProjectLLMConfig,
    ProjectAgentPrompt,
    ChatSession,
    ChatMessage,
    Project_Pydantic,
    ProjectIn_Pydantic,
    Company_Pydantic,
    CompanyIn_Pydantic,
    InvoiceProject_Pydantic,
    InvoiceProjectIn_Pydantic,
    InvoiceUpload_Pydantic,
    ProjectLLMConfig_Pydantic,
    ProjectAgentPrompt_Pydantic,
    ChatSession_Pydantic,
    ChatMessage_Pydantic,
)


app = FastAPI(
    title="Doris API Gateway",
    description="极简的 HTTP API Gateway for Apache Doris",
    version="1.0.0"
)


def _normalize_base_url(base_url: str) -> str:
    if not base_url:
        return ""
    url = base_url.rstrip("/")
    for suffix in ("/chat/completions", "/v1/chat/completions"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url


def _read_default_agent_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "project_agent_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

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
    应用启动时初始化数据库并预热缓存
    """
    # 初始化 SQLite 元数据数据库
    await init_metadata_db()

    import time
    import pymysql

    max_retries = 1
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

            # ========== 新增：启动预热 ==========
            print("🔥 开始预热项目数据缓存...")
            try:
                await _warmup_project_caches()
                print("✅ 缓存预热完成")
            except Exception as warmup_error:
                print(f"⚠️ 缓存预热失败（不影响启动）: {warmup_error}")
            # ===================================

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
                print("⚠️ 无法连接到 Doris FE，将以 [元数据模式] 启动")
                print(f"错误: {str(e)}")
                print("注意: 发票分析和银行流水模块可能无法正常工作")
                print("=" * 60)
                # raise  <-- Commented out to allow startup


async def _warmup_project_caches():
    """
    启动时预热所有项目的表和schema缓存
    """
    from metadata_models import Project

    # 获取所有项目
    projects = await Project.all()

    if not projects:
        print("  ℹ️  暂无项目，跳过预热")
        return

    print(f"  📋 发现 {len(projects)} 个项目，开始预热...")

    for project in projects:
        try:
            db_name = ensure_project_db(project.id)
            # 预加载表列表（会触发缓存）
            tables = doris_client.get_tables(database=db_name)
            print(f"  ✓ 项目 #{project.id} ({project.name}): {len(tables)} 张表")

            # 预加载部分表的schema（避免启动时间过长，只加载前5张表）
            for table in tables[:5]:
                try:
                    doris_client.get_table_schema(table, database=db_name)
                except Exception:
                    pass

        except Exception as e:
            print(f"  ✗ 项目 #{project.id} 预热失败: {e}")
            continue


@app.on_event("shutdown")
async def shutdown_event():
    await close_metadata_db()

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


class ProjectLLMConfigRequest(BaseModel):
    provider_type: str
    endpoint: str
    model_name: str
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ProjectAgentPromptRequest(BaseModel):
    prompt: str


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
async def list_tables(project_id: Optional[int] = None):
    """获取所有表"""
    try:
        db_name = ensure_project_db(int(project_id)) if project_id else None
        tables = doris_client.get_tables(database=db_name)
        return {
            "success": True,
            "tables": tables,
            "count": len(tables)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tables/{table_name}/schema")
async def get_table_schema(table_name: str, project_id: Optional[int] = None):
    """获取表结构"""
    try:
        db_name = ensure_project_db(int(project_id)) if project_id else None
        schema = doris_client.get_table_schema(table_name, database=db_name)
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
    Natural language query endpoint (agent-to-agent).
    """
    try:
        query = request.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Missing 'query' parameter")

        project_id = request.get("project_id")
        db_name = ensure_project_db(int(project_id)) if project_id else None

        project_cfg = None
        if project_id:
            project_cfg = await ProjectLLMConfig.filter(project_id=int(project_id)).first()

        api_key = request.get("api_key") or (project_cfg.api_key if project_cfg else None) or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = request.get("model") or (project_cfg.model_name if project_cfg else None) or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        base_url = request.get("base_url") or (project_cfg.endpoint if project_cfg else None) or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="API key not provided. Please provide 'api_key' in request or set DEEPSEEK_API_KEY/OPENAI_API_KEY environment variable",
            )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Natural language query: {query}")
        logger.info(f"=== Using model: {model} at {base_url}")

        allowed_tables = None
        prompt_query = query
        if db_name:
            allowed_tables = set(doris_client.get_tables(database=db_name))
            if allowed_tables:
                prompt_query = f"Only use these tables to generate SQL: {', '.join([f'`{t}`' for t in sorted(allowed_tables)])}. Question: {query}"

        vanna = VannaDorisOpenAI(
            doris_client=doris_client,
            api_key=api_key,
            model=model,
            base_url=base_url,
            config={"temperature": (project_cfg.temperature if project_cfg and project_cfg.temperature is not None else 0.1)},
            database=db_name,
        )

        logger.info("=== Generating SQL with Vanna.AI...")
        generated_sql = vanna.generate_sql(question=prompt_query)
        logger.info(f"=== Generated SQL: {generated_sql}")

        generated_sql = _strip_db_prefix(generated_sql, {db_name, DORIS_CONFIG.get("database")})
        safe_sql = _validate_generated_sql(generated_sql, allowed_tables)
        query_result = vanna.run_sql(safe_sql)
        logger.info(f"=== Query executed successfully, returned {len(query_result)} rows")

        return {
            "success": True,
            "query": query,
            "sql": safe_sql,
            "data": query_result,
            "count": len(query_result),
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
            detail={"error": str(e), "traceback": traceback.format_exc()},
        )


@app.post("/api/upload/preview")
async def preview_excel_file(file: UploadFile = File(...), rows: int = Form(10)):
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


# ============ Project & Company APIs ============

@app.get("/api/projects", response_model=List[Project_Pydantic])
async def get_projects():
    return await Project_Pydantic.from_queryset(Project.all())

@app.post("/api/projects", response_model=Project_Pydantic)
async def create_project(project: ProjectIn_Pydantic):
    obj = await Project.create(**project.dict(exclude_unset=True))
    try:
        ensure_project_db(obj.id)
    except Exception as e:
        print(f"[Project] ensure db failed: {e}")
    return await Project_Pydantic.from_tortoise_orm(obj)

@app.get("/api/projects/{project_id}", response_model=Project_Pydantic)
async def get_project(project_id: int):
    return await Project_Pydantic.from_queryset_single(Project.get(id=project_id))

@app.post("/api/projects/{project_id}/reset-db")
async def reset_project_database(project_id: int, clear_uploads: bool = True):
    """Drop and recreate project database, and reset related metadata."""
    await Project.get(id=project_id)
    db_name = project_db_name(project_id)
    doris_reset = True
    doris_error = None
    import time
    for attempt in range(3):
        try:
            doris_client.drop_database_if_exists(db_name)
            doris_client.create_database_if_not_exists(db_name)
            doris_error = None
            doris_reset = True
            break
        except Exception as e:
            doris_reset = False
            doris_error = str(e)
            if attempt < 2:
                time.sleep(2)

    # reset invoice metadata
    await InvoiceProject.filter(project_id=project_id).update(
        sales_raw_table=None,
        purchase_raw_table=None,
        derived_table_1=None,
        derived_table_2=None,
        derived_table_3=None,
        derived_table_4=None,
        derived_table_5=None,
        sales_uploaded_at=None,
        purchase_uploaded_at=None,
        derived_generated_at=None,
    )

    if clear_uploads:
        invoice_project_ids = await InvoiceProject.filter(project_id=project_id).values_list("id", flat=True)
        if invoice_project_ids:
            await InvoiceUpload.filter(invoice_project_id__in=list(invoice_project_ids)).delete()
        await InvoiceProject.filter(project_id=project_id).delete()

    return {"success": True, "database": db_name, "doris_reset": doris_reset, "doris_error": doris_error}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int):
    await Project.filter(id=project_id).delete()
    return {"success": True}

@app.get("/api/projects/{project_id}/companies", response_model=List[Company_Pydantic])
async def get_project_companies(project_id: int):
    return await Company_Pydantic.from_queryset(Company.filter(project_id=project_id))

@app.post("/api/projects/{project_id}/companies", response_model=Company_Pydantic)
async def create_company(project_id: int, company: CompanyIn_Pydantic):
    # Ensure project exists
    await Project.get(id=project_id)
    obj = await Company.create(project_id=project_id, **company.dict(exclude_unset=True))
    return await Company_Pydantic.from_tortoise_orm(obj)

@app.get("/api/companies/{company_id}", response_model=Company_Pydantic)
async def get_company(company_id: int):
    return await Company_Pydantic.from_queryset_single(Company.get(id=company_id))

@app.put("/api/companies/{company_id}", response_model=Company_Pydantic)
async def update_company(company_id: int, company: CompanyIn_Pydantic):
    await Company.filter(id=company_id).update(**company.dict(exclude_unset=True))
    return await Company_Pydantic.from_queryset_single(Company.get(id=company_id))

@app.delete("/api/companies/{company_id}")
async def delete_company(company_id: int):
    await Company.filter(id=company_id).delete()
    return {"success": True}


@app.get("/api/projects/{project_id}/llm-config")
async def get_project_llm_config(project_id: int):
    await Project.get(id=project_id)
    cfg = await ProjectLLMConfig.filter(project_id=project_id).first()
    if not cfg:
        return {"success": True, "config": None}
    data = await ProjectLLMConfig_Pydantic.from_tortoise_orm(cfg)
    return {"success": True, "config": data}


@app.put("/api/projects/{project_id}/llm-config")
async def upsert_project_llm_config(project_id: int, req: ProjectLLMConfigRequest):
    await Project.get(id=project_id)
    payload = req.dict(exclude_unset=True)
    existing = await ProjectLLMConfig.filter(project_id=project_id).first()
    if existing:
        await ProjectLLMConfig.filter(id=existing.id).update(**payload)
        cfg = await ProjectLLMConfig.get(id=existing.id)
    else:
        cfg = await ProjectLLMConfig.create(project_id=project_id, **payload)
    data = await ProjectLLMConfig_Pydantic.from_tortoise_orm(cfg)
    return {"success": True, "config": data}


@app.post("/api/projects/{project_id}/llm-config/test")
async def test_project_llm_config(project_id: int, req: ProjectLLMConfigRequest):
    await Project.get(id=project_id)
    if not req.api_key:
        raise HTTPException(status_code=400, detail={"error": "API key is required"})

    try:
        from openai import OpenAI

        base_url = _normalize_base_url(req.endpoint) or req.endpoint
        client = OpenAI(api_key=req.api_key, base_url=base_url)
        client.chat.completions.create(
            model=req.model_name,
            messages=[{"role": "user", "content": "ping"}],
            temperature=req.temperature if req.temperature is not None else 0,
            max_tokens=min(req.max_tokens or 16, 64),
        )
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})


@app.delete("/api/projects/{project_id}/llm-config")
async def delete_project_llm_config(project_id: int):
    await Project.get(id=project_id)
    await ProjectLLMConfig.filter(project_id=project_id).delete()
    return {"success": True}


@app.get("/api/projects/{project_id}/agent-prompt")
async def get_project_agent_prompt(project_id: int):
    await Project.get(id=project_id)
    cfg = await ProjectAgentPrompt.filter(project_id=project_id).first()
    if cfg:
        data = await ProjectAgentPrompt_Pydantic.from_tortoise_orm(cfg)
        return {"success": True, "prompt": data.prompt, "source": "project"}
    return {"success": True, "prompt": _read_default_agent_prompt(), "source": "default"}


@app.put("/api/projects/{project_id}/agent-prompt")
async def upsert_project_agent_prompt(project_id: int, req: ProjectAgentPromptRequest):
    await Project.get(id=project_id)
    prompt_text = (req.prompt or "").strip()
    existing = await ProjectAgentPrompt.filter(project_id=project_id).first()
    if existing:
        await ProjectAgentPrompt.filter(id=existing.id).update(prompt=prompt_text)
        cfg = await ProjectAgentPrompt.get(id=existing.id)
    else:
        cfg = await ProjectAgentPrompt.create(project_id=project_id, prompt=prompt_text)
    data = await ProjectAgentPrompt_Pydantic.from_tortoise_orm(cfg)
    return {"success": True, "prompt": data.prompt, "source": "project"}


@app.delete("/api/projects/{project_id}/agent-prompt")
async def delete_project_agent_prompt(project_id: int):
    await Project.get(id=project_id)
    await ProjectAgentPrompt.filter(project_id=project_id).delete()
    return {"success": True, "prompt": _read_default_agent_prompt(), "source": "default"}

# ============ Invoice Project APIs ============

@app.get(
    "/api/projects/{project_id}/companies/{company_id}/invoice-projects",
    response_model=List[InvoiceProject_Pydantic],
)
async def list_invoice_projects(project_id: int, company_id: int):
    await Project.get(id=project_id)
    await Company.get(id=company_id, project_id=project_id)
    return await InvoiceProject_Pydantic.from_queryset(
        InvoiceProject.filter(project_id=project_id, company_id=company_id).order_by("-id")
    )


@app.post(
    "/api/projects/{project_id}/companies/{company_id}/invoice-projects",
    response_model=InvoiceProject_Pydantic,
)
async def create_invoice_project(project_id: int, company_id: int, invoice_project: InvoiceProjectIn_Pydantic):
    await Project.get(id=project_id)
    await Company.get(id=company_id, project_id=project_id)
    payload = invoice_project.dict(exclude_unset=True)
    payload.pop("project_id", None)
    payload.pop("company_id", None)
    obj = await InvoiceProject.create(project_id=project_id, company_id=company_id, **payload)
    return await InvoiceProject_Pydantic.from_tortoise_orm(obj)


@app.get("/api/invoice-projects/{invoice_project_id}", response_model=InvoiceProject_Pydantic)
async def get_invoice_project(invoice_project_id: int):
    return await InvoiceProject_Pydantic.from_queryset_single(InvoiceProject.get(id=invoice_project_id))


@app.delete("/api/invoice-projects/{invoice_project_id}")
async def delete_invoice_project(invoice_project_id: int):
    await InvoiceProject.filter(id=invoice_project_id).delete()
    return {"success": True}


@app.get("/api/modules/invoice/projects/{invoice_project_id}/uploads")
async def list_invoice_uploads(invoice_project_id: int):
    await InvoiceProject.get(id=invoice_project_id)
    uploads = await InvoiceUpload.filter(invoice_project_id=invoice_project_id).order_by("-id").values(
        "id",
        "direction",
        "filename",
        "file_size",
        "row_count",
        "status",
        "error_message",
        "created_at",
    )
    for row in uploads:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
    return uploads

# ============ Module APIs ============

def _month_range(anchor: datetime) -> tuple[datetime, datetime]:
    start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end

def _safe_scalar(sql: str, default: Any = 0, database: Optional[str] = None):
    try:
        res = doris_client.execute_query(sql, database=database)
        if not res:
            return default
        val = next(iter(res[0].values()))
        return default if val is None else val
    except Exception:
        return default

def _strip_db_prefix(sql: str, allowed_db_names: Optional[set]) -> str:
    if not sql or not allowed_db_names:
        return sql
    cleaned = sql
    import re
    for db_name in allowed_db_names:
        if not db_name:
            continue
        pattern = re.compile(
            rf"\b{re.escape(db_name)}\s*\.\s*`?([A-Za-z0-9_]+)`?",
            re.IGNORECASE,
        )
        cleaned = re.sub(pattern, r"`\1`", cleaned)
    return cleaned


def _validate_generated_sql(sql: str, allowed_tables: Optional[set] = None) -> str:
    sql_clean = (sql or '').strip().rstrip(';')
    if not sql_clean:
        raise HTTPException(status_code=400, detail={'error': 'Empty SQL', 'sql': sql})
    if ';' in sql_clean:
        raise HTTPException(status_code=400, detail={'error': 'Only single-statement SQL allowed', 'sql': sql})
    sql_upper = sql_clean.upper()
    if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
        raise HTTPException(status_code=400, detail={'error': 'Only SELECT statements allowed', 'sql': sql})
    forbidden = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
    if any(f in sql_upper for f in forbidden):
        raise HTTPException(status_code=400, detail={'error': 'Forbidden SQL keyword detected', 'sql': sql})
    import re
    if allowed_tables:
        referenced = set(re.findall(r'(?:FROM|JOIN)\s+`?([A-Za-z0-9_]+)`?', sql_clean, flags=re.IGNORECASE))
        illegal = sorted([t for t in referenced if t not in allowed_tables])
        if illegal:
            raise HTTPException(status_code=400, detail={'error': 'SQL references non-project tables', 'illegal_tables': illegal, 'sql': sql})
    return sql_clean


@app.get("/api/projects/{project_id}/companies/{company_id}/dashboard")
async def get_company_dashboard(project_id: int, company_id: int):
    await Project.get(id=project_id)
    await Company.get(id=company_id, project_id=project_id)

    invoice_project = (
        await InvoiceProject.filter(project_id=project_id, company_id=company_id)
        .order_by("-id")
        .first()
    )

    try:
        db_name = ensure_project_db(project_id)
        tables = set(doris_client.get_tables(database=db_name))
    except Exception:
        tables = set()

    sales_table = None
    purchase_table = None
    if invoice_project:
        sales_table = invoice_project.sales_raw_table or invoice_handler._build_raw_table_name(
            project_id, company_id, invoice_project.id, "sales"
        )
        purchase_table = invoice_project.purchase_raw_table or invoice_handler._build_raw_table_name(
            project_id, company_id, invoice_project.id, "purchase"
        )

    def table_exists(name: Optional[str]) -> bool:
        return bool(name and name in tables)

    now = datetime.utcnow()
    cur_start, cur_end = _month_range(now)
    prev_start = (cur_start - timedelta(days=1)).replace(day=1)
    prev_end = cur_start

    def sum_amount(table_name: str, start: datetime, end: datetime) -> float:
        sql = (
            f"SELECT COALESCE(SUM(amount_with_tax), 0) AS total "
            f"FROM `{table_name}` "
            f"WHERE is_valid = 1 AND invoice_date >= '{start:%Y-%m-%d %H:%M:%S}' "
            f"AND invoice_date < '{end:%Y-%m-%d %H:%M:%S}'"
        )
        return float(_safe_scalar(sql, 0, database=db_name) or 0)

    def count_invalid(table_name: str, start: datetime, end: datetime) -> int:
        sql = (
            f"SELECT COALESCE(SUM(CASE WHEN is_valid = 0 OR is_valid IS NULL THEN 1 ELSE 0 END), 0) AS cnt "
            f"FROM `{table_name}` "
            f"WHERE invoice_date >= '{start:%Y-%m-%d %H:%M:%S}' "
            f"AND invoice_date < '{end:%Y-%m-%d %H:%M:%S}'"
        )
        return int(_safe_scalar(sql, 0, database=db_name) or 0)

    monthly_purchase_total = 0.0
    monthly_sales_total = 0.0
    purchase_mom = None
    sales_mom = None
    pending_exceptions = 0

    if table_exists(purchase_table):
        monthly_purchase_total = sum_amount(purchase_table, cur_start, cur_end)
        prev_purchase = sum_amount(purchase_table, prev_start, prev_end)
        if prev_purchase > 0:
            purchase_mom = (monthly_purchase_total - prev_purchase) / prev_purchase
        pending_exceptions += count_invalid(purchase_table, cur_start, cur_end)

    if table_exists(sales_table):
        monthly_sales_total = sum_amount(sales_table, cur_start, cur_end)
        prev_sales = sum_amount(sales_table, prev_start, prev_end)
        if prev_sales > 0:
            sales_mom = (monthly_sales_total - prev_sales) / prev_sales
        pending_exceptions += count_invalid(sales_table, cur_start, cur_end)

    bank_balance = None
    bank_table = None
    bank_tables = [t for t in tables if t.startswith(f"bank_statement_{project_id}_{company_id}_")]
    if bank_tables:
        def extract_ts(name: str) -> int:
            try:
                return int(name.rsplit("_", 1)[-1])
            except Exception:
                return 0
        bank_table = max(bank_tables, key=extract_ts)
        sql = f"SELECT balance FROM `{bank_table}` ORDER BY trans_date DESC, id DESC LIMIT 1"
        bank_balance = _safe_scalar(sql, None, database=db_name)
        bank_balance = float(bank_balance) if bank_balance is not None else None

    activities = []
    if invoice_project:
        if invoice_project.sales_uploaded_at:
            activities.append({
                "type": "upload",
                "text": "Sales invoice uploaded",
                "time": invoice_project.sales_uploaded_at.isoformat()
            })
        if invoice_project.purchase_uploaded_at:
            activities.append({
                "type": "upload",
                "text": "Purchase invoice uploaded",
                "time": invoice_project.purchase_uploaded_at.isoformat()
            })
        if invoice_project.derived_generated_at:
            activities.append({
                "type": "success",
                "text": "Invoice analysis generated",
                "time": invoice_project.derived_generated_at.isoformat()
            })

    if bank_table:
        bank_time = _safe_scalar(f"SELECT MAX(created_at) AS last_time FROM `{bank_table}`", None, database=db_name)
        if bank_time:
            try:
                bank_time_str = bank_time.isoformat()
            except Exception:
                bank_time_str = str(bank_time)
            activities.append({
                "type": "upload",
                "text": "Bank statement processed",
                "time": bank_time_str
            })

    activities = sorted(
        [a for a in activities if a.get("time")],
        key=lambda x: x["time"],
        reverse=True
    )

    return {
        "success": True,
        "metrics": {
            "monthly_purchase_total": monthly_purchase_total,
            "monthly_purchase_mom": purchase_mom,
            "monthly_sales_total": monthly_sales_total,
            "monthly_sales_mom": sales_mom,
            "pending_exceptions": pending_exceptions,
            "bank_balance": bank_balance,
        },
        "activities": activities,
        "sources": {
            "invoice_project_id": invoice_project.id if invoice_project else None,
            "sales_table": sales_table if table_exists(sales_table) else None,
            "purchase_table": purchase_table if table_exists(purchase_table) else None,
            "bank_table": bank_table,
        },
        "generated_at": now.isoformat()
    }

@app.post("/api/modules/invoice/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    project_id: Optional[int] = Form(None),
    company_id: Optional[int] = Form(None),
    invoice_project_id: Optional[int] = Form(None),
    direction: Optional[str] = Form(None),
):
    """上传并分析发票"""
    if invoice_project_id:
        invoice_project = await InvoiceProject.get(id=invoice_project_id)
        project_id = invoice_project.project_id
        company_id = invoice_project.company_id
    if not project_id or not company_id:
        raise HTTPException(status_code=400, detail="Missing 'project_id'/'company_id' or 'invoice_project_id'")

    direction_hint = direction
    if not direction_hint and file.filename:
        direction_hint = invoice_handler._detect_direction(file.filename)

    if invoice_project_id and file.filename:
        if direction_hint and direction_hint != "unknown":
            duplicate = await InvoiceUpload.filter(
                invoice_project_id=invoice_project_id,
                direction=direction_hint,
                filename=file.filename,
                status="success",
            ).first()
        else:
            duplicate = await InvoiceUpload.filter(
                invoice_project_id=invoice_project_id,
                filename=file.filename,
                status="success",
            ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="该文件已上传，请勿重复上传")

    content = await file.read()
    try:
        result = invoice_handler.process_invoice_file(
            content,
            project_id,
            company_id,
            invoice_project_id=invoice_project_id,
            direction=direction,
            filename=file.filename,
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Invoice upload error: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"[InvoiceUpload] Error: {str(e)}")
        print(traceback.format_exc())
        if invoice_project_id and file.filename:
            failed_direction = direction_hint or "unknown"
            payload = {
                "file_size": len(content) if content else None,
                "row_count": None,
                "status": "failed",
                "error_message": str(e),
            }
            existing = await InvoiceUpload.filter(
                invoice_project_id=invoice_project_id,
                direction=failed_direction,
                filename=file.filename,
            ).first()
            if existing:
                await InvoiceUpload.filter(id=existing.id).update(**payload)
            else:
                await InvoiceUpload.create(
                    invoice_project_id=invoice_project_id,
                    direction=failed_direction,
                    filename=file.filename,
                    **payload,
                )
        raise HTTPException(status_code=500, detail={"error": str(e), "traceback": traceback.format_exc()})

    if invoice_project_id and result.get("success"):
        from datetime import datetime

        updates: Dict[str, Any] = {}
        raw_table = result.get("raw_table_name")
        uploaded_direction = result.get("direction")
        if uploaded_direction == "sales":
            updates["sales_raw_table"] = raw_table
            updates["sales_uploaded_at"] = datetime.utcnow()
        elif uploaded_direction == "purchase":
            updates["purchase_raw_table"] = raw_table
            updates["purchase_uploaded_at"] = datetime.utcnow()

        derived_tables = result.get("derived_tables") or {}
        if derived_tables:
            updates["derived_table_1"] = derived_tables.get("table1")
            updates["derived_table_2"] = derived_tables.get("table2")
            updates["derived_table_3"] = derived_tables.get("table3")
            updates["derived_table_4"] = derived_tables.get("table4")
            updates["derived_table_5"] = derived_tables.get("table5")
            updates["derived_generated_at"] = datetime.utcnow()

        if updates:
            await InvoiceProject.filter(id=invoice_project_id).update(**updates)

        if file.filename:
            uploaded_direction = result.get("direction") or direction_hint or "unknown"
            payload = {
                "file_size": len(content) if content else None,
                "row_count": result.get("row_count"),
                "status": "success",
                "error_message": None,
            }
            existing = await InvoiceUpload.filter(
                invoice_project_id=invoice_project_id,
                direction=uploaded_direction,
                filename=file.filename,
            ).first()
            if existing:
                await InvoiceUpload.filter(id=existing.id).update(**payload)
            else:
                await InvoiceUpload.create(
                    invoice_project_id=invoice_project_id,
                    direction=uploaded_direction,
                    filename=file.filename,
                    **payload,
                )
    return result

@app.post("/api/modules/bank/upload")
async def upload_bank_statement(
    file: UploadFile = File(...),
    project_id: int = Form(...),
    company_id: int = Form(...)
):
    """上传并分析银行流水 PDF"""
    content = await file.read()
    result = bank_handler.process_bank_statement(content, project_id, company_id)
    return result

@app.get("/api/modules/invoice/projects/{invoice_project_id}/export")
async def export_invoice_project(invoice_project_id: int):
    items = "sales_raw,purchase_raw,table1,table2,table3,table4,table5"
    return await export_invoice_project_selected(invoice_project_id, items)


@app.get("/api/modules/invoice/projects/{invoice_project_id}/export-selected")
async def export_invoice_project_selected(invoice_project_id: int, items: str = ""):
    invoice_project = await InvoiceProject.get(id=invoice_project_id)
    try:
        db_name = ensure_project_db(invoice_project.project_id)
    except OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Doris FE 未就绪或不可用，请稍后重试。",
        ) from exc

    sales_raw = invoice_project.sales_raw_table or invoice_handler._build_raw_table_name(
        invoice_project.project_id, invoice_project.company_id, invoice_project_id, "sales"
    )
    purchase_raw = invoice_project.purchase_raw_table or invoice_handler._build_raw_table_name(
        invoice_project.project_id, invoice_project.company_id, invoice_project_id, "purchase"
    )
    table1 = invoice_project.derived_table_1 or f"invoice_table1_sales_category_{invoice_project_id}"
    table2 = invoice_project.derived_table_2 or f"invoice_table2_sales_customer_{invoice_project_id}"
    table3 = invoice_project.derived_table_3 or f"invoice_table3_purchase_category_{invoice_project_id}"
    table4 = invoice_project.derived_table_4 or f"invoice_table4_purchase_supplier_{invoice_project_id}"
    table5 = invoice_project.derived_table_5 or f"invoice_table5_match_{invoice_project_id}"

    table_map = {
        "sales_raw": ("\u9500\u9879\u539f\u59cb", sales_raw),
        "purchase_raw": ("\u8fdb\u9879\u539f\u59cb", purchase_raw),
        "table1": ("\u8868\u4e00\u9500\u9879\u7c7b\u522b", table1),
        "table2": ("\u8868\u4e8c\u9500\u9879\u5ba2\u6237", table2),
        "table3": ("\u8868\u4e09\u8fdb\u9879\u7c7b\u522b", table3),
        "table4": ("\u8868\u56db\u8fdb\u9879\u4f9b\u5e94\u5546", table4),
        "table5": ("\u8868\u4e94\u8fdb\u9500\u5339\u914d", table5),
    }

    selected_keys = [k for k in (items or "").split(",") if k]
    if not selected_keys:
        selected_keys = list(table_map.keys())

    import pandas as pd

    output = BytesIO()
    # Use openpyxl to avoid a hard dependency on xlsxwriter in the container.
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for key in selected_keys:
            if key not in table_map:
                continue
            sheet_name, table_name = table_map[key]
            try:
                rows = doris_client.execute_query(f"SELECT * FROM `{table_name}`", database=db_name)
            except Exception:
                rows = []
            df = pd.DataFrame(rows)
            if "id" in df.columns:
                df = df.drop(columns=["id"])
            for col in ["project_id", "company_id", "invoice_project_id"]:
                if col in df.columns:
                    df = df.drop(columns=[col])
            safe_sheet = sheet_name[:31] if sheet_name else key[:31]
            df.to_excel(writer, sheet_name=safe_sheet, index=False)

    output.seek(0)
    filename = f"invoice_project_{invoice_project_id}_export.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/modules/invoice/projects/{invoice_project_id}/doris-status")
async def get_invoice_project_doris_status(invoice_project_id: int):
    invoice_project = await InvoiceProject.get(id=invoice_project_id)
    db_name = ensure_project_db(invoice_project.project_id)

    sales_raw = invoice_project.sales_raw_table or invoice_handler._build_raw_table_name(
        invoice_project.project_id, invoice_project.company_id, invoice_project_id, "sales"
    )
    purchase_raw = invoice_project.purchase_raw_table or invoice_handler._build_raw_table_name(
        invoice_project.project_id, invoice_project.company_id, invoice_project_id, "purchase"
    )
    table1 = invoice_project.derived_table_1 or f"invoice_table1_sales_category_{invoice_project_id}"
    table2 = invoice_project.derived_table_2 or f"invoice_table2_sales_customer_{invoice_project_id}"
    table3 = invoice_project.derived_table_3 or f"invoice_table3_purchase_category_{invoice_project_id}"
    table4 = invoice_project.derived_table_4 or f"invoice_table4_purchase_supplier_{invoice_project_id}"
    table5 = invoice_project.derived_table_5 or f"invoice_table5_match_{invoice_project_id}"

    try:
        tables_in_db = set(doris_client.get_tables(database=db_name))
    except Exception:
        tables_in_db = set()

    async def _sum_upload_rows(direction: str) -> int:
        rows = await InvoiceUpload.filter(invoice_project_id=invoice_project_id, direction=direction).values_list(
            "row_count", flat=True
        )
        total = 0
        for r in rows:
            if r is None:
                continue
            try:
                total += int(r)
            except Exception:
                continue
        return total

    sales_rows = await _sum_upload_rows("sales")
    purchase_rows = await _sum_upload_rows("purchase")

    sheets = [
        ("\u9500\u9879\u539f\u59cb", sales_raw, sales_rows, True),
        ("\u8fdb\u9879\u539f\u59cb", purchase_raw, purchase_rows, True),
        ("\u8868\u4e00\u9500\u9879\u7c7b\u522b", table1, None, False),
        ("\u8868\u4e8c\u9500\u9879\u5ba2\u6237", table2, None, False),
        ("\u8868\u4e09\u8fdb\u9879\u7c7b\u522b", table3, None, False),
        ("\u8868\u56db\u8fdb\u9879\u4f9b\u5e94\u5546", table4, None, False),
        ("\u8868\u4e94\u8fdb\u9500\u5339\u914d", table5, None, False),
    ]

    tables = []
    for label, table_name, preset_cnt, is_raw in sheets:
        exists = table_name in tables_in_db
        cnt = None
        if exists:
            if is_raw:
                cnt = preset_cnt
            else:
                try:
                    res = doris_client.execute_query(f"SELECT COUNT(1) AS cnt FROM `{table_name}`", database=db_name)
                    cnt = int(res[0]["cnt"]) if res else 0
                except Exception:
                    cnt = None
        tables.append({"label": label, "table_name": table_name, "exists": exists, "row_count": cnt})

    return {"success": True, "invoice_project_id": invoice_project_id, "tables": tables}


@app.get("/api/modules/invoice/projects/{invoice_project_id}/analysis")
async def get_invoice_project_analysis(invoice_project_id: int):
    invoice_project = await InvoiceProject.get(id=invoice_project_id)
    db_name = ensure_project_db(invoice_project.project_id)

    sales_raw = invoice_project.sales_raw_table or invoice_handler._build_raw_table_name(
        invoice_project.project_id, invoice_project.company_id, invoice_project_id, "sales"
    )
    purchase_raw = invoice_project.purchase_raw_table or invoice_handler._build_raw_table_name(
        invoice_project.project_id, invoice_project.company_id, invoice_project_id, "purchase"
    )

    table1 = invoice_project.derived_table_1 or f"invoice_table1_sales_category_{invoice_project_id}"
    table2 = invoice_project.derived_table_2 or f"invoice_table2_sales_customer_{invoice_project_id}"
    table3 = invoice_project.derived_table_3 or f"invoice_table3_purchase_category_{invoice_project_id}"
    table4 = invoice_project.derived_table_4 or f"invoice_table4_purchase_supplier_{invoice_project_id}"
    table5 = invoice_project.derived_table_5 or f"invoice_table5_match_{invoice_project_id}"

    def _safe_rows(sql: str):
        try:
            return doris_client.execute_query(sql, database=db_name)
        except Exception:
            return []

    def _summary_for(table_name: str, label: str):
        sql = f"""
            SELECT
              COALESCE(SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END), 0) AS cnt,
              COALESCE(SUM(CASE WHEN is_valid = 1 THEN amount_with_tax ELSE 0 END), 0) AS total_amount,
              COALESCE(SUM(CASE WHEN is_valid = 1 THEN tax_amount ELSE 0 END), 0) AS total_tax,
              COALESCE(SUM(CASE WHEN is_void = 1 THEN 1 ELSE 0 END), 0) AS void_count,
              COALESCE(SUM(CASE WHEN is_red = 1 THEN 1 ELSE 0 END), 0) AS red_flush_count,
              COALESCE(COUNT(DISTINCT CASE WHEN is_valid = 1 THEN invoice_month ELSE NULL END), 0) AS months
            FROM `{table_name}`
        """
        row = _safe_rows(sql)
        if row and isinstance(row, list) and isinstance(row[0], dict):
            data = row[0]
        else:
            data = {}
        months = int(data.get("months") or 0)
        return {
            "category": label,
            "count": int(data.get("cnt") or 0),
            "total_amount": float(data.get("total_amount") or 0),
            "total_tax": float(data.get("total_tax") or 0),
            "void_count": int(data.get("void_count") or 0),
            "red_flush_count": int(data.get("red_flush_count") or 0),
            "months": int(max(1, months)) if months > 0 else 0,
        }

    def _with_keys(rows, prefix):
        for idx, r in enumerate(rows or []):
            try:
                r["_key"] = f"{prefix}_{idx}"
            except Exception:
                pass
        return rows or []

    summary_rows = [
        _summary_for(sales_raw, "\u9500\u552e"),
        _summary_for(purchase_raw, "\u8fdb\u9879"),
    ]

    sales_by_item = _with_keys(_safe_rows(f"SELECT * FROM `{table1}`"), "sales_by_item")
    sales_by_buyer = _with_keys(_safe_rows(f"SELECT * FROM `{table2}`"), "sales_by_buyer")
    purchase_by_item = _with_keys(_safe_rows(f"SELECT * FROM `{table3}`"), "purchase_by_item")
    purchase_by_seller = _with_keys(_safe_rows(f"SELECT * FROM `{table4}`"), "purchase_by_seller")
    match_by_category = _with_keys(_safe_rows(f"SELECT * FROM `{table5}`"), "match_by_category")

    return {
        "summary": summary_rows,
        "sales_by_item": sales_by_item,
        "sales_by_buyer": sales_by_buyer,
        "purchase_by_item": purchase_by_item,
        "purchase_by_seller": purchase_by_seller,
        "match_by_category": match_by_category,
    }


@app.post("/api/modules/invoice/query/natural")
async def invoice_natural_language_query(request: Dict[str, Any]):
    query = request.get("query")
    invoice_project_id = request.get("invoice_project_id")
    if not query or not invoice_project_id:
        raise HTTPException(status_code=400, detail="Missing 'query' or 'invoice_project_id'")

    invoice_project = await InvoiceProject.get(id=int(invoice_project_id))
    db_name = ensure_project_db(invoice_project.project_id)
    project_cfg = await ProjectLLMConfig.filter(project_id=invoice_project.project_id).first()

    allowed_tables = {
        invoice_project.sales_raw_table or invoice_handler._build_raw_table_name(
            invoice_project.project_id, invoice_project.company_id, invoice_project.id, "sales"
        ),
        invoice_project.purchase_raw_table or invoice_handler._build_raw_table_name(
            invoice_project.project_id, invoice_project.company_id, invoice_project.id, "purchase"
        ),
        invoice_project.derived_table_1 or f"invoice_table1_sales_category_{invoice_project.id}",
        invoice_project.derived_table_2 or f"invoice_table2_sales_customer_{invoice_project.id}",
        invoice_project.derived_table_3 or f"invoice_table3_purchase_category_{invoice_project.id}",
        invoice_project.derived_table_4 or f"invoice_table4_purchase_supplier_{invoice_project.id}",
        invoice_project.derived_table_5 or f"invoice_table5_match_{invoice_project.id}",
    }

    api_key = request.get("api_key") or (project_cfg.api_key if project_cfg else None) or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = request.get("model") or (project_cfg.model_name if project_cfg else None) or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = request.get("base_url") or (project_cfg.endpoint if project_cfg else None) or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="API key not provided. Please provide 'api_key' in request or set DEEPSEEK_API_KEY/OPENAI_API_KEY environment variable",
        )

    vanna = VannaDorisOpenAI(
        doris_client=doris_client,
        api_key=api_key,
        model=model,
        base_url=base_url,
        config={"temperature": (project_cfg.temperature if project_cfg and project_cfg.temperature is not None else 0.1)},
        database=db_name,
    )

    prompt_query = f"仅使用这些表生成SQL: {', '.join([f'`{t}`' for t in sorted(allowed_tables)])}\n问题: {query}"
    generated_sql = vanna.generate_sql(question=prompt_query)

    generated_sql = _strip_db_prefix(generated_sql, {db_name, DORIS_CONFIG.get("database")})
    safe_sql = _validate_generated_sql(generated_sql, allowed_tables)

    query_result = vanna.run_sql(safe_sql)
    return {
        "success": True,
        "query": query,
        "sql": safe_sql,
        "data": query_result,
        "count": len(query_result),
        "allowed_tables": sorted(allowed_tables),
    }

@app.post("/api/agent/chat")
async def agent_chat(
    message: str = Form(...),
    project_id: int = Form(...),
    company_id: int = Form(...)
):
    """Agent 聊天接口"""
    result = agent_handler.chat(message, project_id, company_id)
    return result


@app.post("/api/agent/chat/stream")
async def agent_chat_stream(
    message: str = Form(...),
    project_id: int = Form(...),
    company_id: int = Form(...)
):
    """Agent 流式聊天接口 - 使用 Server-Sent Events，展示工具调用过程"""
    import asyncio

    async def event_generator():
        # 发送开始事件
        yield f"data: {json.dumps({'type': 'start', 'content': ''}, ensure_ascii=False)}\n\n"

        try:
            # 使用流式生成器
            for event in agent_handler.stream_chat(message, project_id, company_id):
                event_data = event.to_dict()
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.05)  # 小延迟让前端有时间渲染

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'查询失败：{str(e)}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/agent/external")
async def external_agent_query(request: Dict[str, Any]):
    """
    外部 Agent 自然语言查询入口。
    - 若传入 invoice_project_id，则仅允许访问该发票项目相关表（等同 /api/modules/invoice/query/natural）
    - 否则走全局自然语言查询（等同 /api/query/natural）
    Body:
      {
        "query": "自然语言问题",
        "invoice_project_id": 1,           // 可选
        "api_key": "sk-xxx",               // 可选
        "model": "deepseek-chat",          // 可选
        "base_url": "https://api.deepseek.com" // 可选
      }
    """
    query = request.get("query") or request.get("message")
    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' parameter")

    project_id = request.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="Missing 'project_id' parameter")

    company_id = request.get("company_id") or 0

    # 外部 Agent 统一走项目级 Agent（LangGraph 工具调用）
    result = agent_handler.chat(query, int(project_id), int(company_id))
    return {"success": True, "project_id": project_id, "company_id": company_id, **result}


# ============ Chat Session APIs（聊天历史和上下文记忆） ============

@app.get("/api/projects/{project_id}/companies/{company_id}/chat-sessions")
async def list_chat_sessions(project_id: int, company_id: int, limit: int = 20):
    """获取聊天会话列表"""
    sessions = await ChatSession.filter(
        project_id=project_id,
        company_id=company_id,
        is_active=True
    ).order_by("-updated_at").limit(limit)

    result = []
    for s in sessions:
        # 获取最后一条消息作为预览
        last_msg = await ChatMessage.filter(session_id=s.id).order_by("-id").first()
        result.append({
            "id": s.id,
            "title": s.title,
            "summary": s.summary,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "last_message": last_msg.content[:100] if last_msg else None
        })
    return {"success": True, "sessions": result}


@app.post("/api/projects/{project_id}/companies/{company_id}/chat-sessions")
async def create_chat_session(project_id: int, company_id: int):
    """创建新聊天会话"""
    session = await ChatSession.create(
        project_id=project_id,
        company_id=company_id,
        title="新对话"
    )
    return {"success": True, "session_id": session.id}


@app.get("/api/chat-sessions/{session_id}/messages")
async def get_chat_messages(session_id: int, limit: int = 50):
    """获取会话消息历史"""
    messages = await ChatMessage.filter(session_id=session_id).order_by("id").limit(limit)
    return {
        "success": True,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sql": m.sql,
                "widget": m.widget,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }


@app.delete("/api/chat-sessions/{session_id}")
async def delete_chat_session(session_id: int):
    """删除聊天会话"""
    await ChatMessage.filter(session_id=session_id).delete()
    await ChatSession.filter(id=session_id).delete()
    return {"success": True}


@app.put("/api/chat-sessions/{session_id}/title")
async def update_chat_session_title(session_id: int, request: Dict[str, Any]):
    """更新会话标题"""
    title = request.get("title", "").strip()
    if title:
        await ChatSession.filter(id=session_id).update(title=title)
    return {"success": True}


@app.post("/api/agent/chat/with-history")
async def agent_chat_with_history(
    message: str = Form(...),
    project_id: int = Form(...),
    company_id: int = Form(...),
    session_id: Optional[int] = Form(None)
):
    """带历史上下文的Agent聊天接口"""

    # 如果没有session_id，创建新会话
    if not session_id:
        session = await ChatSession.create(
            project_id=project_id,
            company_id=company_id,
            title=message[:30] + "..." if len(message) > 30 else message
        )
        session_id = session.id
    else:
        # 验证session存在
        session = await ChatSession.filter(id=session_id).first()
        if not session:
            session = await ChatSession.create(
                project_id=project_id,
                company_id=company_id,
                title=message[:30] + "..." if len(message) > 30 else message
            )
            session_id = session.id

    # 保存用户消息
    await ChatMessage.create(
        session_id=session_id,
        role="user",
        content=message
    )

    # 获取历史消息作为上下文（最近10条）
    history_messages = await ChatMessage.filter(session_id=session_id).order_by("-id").limit(10)
    history_messages = list(reversed(history_messages))  # 按时间正序

    # 构建历史上下文
    history_context = []
    for msg in history_messages[:-1]:  # 排除刚刚添加的当前消息
        history_context.append({
            "role": msg.role,
            "content": msg.content[:500]  # 截断过长的消息
        })

    # 调用Agent处理（传入历史上下文）
    result = agent_handler.chat_with_context(message, project_id, company_id, history_context)

    # 保存AI响应
    await ChatMessage.create(
        session_id=session_id,
        role="assistant",
        content=result.get("message", ""),
        sql=result.get("sql"),
        widget=result.get("widget")
    )

    # 更新会话时间
    await ChatSession.filter(id=session_id).update(updated_at=datetime.utcnow())

    return {
        "success": True,
        "session_id": session_id,
        **result
    }


@app.post("/api/agent/chat/stream/with-history")
async def agent_chat_stream_with_history(
    message: str = Form(...),
    project_id: int = Form(...),
    company_id: int = Form(...),
    session_id: Optional[int] = Form(None)
):
    """带历史上下文的流式聊天接口"""
    import asyncio

    # 如果没有session_id，创建新会话
    actual_session_id = session_id
    if not actual_session_id:
        session = await ChatSession.create(
            project_id=project_id,
            company_id=company_id,
            title=message[:30] + "..." if len(message) > 30 else message
        )
        actual_session_id = session.id

    # 保存用户消息
    await ChatMessage.create(
        session_id=actual_session_id,
        role="user",
        content=message
    )

    # 获取历史消息
    history_messages = await ChatMessage.filter(session_id=actual_session_id).order_by("-id").limit(10)
    history_messages = list(reversed(history_messages))

    history_context = []
    for msg in history_messages[:-1]:
        history_context.append({
            "role": msg.role,
            "content": msg.content[:500]
        })

    async def event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': actual_session_id}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'thinking', 'content': '正在分析问题...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.1)

        try:
            result = agent_handler.chat_with_context(message, project_id, company_id, history_context)
            response_message = result.get("message", "")
            widget = result.get("widget")

            paragraphs = response_message.split('\n\n')
            accumulated = ""

            for i, para in enumerate(paragraphs):
                accumulated += para
                if i < len(paragraphs) - 1:
                    accumulated += '\n\n'

                if '|' in para and '---' in para:
                    yield f"data: {json.dumps({'type': 'table', 'content': accumulated}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'content', 'content': accumulated}, ensure_ascii=False)}\n\n"

                await asyncio.sleep(0.05)

            # 保存AI响应
            await ChatMessage.create(
                session_id=actual_session_id,
                role="assistant",
                content=response_message,
                sql=result.get("sql"),
                widget=widget
            )

            await ChatSession.filter(id=actual_session_id).update(updated_at=datetime.utcnow())

            yield f"data: {json.dumps({'type': 'done', 'content': response_message, 'widget': widget, 'session_id': actual_session_id}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'查询失败：{str(e)}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )




if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True
    )
