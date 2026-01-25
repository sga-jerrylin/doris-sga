import pandas as pd
import numpy as np
from io import BytesIO
from typing import Dict, Any, List, Optional
from db import doris_client, project_db_name, ensure_project_db
from upload_handler import excel_handler
import re
from datetime import datetime


class InvoiceHandler:
    """
    发票处理：
    - 优先读取“信息汇总表”，找不到则读取第一个 sheet
    - 先剔除作废/红冲后再做统计
    - 生成销项/进项的两组报表：
        * 表一：公司+货物大类
        * 表二：公司+往来方
    """

    def __init__(self):
        self.db = doris_client

    def process_invoice_file(
        self,
        file_content: bytes,
        project_id: int,
        company_id: int,
        invoice_project_id: Optional[int] = None,
        direction: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        df_raw = self._read_first_sheet(file_content)
        detected_direction = self._detect_direction(filename)
        direction_final = direction or detected_direction

        df_clean = self._standardize_columns(df_raw)
        if df_clean.empty:
            raise ValueError("未解析到有效发票行，请确认上传的是“信息汇总表”且表头匹配。")
        row_count = len(df_clean)
        db_name = ensure_project_db(project_id)
        df_clean["project_id"] = project_id
        df_clean["company_id"] = company_id
        df_clean["invoice_project_id"] = invoice_project_id
        df_clean["direction"] = direction_final

        # 状态标记
        df_clean["is_void"] = df_clean["invoice_status"].astype(str).str.contains("作废", na=False)
        df_clean["is_red"] = df_clean["invoice_status"].astype(str).str.contains("红", na=False)
        df_clean["is_valid"] = ~(df_clean["is_void"] | df_clean["is_red"])

        # 月份信息
        df_clean["invoice_month"] = df_clean["invoice_date"].dt.to_period("M")

        # 处理税率为数字
        df_clean["tax_rate"] = df_clean["tax_rate"].apply(self._to_rate)

        # 货物大类
        df_clean["item_category"] = df_clean["item_name"].apply(self._extract_major_category)

        # 根据方向拆分
        if direction_final == "sales":
            df_sales = df_clean.copy()
            df_purchase = df_clean.head(0)
        elif direction_final == "purchase":
            df_purchase = df_clean.copy()
            df_sales = df_clean.head(0)
        else:
            # 未知时，双向各做一份，避免漏报
            df_sales = df_clean.copy()
            df_purchase = df_clean.copy()

        analysis = self.run_analysis(df_sales, df_purchase)

        # 持久化到 Doris（保留原始行）
        raw_table_name = self._build_raw_table_name(project_id, company_id, invoice_project_id, direction_final)
        self._save_raw_to_doris(raw_table_name, df_clean, database=db_name)

        derived_tables: Dict[str, str] = {}
        if invoice_project_id:
            sales_raw = self._build_raw_table_name(project_id, company_id, invoice_project_id, "sales")
            purchase_raw = self._build_raw_table_name(project_id, company_id, invoice_project_id, "purchase")
            try:
                try:
                    df_sales_full = self._load_doris_table(sales_raw, database=db_name)
                except Exception:
                    df_sales_full = pd.DataFrame()

                try:
                    df_purchase_full = self._load_doris_table(purchase_raw, database=db_name)
                except Exception:
                    df_purchase_full = pd.DataFrame()

                derived = self._build_derived_tables(df_sales_full, df_purchase_full)
                derived_tables = self._save_derived_tables(
                    project_id=project_id,
                    company_id=company_id,
                    invoice_project_id=invoice_project_id,
                    derived=derived,
                    database=db_name,
                )
                analysis = derived.get("analysis") or analysis
            except Exception as e:
                print(f"[InvoiceHandler] Derived tables skipped: {e}")

        return {
            "success": True,
            "direction": direction_final,
            "raw_table_name": raw_table_name,
            "analysis": analysis,
            "derived_tables": derived_tables,
            "row_count": row_count,
        }

    # ----------- 核心分析 -----------
    def run_analysis(self, df_sales: pd.DataFrame, df_purchase: pd.DataFrame) -> Dict[str, Any]:
        summary_rows = []
        sales_tables = {"sales_by_item": [], "sales_by_buyer": []}
        purchase_tables = {"purchase_by_item": [], "purchase_by_seller": []}
        match_tables = {"match_by_category": []}

        # 销项
        if not df_sales.empty:
            sales_valid = df_sales[df_sales["is_valid"]]
            summary_rows.append(self._build_summary("销项", sales_valid, df_sales))
            sales_tables["sales_by_item"] = self._group_table(
                df_all=df_sales,
                df_valid=sales_valid,
                group_keys=["seller_name", "item_category", "tax_rate"]
            )
            sales_tables["sales_by_buyer"] = self._group_table(
                df_all=df_sales,
                df_valid=sales_valid,
                group_keys=["seller_name", "buyer_name", "tax_rate"]
            )

        # 进项
        if not df_purchase.empty:
            purchase_valid = df_purchase[df_purchase["is_valid"]]
            summary_rows.append(self._build_summary("进项", purchase_valid, df_purchase))
            purchase_tables["purchase_by_item"] = self._group_table(
                df_all=df_purchase,
                df_valid=purchase_valid,
                group_keys=["buyer_name", "item_category", "tax_rate"]
            )
            purchase_tables["purchase_by_seller"] = self._group_table(
                df_all=df_purchase,
                df_valid=purchase_valid,
                group_keys=["buyer_name", "seller_name", "tax_rate"]
            )

        if (not df_sales.empty) and (not df_purchase.empty):
            match_tables["match_by_category"] = self._match_sales_purchase(df_sales, df_purchase)

        # 添加行键便于前端 rowKey
        def with_key(rows: List[Dict[str, Any]], prefix: str) -> List[Dict[str, Any]]:
            for i, r in enumerate(rows):
                r["_key"] = f"{prefix}_{i}"
            return rows

        for k in sales_tables:
            sales_tables[k] = with_key(sales_tables[k], k)
        for k in purchase_tables:
            purchase_tables[k] = with_key(purchase_tables[k], k)
        for k in match_tables:
            match_tables[k] = with_key(match_tables[k], k)

        return {
            "summary": summary_rows,
            **sales_tables,
            **purchase_tables,
            **match_tables,
        }

    # ----------- 分析子方法 -----------
    def _build_summary(self, label: str, df_valid: pd.DataFrame, df_all: pd.DataFrame) -> Dict[str, Any]:
        return {
            "category": label,
            "count": int(len(df_valid)),
            "total_amount": float(df_valid["amount_with_tax"].sum() or 0),
            "total_tax": float(df_valid["tax_amount"].sum() or 0),
            "void_count": int(df_all["is_void"].sum()),
            "red_flush_count": int(df_all["is_red"].sum()),
            "months": int(max(1, df_valid["invoice_month"].nunique()))
        }

    def _group_table(self, df_all: pd.DataFrame, df_valid: pd.DataFrame, group_keys: List[str]) -> List[Dict[str, Any]]:
        if df_valid.empty:
            return []

        # 填补空值以便分组
        df_all = df_all.copy()
        df_valid = df_valid.copy()
        for col in group_keys:
            df_all[col] = df_all[col].fillna("未填写")
            df_valid[col] = df_valid[col].fillna("未填写")

        total_amount = df_valid["amount_with_tax"].sum() or 1
        month_count = max(1, df_valid["invoice_month"].nunique())

        rows: List[Dict[str, Any]] = []
        for group_values, g_valid in df_valid.groupby(group_keys, dropna=False):
            if not isinstance(group_values, tuple):
                group_values = (group_values,)

            # 在所有行中（包含作废/红冲）筛同组用于作废/红冲计数
            mask = pd.Series(True, index=df_all.index)
            for col, val in zip(group_keys, group_values):
                mask = mask & (df_all[col] == val)
            g_all = df_all[mask]

            row: Dict[str, Any] = {}
            for col, val in zip(group_keys, group_values):
                row[col] = val

            amount_with_tax = g_valid["amount_with_tax"].sum() or 0
            quantity_sum = float(g_valid["quantity"].sum() or 0)
            weighted_avg_unit_price = 0.0
            if quantity_sum > 0:
                weighted_avg_unit_price = float((g_valid["unit_price"] * g_valid["quantity"]).sum() / quantity_sum)
            invoice_count = int(g_valid["invoice_doc_id"].nunique()) if "invoice_doc_id" in g_valid.columns else int(len(g_valid))
            special_mask = g_valid["invoice_type"].astype(str).str.contains("专", na=False)
            row.update({
                "tax_rate": self._first(g_valid, "tax_rate"),
                "amount_with_tax": float(amount_with_tax),
                "share": round(float(amount_with_tax) / float(total_amount) * 100, 2),
                "quantity": quantity_sum,
                "avg_unit_price": float(weighted_avg_unit_price),
                "max_unit_price": float(g_valid["unit_price"].max(skipna=True) or 0),
                "invoice_count": invoice_count,
                "avg_monthly_invoice_count": float(invoice_count / month_count),
                "special_amount": float(g_valid[special_mask]["amount_with_tax"].sum() or 0),
                "normal_amount": float(g_valid[~special_mask]["amount_with_tax"].sum() or 0),
                "void_count": int(g_all["is_void"].sum()),
                "red_flush_count": int(g_all["is_red"].sum())
            })
            rows.append(row)

        # 按金额倒序
        rows = sorted(rows, key=lambda r: r.get("amount_with_tax", 0), reverse=True)
        return rows

    # ----------- IO & 预处理 -----------
    def _read_first_sheet(self, file_content: bytes) -> pd.DataFrame:
        # 优先读取“信息汇总”相关 sheet（允许信息汇总表1等变体），否则退回第一个 sheet
        excel = pd.ExcelFile(BytesIO(file_content))

        def normalize(name: Any) -> str:
            s = str(name).strip().lower()
            s = re.sub(r"[\s\W_]+", "", s)
            s = re.sub(r"\d+", "", s)
            return s

        best_sheet = None
        best_score = 0
        for name in excel.sheet_names:
            normalized = normalize(name)
            score = 0
            if "信息汇总表" in normalized:
                score = 100
            elif "信息汇总" in normalized:
                score = 90
            elif "信息" in normalized and "汇总" in normalized:
                score = 80
            elif "汇总表" in normalized:
                score = 70
            elif "汇总" in normalized:
                score = 60
            if score > best_score:
                best_score = score
                best_sheet = name

        if not best_sheet:
            best_sheet = excel.sheet_names[0]
        return excel.parse(best_sheet)

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        column_map = {
            "销方名称": "seller_name",
            "销售方名称": "seller_name",
            "购买方名称": "buyer_name",
            "购方名称": "buyer_name",
            "货物或应税劳务名称": "item_name",
            "税率": "tax_rate",
            "金额": "amount",
            "税额": "tax_amount",
            "价税合计": "amount_with_tax",
            "价税合计（含税）": "amount_with_tax",
            "发票状态": "invoice_status",
            "发票票种": "invoice_type",
            "开票日期": "invoice_date",
            "数量": "quantity",
            "单价": "unit_price",
            "发票代码": "invoice_code",
            "发票号码": "invoice_number"
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        # 只保留分析相关列
        needed = [
            "seller_name",
            "buyer_name",
            "item_name",
            "tax_rate",
            "amount",
            "tax_amount",
            "amount_with_tax",
            "invoice_status",
            "invoice_type",
            "invoice_date",
            "quantity",
            "unit_price",
            "invoice_code",
            "invoice_number"
        ]
        for col in needed:
            if col not in df.columns:
                df[col] = None

        # 清理日期
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")

        # 数值列
        for num_col in ["amount", "tax_amount", "amount_with_tax", "quantity", "unit_price"]:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

        # 基础去空行
        df = df.dropna(how="all")
        df = df[
            ~(
                (df["amount_with_tax"] == 0)
                & (df["amount"] == 0)
                & (df["tax_amount"] == 0)
                & df["invoice_date"].isna()
            )
        ]

        df["invoice_doc_id"] = (
            df["invoice_code"].astype(str).fillna("")
            + "_"
            + df["invoice_number"].astype(str).fillna("")
        )

        return df

    def _build_raw_table_name(
        self,
        project_id: int,
        company_id: int,
        invoice_project_id: Optional[int],
        direction: str,
    ) -> str:
        safe_direction = direction if direction in ("sales", "purchase") else "unknown"
        if invoice_project_id:
            return f"invoice_raw_{invoice_project_id}_{safe_direction}"
        return f"invoice_data_{project_id}_{company_id}_{safe_direction}"

    def _column_is_nullable(self, schema: List[Dict[str, Any]], column_name: str) -> bool:
        for row in schema:
            field = (
                row.get("Field")
                or row.get("field")
                or row.get("COLUMN_NAME")
                or row.get("column_name")
                or ""
            )
            if str(field).lower() != column_name.lower():
                continue
            null_flag = (
                row.get("Null")
                or row.get("NULL")
                or row.get("is_nullable")
                or row.get("IS_NULLABLE")
                or ""
            )
            return str(null_flag).strip().upper() in ("YES", "Y", "TRUE", "1")
        return False

    def _ensure_autoinc_not_null(self, table_name: str, create_sql: str, database: Optional[str] = None):
        if self.db.table_exists(table_name, database=database):
            try:
                schema = self.db.get_table_schema(table_name, database=database)
            except Exception:
                schema = []
            if self._column_is_nullable(schema, "id"):
                try:
                    self.db.execute_update(f"DROP TABLE `{table_name}`", database=database)
                except Exception:
                    pass
        self.db.execute_update(create_sql, database=database)

    def _save_raw_to_doris(self, table_name: str, df: pd.DataFrame, database: Optional[str] = None):
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            `id` BIGINT NOT NULL AUTO_INCREMENT,
            `project_id` BIGINT,
            `company_id` BIGINT,
            `invoice_project_id` BIGINT,
            `direction` VARCHAR(20),
            `seller_name` VARCHAR(255),
            `buyer_name` VARCHAR(255),
            `item_name` VARCHAR(255),
            `item_category` VARCHAR(255),
            `tax_rate` DOUBLE,
            `amount` DOUBLE,
            `tax_amount` DOUBLE,
            `amount_with_tax` DOUBLE,
            `invoice_status` VARCHAR(255),
            `invoice_type` VARCHAR(255),
            `invoice_date` DATETIME,
            `quantity` DOUBLE,
            `unit_price` DOUBLE,
            `is_void` BOOLEAN,
            `is_red` BOOLEAN,
            `is_valid` BOOLEAN,
            `invoice_code` VARCHAR(100),
            `invoice_number` VARCHAR(100),
            `invoice_doc_id` VARCHAR(255),
            `invoice_month` VARCHAR(20)
        )
        UNIQUE KEY(`id`)
        DISTRIBUTED BY HASH(`id`) BUCKETS 8
        PROPERTIES ("replication_num" = "1");
        """
        try:
            self._ensure_autoinc_not_null(table_name, create_sql, database=database)

            df = df.copy()
            df["invoice_month"] = df["invoice_month"].astype(str)
            col_order = [
                "project_id",
                "company_id",
                "invoice_project_id",
                "direction",
                "seller_name",
                "buyer_name",
                "item_name",
                "item_category",
                "tax_rate",
                "amount",
                "tax_amount",
                "amount_with_tax",
                "invoice_status",
                "invoice_type",
                "invoice_date",
                "quantity",
                "unit_price",
                "is_void",
                "is_red",
                "is_valid",
                "invoice_code",
                "invoice_number",
                "invoice_doc_id",
                "invoice_month",
            ]
            for col in col_order:
                if col not in df.columns:
                    df[col] = None
            df = df[col_order]
            # 清理字符串列中的换行/制表符，避免 Stream Load 列数错位
            # 使用批量操作提高性能
            obj_cols = df.select_dtypes(include=['object']).columns
            if len(obj_cols) > 0:
                df[obj_cols] = df[obj_cols].fillna("").astype(str).apply(
                    lambda col: col.str.replace(r'[\n\r\t]', ' ', regex=True).replace({"nan": "", "<NA>": ""})
                )
            try:
                excel_handler.stream_load(df, table_name, max_filter_ratio=0.02, database=database)
            except Exception as e:
                if "auto increment column should be NOT NULL" in str(e):
                    try:
                        self.db.execute_update(f"DROP TABLE `{table_name}`", database=database)
                    except Exception:
                        pass
                    self._ensure_autoinc_not_null(table_name, create_sql, database=database)
                    excel_handler.stream_load(df, table_name, max_filter_ratio=0.02, database=database)
                else:
                    raise
        except Exception as e:
            raise RuntimeError(f"[InvoiceHandler] Doris load failed for {table_name}: {e}") from e

    def _load_doris_table(self, table_name: str, database: Optional[str] = None) -> pd.DataFrame:
        rows = self.db.execute_query(f"SELECT * FROM `{table_name}`", database=database)
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        if "invoice_date" in df.columns:
            df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
        for num_col in ["amount", "tax_amount", "amount_with_tax", "quantity", "unit_price", "tax_rate"]:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)
        for bool_col in ["is_void", "is_red", "is_valid"]:
            if bool_col in df.columns:
                df[bool_col] = df[bool_col].astype(bool)
        return df

    def _build_derived_tables(self, df_sales: pd.DataFrame, df_purchase: pd.DataFrame) -> Dict[str, Any]:
        analysis = self.run_analysis(df_sales, df_purchase)

        def drop_key(df: pd.DataFrame) -> pd.DataFrame:
            if "_key" in df.columns:
                return df.drop(columns=["_key"])
            return df

        derived = {
            "analysis": analysis,
            "table1": drop_key(pd.DataFrame(analysis.get("sales_by_item") or [])),
            "table2": drop_key(pd.DataFrame(analysis.get("sales_by_buyer") or [])),
            "table3": drop_key(pd.DataFrame(analysis.get("purchase_by_item") or [])),
            "table4": drop_key(pd.DataFrame(analysis.get("purchase_by_seller") or [])),
            "table5": drop_key(pd.DataFrame(analysis.get("match_by_category") or [])),
        }
        return derived

    def _save_derived_tables(
        self,
        project_id: int,
        company_id: int,
        invoice_project_id: int,
        derived: Dict[str, Any],
        database: Optional[str] = None,
    ) -> Dict[str, str]:
        table_names = {
            "table1": f"invoice_table1_sales_category_{invoice_project_id}",
            "table2": f"invoice_table2_sales_customer_{invoice_project_id}",
            "table3": f"invoice_table3_purchase_category_{invoice_project_id}",
            "table4": f"invoice_table4_purchase_supplier_{invoice_project_id}",
            "table5": f"invoice_table5_match_{invoice_project_id}",
        }

        t1 = derived.get("table1") if derived.get("table1") is not None else pd.DataFrame()
        t2 = derived.get("table2") if derived.get("table2") is not None else pd.DataFrame()
        t3 = derived.get("table3") if derived.get("table3") is not None else pd.DataFrame()
        t4 = derived.get("table4") if derived.get("table4") is not None else pd.DataFrame()
        t5 = derived.get("table5") if derived.get("table5") is not None else pd.DataFrame()

        self._save_agg_table(
            table_name=table_names["table1"],
            project_id=project_id,
            company_id=company_id,
            invoice_project_id=invoice_project_id,
            df=t1,
            dimensions=["seller_name", "item_category", "tax_rate"],
            database=database,
        )
        self._save_agg_table(
            table_name=table_names["table2"],
            project_id=project_id,
            company_id=company_id,
            invoice_project_id=invoice_project_id,
            df=t2,
            dimensions=["seller_name", "buyer_name", "tax_rate"],
            database=database,
        )
        self._save_agg_table(
            table_name=table_names["table3"],
            project_id=project_id,
            company_id=company_id,
            invoice_project_id=invoice_project_id,
            df=t3,
            dimensions=["buyer_name", "item_category", "tax_rate"],
            database=database,
        )
        self._save_agg_table(
            table_name=table_names["table4"],
            project_id=project_id,
            company_id=company_id,
            invoice_project_id=invoice_project_id,
            df=t4,
            dimensions=["buyer_name", "seller_name", "tax_rate"],
            database=database,
        )
        self._save_match_table(
            table_name=table_names["table5"],
            project_id=project_id,
            company_id=company_id,
            invoice_project_id=invoice_project_id,
            df=t5,
            database=database,
        )
        return table_names

    def _save_agg_table(
        self,
        table_name: str,
        project_id: int,
        company_id: int,
        invoice_project_id: int,
        df: pd.DataFrame,
        dimensions: List[str],
        database: Optional[str] = None,
    ):
        df = df if df is not None else pd.DataFrame()

        metric_columns = [
            ("amount_with_tax", "DOUBLE"),
            ("share", "DOUBLE"),
            ("quantity", "DOUBLE"),
            ("avg_unit_price", "DOUBLE"),
            ("max_unit_price", "DOUBLE"),
            ("invoice_count", "BIGINT"),
            ("avg_monthly_invoice_count", "DOUBLE"),
            ("special_amount", "DOUBLE"),
            ("normal_amount", "DOUBLE"),
            ("void_count", "BIGINT"),
            ("red_flush_count", "BIGINT"),
        ]

        dim_defs = []
        for d in dimensions:
            if d == "tax_rate":
                dim_defs.append(("tax_rate", "DOUBLE"))
            else:
                dim_defs.append((d, "VARCHAR(255)"))

        schema_cols = (
            [("project_id", "BIGINT"), ("company_id", "BIGINT"), ("invoice_project_id", "BIGINT")]
            + dim_defs
            + metric_columns
        )

        cols_sql = ",\n                ".join([f"`{name}` {tp}" for name, tp in schema_cols])
        create_sql = f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                `id` BIGINT NOT NULL AUTO_INCREMENT,
                {cols_sql}
            )
            UNIQUE KEY(`id`)
            DISTRIBUTED BY HASH(`id`) BUCKETS 8
            PROPERTIES ("replication_num" = "1");
            """

        try:
            self._ensure_autoinc_not_null(table_name, create_sql, database=database)
            try:
                self.db.execute_update(f"TRUNCATE TABLE `{table_name}`", database=database)
            except Exception:
                pass

            if df.empty:
                return

            payload = df.copy()
            payload["project_id"] = project_id
            payload["company_id"] = company_id
            payload["invoice_project_id"] = invoice_project_id
            col_order = [c[0] for c in schema_cols]
            defaults: Dict[str, Any] = {}
            for name, tp in schema_cols:
                if name in ("project_id", "company_id", "invoice_project_id"):
                    continue
                if tp.startswith("VARCHAR"):
                    defaults[name] = ""
                else:
                    defaults[name] = 0

            for col, default_value in defaults.items():
                if col not in payload.columns:
                    payload[col] = default_value
            payload = payload[col_order]
            excel_handler.stream_load(payload, table_name, database=database)
        except Exception as e:
            print(f"[InvoiceHandler] Doris load skipped: {e}")

    def _save_match_table(
        self,
        table_name: str,
        project_id: int,
        company_id: int,
        invoice_project_id: int,
        df: pd.DataFrame,
        database: Optional[str] = None,
    ):
        df = df if df is not None else pd.DataFrame()

        create_sql = f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                `id` BIGINT NOT NULL AUTO_INCREMENT,
                `project_id` BIGINT,
                `company_id` BIGINT,
                `invoice_project_id` BIGINT,
                `company_name` VARCHAR(255),
                `item_category` VARCHAR(255),
                `sales_quantity` DOUBLE,
                `purchase_quantity` DOUBLE,
                `quantity_diff` DOUBLE,
                `sales_avg_unit_price` DOUBLE,
                `purchase_avg_unit_price` DOUBLE,
                `avg_unit_price_diff` DOUBLE
            )
            UNIQUE KEY(`id`)
            DISTRIBUTED BY HASH(`id`) BUCKETS 8
            PROPERTIES ("replication_num" = "1");
            """

        try:
            self._ensure_autoinc_not_null(table_name, create_sql, database=database)
            try:
                self.db.execute_update(f"TRUNCATE TABLE `{table_name}`", database=database)
            except Exception:
                pass

            if df.empty:
                return

            payload = df.copy()
            payload["project_id"] = project_id
            payload["company_id"] = company_id
            payload["invoice_project_id"] = invoice_project_id
            col_order = [
                "project_id",
                "company_id",
                "invoice_project_id",
                "company_name",
                "item_category",
                "sales_quantity",
                "purchase_quantity",
                "quantity_diff",
                "sales_avg_unit_price",
                "purchase_avg_unit_price",
                "avg_unit_price_diff",
            ]
            defaults = {
                "company_name": "",
                "item_category": "",
                "sales_quantity": 0.0,
                "purchase_quantity": 0.0,
                "quantity_diff": 0.0,
                "sales_avg_unit_price": 0.0,
                "purchase_avg_unit_price": 0.0,
                "avg_unit_price_diff": 0.0,
            }
            for col, default_value in defaults.items():
                if col not in payload.columns:
                    payload[col] = default_value
            payload = payload[col_order]
            excel_handler.stream_load(payload, table_name, database=database)
        except Exception as e:
            print(f"[InvoiceHandler] Doris load skipped: {e}")

    def _match_sales_purchase(self, df_sales: pd.DataFrame, df_purchase: pd.DataFrame) -> List[Dict[str, Any]]:
        sales_valid = df_sales[df_sales["is_valid"]].copy()
        purchase_valid = df_purchase[df_purchase["is_valid"]].copy()
        if sales_valid.empty and purchase_valid.empty:
            return []

        def most_common_nonempty(df: pd.DataFrame, col: str) -> str:
            if df.empty or col not in df.columns:
                return ""
            s = df[col].astype(str).fillna("").map(lambda x: x.strip())
            s = s[s != ""]
            if s.empty:
                return ""
            return str(s.value_counts().idxmax())

        company_name = most_common_nonempty(sales_valid, "seller_name") or most_common_nonempty(purchase_valid, "buyer_name")
        if not company_name:
            company_name = most_common_nonempty(sales_valid, "buyer_name") or most_common_nonempty(purchase_valid, "seller_name")

        def agg(df: pd.DataFrame) -> pd.DataFrame:
            if df.empty:
                return pd.DataFrame(columns=["item_category", "quantity", "avg_unit_price"])
            grouped = df.groupby(["item_category"], dropna=False)
            qty = grouped["quantity"].sum().astype(float)
            price_num = (df["unit_price"] * df["quantity"]).groupby(df["item_category"]).sum().astype(float)
            avg_price = (price_num / qty.replace({0: np.nan})).fillna(0.0)
            return pd.DataFrame(
                {
                    "item_category": qty.index,
                    "quantity": qty.values,
                    "avg_unit_price": avg_price.values,
                }
            )

        sales_agg = agg(sales_valid).rename(
            columns={"quantity": "sales_quantity", "avg_unit_price": "sales_avg_unit_price"}
        )
        purchase_agg = agg(purchase_valid).rename(
            columns={"quantity": "purchase_quantity", "avg_unit_price": "purchase_avg_unit_price"}
        )

        merged = pd.merge(sales_agg, purchase_agg, on="item_category", how="outer")
        merged = merged.fillna(0)
        merged["company_name"] = company_name or ""
        merged["quantity_diff"] = merged["sales_quantity"] - merged["purchase_quantity"]
        merged["avg_unit_price_diff"] = merged["sales_avg_unit_price"] - merged["purchase_avg_unit_price"]

        merged = merged.sort_values(by="sales_quantity", ascending=False)
        cols = [
            "company_name",
            "item_category",
            "sales_quantity",
            "purchase_quantity",
            "quantity_diff",
            "sales_avg_unit_price",
            "purchase_avg_unit_price",
            "avg_unit_price_diff",
        ]
        return merged[cols].to_dict(orient="records")

    # ----------- 工具方法 -----------
    def _detect_direction(self, filename: Optional[str]) -> str:
        if not filename:
            return "unknown"
        if "进项" in filename:
            return "purchase"
        if "销项" in filename:
            return "sales"
        return "unknown"

    def _extract_major_category(self, name: Any) -> str:
        if not isinstance(name, str):
            return "未分类"
        if "*" in name:
            parts = [p for p in name.split("*") if p]
            return parts[0] if parts else name
        return name

    def _to_rate(self, value: Any) -> float:
        if pd.isna(value):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if s.endswith("%"):
            try:
                return float(s.rstrip("%")) / 100
            except:
                return 0.0
        try:
            return float(s)
        except:
            return 0.0

    def _first(self, df: pd.DataFrame, col: str) -> Any:
        return df[col].iloc[0] if col in df.columns and len(df) > 0 else None


invoice_handler = InvoiceHandler()
