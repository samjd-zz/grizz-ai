import requests
import groq
from openai import OpenAI

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

def groq_client():
    return groq.Groq(api_key=config.GROQ_API_KEY)

def perplexity_client():
    return OpenAI(api_key=config.PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")