import requests

from api_handlers import openai_client
from logger import app_logger


def generate_dalle_images(desc):
    try:
        app_logger.debug(f"Generating image with DALL-E...")
        client = openai_client()
        response = client.images.generate(
            model='dall-e-3',
            prompt=desc,
            size='1024x1024',
            quality='standard',
            n=1,
        )
        image_url = response.data[0].url
        image_data = requests.get(image_url).content
        app_logger.debug(f'Successfully generated image with DALL-E.')
        return image_data
    except Exception as e:
        app_logger.error(f"Error generating image with DALL-E: {e}")
        return None
