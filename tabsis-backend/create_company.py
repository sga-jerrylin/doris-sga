import requests

url = "http://localhost:8018/api/projects/1/companies"
payload = {
    "name": "上海未来科技有限公司",
    "tax_id": "91310115MA1KXXXXXX",
    "background_info": "上海未来科技有限公司是一家专注于人工智能和大数据分析的高新技术企业。公司成立于2020年，致力于为企业提供智能化的财务管理和决策支持方案。"
}

try:
    response = requests.post(url, json=payload)
    print(response.status_code)
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
