import requests

# 1. 检查后端是否运行
try:
    response = requests.get("http://localhost:8018/api/tables")
    print(f"✓ 后端服务运行正常 (状态码: {response.status_code})")
except Exception as e:
    print(f"✗ 后端服务连接失败: {e}")
    exit(1)

# 2. 检查是否有 project 和 company
try:
    # 检查 project
    response = requests.get("http://localhost:8018/api/projects")
    projects = response.json()
    print(f"\n项目列表: {len(projects)} 个项目")
    if projects:
        project_id = projects[0]['id']
        print(f"  - 项目 ID: {project_id}, 名称: {projects[0].get('name', 'N/A')}")

        # 检查 company
        response = requests.get(f"http://localhost:8018/api/projects/{project_id}/companies")
        companies = response.json()
        print(f"\n公司列表: {len(companies)} 个公司")
        if companies:
            company_id = companies[0]['id']
            print(f"  - 公司 ID: {company_id}, 名称: {companies[0].get('name', 'N/A')}")

            # 检查 invoice_project
            response = requests.get(f"http://localhost:8018/api/projects/{project_id}/companies/{company_id}/invoice-projects")
            invoice_projects = response.json()
            print(f"\n发票项目列表: {len(invoice_projects)} 个发票项目")
            if invoice_projects:
                invoice_project_id = invoice_projects[0]['id']
                print(f"  - 发票项目 ID: {invoice_project_id}, 名称: {invoice_projects[0].get('name', 'N/A')}")
                print(f"\n✓ 可以使用 invoice_project_id={invoice_project_id} 进行测试")
            else:
                print("\n⚠ 没有发票项目，需要创建一个")
        else:
            print("\n⚠ 没有公司，需要创建一个")
    else:
        print("\n⚠ 没有项目，需要创建一个")
except Exception as e:
    print(f"\n✗ 检查失败: {e}")
    import traceback
    traceback.print_exc()
