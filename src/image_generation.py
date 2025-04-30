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
        frame_match = re.search(r'Frame:\s*(.*?)(?=Setting:|$)', panel, re.DOTALL)
        setting_match = re.search(r'Setting:\s*(.*?)(?=Characters:|$)', panel, re.DOTALL)
        characters_match = re.search(r'Characters:\s*(.*?)(?=Action:|$)', panel, re.DOTALL)
        action_match = re.search(r'Action:\s*(.*?)(?=Dialogue:|$)', panel, re.DOTALL)
        dialogue_match = re.search(r'Dialogue:\s*(.*?)(?=\n\n|$)', panel, re.DOTALL)

        parsed_panel = {
            'frame': frame_match.group(1).strip() if frame_match else '',
            'setting': setting_match.group(1).strip() if setting_match else '',
            'characters': characters_match.group(1).strip() if characters_match else '',
            'action': action_match.group(1).strip() if action_match else '',
            'dialogue': dialogue_match.group(1).strip() if dialogue_match else ''
        }
        parsed_panels.append(parsed_panel)
    return parsed_panels

def generate_safe_prompt(panel, retry_count, original_story=None, comic_artist_style=None):
    style = comic_artist_style if comic_artist_style else ""
    
    # For "no news" case, use specific prompts
    if original_story and "No Current News Events" in original_story:
        if retry_count == 0:
            if "Panel 1:" in panel:
                return "A modern newsroom interior with large windows, two journalists at their desks checking computers and news monitors. The scene is well-lit and professional."
            elif "Panel 2:" in panel:
                return "A peaceful view through a large newsroom window showing a serene town landscape. A journalist holding a coffee mug looks thoughtfully out the window."
            elif "Panel 3:" in panel:
                return "Journalists and community members gathered around a planning board in a bright newsroom, discussing future stories. Local photographs and awards visible on walls."
        else:
            return "A peaceful newsroom scene with journalists working at their desks, large windows showing a serene town view."
    
    # For regular news stories
    if retry_count == 0:
        # Combine all panel elements into a detailed scene description
        prompt = f"In the style of {style}, create a detailed illustration: "
        prompt += f"Using a {panel['frame']}, show a scene in {panel['setting']}. "
        prompt += f"The scene features {panel['characters']}. "
        prompt += f"In this moment, {panel['action']}. "
        if panel['dialogue']:
            prompt += f"Include a speech bubble with the text: '{panel['dialogue']}'. "
        prompt += "Make the scene dynamic and visually engaging, with clear focus on the main action."
    elif retry_count == 1 and original_story:
        prompt = f"In the style of {style}, illustrate this story: {original_story}"
    else:
        prompt = f"In the style of {style}, create a symbolic scene representing the story. "
        prompt += "Focus on key visual elements and emotional tone. "
    
    return filter_content(prompt, strict=(retry_count > 0))

def generate_flux1_images(comic_script, original_story, comic_artist_style=None):
    app_logger.debug(f"Generating images with FLUX.1-schnell...")

    model_id = config.FLUX1_MODEL_LOCATION

    pipe = FluxPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16)
    pipe.enable_sequential_cpu_offload() # offload the model to CPU in a sequential manner. This is useful for large batch sizes

    # Parse the comic script into panels
    panels = parse_comic_script(comic_script)
    
    image_urls = []
    for panel in panels:
        # Generate a safe prompt
        prompt = generate_safe_prompt(panel, 0, original_story, comic_artist_style)
        image = pipe(
            prompt,
            guidance_scale=7.5,  # 0.0 is the for maximum creativity [1 to 20, with most models using a default of 7-7.5]
            output_type="pil",
            num_inference_steps=4, #use a larger number if you are using [dev]
            max_sequence_length=256,
            generator=torch.Generator("cpu")
        ).images[0]
        image_urls.append(image)
    return image_urls

def generate_dalle_images(comic_script, original_story, comic_artist_style=None):
    try:
        app_logger.debug(f"Generating images with DALL-E...")
        
        # Create a DallEAPIWrapper instance
        dalle = DallEAPIWrapper(api_key=config.OPENAI_API_KEY, model='dall-e-3')
        
        # Parse the comic script into panels
        panels = parse_comic_script(comic_script)
        
        image_urls = []
        last_request_time = 0
        for index, panel in enumerate(panels, 1):
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
                    prompt = generate_safe_prompt(panel, retry_count, original_story, comic_artist_style)
                    app_logger.debug(f"Attempt {retry_count + 1} for Panel {index}. Prompt: {prompt}")

                    # Generate the image
                    image_url = dalle.run(prompt + " Create this as a comic panel with clear, detailed visuals that match the description exactly. Ensure the image aligns with content policies.")
                    image_urls.append(image_url)
                    
                    last_request_time = time.time()
                    app_logger.debug(f'Successfully generated image URL for Panel {index} with DALL-E.')
                    break  # Success, exit the retry loop
                except Exception as panel_error:
                    error_message = str(panel_error)
                    app_logger.error(f"Error for Panel {index}, Attempt {retry_count + 1}: {error_message}")
                    
                    if "rate_limit_exceeded" in error_message:
                        retry_count += 1
                        wait_time = 60 * retry_count  # Increase wait time with each retry
                        app_logger.warning(f"Rate limit exceeded for Panel {index}. Retrying in {wait_time} seconds. Attempt {retry_count}/{max_retries}")
                        time.sleep(wait_time)
                    elif "safety system" in error_message:
                        if retry_count == 0:
                            app_logger.warning(f"Content rejected by safety system for Panel {index}. Trying with original story.")
                            retry_count += 1
                        else:
                            app_logger.warning(f"Content rejected by safety system for Panel {index} using original story. Skipping this panel.")
                            image_urls.append(None)
                            break
                    else:
                        app_logger.error(f"Unhandled error generating image for Panel {index}: {panel_error}")
                        image_urls.append(None)
                        break  # Exit the retry loop for unhandled errors
            
            if retry_count == max_retries:
                app_logger.error(f"Failed to generate image for Panel {index} after {max_retries} attempts.")
                image_urls.append(None)
        
        return image_urls
    except Exception as e:
        app_logger.error(f"Error in generate_dalle_images: {e}")
        return None
