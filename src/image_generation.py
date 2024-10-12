import warnings
warnings.filterwarnings("ignore", message="You set `add_prefix_space`. The tokenizer needs to be converted from the slow tokenizers")

import requests
import re
import time
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper 

import matplotlib.pyplot as plt
import torch
from diffusers import FluxPipeline

from logger import app_logger
from config import load_config
from utils import filter_content

config = load_config()

def parse_comic_script(comic_script):
    panels = re.findall(r'Panel \d+:(.*?)(?=Panel \d+:|$)', comic_script, re.DOTALL)
    parsed_panels = []
    for panel in panels[:3]:  # Limit to 3 panels
        frame_match = re.search(r'\(Frame: (.*?)\)', panel)
        setting_match = re.search(r'Setting: (.*?)(?=Characters:|Action:|Dialogue:|$)', panel, re.DOTALL)
        characters_match = re.search(r'Characters: (.*?)(?=Action:|Dialogue:|$)', panel, re.DOTALL)
        action_match = re.search(r'Action: (.*?)(?=Dialogue:|$)', panel, re.DOTALL)
        dialogue_match = re.search(r'Dialogue: (.*?)$', panel, re.DOTALL)

        parsed_panel = {
            'frame': frame_match.group(1) if frame_match else '',
            'setting': setting_match.group(1).strip() if setting_match else '',
            'characters': characters_match.group(1).strip() if characters_match else '',
            'action': action_match.group(1).strip() if action_match else '',
            'dialogue': dialogue_match.group(1).strip() if dialogue_match else ''
        }
        parsed_panels.append(parsed_panel)
    return parsed_panels

def generate_safe_prompt(panel_tuple, retry_count, original_story=None, comic_artist_style=None):
    index, panel = panel_tuple
    style = comic_artist_style or config.COMIC_ARTIST_STYLE
    if retry_count == 0:
        prompt = f"{style}: {panel['frame']} of {panel['setting']}. "
        prompt += f"Characters: {panel['characters']}. "
        prompt += f"Action: {panel['action']}. "
        if panel['dialogue']:
            prompt += f"Include speech bubble with: '{panel['dialogue']}'"
    elif retry_count == 1 and original_story:
        prompt = f"{style}: Create an image based on this story: {original_story}"
    else:
        prompt = f"{style}: A generic scene related to the story. "
        prompt += "Show abstract or symbolic representations of characters and actions. "
    
    return filter_content(prompt, strict=(retry_count > 0))

def generate_flux1_images(comic_script, original_story, comic_artist_style=None):
    app_logger.debug(f"Generating images with FLUX.1-schnell...")

    model_id = config.FLUX1_MODEL_LOCATION

    pipe = FluxPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
    pipe.enable_sequential_cpu_offload() # offload the model to CPU in a sequential manner. This is useful for large batch sizes

    # Parse the comic script into panels
    panels = parse_comic_script(comic_script)
    
    image_urls = []
    for panel_tuple in enumerate(panels, 1):
        # Generate a safe prompt
        prompt = generate_safe_prompt(panel_tuple, 0, original_story, comic_artist_style)
        image = pipe(
            prompt,
            guidance_scale=7.5,  # 0.0 is the for maximum creativity [1 to 20, with most models using a default of 7-7.5]
            output_type="pil",
            num_inference_steps=4, #use a larger number if you are using [dev]
            max_sequence_length=256,
            generator=torch.Generator("cpu")
        ).images[0]
        image_urls.append(image)
        #image.save("flux-schnell.png")
    return image_urls

def generate_dalle_images(comic_script, original_story, comic_artist_style=None):
    try:
        app_logger.debug(f"Generating images with DALL-E using langchain...")
        
        # Create a DallEAPIWrapper instance
        dalle = DallEAPIWrapper(api_key=config.OPENAI_API_KEY, model='dall-e-3')
        
        # Parse the comic script into panels
        panels = parse_comic_script(comic_script)
        
        image_urls = []
        last_request_time = 0
        for panel_tuple in enumerate(panels, 1):
            retry_count = 0
            max_retries = 2  # We now only need 2 retries: original prompt and original story
            while retry_count < max_retries:
                try:
                    # Implement rate limiting
                    current_time = time.time()
                    time_since_last_request = current_time - last_request_time
                    if time_since_last_request < config.DALLE_RATE_LIMIT_PERIOD / config.DALLE_RATE_LIMIT:
                        sleep_time = (config.DALLE_RATE_LIMIT_PERIOD / config.DALLE_RATE_LIMIT) - time_since_last_request
                        app_logger.debug(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds before next DALL-E request")
                        time.sleep(sleep_time)

                    # Generate a safe prompt
                    prompt = generate_safe_prompt(panel_tuple, retry_count, original_story, comic_artist_style)
                    app_logger.debug(f"Attempt {retry_count + 1} for Panel {panel_tuple[0]}. Prompt: {prompt}")

                    # Generate the image
                    image_url = dalle.run(prompt + " IMPORTANT: Avoid any content that may be considered inappropriate or offensive, ensuring the image aligns with content policies.")
                    image_urls.append(image_url)
                    
                    last_request_time = time.time()
                    app_logger.debug(f'Successfully generated image URL for Panel {panel_tuple[0]} with DALL-E using langchain.')
                    break  # Success, exit the retry loop
                except Exception as panel_error:
                    error_message = str(panel_error)
                    app_logger.error(f"Error for Panel {panel_tuple[0]}, Attempt {retry_count + 1}: {error_message}")
                    
                    if "rate_limit_exceeded" in error_message:
                        retry_count += 1
                        wait_time = 60 * retry_count  # Increase wait time with each retry
                        app_logger.warning(f"Rate limit exceeded for Panel {panel_tuple[0]}. Retrying in {wait_time} seconds. Attempt {retry_count}/{max_retries}")
                        time.sleep(wait_time)
                    elif "safety system" in error_message:
                        if retry_count == 0:
                            app_logger.warning(f"Content rejected by safety system for Panel {panel_tuple[0]}. Trying with original story.")
                            retry_count += 1
                        else:
                            app_logger.warning(f"Content rejected by safety system for Panel {panel_tuple[0]} using original story. Skipping this panel.")
                            image_urls.append(None)
                            break
                    else:
                        app_logger.error(f"Unhandled error generating image for Panel {panel_tuple[0]}: {panel_error}")
                        image_urls.append(None)
                        break  # Exit the retry loop for unhandled errors
            
            if retry_count == max_retries:
                app_logger.error(f"Failed to generate image for Panel {panel_tuple[0]} after {max_retries} attempts.")
                image_urls.append(None)
        
        return image_urls
    except Exception as e:
        app_logger.error(f"Error in generate_dalle_images: {e}")
        return None
