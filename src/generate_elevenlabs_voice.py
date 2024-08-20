import requests

# Replace this with your actual ElevenLabs API key
API_KEY = 'your_elevenlabs_api_key'
API_URL = 'https://api.elevenlabs.io/v1/text-to-speech'

def generate_voice(text, voice='YogiBearDJ', stability=0.75, style=0.75):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    data = {
        "text": text,
        "voice_settings": {
            "stability": stability,
            "style": style
        }
    }
    
    # You can also customize 'voice_settings' based on desired voice behavior
    response = requests.post(f"{API_URL}/{voice}", headers=headers, json=data)
    
    if response.status_code == 200:
        # Save the audio file
        with open("output_yogi_bear_dj.mp3", "wb") as audio_file:
            audio_file.write(response.content)
        print("Voice generated and saved as output_yogi_bear_dj.mp3")
    else:
        print("Failed to generate voice:", response.json())

# Example text for the Yogi Bear DJ character
#text_to_speak = "Hey there, folks! It's Yogi Bear on the air, bringing you the smoothest tunes this side of Jellystone Park!"
#generate_voice(text_to_speak)
