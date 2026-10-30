"""Database connection settings, read from environment variables or a .env file."""
import os

from dotenv import load_dotenv

load_dotenv()

MYSQL_URL = os.getenv("MYSQL_URL", "mysql+pymysql://retail:retail@localhost:3306/retail")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "retail")
