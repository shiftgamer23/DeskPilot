"""Central settings, read from environment / .env. Nothing else in the app reads os.environ."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- LLM provider (swappable: "groq" | "gemini") ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Data paths ---
RAW_TICKETS = ROOT / "data" / "raw" / "support_tickets.jsonl"
SYNTHETIC_DIR = ROOT / "data" / "synthetic"
CUSTOMER_PROFILES = SYNTHETIC_DIR / "customer_profiles.json"
ACCOUNT_NOTES = SYNTHETIC_DIR / "account_notes.json"
FLAGSHIP_SCENARIOS = SYNTHETIC_DIR / "flagship_scenarios.json"
SPLITS = SYNTHETIC_DIR / "splits.json"  # dev / eval / corpus ticket IDs
TICKET_CUSTOMERS = SYNTHETIC_DIR / "ticket_customers.json"  # dev/eval ticket_id -> customer_id

SEED = 42

# --- Retrieval ---
CHROMA_DIR = ROOT / "data" / "index" / "chroma"
CHROMA_COLLECTION = "past_tickets"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Agent / confidence gate ---
# Real dataset queues/types/priorities - the agent's structured decision must use exactly these.
QUEUES = [
    "Technical Support", "Product Support", "Customer Service", "IT Support", "Billing and Payments",
    "Returns and Exchanges", "Service Outages and Maintenance", "Sales and Pre-Sales", "Human Resources",
    "General Inquiry",
]
TICKET_TYPES = ["Incident", "Request", "Problem", "Change"]
PRIORITIES = ["low", "medium", "high"]
ACTIONS = ["auto_resolve", "route", "escalate"]

# Deterministic gate thresholds (empirical - see eval/results/, calibrated on the dev slice, not the
# eval slice, to avoid tuning against the numbers we later report).
AUTO_RESOLVE_MIN_SCORE = 0.02  # hybrid top-1 RRF score (pool=20, rrf_k=60); ceiling is ~0.033 for this config
VIP_REPEAT_MIN_PRIOR = 3  # prior_ticket_count at/above which a premium customer's repeat pattern forces escalation
MAX_AGENT_TURNS = 6  # safety cap on the tool-calling loop

# --- Cache (Phase 6) ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", str(7 * 24 * 3600)))  # 7 days

# --- Persistence (ticket run history; optional - unset means in-memory only, see app/infra/db.py) ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Voice mode (Sarvam AI, English only - see app/infra/voice.py). Unset key = voice endpoints return 503. ---
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
SARVAM_TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "shubh")
VOICE_LANGUAGE = "en-IN"

# --- Observability (Phase 6) ---
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL")
