"""Agent handler: project-scoped AI assistant with Tool Use pattern.

核心思路：让大模型自主决定何时查询数据库，何时直接回答。
- query_data(question): 用自然语言查询数据，内部生成SQL执行
- list_tables(): 查看可用表
- get_table_schema(table_name): 查看表结构
"""
from typing import Dict, Any, List, Optional, TypedDict, Generator
import os
import re
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

from db import doris_client, ensure_project_db
from metadata_db import DB_FILE
from vanna_doris import VannaDorisOpenAI

# OpenAI client for Tool Use
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# LangGraph is optional
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

SCHEMA_CACHE: Dict[str, Dict[str, Any]] = {}
SCHEMA_CACHE_TTL = timedelta(minutes=10)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "project_agent_prompt.txt"



def _get_project_llm_config(project_id: int) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT provider_type, endpoint, model_name, api_key, temperature, max_tokens FROM project_llm_configs WHERE project_id = ?",
            (project_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "provider_type": row[0],
                "endpoint": row[1],
                "model_name": row[2],
                "api_key": row[3],
                "temperature": row[4],
                "max_tokens": row[5],
            }
    except Exception:
        return {}
    return {}


def _read_default_agent_prompt() -> str:
    try:
        if DEFAULT_PROMPT_PATH.exists():
            return DEFAULT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return (
        "你是 TabSis 表姐助手（项目级 Agent）。\n"
        "目标：基于当前项目的数据回答用户问题，必要时执行多步查询并汇总。\n"
        "规则：只使用系统允许的表；不要写 company_id 过滤；不要使用 db.table 前缀。"
    )


def _get_project_agent_prompt(project_id: int) -> str:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT prompt FROM project_agent_prompts WHERE project_id = ?",
            (project_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    return _read_default_agent_prompt()

def _tables_with_company_id(db_name: str, tables: List[str]) -> set:
    eligible = set()
    for t in tables:
        try:
            schema = doris_client.get_table_schema(t, database=db_name)
            for row in schema:
                field = (
                    row.get("Field")
                    or row.get("field")
                    or row.get("COLUMN_NAME")
                    or row.get("column_name")
                    or ""
                )
                if str(field).lower() == "company_id":
                    eligible.add(t)
                    break
        except Exception:
            continue
    return eligible


def _rewrite_sql_with_company_filter(sql: str, company_id: int, tables_with_company: set) -> str:
    if not tables_with_company:
        return sql

    def repl(match):
        keyword = match.group(1)
        table = match.group(2)
        alias = match.group(3) or ""
        if table not in tables_with_company:
            return match.group(0)
        alias_clean = alias.strip()
        if not alias_clean:
            # 使用显式的 AS 别名，确保子查询有明确别名
            alias = f" AS `{table}`"
        else:
            # 保留原有别名，但确保格式正确
            alias = f" {alias_clean}"
        return f"{keyword} (SELECT * FROM `{table}` WHERE company_id = {int(company_id)}){alias}"

    join_pattern = re.compile(
        r"(\bLEFT\s+OUTER\s+JOIN|\bRIGHT\s+OUTER\s+JOIN|\bFULL\s+OUTER\s+JOIN|\bLEFT\s+JOIN|\bRIGHT\s+JOIN|\bINNER\s+JOIN|\bFULL\s+JOIN|\bJOIN|\bFROM)\s+`?([A-Za-z0-9_]+)`?(\s+(?:AS\s+)?[A-Za-z0-9_]+)?",
        re.IGNORECASE,
    )
    return re.sub(join_pattern, repl, sql)


def _enforce_company_filter(sql: str, company_id: int, db_name: str, tables: List[str]) -> (str, bool):
    if not company_id:
        return sql, False
    if re.search(r"\bcompany_id\b", sql, flags=re.IGNORECASE):
        return sql, True
    tables_with_company = _tables_with_company_id(db_name, tables)
    rewritten = _rewrite_sql_with_company_filter(sql, company_id, tables_with_company)
    return rewritten, rewritten != sql


DERIVED_ALIAS_KEYWORDS = {
    "WHERE",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "FULL",
    "ON",
    "GROUP",
    "ORDER",
    "LIMIT",
    "UNION",
    "HAVING",
    "QUALIFY",
    "CROSS",
    "WINDOW",
}


def _ensure_derived_table_aliases(sql: str) -> str:
    if not sql:
        return sql
    lower = sql.lower()
    i = 0
    alias_index = 1
    output: List[str] = []
    pattern = re.compile(
        r"\b(from|join|left\s+join|right\s+join|inner\s+join|full\s+join|left\s+outer\s+join|right\s+outer\s+join|full\s+outer\s+join)\s*\(",
        re.IGNORECASE,
    )
    while True:
        match = pattern.search(lower, i)
        if not match:
            output.append(sql[i:])
            break
        start = match.start()
        open_idx = match.end() - 1  # points at '('
        output.append(sql[i:open_idx + 1])
        j = open_idx + 1
        depth = 1
        quote: Optional[str] = None
        while j < len(sql) and depth > 0:
            ch = sql[j]
            if quote:
                if ch == quote and (j == 0 or sql[j - 1] != "\\"):
                    quote = None
            else:
                if ch in ("'", '"'):
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            j += 1
        output.append(sql[open_idx + 1:j])
        k = j
        while k < len(sql) and sql[k].isspace():
            k += 1
        alias_exists = False
        if k < len(sql):
            alias_match = re.match(r"(AS\s+)?(`?[A-Za-z_][A-Za-z0-9_]*`?)", sql[k:], flags=re.IGNORECASE)
            if alias_match:
                alias_token = alias_match.group(2).strip("`")
                if alias_token.upper() not in DERIVED_ALIAS_KEYWORDS:
                    alias_exists = True
        if not alias_exists:
            output.append(f" AS subq_{alias_index}")
            alias_index += 1
        i = j
    return "".join(output)


def _normalize_base_url(base_url: str) -> str:
    if not base_url:
        return ""
    url = base_url.rstrip("/")
    for suffix in ("/chat/completions", "/v1/chat/completions"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url


def _parse_tool_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if payload is None:
        return {}
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {"raw": payload}
    return {"raw": payload}


def _get_schema_context(db_name: str, tables: List[str]) -> str:
    if not tables:
        return ""
    now = datetime.utcnow()
    cache = SCHEMA_CACHE.get(db_name)
    if cache and cache.get("expires_at") and cache["expires_at"] > now:
        table_map = cache.get("tables", {})
    else:
        table_map: Dict[str, List[str]] = {}
        for table in tables:
            try:
                schema = doris_client.get_table_schema(table, database=db_name)
            except Exception:
                schema = []
            cols: List[str] = []
            for row in schema:
                field = (
                    row.get("Field")
                    or row.get("field")
                    or row.get("COLUMN_NAME")
                    or row.get("column_name")
                    or ""
                )
                if field:
                    cols.append(str(field))
            table_map[table] = cols
        SCHEMA_CACHE[db_name] = {
            "tables": table_map,
            "expires_at": now + SCHEMA_CACHE_TTL,
        }

    parts: List[str] = []
    for table, cols in table_map.items():
        if not cols:
            continue
        display_cols = cols[:40]
        if len(cols) > 40:
            display_cols.append("...")
        if "company_id" in cols:
            display_cols = ["company_id*"] + [c for c in display_cols if c != "company_id"]
        parts.append(f"{table}({', '.join(display_cols)})")
    return "\n".join(parts)


class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]



def _looks_like_table_list_request(message: str) -> bool:
    m = message.lower()
    keywords = ["show tables", "list tables", "有哪些表", "有什么表", "表有哪些", "表结构", "table list"]
    return any(k in m for k in keywords)


def _looks_like_data_request(message: str) -> bool:
    if not message:
        return False
    m = message.lower()
    keywords = [
        "??", "??", "??", "??", "top", "?", "??", "?", "??", "??", "??", "??",
        "??", "sum", "avg", "count", "max", "min", "??", "??", "??", "??", "??", "??",
        "?", "??", "??", "??", "??"
    ]
    return any(k in m for k in keywords)

def _build_history_messages(history=None):
    if not history:
        return []
    messages = []
    for msg in history[-6:]:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content or role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": content[:500]})
    return messages

def _sanitize_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.replace("|", "\\|")
    return text


def _markdown_table(rows: List[Dict[str, Any]], max_rows: int = 50) -> str:
    if not rows:
        return "（无数据）"
    headers = list(rows[0].keys())
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines = [header_line, sep_line]
    for row in rows[:max_rows]:
        line = "| " + " | ".join(_sanitize_cell(row.get(h, "")) for h in headers) + " |"
        lines.append(line)
    if len(rows) > max_rows:
        lines.append(f"\n仅展示前 {max_rows} 行。")
    return "\n".join(lines)


def _validate_sql(sql: str, allowed_tables: Optional[set] = None) -> str:
    if not sql:
        raise ValueError("Empty SQL")
    sql_clean = sql.strip().rstrip(";")
    if ";" in sql_clean:
        raise ValueError("Only single-statement SQL allowed")
    sql_upper = sql_clean.upper()
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        raise ValueError("Only SELECT statements allowed")
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
    if any(f in sql_upper for f in forbidden):
        raise ValueError("Forbidden SQL keyword detected")
    if allowed_tables:
        referenced = set(re.findall(r"(?:FROM|JOIN)\s+`?([A-Za-z0-9_]+)`?", sql_clean, flags=re.IGNORECASE))
        illegal = sorted([t for t in referenced if t not in allowed_tables])
        if illegal:
            raise ValueError(f"SQL references non-project tables: {', '.join(illegal)}")
    return sql_clean


def _strip_db_prefix(sql: str, allowed_db_names: set) -> str:
    if not sql or not allowed_db_names:
        return sql
    cleaned = sql
    for db_name in allowed_db_names:
        if not db_name:
            continue
        pattern = re.compile(
            rf"\b{re.escape(db_name)}\s*\.\s*`?([A-Za-z0-9_]+)`?",
            re.IGNORECASE,
        )
        cleaned = re.sub(pattern, r"`\1`", cleaned)
    return cleaned


class ToolCallEvent:
    """工具调用事件，用于流式输出"""
    def __init__(self, event_type: str, tool_name: str = "", content: Any = None, status: str = "running", widget: Any = None):
        self.type = event_type  # 'tool_start', 'tool_result', 'thinking', 'content', 'done', 'error'
        self.tool_name = tool_name
        self.content = content
        self.status = status  # 'running', 'success', 'error'
        self.widget = widget

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": self.type,
            "tool_name": self.tool_name,
            "content": self.content,
            "status": self.status
        }
        if self.widget is not None:
            result["widget"] = self.widget
        return result


class AgentHandler:
    def __init__(self):
        self.db = doris_client
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    def chat(self, message: str, project_id: int, company_id: int, context: Dict[str, Any] = None) -> Dict[str, Any]:
        if not project_id:
            return {"message": "请先选择项目后再提问。", "widget": None}

        try:
            db_name = ensure_project_db(int(project_id))
        except Exception as e:
            return {"message": f"项目数据库不可用: {e}", "widget": None}

        tables = []
        try:
            tables = self.db.get_tables(database=db_name)
        except Exception:
            tables = []

        if not tables:
            return {"message": "当前项目暂无数据表，请先上传数据。", "widget": None}

        if _looks_like_table_list_request(message):
            table_list = "\n".join([f"- {t}" for t in tables])
            return {"message": f"当前项目表清单：\n\n{table_list}", "widget": None}

        history_messages = _build_history_messages((context or {}).get("history"))
        project_cfg = _get_project_llm_config(int(project_id))
        api_key = project_cfg.get("api_key") or self.api_key
        model_name = project_cfg.get("model_name") or self.model_name
        base_url = project_cfg.get("endpoint") or self.base_url
        temperature = project_cfg.get("temperature")

        if not api_key:
            return {"message": "未配置 LLM API Key（项目或环境变量）。", "widget": None}

        company_info = self._get_company_info(company_id)

        schema_context = _get_schema_context(db_name, tables)
        project_prompt = _get_project_agent_prompt(int(project_id))

        # 表业务描述（帮助LLM理解每张表的用途）
        table_descriptions = """
表业务说明：
- invoice_raw_*_sales: 销项原始表 - 公司开出的销售发票明细
- invoice_raw_*_purchase: 进项原始表 - 公司收到的采购发票明细
- invoice_table1_sales_category_*: 表一·销项类别统计表 - 按销售开票类别统计，含税率、销售金额(价税合计)、销售占比、销售数量、平均单价
- invoice_table2_sales_customer_*: 表二·销项客户统计表 - 按销售客户统计，含税率、销售金额(价税合计)、销售占比、销售数量、平均单价
- invoice_table3_purchase_category_*: 表三·进项类别统计表 - 按采购类别统计，含税率、采购金额(价税合计)、采购占比、采购数量、平均单价
- invoice_table4_purchase_supplier_*: 表四·进项供应商统计表 - 按供应商统计，含税率、采购金额(价税合计)、采购占比、采购数量、平均单价
- invoice_table5_match_*: 表五·进销匹配表 - 对比销售和采购的数量、单价差异

分析建议：
- 多维度分析：可查询表1-5中的汇总数据
- 客户分析：查表二(sales_customer)
- 供应商分析：查表四(purchase_supplier)
- 进销对比：查表五(match)
- 原始明细：查raw表
"""

        system_prefix = (
            "你是TabSis表姐助手，负责将用户问题转成SQL并查询结果。\n"
            f"当前项目ID: {project_id}\n"
            f"当前企业: {company_info.get('name')} (ID: {company_id})\n"
            f"企业背景: {company_info.get('background_info')}\n"
            f"仅允许使用这些表: {', '.join([f'`{t}`' for t in tables])}\n"
            "企业范围由系统自动处理，不要在SQL中手动写 company_id 过滤。\n"
            "不要使用数据库前缀（例如 db.table）。\n"
            "只输出一条可执行的SELECT/CTE SQL。\n\n"
            f"{table_descriptions}"
        )
        if schema_context:
            system_prefix = f"{system_prefix}\n表结构（含 company_id* 标识）：\n{schema_context}"
        if project_prompt:
            system_prefix = f"{system_prefix}\n\n项目提示词：\n{project_prompt}"

        try:
            if not LANGGRAPH_AVAILABLE:
                vanna = VannaDorisOpenAI(
                    doris_client=self.db,
                    api_key=api_key,
                    model=model_name,
                    base_url=base_url,
                    config={"temperature": (temperature if temperature is not None else 0.1)},
                    database=db_name,
                )

                generated_sql = vanna.generate_sql(question=f"{system_prefix}\n问题: {message}")

                # 清理SQL：去除markdown代码块标记
                sql_clean = generated_sql.strip()
                if sql_clean.startswith('```sql'):
                    sql_clean = sql_clean[6:]
                elif sql_clean.startswith('```'):
                    sql_clean = sql_clean[3:]
                if sql_clean.endswith('```'):
                    sql_clean = sql_clean[:-3]
                sql_clean = sql_clean.strip()

                # 检查是否为有效的SELECT语句
                sql_upper = sql_clean.upper().strip()
                if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
                    return {"message": f"生成的SQL无效，请尝试更具体的问题。\n\n收到: {sql_clean[:100]}...", "widget": None}

                sql = _strip_db_prefix(
                    sql_clean,
                    {db_name, os.getenv("DORIS_DATABASE", "").strip()},
                )
                sql = _validate_sql(sql, allowed_tables=set(tables))
                sql, enforced = _enforce_company_filter(sql, int(company_id), db_name, tables)
                sql = _ensure_derived_table_aliases(sql)

                rows = vanna.run_sql(sql)
                table_md = _markdown_table(rows)

                if not enforced:
                    note = "⚠️ 未能自动加 company_id 过滤（部分表无 company_id 字段），请手动确认范围。"
                else:
                    note = ""

                response_md = f"已执行SQL：\n\n```sql\n{sql}\n```\n\n结果：\n\n{table_md}"
                if note:
                    response_md = f"{response_md}\n\n{note}"
                return {"message": response_md, "widget": None}

            normalized_url = _normalize_base_url(base_url) or "https://api.deepseek.com"

            def list_tables() -> List[str]:
                return tables

            def get_table_schema(table_name: str) -> List[Dict[str, Any]]:
                return doris_client.get_table_schema(table_name, database=db_name)

            def run_sql(sql: str) -> Dict[str, Any]:
                # 清理SQL：去除markdown代码块标记
                sql_clean = sql.strip()
                if sql_clean.startswith('```sql'):
                    sql_clean = sql_clean[6:]
                elif sql_clean.startswith('```'):
                    sql_clean = sql_clean[3:]
                if sql_clean.endswith('```'):
                    sql_clean = sql_clean[:-3]
                sql_clean = sql_clean.strip()

                # 检查是否为空或非SELECT语句
                if not sql_clean:
                    return {"error": "SQL为空", "sql": sql, "rows": [], "enforced": False}

                sql_upper = sql_clean.upper().strip()
                if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
                    return {"error": f"只支持SELECT查询，收到: {sql_clean[:50]}...", "sql": sql_clean, "rows": [], "enforced": False}

                try:
                    cleaned = _strip_db_prefix(sql_clean, {db_name, os.getenv("DORIS_DATABASE", "").strip()})
                    safe_sql = _validate_sql(cleaned, allowed_tables=set(tables))
                    safe_sql, enforced = _enforce_company_filter(safe_sql, int(company_id), db_name, tables)
                    safe_sql = _ensure_derived_table_aliases(safe_sql)
                    rows = doris_client.execute_query(safe_sql, database=db_name)
                    return {"sql": safe_sql, "rows": rows, "enforced": enforced}
                except Exception as e:
                    return {"error": str(e), "sql": sql_clean, "rows": [], "enforced": False}

            tools_spec = [
                {
                    "type": "function",
                    "function": {
                        "name": "list_tables",
                        "description": "列出当前项目可用的表",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_table_schema",
                        "description": "获取表结构",
                        "parameters": {
                            "type": "object",
                            "properties": {"table_name": {"type": "string"}},
                            "required": ["table_name"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "run_sql",
                        "description": "执行SQL并返回结果",
                        "parameters": {
                            "type": "object",
                            "properties": {"sql": {"type": "string"}},
                            "required": ["sql"],
                        },
                    },
                },
            ]

            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=normalized_url)

            def agent_node(state: AgentState) -> AgentState:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=state["messages"],
                    tools=tools_spec,
                    tool_choice="auto",
                    temperature=temperature if temperature is not None else 0.1,
                    max_tokens=project_cfg.get("max_tokens") or 2000,
                )
                message_obj = response.choices[0].message
                tool_calls = message_obj.tool_calls or []
                tool_call_dicts = []
                for call in tool_calls:
                    tool_call_dicts.append({
                        "id": call.id,
                        "type": call.type,
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    })
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": message_obj.content or "",
                }
                if tool_call_dicts:
                    assistant_msg["tool_calls"] = tool_call_dicts
                return {
                    "messages": state["messages"] + [assistant_msg],
                    "tool_calls": tool_call_dicts,
                }

            def tool_node(state: AgentState) -> AgentState:
                messages = list(state["messages"])
                for call in state.get("tool_calls", []) or []:
                    fn = call.get("function", {}) or {}
                    name = fn.get("name")
                    args_raw = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {}

                    result: Any
                    if name == "list_tables":
                        result = list_tables()
                    elif name == "get_table_schema":
                        result = get_table_schema(args.get("table_name", ""))
                    elif name == "run_sql":
                        result = run_sql(args.get("sql", ""))
                    else:
                        result = {"error": f"Unknown tool: {name}"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                return {"messages": messages, "tool_calls": []}

            def should_continue(state: AgentState) -> str:
                return "tools" if state.get("tool_calls") else "end"

            graph = StateGraph(AgentState)
            graph.add_node("agent", agent_node)
            graph.add_node("tools", tool_node)
            graph.set_entry_point("agent")
            graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
            graph.add_edge("tools", "agent")
            app = graph.compile()

            system_message = (
                "你是项目级数据助手，会使用工具分步完成查询。\n"
                "流程：必要时先 list_tables / get_table_schema，再生成SQL调用 run_sql。\n"
                "规则：只使用 list_tables 返回的表；不要写数据库前缀；不要手写 company_id 过滤。\n"
                "最终用简洁中文作答，可附上关键数据摘要。"
            )

            def run_agent(extra_system: str = None):
                messages = [
                    {"role": "system", "content": system_prefix},
                    {"role": "system", "content": system_message},
                ]
                if extra_system:
                    messages.append({"role": "system", "content": extra_system})
                if history_messages:
                    messages.extend(history_messages)
                messages.append({"role": "user", "content": message})
                return app.invoke({"messages": messages, "tool_calls": []}, {"recursion_limit": 15})

            def extract_result(result_payload):
                messages = result_payload.get("messages", [])
                answer = ""
                tool_payload = {}
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and not msg.get("tool_calls"):
                        answer = msg.get("content") or ""
                        break
                for msg in reversed(messages):
                    if msg.get("role") == "tool" and msg.get("name") == "run_sql":
                        tool_payload = _parse_tool_payload(msg.get("content"))
                        break
                return answer, tool_payload

            result = run_agent()
            answer, tool_payload = extract_result(result)

            sql = tool_payload.get("sql")
            rows = tool_payload.get("rows") if tool_payload else None
            enforced = tool_payload.get("enforced", False)

            if not sql and _looks_like_data_request(message):
                result = run_agent("You must call run_sql to query data before answering.")
                answer, tool_payload = extract_result(result)
                sql = tool_payload.get("sql")
                rows = tool_payload.get("rows") if tool_payload else None
                enforced = tool_payload.get("enforced", False)

            table_md = _markdown_table(rows) if rows is not None else ""

            if sql:
                if not enforced and company_id:
                    note = "注意：company_id 过滤未应用，请确认查询范围。"
                elif not company_id:
                    note = "注意：未提供 company_id，本次查询为项目级范围。"
                else:
                    note = ""
            else:
                note = ""

            response_parts = []
            if answer:
                response_parts.append(answer)
            if sql:
                response_parts.append(f"SQL:\n\n```sql\n{sql}\n```")
                response_parts.append(f"Result:\n\n{table_md}")
            if note:
                response_parts.append(note)
            response_md = "\n\n".join(response_parts) if response_parts else answer or "(no response)"
            return {"message": response_md, "widget": None, "sql": sql}
        except Exception as e:
            return {"message": f"查询失败：{e}", "widget": None}

    def _get_company_info(self, company_id: int) -> Dict[str, Any]:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT name, background_info FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"name": row[0], "background_info": row[1]}
        except Exception:
            pass
        return {"name": f"Company {company_id}", "background_info": ""}

    def chat_with_context(self, message: str, project_id: int, company_id: int, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Chat with history context."""
        return self.chat(message, project_id, company_id, context={"history": history or []})

    def stream_chat(self, message: str, project_id: int, company_id: int):
        """流式聊天 - 生成器方法，逐步 yield 工具调用事件"""
        if not project_id:
            yield ToolCallEvent("error", content="请先选择项目后再提问。")
            return

        # Step 1: 初始化数据库
        yield ToolCallEvent("tool_start", "init_database", "正在连接项目数据库...", "running")
        try:
            db_name = ensure_project_db(int(project_id))
            yield ToolCallEvent("tool_result", "init_database", f"已连接数据库: {db_name}", "success")
        except Exception as e:
            yield ToolCallEvent("tool_result", "init_database", f"数据库连接失败: {e}", "error")
            yield ToolCallEvent("error", content=f"项目数据库不可用: {e}")
            return

        # Step 2: 获取表列表
        yield ToolCallEvent("tool_start", "list_tables", "正在获取可用数据表...", "running")
        tables = []
        try:
            tables = self.db.get_tables(database=db_name)
            yield ToolCallEvent("tool_result", "list_tables", f"发现 {len(tables)} 张表: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}", "success")
        except Exception:
            yield ToolCallEvent("tool_result", "list_tables", "获取表列表失败", "error")

        if not tables:
            yield ToolCallEvent("error", content="当前项目暂无数据表，请先上传数据。")
            return

        if _looks_like_table_list_request(message):
            table_list = "\n".join([f"- {t}" for t in tables])
            yield ToolCallEvent("done", content=f"当前项目表清单：\n\n{table_list}")
            return

        # Step 3: 获取 LLM 配置
        yield ToolCallEvent("tool_start", "get_llm_config", "正在加载 LLM 配置...", "running")
        project_cfg = _get_project_llm_config(int(project_id))
        api_key = project_cfg.get("api_key") or self.api_key
        model_name = project_cfg.get("model_name") or self.model_name
        base_url = project_cfg.get("endpoint") or self.base_url
        temperature = project_cfg.get("temperature")

        if not api_key:
            yield ToolCallEvent("tool_result", "get_llm_config", "未配置 API Key", "error")
            yield ToolCallEvent("error", content="未配置 LLM API Key（项目或环境变量）。")
            return
        yield ToolCallEvent("tool_result", "get_llm_config", f"使用模型: {model_name}", "success")

        # Step 4: 获取企业信息和表结构
        yield ToolCallEvent("tool_start", "get_context", "正在获取企业信息和表结构...", "running")
        company_info = self._get_company_info(company_id)
        schema_context = _get_schema_context(db_name, tables)
        project_prompt = _get_project_agent_prompt(int(project_id))
        yield ToolCallEvent("tool_result", "get_context", f"企业: {company_info.get('name')}, 表结构已加载", "success")

        # 构建 system prompt
        table_descriptions = """
表业务说明：
- invoice_raw_*_sales: 销项原始表 - 公司开出的销售发票明细
- invoice_raw_*_purchase: 进项原始表 - 公司收到的采购发票明细
- invoice_table1_sales_category_*: 表一·销项类别统计表
- invoice_table2_sales_customer_*: 表二·销项客户统计表
- invoice_table3_purchase_category_*: 表三·进项类别统计表
- invoice_table4_purchase_supplier_*: 表四·进项供应商统计表
- invoice_table5_match_*: 表五·进销匹配表
"""
        system_prefix = (
            "你是TabSis表姐助手，负责将用户问题转成SQL并查询结果。\n"
            f"当前项目ID: {project_id}\n"
            f"当前企业: {company_info.get('name')} (ID: {company_id})\n"
            f"企业背景: {company_info.get('background_info')}\n"
            f"仅允许使用这些表: {', '.join([f'`{t}`' for t in tables])}\n"
            "企业范围由系统自动处理，不要在SQL中手动写 company_id 过滤。\n"
            "不要使用数据库前缀（例如 db.table）。\n"
            "只输出一条可执行的SELECT/CTE SQL。\n\n"
            f"{table_descriptions}"
        )
        if schema_context:
            system_prefix = f"{system_prefix}\n表结构（含 company_id* 标识）：\n{schema_context}"
        if project_prompt:
            system_prefix = f"{system_prefix}\n\n项目提示词：\n{project_prompt}"

        # Step 5: 调用 LLM 生成 SQL（带重试机制）
        MAX_RETRIES = 3
        vanna = VannaDorisOpenAI(
            doris_client=self.db,
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            config={"temperature": (temperature if temperature is not None else 0.1)},
            database=db_name,
        )

        sql = None
        rows = None
        enforced = False
        error_history: List[str] = []  # 记录错误历史，用于反馈给 LLM

        for attempt in range(1, MAX_RETRIES + 1):
            attempt_label = f"(尝试 {attempt}/{MAX_RETRIES})" if attempt > 1 else ""
            yield ToolCallEvent("tool_start", "generate_sql", f"正在分析问题并生成 SQL...{attempt_label}", "running")

            try:
                # 构建问题，如果有错误历史则附带
                question = f"{system_prefix}\n问题: {message}"
                if error_history:
                    error_context = "\n".join([f"- {err}" for err in error_history])
                    question = (
                        f"{question}\n\n"
                        f"【重要】之前的尝试失败了，请根据以下错误修正你的SQL：\n{error_context}\n"
                        f"请仔细检查表名是否在允许列表中，并确保SQL语法正确。"
                    )

                generated_sql = vanna.generate_sql(question=question)

                # 清理 SQL
                sql_clean = generated_sql.strip()
                if sql_clean.startswith('```sql'):
                    sql_clean = sql_clean[6:]
                elif sql_clean.startswith('```'):
                    sql_clean = sql_clean[3:]
                if sql_clean.endswith('```'):
                    sql_clean = sql_clean[:-3]
                sql_clean = sql_clean.strip()

                sql_upper = sql_clean.upper().strip()
                if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
                    error_msg = f"生成的SQL无效（不是SELECT语句）: {sql_clean[:80]}"
                    error_history.append(error_msg)
                    yield ToolCallEvent("tool_result", "generate_sql", f"❌ {error_msg}", "error")
                    continue

                # 验证和处理 SQL
                sql = _strip_db_prefix(sql_clean, {db_name, os.getenv("DORIS_DATABASE", "").strip()})
                sql = _validate_sql(sql, allowed_tables=set(tables))
                sql, enforced = _enforce_company_filter(sql, int(company_id), db_name, tables)
                sql = _ensure_derived_table_aliases(sql)

                # 显示生成的 SQL
                sql_preview = sql[:100] + "..." if len(sql) > 100 else sql
                yield ToolCallEvent("tool_result", "generate_sql", f"```sql\n{sql_preview}\n```", "success")

            except ValueError as e:
                # SQL 验证错误（如使用了非法表名）
                error_msg = str(e)
                error_history.append(error_msg)
                yield ToolCallEvent("tool_result", "generate_sql", f"❌ SQL验证失败: {error_msg}", "error")
                continue

            except Exception as e:
                error_msg = f"SQL生成异常: {e}"
                error_history.append(error_msg)
                yield ToolCallEvent("tool_result", "generate_sql", f"❌ {error_msg}", "error")
                continue

            # Step 6: 执行 SQL
            yield ToolCallEvent("tool_start", "run_sql", f"正在执行查询...{attempt_label}", "running")
            try:
                rows = vanna.run_sql(sql)
                row_count = len(rows) if rows else 0
                yield ToolCallEvent("tool_result", "run_sql", f"查询完成，返回 {row_count} 条记录", "success")
                break  # 成功，跳出重试循环

            except Exception as e:
                error_msg = f"SQL执行错误: {e}"
                error_history.append(error_msg)
                yield ToolCallEvent("tool_result", "run_sql", f"❌ {error_msg}", "error")
                sql = None  # 重置，准备重试
                continue

        # 检查是否所有重试都失败了
        if sql is None or rows is None:
            all_errors = "\n".join([f"• {err}" for err in error_history])
            yield ToolCallEvent("error", content=f"经过 {MAX_RETRIES} 次尝试仍然失败：\n\n{all_errors}\n\n请尝试更具体的问题描述。")
            return

        # Step 7: 格式化结果
        yield ToolCallEvent("tool_start", "format_result", "正在格式化结果...", "running")
        table_md = _markdown_table(rows)

        if not enforced:
            note = "\n\n⚠️ 未能自动加 company_id 过滤（部分表无 company_id 字段），请手动确认范围。"
        else:
            note = ""

        response_md = f"已执行SQL：\n\n```sql\n{sql}\n```\n\n结果：\n\n{table_md}{note}"
        yield ToolCallEvent("tool_result", "format_result", "结果已格式化", "success")

        # 完成
        yield ToolCallEvent("done", content=response_md, widget=None)


agent_handler = AgentHandler()
