import requests
from openai import OpenAI
from elevenlabs import Client

from config import load_config

config = load_config()

def getimg_api_request(endpoint, payload):
    api_key = config.STABLE_DIFFUSION_API_KEY
    url = f"https://api.getimg.ai/v1/{endpoint}"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def openai_client():
    return OpenAI(api_key=config.OPENAI_API_KEY)

def perplexity_client():
    return OpenAI(api_key=config.PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")

# Use the text-to-speech endpoint to convert text into speech
# response = client.text_to_speech("Hello, world!")
# print(response["audio"])
def elevenLabs_client():
    return Client(api_key=config.API_KEY_ELEVENLABS)