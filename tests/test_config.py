from src.config import OPENROUTER_API_KEY


if OPENROUTER_API_KEY:
    print("API key loaded successfully")
else:
    print("API key was not found")