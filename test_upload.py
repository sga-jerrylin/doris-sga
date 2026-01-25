import requests
import sys

def test_upload_invoice(file_path, invoice_project_id=1, direction='sales'):
    """测试上传发票接口"""
    url = "http://localhost:8018/api/modules/invoice/upload"

    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'invoice_project_id': str(invoice_project_id),
                'direction': direction
            }

            print(f"正在上传文件: {file_path}")
            print(f"参数: invoice_project_id={invoice_project_id}, direction={direction}")

            response = requests.post(url, files=files, data=data)

            print(f"\n响应状态码: {response.status_code}")
            print(f"响应内容:\n{response.text}")

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print("\n✓ 上传成功!")
                    return True
                else:
                    print("\n✗ 上传失败:", result)
                    return False
            else:
                print(f"\n✗ HTTP 错误 {response.status_code}")
                return False

    except Exception as e:
        print(f"\n✗ 发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 使用测试文件
    test_file = r"测试用例\KN进销项源\2023-2025.06月销项明细\2023年全量发票查询导出结果.xlsx"
    test_upload_invoice(test_file, invoice_project_id=1, direction='sales')
