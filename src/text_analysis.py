from api_handlers import openai_client, groq_client
from logger import app_logger
import ollama
from config import load_config

config = load_config()

def analyze_text_opai(text, location):
    try:
        app_logger.debug(f"Analyzing text with OpenAI...")
        client = openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            #model="chatgpt-4o-latest",
            messages=[
                {"role": "system", "content": f"You are a visionary comic scriptwriter collaborating with an AI that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to bring the comic to life. Please go into great detail when explaining the scene to the AI. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics in your script.\n\nInstructions:\n1. **Characters**: Provide distinct and vivid descriptions of each character's physical appearance, clothing, and defining traits. Make the descriptions visually rich and ensure the AI can clearly visualize them.\n\n2. **Scenes**: Describe each scene with specific visual details, including the setting, mood, and atmosphere. Mention any key objects or elements that should be in the background. Include local landmarks or characteristics of {location} when appropriate.\n\n3. **Actions and Poses**: For each panel, describe the character's actions and poses, paying attention to body language and expressions.\n\n4. **Dialogue**: Write out the dialogue between characters, and specify where to place speech bubbles in the panels. Consider local dialects or expressions if relevant.\n\n5. **Panel Descriptions**: For each comic panel, explain how the scene should be framed, such as close-ups, zoomed-out shots, or specific angles.\n\n6. **Style and Color**: Suggest color palettes or art styles that match the tone of the comic and the atmosphere of {location}.\n\n7. **Consistency**: Ensure the story flows smoothly from panel to panel.\n\nOutput Format: Provide your script in a sequential format that breaks down the story panel by panel, with character descriptions, scene descriptions, actions and poses, and dialogue placement."},
                {"role": "user", "content": text}
            ],
            max_tokens=150
        )
        analysis = response.choices[0].message.content.strip()
        app_logger.debug(f"Text analyzed successfully")
        return analysis
    except Exception as e:
        app_logger.error(f"Error analyzing text with OpenAI: {e}")
        return None

def analyze_text_groq(text, location, model_version="llama3-groq-70b-8192-tool-use-preview"):
    app_logger.debug(f"Analyzing text with Groq...")
    client = groq_client()

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are a visionary comic scriptwriter collaborating with an AI that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to bring the comic to life. Please go into great detail when explaining the scene to the AI. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics in your script.\n\nInstructions:\n1. **Characters**: Provide distinct and vivid descriptions of each character's physical appearance, clothing, and defining traits. Make the descriptions visually rich and ensure the AI can clearly visualize them.\n\n2. **Scenes**: Describe each scene with specific visual details, including the setting, mood, and atmosphere. Mention any key objects or elements that should be in the background. Include local landmarks or characteristics of {location} when appropriate.\n\n3. **Actions and Poses**: For each panel, describe the character's actions and poses, paying attention to body language and expressions.\n\n4. **Dialogue**: Write out the dialogue between characters, and specify where to place speech bubbles in the panels. Consider local dialects or expressions if relevant.\n\n5. **Panel Descriptions**: For each comic panel, explain how the scene should be framed, such as close-ups, zoomed-out shots, or specific angles.\n\n6. **Style and Color**: Suggest color palettes or art styles that match the tone of the comic and the atmosphere of {location}.\n\n7. **Consistency**: Ensure the story flows smoothly from panel to panel.\n\nOutput Format: Provide your script in a sequential format that breaks down the story panel by panel, with character descriptions, scene descriptions, actions and poses, and dialogue placement."},
                {"role": "user", "content": text}
            ],
            model=model_version,
            temperature=0.7,
            max_tokens=150,
        )

        result = chat_completion.choices[0].message.content.strip()
        app_logger.debug(f"Text analyzed successfully with Groq.")
        return result
    except Exception as e:
        app_logger.error(f"Error analyzing text with Groq: {e}.")
        return None

def analyze_text_ollama(text, location, model="mistral", system_prompt=None):
    app_logger.debug(f"Analyzing text with Ollama...")
    
    try:
        if system_prompt is None:
            system_prompt = f"You are a visionary comic scriptwriter collaborating with an AI that generates comic strip visuals. Your task is to write a highly detailed and imaginative comic strip script that clearly describes characters, scenes, actions, and dialogue. This script will guide an image generator AI like DALL-E to bring the comic to life. Please go into great detail when explaining the scene to the AI. The comic is set in {location}, so make sure to incorporate relevant local elements and characteristics in your script. Instructions: 1. **Characters**: Provide distinct and vivid descriptions of each character's physical appearance, clothing, and defining traits. Make the descriptions visually rich and ensure the AI can clearly visualize them. 2. **Scenes**: Describe each scene with specific visual details, including the setting, mood, and atmosphere. Mention any key objects or elements that should be in the background. Include local landmarks or characteristics of {location} when appropriate. 3. **Actions and Poses**: For each panel, describe the character's actions and poses, paying attention to body language and expressions. 4. **Dialogue**: Write out the dialogue between characters, and specify where to place speech bubbles in the panels. Consider local dialects or expressions if relevant. 5. **Panel Descriptions**: For each comic panel, explain how the scene should be framed, such as close-ups, zoomed-out shots, or specific angles. 6. **Style and Color**: Suggest color palettes or art styles that match the tone of the comic and the atmosphere of {location}. 7. **Consistency**: Ensure the story flows smoothly from panel to panel. Output Format: Provide your script in a sequential format that breaks down the story panel by panel, with character descriptions, scene descriptions, actions and poses, and dialogue placement."

        response = ollama.chat(model=model, messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text}
        ])

        result = response['message']['content'].strip()
        app_logger.debug(f"Text analyzed successfully with Ollama.")
        return result
    except Exception as e:
        app_logger.error(f"Error analyzing text with Ollama: {e}.")
        return None