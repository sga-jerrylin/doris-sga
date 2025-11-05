"""
Doris Agent - Python 调用示例

这是一个完整的 Python Agent 示例,展示如何通过 HTTP API 与 Doris 数据中台交互。

使用前请确保:
1. Doris 服务已启动: docker-compose up -d
2. 安装依赖: pip install requests pandas
"""

import requests
import json
from typing import Dict, Any, List, Optional


class DorisAgent:
    """Doris 数据中台 Agent 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8018", api_key: Optional[str] = None):
        """
        初始化 Doris Agent
        
        Args:
            base_url: API 基础地址
            api_key: DeepSeek API Key (可选,如果不提供则使用服务端默认配置)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """检查服务健康状态"""
        response = self.session.get(f"{self.base_url}/api/health")
        response.raise_for_status()
        return response.json()
    
    def ask(self, question: str, api_key: Optional[str] = None, 
            model: str = "deepseek-chat") -> Dict[str, Any]:
        """
        使用自然语言提问 (核心 Agent-to-Agent 接口)
        
        Args:
            question: 自然语言问题
            api_key: API Key (可选,覆盖初始化时的配置)
            model: 模型名称
            
        Returns:
            包含 SQL、查询结果和记录数的字典
            
        Example:
            result = agent.ask("2022年广东省有多少个机构?")
            print(f"SQL: {result['sql']}")
            print(f"结果: {result['data']}")
        """
        url = f"{self.base_url}/api/query/natural"
        payload = {"query": question}
        
        # 使用提供的 API Key,或使用初始化时的 API Key
        key = api_key or self.api_key
        if key:
            payload["api_key"] = key
            payload["model"] = model
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def upload_excel(self, file_path: str, table_name: str, 
                     create_table: bool = True) -> Dict[str, Any]:
        """
        上传 Excel 文件到 Doris
        
        Args:
            file_path: Excel 文件路径
            table_name: 目标表名
            create_table: 是否自动创建表
            
        Returns:
            上传结果,包含导入行数等信息
            
        Example:
            result = agent.upload_excel("data.xlsx", "institutions")
            print(f"导入了 {result['rows_imported']} 行数据")
        """
        url = f"{self.base_url}/api/upload"
        
        with open(file_path, 'rb') as f:
            files = {
                'file': (file_path, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            data = {
                'table_name': table_name,
                'create_table': str(create_table).lower()
            }
            response = self.session.post(url, files=files, data=data)
        
        response.raise_for_status()
        return response.json()
    
    def preview_excel(self, file_path: str, rows: int = 10) -> Dict[str, Any]:
        """
        预览 Excel 文件内容
        
        Args:
            file_path: Excel 文件路径
            rows: 预览行数
            
        Returns:
            预览数据和列信息
        """
        url = f"{self.base_url}/api/upload/preview"
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path, f)}
            data = {'rows': rows}
            response = self.session.post(url, files=files, data=data)
        
        response.raise_for_status()
        return response.json()
    
    def query(self, sql: str) -> Dict[str, Any]:
        """
        执行 SQL 查询
        
        Args:
            sql: SQL 查询语句
            
        Returns:
            查询结果
            
        Example:
            result = agent.query("SELECT * FROM institutions LIMIT 10")
            for row in result['data']:
                print(row)
        """
        url = f"{self.base_url}/api/execute"
        payload = {
            "action": "query",
            "params": {"sql": sql}
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        url = f"{self.base_url}/api/tables"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()['tables']
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取表结构
        
        Args:
            table_name: 表名
            
        Returns:
            表结构信息列表
        """
        url = f"{self.base_url}/api/tables/{table_name}/schema"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()['schema']
    
    def create_llm_config(self, resource_name: str, provider_type: str,
                         endpoint: str, model_name: str, 
                         api_key: str, **kwargs) -> Dict[str, Any]:
        """
        创建 LLM 配置
        
        Args:
            resource_name: 资源名称
            provider_type: 提供商类型 (openai, deepseek, qwen 等)
            endpoint: API 端点
            model_name: 模型名称
            api_key: API Key
            **kwargs: 其他参数 (temperature, max_tokens 等)
        """
        url = f"{self.base_url}/api/llm/config"
        payload = {
            "resource_name": resource_name,
            "provider_type": provider_type,
            "endpoint": endpoint,
            "model_name": model_name,
            "api_key": api_key,
            **kwargs
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def main():
    """示例用法"""
    
    # 初始化 Agent (可选提供 API Key)
    agent = DorisAgent(
        base_url="http://localhost:8018",
        api_key="sk-748638f482f74b7392a6dafd89bdd307"  # 替换为你的 API Key
    )
    
    print("=" * 60)
    print("Doris Agent 示例")
    print("=" * 60)
    
    # 1. 健康检查
    print("\n1. 健康检查...")
    try:
        health = agent.health_check()
        print(f"✅ 服务状态: {health}")
    except Exception as e:
        print(f"❌ 服务未启动: {e}")
        return
    
    # 2. 查看所有表
    print("\n2. 查看所有表...")
    try:
        tables = agent.get_tables()
        print(f"📊 数据库中的表: {tables}")
    except Exception as e:
        print(f"❌ 获取表列表失败: {e}")
    
    # 3. 自然语言查询示例
    print("\n3. 自然语言查询示例...")
    questions = [
        "有哪些表?",
        "统计每个表的记录数",
    ]
    
    for question in questions:
        print(f"\n❓ 问题: {question}")
        try:
            result = agent.ask(question)
            print(f"📝 生成的 SQL:\n{result['sql']}")
            print(f"📊 查询结果: {result['data']}")
            print(f"📈 记录数: {result['count']}")
        except Exception as e:
            print(f"❌ 查询失败: {e}")
    
    # 4. 直接 SQL 查询示例
    print("\n4. 直接 SQL 查询示例...")
    try:
        result = agent.query("SHOW DATABASES")
        print(f"📊 数据库列表: {result['data']}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")
    
    # 5. Excel 上传示例 (如果有文件)
    print("\n5. Excel 上传示例...")
    print("💡 提示: 准备一个 Excel 文件,然后使用:")
    print("   result = agent.upload_excel('data.xlsx', 'my_table')")
    
    print("\n" + "=" * 60)
    print("✅ 示例完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()

