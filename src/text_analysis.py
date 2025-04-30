import warnings
# Suppress the specific LangChain deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*BaseChatModel.__call__.*")

import os
import dotenv
from datetime import datetime
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import logging

# Configure more verbose logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
dotenv.load_dotenv(dotenv_path)

# Set OpenAI API key explicitly for langchain
os.environ["OPENAI_API_KEY"] = os.getenv("API_KEY_OPENAI", "")

# Force reload config to ensure we get the latest values
from importlib import reload
import config as config_module
reload(config_module)
from config import load_config

# Make sure we've got the freshest config
config = load_config()

from api_handlers import elevenlabs_client
from utils import unload_ollama_model, filter_content
from logger import app_logger
from config import load_config

config = load_config()

YOGI_BEAR_VOICE_ID = None  # Global variable to store Yogi Bear voice ID

def get_filtered_words():
    # Get the list of filtered words from the filter_content function
    return filter_content("", strict=True).split()

def get_no_news_script(location):
    """Generate a consistent script for when there are no news events"""
    script = f"""Panel 1:
Frame: Wide shot of newsroom interior
Setting: A modern newsroom in {location} with large windows showing the town's scenic landscape. News monitors on walls display local updates.
Characters: Two local reporters at their desks
Action: Reporters diligently checking various news sources and social media feeds on their computers
Dialogue: "It's been a quiet news day."

Panel 2:
Frame: Medium close-up through window
Setting: Same newsroom, focusing on the large window with town view
Characters: One reporter holding a coffee mug
Action: Reporter taking a thoughtful pause, looking out at the peaceful town scenery
Dialogue: "Sometimes no news is good news."

Panel 3:
Frame: Wide group shot
Setting: Newsroom planning area with community board
Characters: Reporters and local community members
Action: Group gathered around planning board, discussing future stories and community engagement
Dialogue: "Let's focus on positive community stories!"

Summary:
Panel 1: Local reporters diligently checking various news sources for updates, showcasing their commitment to keeping the community informed.
Panel 2: A peaceful moment as reporters take in the serene view of the town, reflecting on the quiet news day.
Panel 3: Reporters actively engaging with community members to plan future stories and events, turning a quiet news day into an opportunity for community connection.

Style and Color:
Use warm, natural lighting throughout. The color palette should include soft blues and greens from the window views, warm wood tones from the office furniture, and pops of color from the news monitors and community board.

Consistency:
Maintain a positive, forward-looking tone throughout the panels."""
    return script

def extract_panel_summaries(summary):
    """Extract just the panel summaries without style/consistency sections"""
    # Split by newlines and keep only panel summaries
    lines = summary.split('\n')
    panel_summaries = []
    for line in lines:
        if line.startswith('Panel ') and ':' in line:
            panel_summary = line.split(':', 1)[1].strip()
            # Stop if we hit style/consistency sections
            if 'Style and Color:' in panel_summary or 'Consistency:' in panel_summary:
                break
            panel_summaries.append(panel_summary)
    return panel_summaries

def summarize_comic_text(text, model=None, system_prompt=None):
    # Force load the latest config
    fresh_config = load_config()
    
    # Always get the value directly from environment, then fall back to config
    model_name = os.getenv('OPENAI_TEXT_ANALYZE_MODEL') or (model if model else fresh_config.OPENAI_TEXT_ANALYZE_MODEL)
    
    # Print direct debug information
    print(f"DEBUG - Using OpenAI model for summary: {model_name}")
    app_logger.info(f"Summarize comic text with OpenAI using model: {model_name}...")
    
    try:
        if system_prompt is None:
            system_prompt = f"""You are a creative and imaginative news writer with a talent for summarizing comic strips. Your task is to create concise and engaging summaries for each panel of a comic strip. The summaries should capture the essence of each panel while maintaining the flow of the story.

Instructions:
1. Analyze the provided comic script and identify the individual panels.
2. For each panel, create a brief summary that captures the key elements:
   - Characters present
   - Setting or background
   - Actions or events occurring
   - Any significant dialogue or text
3. Keep each panel summary concise, ideally 2-3 sentences long.
4. Ensure the summaries flow together to tell a coherent story.
5. Maintain the tone and style of the original comic.

Output Format: Provide your summaries in the following format:

Panel 1: [Summary of the first panel]
Panel 2: [Summary of the second panel]
Panel 3: [Summary of the third panel]

IMPORTANT: Always provide exactly three panel summaries, regardless of the number of panels in the original script. If the original has fewer than three panels, extrapolate logically. If it has more, condense the story into three key moments.
IMPORTANT: Avoid any content that may be considered inappropriate or offensive, ensuring the image aligns with content policies.
"""

        # Use OpenAI instead of Ollama
        openai_api_key = os.environ.get("OPENAI_API_KEY") or config.OPENAI_API_KEY
        if not openai_api_key:
            app_logger.error("OpenAI API key not found. Please set API_KEY_OPENAI in your environment.")
            return "Panel 1: First panel of the comic.\nPanel 2: Second panel of the comic.\nPanel 3: Third panel of the comic."
            
        # Use the same optimal settings for the summary generation
        chat = ChatOpenAI(
            model_name=model_name,  # Use the explicitly determined model_name instead of parameter
            temperature=0.7,  # Keep temperature moderate for summaries
            max_tokens=1000,  # Shorter limit for summaries
            openai_api_key=openai_api_key
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text)
        ]
        
        response = chat(messages)

        result = response.content.strip()
        app_logger.debug(f"Text summarized successfully with OpenAI using model: {model_name}.")
        return result
    except Exception as e:
        app_logger.error(f"Error summarizing text with OpenAI using model: {model_name}: {e}.")
        # Provide a simple fallback summary
        return "Panel 1: First panel of the comic.\nPanel 2: Second panel of the comic.\nPanel 3: Third panel of the comic."

def analyze_text_ollama(text, location, comic_artist_style, model=None, system_prompt=None):
    """
    Note: Despite the function name including 'ollama', this function now uses OpenAI's API.
    The name is kept for backward compatibility with existing code.
    """
    # Force load the latest config
    fresh_config = load_config()
    
    # Always get the value directly from environment, then fall back to config
    model_name = os.getenv('OPENAI_TEXT_ANALYZE_MODEL') or (model if model else fresh_config.OPENAI_TEXT_ANALYZE_MODEL)
    
    # Print direct debug information
    print(f"DEBUG - Using OpenAI model: {model_name}")
    app_logger.info(f"Analyzing text with OpenAI using model: {model_name}...")
    
    try:
        filtered_words = get_filtered_words()
        filtered_words_str = ", ".join(filtered_words)
        if system_prompt is None:
            system_prompt = f"""You are a visionary comic scriptwriter collaborating with an AI {comic_artist_style} 
            that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script 
            that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to 
            bring the comic to life. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics.

IMPORTANT: Do not use any of the following words or phrases in your script: {filtered_words_str}. These words may trigger content filters, so please use alternative language or descriptions.
IMPORTANT: Please make sure the panel descriptions are clear and detailed, focusing on visual elements that can be depicted in an image.
IMPORTANT: Only generate 3 panels per comic strip.
IMPORTANT: Avoid any content that may be considered inappropriate or offensive, ensuring the image aligns with content policies.

Instructions:
1. For each panel, provide the following information in a structured format:
   Frame: Describe the camera angle and shot type (e.g., wide shot, close-up, medium shot)
   Setting: Describe the location and environment in detail, including time of day, weather, and key visual elements
   Characters: List and describe the characters present in the panel, including their appearance, expressions, and positioning
   Action: Describe what is happening in the panel with specific visual details
   Dialogue: Include any speech or text that should appear (optional)

2. After the panel descriptions, provide a summary section with a brief description of each panel's key elements.

Output Format:

Panel 1:
Frame: [Camera angle and shot type]
Setting: [Detailed description of location]
Characters: [Description of characters present]
Action: [What is happening in the panel]
Dialogue: [Any speech or text, if needed]

Panel 2:
[Same format as Panel 1]

Panel 3:
[Same format as Panel 1]

Summary:
Panel 1: [Brief summary of first panel]
Panel 2: [Brief summary of second panel]
Panel 3: [Brief summary of third panel]

Style and Color:
[Describe the overall visual style and color palette]

Consistency:
[Notes on maintaining visual consistency across panels]"""

        # Use OpenAI instead of Ollama
        try:
            # Use the API key already set in the environment
            openai_api_key = os.environ.get("OPENAI_API_KEY") or config.OPENAI_API_KEY
            if not openai_api_key:
                app_logger.error("OpenAI API key not found. Please set API_KEY_OPENAI in your environment.")
                return None, None, None
                
            # Set up ChatOpenAI with appropriate settings for the model
            # For GPT-4-1106-mini, we can use higher temperature for more creative outputs
            # We'll also increase the max_tokens for longer comic scripts
            chat = ChatOpenAI(
                model_name=model_name,  # Use the explicitly determined model_name instead of parameter
                temperature=0.8,  # Slightly higher for more creative outputs
                max_tokens=4000,  # Ensure we get full-length scripts
                openai_api_key=openai_api_key
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=text)
            ]
            
            response = chat(messages)
            
            comic_script = response.content.strip()
            app_logger.debug(f"Text analyzed successfully with OpenAI using model: {model_name}.")
        except Exception as openai_error:
            app_logger.error(f"Error using OpenAI: {openai_error}. Falling back to summarize_comic_text.")
            return None, None, None
        
        # Extract summary from the comic script
        summary_start = comic_script.find("Summary:")
        if summary_start != -1:
            summary = comic_script[summary_start:]
            comic_script = comic_script[:summary_start].strip()
            # Extract just the panel summaries without style/consistency sections
            panel_summaries = extract_panel_summaries(summary)
        else:
            # If no summary is found, generate one using OpenAI again
            try:
                summary_prompt = f"""Summarize the following comic script into three panel summaries:

{comic_script}

Output format:
Panel 1: [Brief summary]
Panel 2: [Brief summary]
Panel 3: [Brief summary]"""
                
                # Reuse the same chat client with API key already set
                summary_messages = [HumanMessage(content=summary_prompt)]
                summary_response = chat(summary_messages)
                summary = summary_response.content.strip()
                panel_summaries = extract_panel_summaries(summary)
            except Exception as summary_error:
                app_logger.error(f"Error generating summary with OpenAI: {summary_error}")
                summary = f"Panel 1: First panel of the comic.\nPanel 2: Second panel of the comic.\nPanel 3: Third panel of the comic."
                panel_summaries = ["First panel of the comic", "Second panel of the comic", "Third panel of the comic"]
        
        app_logger.debug("Generated summary for the comic script.")
        
        return comic_script, summary, panel_summaries
    except Exception as e:
        app_logger.error(f"Error analyzing text with OpenAI: {e}.")
        return None, None, None

def create_yogi_bear_voice():
    global YOGI_BEAR_VOICE_ID
    try:
        app_logger.debug("Creating Yogi Bear voice...")
        client = elevenlabs_client()

        # Check if the Yogi Bear voice already exists
        voices = client.voices.get_all()

        yogi_bear_voice = next((voice for voice in voices if voice[1] == "Yogi Bear"), None)

        if not yogi_bear_voice:
            app_logger.debug("Yogi Bear voice not found. Creating a new one.")
            # Create a new voice if it doesn't exist
            voice_files = [
                os.path.join(config.TRAINING_FOLDER, 'voices', f)
                for f in os.listdir(os.path.join(config.TRAINING_FOLDER, 'voices'))
                if f.startswith('yogi') and f.endswith('.mp3')
            ]
            
            if not voice_files:
                app_logger.error("No Yogi Bear voice samples found in the training folder.")
                return None

            app_logger.debug(f"Found {len(voice_files)} Yogi Bear voice samples")
            
            try:
                yogi_bear_voice = client.voices.add(
                    name="Yogi Bear",
                    description="Yogi Bear's voice from the classic cartoons",
                    files=voice_files
                )
                app_logger.debug(f"Yogi Bear voice created with ID: {yogi_bear_voice.voice_id}")
            except Exception as e:
                app_logger.error(f"Error adding Yogi Bear voice: {e}")
                app_logger.error(f"Exception type: {type(e)}")
                app_logger.error(f"Exception args: {e.args}")
                return None
        else:
            app_logger.debug(f"Using existing Yogi Bear voice with ID: {yogi_bear_voice.voice_id}")

        YOGI_BEAR_VOICE_ID = yogi_bear_voice.voice_id
        return YOGI_BEAR_VOICE_ID
    except Exception as e:
        app_logger.error(f"Error creating Yogi Bear voice: {e}")
        app_logger.error(f"Exception type: {type(e)}")
        app_logger.error(f"Exception args: {e.args}")
        return None

def speak_elevenLabs(text, title):
    try:
        app_logger.debug(f"Generating speech with ElevenLabs...")
        
        client = elevenlabs_client()

        # Use the Yogi Bear voice if available, otherwise fall back to "Liam"
        voice = YOGI_BEAR_VOICE_ID if YOGI_BEAR_VOICE_ID else "Liam"
        app_logger.debug(f"Using voice: {voice}")

        # Generate audio
        audio_generator = client.generate(
            text=text,
            voice=voice,
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
