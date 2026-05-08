import os
from dotenv import load_dotenv

load_dotenv()

COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

if not COHERE_API_KEY:
    raise EnvironmentError(
        "COHERE_API_KEY is missing.\n"
        "Please set the COHERE_API_KEY environment variable with your Cohere API key.\n"
    )
