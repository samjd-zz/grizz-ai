import requests # type: ignore
import json

API_KEY = 'your_uberduck_api_key'
API_SECRET = 'your_uberduck_api_secret'
API_URL = 'https://api.uberduck.ai/speak'

def generate_uberduck_voice(text, voice='yogi-bear'):
    headers = {
        'accept': 'application/json',
        'authorization': f'Basic {API_KEY}:{API_SECRET}',
        'content-type': 'application/json'
    }
    data = {
        'voice': voice,
        'speech': text
    }

    response = requests.post(API_URL, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        print("Request successful, voice generation started")
        job_id = response.json().get('uuid')
        # You may need to poll for the result based on Uberduck's response structure
        # This depends on Uberduck's specific implementation.
    else:
        print("Failed to initiate voice generation:", response.json())
