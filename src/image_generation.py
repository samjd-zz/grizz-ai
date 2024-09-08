import warnings
# Suppress the specific LangChain deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*BaseChatModel.__call__.*")

import requests
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper 


from logger import app_logger
from config import load_config

config = load_config()

def truncate_prompt(prompt, max_length=1000):
    if len(prompt) <= max_length:
        return prompt
    return prompt[:max_length-3] + "..."

def generate_dalle_images(desc):
    try:
        app_logger.debug(f"Generating image with DALL-E using langchain...")
        
        # Create a DallEAPIWrapper instance
        dalle = DallEAPIWrapper(api_key=config.OPENAI_API_KEY, model='dall-e-3')
        
        truncated_desc = truncate_prompt(f"{config.COMIC_ARTIST_STYLE}: " + desc)
        
        # Generate the image
        image_url = dalle.run(truncated_desc)
        
        # Download the image
        image_data = requests.get(image_url).content
        app_logger.debug(f'Successfully generated image with DALL-E using langchain.')
        return image_data
    except Exception as e:
        app_logger.error(f"Error generating image with DALL-E using langchain: {e}")
        return None
