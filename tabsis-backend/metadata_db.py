from tortoise import Tortoise
import os

DB_FILE = os.getenv("METADATA_DB_FILE", "metadata.sqlite3")
DB_URL = f"sqlite://{DB_FILE}"

async def init_metadata_db():
    base_dir = os.path.dirname(DB_FILE)
    if base_dir:
        os.makedirs(base_dir, exist_ok=True)
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["metadata_models"]}
    )
    # Generate schemas
    await Tortoise.generate_schemas()

async def close_metadata_db():
    await Tortoise.close_connections()
