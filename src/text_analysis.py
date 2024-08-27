import os
from datetime import datetime
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from api_handlers import elevenlabs_client
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
        app_logger.debug(f"Analyzing text with OpenAI using langchain...")
        chat = ChatOpenAI(model=config.OPENAI_TEXT_ANALYZE_MODEL, temperature=0.7)
        
        system_prompt = f"""You are a visionary comic scriptwriter collaborating with an AI that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to bring the comic to life. Please go into great detail when explaining the scene to the AI. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics in your script.
Instructions:
1. Characters: Provide distinct and vivid descriptions of each character's physical appearance, clothing, and defining traits. Make the descriptions visually rich and ensure the AI can clearly visualize them.
2. Scenes: Describe each scene with specific visual details, including the setting, mood, and atmosphere. Mention any key objects or elements that should be in the background. Include local landmarks or characteristics of {location} when appropriate.
3. Actions and Poses: For each panel, describe the character's actions and poses, paying attention to body language and expressions.
4. Dialogue: Write out the dialogue between characters, and specify where to place speech bubbles in the panels. Consider local dialects or expressions if relevant.
5. Panel Descriptions: For each comic panel, explain how the scene should be framed, such as close-ups, zoomed-out shots, or specific angles.
6. Style and Color: Suggest color palettes or art styles that match the tone of the comic and the atmosphere of {location}.
7. Consistency: Ensure the story flows smoothly from panel to panel.
Output Format: Provide your script in a sequential format that breaks down the story panel by panel, with character descriptions, scene descriptions, actions and poses, and dialogue placement.

IMPORTANT: Keep your entire response under 1000 characters to ensure it can be used as a DALL-E prompt."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text)
        ]
        
        response = chat(messages)
        analysis = response.content.strip()
        analysis = truncate_script(analysis)
        app_logger.debug(f"Text analyzed successfully with OpenAI using langchain")
        return analysis
    except Exception as e:
        app_logger.error(f"Error analyzing text with OpenAI using langchain: {e}")
        return None


def analyze_text_ollama(text, location, model=config.OLLAMA_TEXT_ANALYZE_MODEL, system_prompt=None):
    app_logger.debug(f"Analyzing text with Ollama using langchain...")
    
    try:
        if system_prompt is None:
            system_prompt = f"""You are a visionary comic scriptwriter collaborating with an AI that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to bring the comic to life. Please go into great detail when explaining the scene to the AI. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics in your script.
Instructions:
1. Characters: Provide distinct and vivid descriptions of each character's physical appearance, clothing, and defining traits. Make the descriptions visually rich and ensure the AI can clearly visualize them.
2. Scenes: Describe each scene with specific visual details, including the setting, mood, and atmosphere. Mention any key objects or elements that should be in the background. Include local landmarks or characteristics of {location} when appropriate.
3. Actions and Poses: For each panel, describe the character's actions and poses, paying attention to body language and expressions.
4. Dialogue: Write out the dialogue between characters, and specify where to place speech bubbles in the panels. Consider local dialects or expressions if relevant.
5. Panel Descriptions: For each comic panel, explain how the scene should be framed, such as close-ups, zoomed-out shots, or specific angles.
6. Style and Color: Suggest color palettes or art styles that match the tone of the comic and the atmosphere of {location}.
7. Consistency: Ensure the story flows smoothly from panel to panel.
Output Format: Provide your script in a sequential format that breaks down the story panel by panel, with character descriptions, scene descriptions, actions and poses, and dialogue placement.
IMPORTANT: Keep your entire response under 1000 characters to ensure it can be used as a DALL-E prompt."""

        chat = ChatOllama(model=model)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text)
        ]
        
        response = chat(messages)

        result = response.content.strip()
        result = truncate_script(result)
        app_logger.debug(f"Text analyzed successfully with Ollama using langchain.")
        return result
    except Exception as e:
        app_logger.error(f"Error analyzing text with Ollama using langchain: {e}.")
        return None
    finally:
        # Ensure model gets unloaded after the conversation is complete or in case of errors
        unload_ollama_model(config.OLLAMA_TEXT_ANALYZE_MODEL)
        app_logger.debug("Unloaded the Ollama model.")

def speak_elevenLabs(text, title):
    try:
        app_logger.debug(f"Generating speech with ElevenLabs...")
        
        client = elevenlabs_client()

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