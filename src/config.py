import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(dotenv_path)

        self.LOCATION = os.getenv("LOCATION", "New York")
        self.SOURCE_DIR = os.getenv("SOURCE_DIR")
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR")
        self.DB_PATH = os.getenv("DB_PATH")

        self.OPENAI_TEXT_ANALYZE_MODEL=os.getenv('OPENAI_TEXT_ANALYZE_MODEL', 'gpt-4o') #model="chatgpt-4o-latest"
        self.PERPLEXITY_SEARCH_MODEL=os.getenv('PERPLEXITY_SEARCH_MODEL', "llama-3.1-sonar-large-128k-online")
        self.OLLAMA_GROQ_TOOL_MODEL=os.getenv('OLLAMA_GROQ_TOOL_MODEL', "llama-3-groq-70b-tool-use")
        self.OLLAMA_TEXT_ANALYZE_MODEL=os.getenv('OLLAMA_TEXT_ANALYZE_MODEL', 'mistral')

        self.OPENAI_API_KEY = os.getenv("API_KEY_OPENAI")
        self.PERPLEXITY_API_KEY = os.getenv("API_KEY_PERPLEXITY")
        self.STABLE_DIFFUSION_API_KEY = os.getenv("API_KEY_STABLE")
        self.GROQ_API_KEY = os.getenv("API_KEY_GROQ")
        self.API_KEY_ELEVENLABS = os.getenv('API_KEY_ELEVENLABS')
        self.API_KEY_OPENROUTER = os.getenv('API_KEY_OPENROUTER')

        self.WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'tiny')
        self.LISTEN_VOICE_ENABLED = os.getenv('LISTEN_VOICE_ENABLED', 'false')
        self.LISTEN_VOICE_DURATION_SHORT = int(os.getenv('LISTEN_VOICE_DURATION_SHORT', 5))
        self.LISTEN_VOICE_DURATION_MED = int(os.getenv('LISTEN_VOICE_DURATION_MED', 10))
        self.LISTEN_VOICE_DURATION_LONG = int(os.getenv('LISTEN_VOICE_DURATION_LONG', 30))

        self.ELEVENLABS_VOICE = os.getenv('ELEVENLABS_VOICE', 'callum')
        self.ELEVENLABS_VOICE_SPEED = os.getenv('ELEVENLABS_VOICE_SPEED', 'regular')
        self.ELEVENLABS_VOICE_SPEED = os.getenv('ELEVENLABS_REC_MINS', '2.5')
        
        self.FB_APP_ID = os.getenv('FB_APP_ID')
        self.FB_APP_SECRET = os.getenv('FB_APP_SECRET')
        self.FB_PAGE_ID = os.getenv('FB_PAGE_ID')
        self.FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

        self.X_CONSUMER_KEY = os.getenv('X_CONSUMER_KEY')
        self.X_CONSUMER_SECRET = os.getenv('X_CONSUMER_SECRET')
        self.X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
        self.X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')
        
        self.DUCKDUCKGO_APP_NAME = os.getenv('DUCKDUCKGO_APP_NAME', 'grizz_ai_app')
        
        
def load_config():
    return Config()
