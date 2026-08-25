import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = str(DATA_DIR / "moneyops_v2.db")

class Settings(BaseModel):
    APP_NAME: str = "MoneyOps AI V2"
    APP_VERSION: str = "2.0.0"
    TAGLINE: str = "An AI financial incident investigator for Razorpay payment operations."
    
    DATABASE_URL: str = f"sqlite:///{DB_PATH}"
    DB_PATH: str = DB_PATH
    
    # Razorpay Test Mode Credentials
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    
    # AI Investigation Configuration
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini")  # "gemini", "anthropic", "openai", "deterministic"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    
    # ML & Engine Settings
    ISOLATION_FOREST_CONTAMINATION: float = 0.05
    ANOMALY_THRESHOLD: float = 0.65
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "*"]

settings = Settings()
