import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(dotenv_path)

        self.LOCATION = os.getenv("LOCATION", "New York")
        self.SOURCE_DIR = os.getenv("SOURCE_DIR")
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR")
        self.OPENAI_API_KEY = os.getenv("API_KEY_OPENAI")
        self.PERPLEXITY_API_KEY = os.getenv("API_KEY_PERPLEXITY")
        self.STABLE_DIFFUSION_API_KEY = os.getenv("API_KEY_STABLE")
        self.GROQ_API_KEY = os.getenv("API_KEY_GROQ")
        self.FB_APP_ID = os.getenv('FB_APP_ID')
        self.FB_APP_SECRET = os.getenv('FB_APP_SECRET')
        self.FB_PAGE_ID = os.getenv('FB_PAGE_ID')
        self.FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
        self.X_CONSUMER_KEY = os.getenv('X_CONSUMER_KEY')
        self.X_CONSUMER_SECRET = os.getenv('X_CONSUMER_SECRET')
        self.X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
        self.X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')
        self.LISTEN_VOICE_DURATION_SHORT = int(os.getenv('LISTEN_VOICE_DURATION_SHORT', 5))
        self.LISTEN_VOICE_DURATION_MED = int(os.getenv('LISTEN_VOICE_DURATION_MED', 10))
        self.LISTEN_VOICE_DURATION_LONG = int(os.getenv('LISTEN_VOICE_DURATION_LONG', 30))
        self.WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'tiny')
        self.LISTEN_VOICE_ENABLED = os.getenv('LISTEN_VOICE_ENABLED', 'false')
        self.DUCKDUCKGO_APP_NAME = os.getenv('DUCKDUCKGO_APP_NAME', 'grizz_ai_app')
        
def load_config():
    return Config()
