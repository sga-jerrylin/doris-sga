#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import os

print("=== 快速诊断上传问题 ===\n")

# 1. 测试后端连接
print("1. 测试后端连接...")
try:
    response = requests.get("http://localhost:8018/api/tables", timeout=5)
    print(f"   ✓ 后端服务正常 (HTTP {response.status_code})\n")
except requests.exceptions.ConnectionError:
    print("   ✗ 无法连接到后端服务 (http://localhost:8018)")
    print("   请确保后端服务正在运行\n")
    exit(1)
except Exception as e:
    print(f"   ✗ 连接错误: {e}\n")
    exit(1)

# 2. 测试上传接口（使用小文件）
print("2. 测试文件上传...")
test_file = r"测试用例\AI发票.xlsx"

if not os.path.exists(test_file):
    print(f"   ✗ 测试文件不存在: {test_file}\n")
    exit(1)

file_size = os.path.getsize(test_file)
print(f"   文件大小: {file_size / 1024:.2f} KB")

try:
    with open(test_file, 'rb') as f:
        files = {'file': (os.path.basename(test_file), f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {
            'invoice_project_id': '1',
            'direction': 'sales'
        }

        print(f"   上传参数: {data}")
        print("   正在上传...")

        response = requests.post(
            "http://localhost:8018/api/modules/invoice/upload",
            files=files,
            data=data,
            timeout=120
        )

        print(f"\n   HTTP 状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("   ✓ 上传成功!")
                print(f"\n   响应详情:")
                print(f"     - 方向: {result.get('direction')}")
                print(f"     - 原始表名: {result.get('raw_table_name')}")
                if 'analysis' in result:
                    analysis = result['analysis']
                    if 'summary' in analysis and analysis['summary']:
                        summary = analysis['summary'][0]
                        print(f"     - 发票数量: {summary.get('count')}")
                        print(f"     - 总金额: ¥{summary.get('total_amount', 0):,.2f}")
            else:
                print("   ✗ 上传失败 (success=false)")
                print(f"\n   响应内容:\n{response.text}")
        else:
            print(f"   ✗ HTTP 错误 {response.status_code}")
            print(f"\n   错误详情:\n{response.text}")

except requests.exceptions.Timeout:
    print("   ✗ 请求超时 (120秒)")
except Exception as e:
    print(f"   ✗ 发生异常: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 诊断完成 ===")
