"""
Doris database client utilities.
"""
import pymysql
from typing import List, Dict, Any, Optional
from config import DORIS_CONFIG


def project_db_name(project_id: int) -> str:
    """Return per-project database name."""
    return f"tabsis_p{project_id}"


class DorisClient:
    """Doris database client."""

    def __init__(self):
        self.config = DORIS_CONFIG

    def _connection_config(self, database: Optional[str] = None, include_database: bool = True) -> Dict[str, Any]:
        cfg = dict(self.config)
        if not include_database:
            cfg.pop("database", None)
            return cfg
        if database is not None:
            cfg["database"] = database
        return cfg

    def get_connection(self, database: Optional[str] = None):
        """Get database connection (optionally override database)."""
        return pymysql.connect(**self._connection_config(database=database))

    def execute_query(self, sql: str, params: tuple = None, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute query and return results."""
        conn = self.get_connection(database=database)
        try:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute(sql, params)
            result = cursor.fetchall()
            return result
        finally:
            conn.close()

    def execute_update(self, sql: str, params: tuple = None, database: Optional[str] = None) -> int:
        """Execute update (INSERT/UPDATE/DELETE/DDL)."""
        conn = self.get_connection(database=database)
        try:
            cursor = conn.cursor()
            affected_rows = cursor.execute(sql, params)
            conn.commit()
            return affected_rows
        finally:
            conn.close()

    def get_tables(self, database: Optional[str] = None) -> List[str]:
        """Get table list for database."""
        sql = "SHOW TABLES"
        result = self.execute_query(sql, database=database)
        db_name = database or self.config.get("database")
        key = f"Tables_in_{db_name}"
        tables: List[str] = []
        for row in result:
            if key in row:
                tables.append(row[key])
            elif row:
                # Fallback: take first value
                tables.append(next(iter(row.values())))
        return tables

    def get_table_schema(self, table_name: str, database: Optional[str] = None) -> List[Dict[str, str]]:
        """Get table schema."""
        sql = f"DESCRIBE {table_name}"
        return self.execute_query(sql, database=database)

    def table_exists(self, table_name: str, database: Optional[str] = None) -> bool:
        """Check if table exists."""
        return table_name in self.get_tables(database=database)

    def create_database_if_not_exists(self, database: str) -> None:
        """Create database if missing."""
        conn = pymysql.connect(**self._connection_config(include_database=False))
        try:
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
            conn.commit()
        finally:
            conn.close()

    def drop_database_if_exists(self, database: str) -> None:
        """Drop database if exists."""
        conn = pymysql.connect(**self._connection_config(include_database=False))
        try:
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
            conn.commit()
        finally:
            conn.close()

    def _escape_string(self, text: str) -> str:
        """Escape string for SQL."""
        conn = self.get_connection()
        try:
            escaped = conn.escape_string(text)
            return f"'{escaped}'"
        finally:
            conn.close()


# Global singleton
doris_client = DorisClient()


def ensure_project_db(project_id: int) -> str:
    """Ensure per-project database exists and return its name."""
    db_name = project_db_name(project_id)
    doris_client.create_database_if_not_exists(db_name)
    return db_name
