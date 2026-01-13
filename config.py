import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

# LLM Settings
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2000
TEMPERATURE = 0.7

# Quality Thresholds
MIN_CONFIDENCE_SCORE = 70
MIN_CONTACT_CONFIDENCE = 80

# Retry Settings
MAX_RETRIES = 2
RETRY_DELAY = 2

# Search Settings
MAX_CONTACTS_PER_SCHOOL = 3
SEARCH_RESULTS_LIMIT = 10

# File Paths
UPLOAD_FOLDER = "data/uploads"
OUTPUT_FOLDER = "data/outputs"
