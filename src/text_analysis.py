import ollama
import os
from datetime import datetime

from api_handlers import openai_client, elevenlabs_client
from utils import unload_ollama_model
from logger import app_logger
from config import load_config

config = load_config()

MAX_SCRIPT_LENGTH = 1000  # Maximum length for DALL-E prompt

def truncate_script(script, max_length=MAX_SCRIPT_LENGTH):
    if len(script) <= max_length:
        return script
    return script[:max_length-3] + "..."

def analyze_text_opai(text, location):
    try:
        app_logger.debug(f"Analyzing text with OpenAI...")
        client = openai_client()
        response = client.chat.completions.create(
            model=config.OPENAI_TEXT_ANALYZE_MODEL,
            messages=[
                {"role": "system", "content": f"You are a visionary comic scriptwriter collaborating with an AI that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to bring the comic to life. Please go into great detail when explaining the scene to the AI. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics in your script.\n\nInstructions:\n1. Characters: Provide distinct and vivid descriptions of each character's physical appearance, clothing, and defining traits. Make the descriptions visually rich and ensure the AI can clearly visualize them.\n\n2. Scenes: Describe each scene with specific visual details, including the setting, mood, and atmosphere. Mention any key objects or elements that should be in the background. Include local landmarks or characteristics of {location} when appropriate.\n\n3. Actions and Poses: For each panel, describe the character's actions and poses, paying attention to body language and expressions.\n\n4. Dialogue: Write out the dialogue between characters, and specify where to place speech bubbles in the panels. Consider local dialects or expressions if relevant.\n\n5. Panel Descriptions: For each comic panel, explain how the scene should be framed, such as close-ups, zoomed-out shots, or specific angles.\n\n6. Style and Color: Suggest color palettes or art styles that match the tone of the comic and the atmosphere of {location}.\n\n7. Consistency: Ensure the story flows smoothly from panel to panel.\n\nOutput Format: Provide your script in a sequential format that breaks down the story panel by panel, with character descriptions, scene descriptions, actions and poses, and dialogue placement.\n\nIMPORTANT: Keep your entire response under 1000 characters to ensure it can be used as a DALL-E prompt."},
                {"role": "user", "content": text}
            ],
            max_tokens=500
        )
        analysis = response.choices[0].message.content.strip()
        analysis = truncate_script(analysis)
        app_logger.debug(f"Text analyzed successfully")
        return analysis
    except Exception as e:
        app_logger.error(f"Error analyzing text with OpenAI: {e}")
        return None


def analyze_text_ollama(text, location, model=config.OLLAMA_TEXT_ANALYZE_MODEL, system_prompt=None):
    app_logger.debug(f"Analyzing text with Ollama...")
    
    try:
        if system_prompt is None:
            system_prompt = f"You are a visionary comic scriptwriter collaborating with an AI that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to bring the comic to life. Please go into great detail when explaining the scene to the AI. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics in your script.\n\nInstructions:\n1. Characters: Provide distinct and vivid descriptions of each character's physical appearance, clothing, and defining traits. Make the descriptions visually rich and ensure the AI can clearly visualize them.\n\n2. Scenes: Describe each scene with specific visual details, including the setting, mood, and atmosphere. Mention any key objects or elements that should be in the background. Include local landmarks or characteristics of {location} when appropriate.\n\n3. Actions and Poses: For each panel, describe the character's actions and poses, paying attention to body language and expressions.\n\n4. Dialogue: Write out the dialogue between characters, and specify where to place speech bubbles in the panels. Consider local dialects or expressions if relevant.\n\n5. Panel Descriptions: For each comic panel, explain how the scene should be framed, such as close-ups, zoomed-out shots, or specific angles.\n\n6. Style and Color: Suggest color palettes or art styles that match the tone of the comic and the atmosphere of {location}.\n\n7. Consistency: Ensure the story flows smoothly from panel to panel.\n\nOutput Format: Provide your script in a sequential format that breaks down the story panel by panel, with character descriptions, scene descriptions, actions and poses, and dialogue placement.\n\nIMPORTANT: Keep your entire response under 1000 characters to ensure it can be used as a DALL-E prompt."

        response = ollama.chat(model=model, messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text}
        ])

        result = response['message']['content'].strip()
        result = truncate_script(result)
        app_logger.debug(f"Text analyzed successfully with Ollama.")
        return result
    except Exception as e:
        app_logger.error(f"Error analyzing text with Ollama: {e}.")
        return None
    finally:
        # Ensure model gets unloaded after the conversation is complete or in case of errors
        unload_ollama_model(config.OLLAMA_TEXT_ANALYZE_MODEL)
        app_logger.debug("Unloaded the Ollama model.")

def speak_elevenLabs(text, title, location):
    try:
        text += f" The story takes place in {location}."
        app_logger.debug(f"Generating speech with ElevenLabs...")
        
        client = elevenlabs_client()

        # List available voices
        # response = client.voices.get_all()
        # data = response.json()

        # # Print the data object to inspect its structure
        # print(data)

        # # Ensure the data is a dictionary
        # if isinstance(data, dict) and 'voices' in data:
        #     # Print the available voices
        #     for voice in data['voices']:
        #         if isinstance(voice, dict):  # If the response is a dictionary
        #             print(f"Voice ID: {voice['voice_id']}")
        #             print(f"Name: {voice['name']}")
        #             print(f"Description: {voice.get('description', 'No description available')}")
        #             print(f"Category: {voice.get('category', 'No category available')}")
        #             print("-----------")
        # else:
        #     print("Unexpected response format:", data)

        # Generate audio
        audio_generator = client.generate(
            text=text,
            voice="Liam",
            model="eleven_multilingual_v2"
        )

        # Convert generator to bytes
        audio = b''.join(audio_generator)
        
        # Create a directory for audio files if it doesn't exist
        audio_dir = os.path.join(config.OUTPUT_DIR, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(x for x in title if x.isalnum() or x in [' ', '_']).rstrip()
        filename = f"{safe_title}_{timestamp}.mp3"
        file_path = os.path.join(audio_dir, filename)
        
        # Save the audio file
        with open(file_path, 'wb') as f:
            f.write(audio)
        
        app_logger.debug(f"Audio file saved: {file_path}")
        return file_path
    except Exception as e:
        app_logger.error(f"Error generating speech with ElevenLabs: {e}")
        return None