"""Point the API at separate test databases so the loaded data is never touched."""
import os

import pytest
from sqlalchemy import create_engine, text

MYSQL_SERVER = os.getenv("TEST_MYSQL_SERVER", "mysql+pymysql://root:root@localhost:3306")
os.environ["MYSQL_URL"] = f"{MYSQL_SERVER}/retail_test"
os.environ["MONGO_DB"] = "retail_test"

with create_engine(MYSQL_SERVER).begin() as conn:
    conn.execute(text("CREATE DATABASE IF NOT EXISTS retail_test"))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from api.mongo_db import transactions  # noqa: E402
from api.sql_db import Base, engine  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    transactions.drop()
    with TestClient(app) as c:  # runs the startup code that creates tables and indexes
        yield c
