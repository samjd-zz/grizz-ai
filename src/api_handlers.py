# Description: This file contains the API handlers for OpenAI, Perplexity and OpenRouter APIs. 
from elevenlabs.client import ElevenLabs
from openai import OpenAI
from config import load_config

config = load_config()

def openai_client():
    return OpenAI(api_key=config.OPENAI_API_KEY)

def perplexity_client():
    return OpenAI(api_key=config.PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")

def openrouter_client():
    return OpenAI(api_key=config.API_KEY_OPENROUTER, base_url="https://openrouter.ai/api/v1")

def elevenlabs_client():
    client = ElevenLabs(api_key=config.API_KEY_ELEVENLABS)
    return client