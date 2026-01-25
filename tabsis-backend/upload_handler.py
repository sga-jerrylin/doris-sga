"""
Excel upload handler.
"""
import pandas as pd
import requests
from typing import Dict, Any, List, Optional
from io import BytesIO
from config import DORIS_STREAM_LOAD, DORIS_CONFIG
from db import doris_client


class ExcelUploadHandler:
    """Excel upload and stream load handler."""

    def __init__(self):
        self.db = doris_client
        self.stream_load_config = DORIS_STREAM_LOAD

    def preview_excel(self, file_content: bytes, rows: int = 10) -> Dict[str, Any]:
        """Preview Excel file."""
        import json
        import numpy as np

        if rows and rows > 0:
            df = pd.read_excel(BytesIO(file_content), nrows=rows)
        else:
            df = pd.read_excel(BytesIO(file_content))

        # Replace NaN/Inf for JSON
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.replace({np.nan: None})

        # Infer types
        column_types: Dict[str, str] = {}
        for col in df.columns:
            dtype = df[col].dtype
            if pd.api.types.is_integer_dtype(dtype):
                column_types[col] = "INT"
            elif pd.api.types.is_float_dtype(dtype):
                column_types[col] = "DECIMAL(18,2)"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                column_types[col] = "DATETIME"
            else:
                column_types[col] = "VARCHAR(500)"

        data = json.loads(df.to_json(orient="records"))

        return {
            "columns": [str(col) for col in df.columns],
            "data": data,
            "row_count": len(df),
            "inferred_types": column_types,
        }

    def create_table(
        self,
        table_name: str,
        columns: Dict[str, str],
        key_columns: List[str] = None,
        database: Optional[str] = None,
    ) -> str:
        """Create table if not exists."""
        if not key_columns:
            key_columns = [list(columns.keys())[0]]

        column_defs = []
        for col_name, col_type in columns.items():
            safe_col_name = col_name.replace(" ", "_").replace("-", "_")
            column_defs.append(f"`{safe_col_name}` {col_type}")

        column_defs_str = ",\n    ".join(column_defs)
        key_columns_str = ", ".join([f"`{k}`" for k in key_columns])

        sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            {column_defs_str}
        )
        DUPLICATE KEY({key_columns_str})
        DISTRIBUTED BY HASH({key_columns_str}) BUCKETS 10
        PROPERTIES (
            "replication_num" = "1"
        )
        """

        self.db.execute_update(sql, database=database)
        return sql

    def import_excel(
        self,
        file_content: bytes,
        table_name: str,
        column_mapping: Dict[str, str] = None,
        create_table_if_not_exists: bool = True,
        column_types: Dict[str, str] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Excel into Doris."""
        import numpy as np

        df = pd.read_excel(BytesIO(file_content))
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna("")

        if column_mapping:
            df = df.rename(columns=column_mapping)

        df.columns = [col.replace(" ", "_").replace("-", "_") for col in df.columns]

        # sanitize strings to avoid CSV parsing errors
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype(str).str.replace("\n", " ", regex=False)
                df[col] = df[col].str.replace("\r", " ", regex=False)
                df[col] = df[col].str.replace("\t", " ", regex=False)

        table_exists = self.db.table_exists(table_name, database=database)

        if not table_exists:
            if not create_table_if_not_exists:
                raise ValueError(f"Table '{table_name}' does not exist")

            if not column_types:
                column_types = {}
                for col in df.columns:
                    dtype = df[col].dtype
                    if pd.api.types.is_integer_dtype(dtype):
                        column_types[col] = "BIGINT"
                    elif pd.api.types.is_float_dtype(dtype):
                        column_types[col] = "DECIMAL(18,2)"
                    elif pd.api.types.is_datetime64_any_dtype(dtype):
                        column_types[col] = "DATETIME"
                    else:
                        column_types[col] = "VARCHAR(500)"

            self.create_table(table_name, column_types, database=database)
        else:
            existing_schema = self.db.get_table_schema(table_name, database=database)

            if len(existing_schema) != len(df.columns):
                self.db.execute_update(f"DROP TABLE `{table_name}`", database=database)

                column_types = {}
                for col in df.columns:
                    dtype = df[col].dtype
                    if pd.api.types.is_integer_dtype(dtype):
                        column_types[col] = "BIGINT"
                    elif pd.api.types.is_float_dtype(dtype):
                        column_types[col] = "DECIMAL(18,2)"
                    elif pd.api.types.is_datetime64_any_dtype(dtype):
                        column_types[col] = "DATETIME"
                    else:
                        column_types[col] = "VARCHAR(500)"

                self.create_table(table_name, column_types, database=database)
                table_exists = False

        result = self.stream_load(df, table_name, database=database)

        return {
            "success": True,
            "table": table_name,
            "rows_imported": len(df),
            "table_created": not table_exists,
            "stream_load_result": result,
        }

    def stream_load(
        self,
        df: pd.DataFrame,
        table_name: str,
        batch_size: int = 10000,
        max_filter_ratio: Optional[float] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Stream load data in batches."""
        import math

        if df.empty:
            return {"Status": "Success", "NumberTotalRows": 0, "NumberLoadedRows": 0}

        if len(df) <= batch_size:
            return self._stream_load_single(df, table_name, max_filter_ratio=max_filter_ratio, database=database)

        total_batches = math.ceil(len(df) / batch_size)
        total_loaded = 0

        print(f"[StreamLoad] Total rows {len(df)}, batches {total_batches}, batch size {batch_size}")

        for i in range(total_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, len(df))
            batch_df = df.iloc[start_idx:end_idx]

            print(f"[StreamLoad] Batch {i+1}/{total_batches} rows {start_idx}-{end_idx}")

            result = self._stream_load_single(batch_df, table_name, max_filter_ratio=max_filter_ratio, database=database)

            if result.get("Status") != "Success":
                raise Exception(f"Batch {i+1} Stream Load failed: {result}")

            total_loaded += result.get("NumberLoadedRows", 0)

        return {
            "Status": "Success",
            "NumberTotalRows": len(df),
            "NumberLoadedRows": total_loaded,
            "BatchCount": total_batches,
        }

    def _stream_load_single(
        self,
        df: pd.DataFrame,
        table_name: str,
        max_filter_ratio: Optional[float] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Single stream load request."""
        # sanitize control chars
        df = df.copy()
        obj_cols = df.select_dtypes(include=["object", "string"]).columns
        if len(obj_cols) > 0:
            df[obj_cols] = df[obj_cols].fillna("").astype(str).apply(
                lambda col: col.str.replace(r"[\x00-\x1F\x7F]", " ", regex=True).replace("nan", "")
            )

        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False, header=False, encoding="utf-8", sep="\t", na_rep="")
        csv_bytes = csv_buffer.getvalue()

        db_name = database or DORIS_CONFIG["database"]
        url = (
            f"http://{self.stream_load_config['host']}:{self.stream_load_config['port']}"
            f"/api/{db_name}/{table_name}/_stream_load"
        )

        columns = [str(c) for c in df.columns]
        headers = {
            "Expect": "100-continue",
            "Content-Type": "text/plain; charset=utf-8",
            "format": "csv",
            "column_separator": "\\t",
            "columns": ",".join(columns),
            "partial_columns": "true",
        }
        if max_filter_ratio is not None:
            headers["max_filter_ratio"] = str(max_filter_ratio)

        response = requests.put(
            url,
            data=csv_bytes,
            headers=headers,
            auth=(self.stream_load_config["user"], self.stream_load_config["password"]),
            timeout=600,
        )

        if response.status_code != 200:
            raise Exception(f"Stream Load failed: {response.text}")

        result = response.json()

        if result.get("Status") != "Success":
            raise Exception(f"Stream Load failed: {result}")

        return result


excel_handler = ExcelUploadHandler()
