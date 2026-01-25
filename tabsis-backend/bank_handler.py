import fitz  # PyMuPDF
from PIL import Image
import io
import json
import base64
import requests
import numpy as np
import time
from typing import Dict, Any, List
from db import doris_client, ensure_project_db
from config import DORIS_CONFIG
import os

# Initialize RapidOCR
try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
except ImportError:
    ocr_engine = None
    print("RapidOCR not found. OCR features will be disabled.")

class BankStatementHandler:
    def __init__(self):
        self.db = doris_client
        # Configuration for AI
        self.api_key = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
        self.api_url = os.getenv('OPENROUTER_URL', 'https://openrouter.ai/api/v1/chat/completions')
        self.model_name = os.getenv('MODEL_NAME', 'google/gemini-2.0-flash-exp') # Default to a fast vision model

    def process_bank_statement(self, file_content: bytes, project_id: int, company_id: int) -> Dict[str, Any]:
        """
        Process PDF Bank Statement.
        1. Convert PDF to Images
        2. OCR & AI Analysis per page
        3. Validate Balances
        4. Save to Doris
        """
        if not self.api_key:
            raise ValueError("API Key not configured (OPENROUTER_API_KEY or OPENAI_API_KEY)")

        # 1. Convert PDF to Images
        images = self._pdf_to_images(file_content)
        total_pages = len(images)
        
        # 2. Analyze Pages
        ctx = DocumentContext()
        ctx.page_count = total_pages
        
        for i, img in enumerate(images):
            page_num = i + 1
            print(f"Processing page {page_num}/{total_pages}...")
            
            # OCR
            ocr_text = self._ocr_extract_text(img)
            
            # AI Analysis
            page_result = self._analyze_page(img, page_num, total_pages, ctx, ocr_text)
            
            # Update Context
            ctx.update_from_page(page_result)
            
        # 3. Validate Balances (Simple version for now)
        # In a real migration, we would include the full 'reflect_and_correct' logic here.
        # For this MVP, we'll skip the complex retry loop to save tokens/time, 
        # but we should at least log validation errors.
        validation_errors = self._validate_transactions(ctx.transactions)
        
        # 4. Save to Doris
        db_name = ensure_project_db(project_id)
        table_name = f"bank_statement_{project_id}_{company_id}_{int(time.time())}"
        self._save_to_doris(table_name, ctx.to_result(), project_id, company_id, database=db_name)
        
        return {
            "success": True,
            "table_name": table_name,
            "company": ctx.company,
            "bank": ctx.bank,
            "period": ctx.period,
            "transaction_count": len(ctx.transactions),
            "validation_errors": validation_errors
        }

    def _pdf_to_images(self, file_content: bytes, dpi=300) -> List[Image.Image]:
        pdf_document = fitz.open(stream=file_content, filetype="pdf")
        images = []
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            mat = fitz.Matrix(dpi/72, dpi/72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
        return images

    def _ocr_extract_text(self, img: Image.Image) -> str:
        if ocr_engine is None:
            return ""
        try:
            img_array = np.array(img)
            result, _ = ocr_engine(img_array)
            if result:
                return "\n".join([item[1] for item in result])
            return ""
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    def _analyze_page(self, img: Image.Image, page_num: int, total_pages: int, ctx: 'DocumentContext', ocr_text: str) -> Dict[str, Any]:
        # Prompt Template (Simplified from pdftoexcel)
        prompt = f"""
        你是银行对账单处理专家。请分析第 {page_num}/{total_pages} 页。
        
        {ctx.to_prompt_context()}
        
        【OCR文字（仅供核对数字）】
        {ocr_text[:4000]}
        
        请提取：公司名、银行名、对账单期间、新增账户、交易记录。
        ⚠️ 余额在最右列。上一笔余额 + 收入 - 支出 = 当前余额。
        
        返回JSON：
        {{
          "公司名": "",
          "银行名": "",
          "对账单期间": "",
          "新增账户": [{{"账号": "", "账户类型": "", "币种": ""}}],
          "交易记录": [
            {{"交易时间": "YYYY-MM-DD", "项目": "描述", "账号": "", "账户类型": "", "币种": "", "收入": "", "支出": "", "余额": "数字"}}
          ]
        }}
        """
        
        img_base64 = self._image_to_base64(img)
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']
            # Clean markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content)
        except Exception as e:
            print(f"AI API Error: {e}")
            return {}

    def _image_to_base64(self, img: Image.Image) -> str:
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def _validate_transactions(self, transactions: List[Dict]) -> List[str]:
        # Simple validation logic
        errors = []
        # Group by account
        groups = {}
        for i, t in enumerate(transactions):
            key = f"{t.get('账号')}|{t.get('账户类型')}|{t.get('币种')}"
            if key not in groups: groups[key] = []
            groups[key].append((i, t))
            
        for key, items in groups.items():
            if len(items) < 2: continue
            for j in range(1, len(items)):
                prev = items[j-1][1]
                curr = items[j][1]
                try:
                    prev_bal = float(str(prev.get('余额', 0)).replace(',', ''))
                    curr_bal = float(str(curr.get('余额', 0)).replace(',', ''))
                    inc = float(str(curr.get('收入', 0) or 0).replace(',', ''))
                    exp = float(str(curr.get('支出', 0) or 0).replace(',', ''))
                    
                    expected = prev_bal + inc - exp
                    if abs(expected - curr_bal) > 0.05:
                        errors.append(f"Balance mismatch at row {items[j][0]}: Expected {expected}, Got {curr_bal}")
                except:
                    pass
        return errors

    def _save_to_doris(self, table_name: str, data: Dict, project_id: int, company_id: int, database: str = None):
        # Create Table
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            `id` BIGINT AUTO_INCREMENT,
            `project_id` BIGINT,
            `company_id` BIGINT,
            `company_name` VARCHAR(255),
            `bank_name` VARCHAR(255),
            `account_number` VARCHAR(100),
            `account_type` VARCHAR(100),
            `currency` VARCHAR(20),
            `trans_date` DATE,
            `description` TEXT,
            `income` DECIMAL(18, 2),
            `expense` DECIMAL(18, 2),
            `balance` DECIMAL(18, 2),
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        UNIQUE KEY(`id`)
        DISTRIBUTED BY HASH(`id`) BUCKETS 10
        PROPERTIES (
            "replication_num" = "1"
        );
        """
        self.db.execute_update(create_sql, database=database)
        
        # Insert Data
        # For bulk insert, we should use Stream Load, but for MVP simple insert is okay or use excel_handler's logic
        # Here we construct a VALUES string (Not efficient for huge data, but fine for demo)
        # Better: Use Stream Load via CSV
        
        import pandas as pd
        rows = []
        company = data.get('公司名', '')
        bank = data.get('银行名', '')
        
        for t in data.get('交易记录', []):
            rows.append({
                'project_id': project_id,
                'company_id': company_id,
                'company_name': company,
                'bank_name': bank,
                'account_number': t.get('账号'),
                'account_type': t.get('账户类型'),
                'currency': t.get('币种'),
                'trans_date': t.get('交易时间'),
                'description': t.get('项目'),
                'income': t.get('收入') or 0,
                'expense': t.get('支出') or 0,
                'balance': t.get('余额') or 0
            })
            
        if rows:
            df = pd.DataFrame(rows)
            # Use excel_handler's stream_load logic if possible, or just write to CSV and load
            # Let's reuse the stream_load method from excel_handler if we can import it, 
            # or just duplicate the simple logic here.
            from upload_handler import excel_handler
            excel_handler.stream_load(df, table_name, database=database)


class DocumentContext:
    def __init__(self):
        self.company = None
        self.bank = None
        self.period = None
        self.accounts = []
        self.transactions = []
        self.current_account = None
        
    def update_from_page(self, result: Dict):
        if not result: return
        if result.get('公司名'): self.company = result['公司名']
        if result.get('银行名'): self.bank = result['银行名']
        if result.get('对账单期间'): self.period = result['对账单期间']
        
        for acc in result.get('新增账户', []):
            if acc not in self.accounts:
                self.accounts.append(acc)
                self.current_account = acc
                
        for t in result.get('交易记录', []):
            self.transactions.append(t)
            
    def to_prompt_context(self):
        return f"已知公司:{self.company}, 银行:{self.bank}, 账户:{len(self.accounts)}个"
        
    def to_result(self):
        return {
            "公司名": self.company,
            "银行名": self.bank,
            "对账单期间": self.period,
            "账户列表": self.accounts,
            "交易记录": self.transactions
        }

bank_handler = BankStatementHandler()
