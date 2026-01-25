@echo off
echo 测试上传发票接口
curl -X POST "http://localhost:8018/api/modules/invoice/upload" ^
  -F "file=@测试用例\AI发票.xlsx" ^
  -F "invoice_project_id=1" ^
  -F "direction=sales" ^
  --verbose
