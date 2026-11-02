import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is missing. Copy .env.example to .env and set a secure value.")
    DATABASE_PATH = str((BASE_DIR / os.getenv("DATABASE_PATH", "database/business_erp.sqlite3")).resolve())
    UPLOAD_FOLDER = str((BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads")).resolve())
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
