import os
from dotenv import load_dotenv


class Config:
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(dotenv_path)

        self.ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
        self.SECRET_KEY = os.getenv('SECRET_KEY')
        self.SUNO_COOKIE = os.getenv('SUNO_COOKIE')

        self.LOCATION = os.getenv("LOCATION", "New York")
        self.SOURCE_DIR = os.getenv("SOURCE_DIR")
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR")
        self.DB_PATH = os.getenv("DB_PATH")
        self.LOG_PATH = os.getenv("LOG_PATH")
        self.GENERATE_AUDIO = os.getenv("GENERATE_AUDIO", "false").lower() == "true"
        self.TRAINING_FOLDER = os.getenv("TRAINING_FOLDER")
        self.FLUX1_MODEL_LOCATION = os.getenv("FLUX1_MODEL_LOCATION")
        self.DEFAULT_LAT=os.getenv('DEFAULT_LAT', 50.693802)
        self.DEFAULT_LON=os.getenv('DEFAULT_LON', -121.936584)

        self.OPENAI_TEXT_ANALYZE_MODEL=os.getenv('OPENAI_TEXT_ANALYZE_MODEL', 'gpt-4-turbo') #Using gpt-4-turbo (previously called gpt-4.1-mini)
        self.PERPLEXITY_SEARCH_MODEL=os.getenv('PERPLEXITY_SEARCH_MODEL', "llama-3.1-sonar-large-128k-online")
        self.OLLAMA_GROQ_TOOL_MODEL=os.getenv('OLLAMA_GROQ_TOOL_MODEL', "llama-3-groq-70b-tool-use")
        self.OLLAMA_TEXT_ANALYZE_MODEL=os.getenv('OLLAMA_TEXT_ANALYZE_MODEL', 'llama3-optimized')
        self.TORCH_IMAGE_TO_TEXT_MODEL=os.getenv('TORCH_IMAGE_TO_TEXT_MODEL', 'unified-vl-t5-base')

        self.OPENAI_API_KEY = os.getenv("API_KEY_OPENAI")
        self.PERPLEXITY_API_KEY = os.getenv("API_KEY_PERPLEXITY")
        self.STABLE_DIFFUSION_API_KEY = os.getenv("API_KEY_STABLE")
        self.GROQ_API_KEY = os.getenv("API_KEY_GROQ")
        self.API_KEY_ELEVENLABS = os.getenv('API_KEY_ELEVENLABS')
        self.API_KEY_OPENROUTER = os.getenv('API_KEY_OPENROUTER')
        self.API_KEY_BRAVE_SEARCH = os.getenv('API_KEY_BRAVE_SEARCH')

        self.WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'tiny')
        self.LISTEN_VOICE_ENABLED = os.getenv('LISTEN_VOICE_ENABLED', 'false').lower() == 'true'
        self.LISTEN_VOICE_DURATION_SHORT = int(os.getenv('LISTEN_VOICE_DURATION_SHORT', 5))
        self.LISTEN_VOICE_DURATION_MED = int(os.getenv('LISTEN_VOICE_DURATION_MED', 10))
        self.LISTEN_VOICE_DURATION_LONG = int(os.getenv('LISTEN_VOICE_DURATION_LONG', 30))

        self.ELEVENLABS_VOICE = os.getenv('ELEVENLABS_VOICE', 'callum')
        self.ELEVENLABS_VOICE_SPEED = os.getenv('ELEVENLABS_VOICE_SPEED', 'regular')
        self.ELEVENLABS_REC_MINS = os.getenv('ELEVENLABS_REC_MINS', '2.5')
        
        self.FB_APP_ID = os.getenv('FB_APP_ID')
        self.FB_APP_SECRET = os.getenv('FB_APP_SECRET')
        self.FB_PAGE_ID = os.getenv('FB_PAGE_ID')
        self.FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

        self.X_CONSUMER_KEY = os.getenv('X_CONSUMER_KEY')
        self.X_CONSUMER_SECRET = os.getenv('X_CONSUMER_SECRET')
        self.X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
        self.X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')
        
        self.DUCKDUCKGO_APP_NAME = os.getenv('DUCKDUCKGO_APP_NAME', 'grizz_ai_app')

        self.WEB_PORT = os.getenv('WEB_PORT', 5000)
        self.WEB_DEBUG = os.getenv('WEB_DEBUG', 'true').lower() == 'true'

        # DALL-E rate limit parameters
        self.DALLE_RATE_LIMIT = int(os.getenv('DALLE_RATE_LIMIT', 5))
        self.DALLE_RATE_LIMIT_PERIOD = int(os.getenv('DALLE_RATE_LIMIT_PERIOD', 60))

def load_config():
    return Config()
