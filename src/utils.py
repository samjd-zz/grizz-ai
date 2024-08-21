import os
import re
from datetime import datetime
from logger import app_logger
from config import OUTPUT_DIR

import torch
import traceback
from transformers import pipeline
from PIL import Image
import warnings

TODAY = datetime.now().strftime("%Y_%m_%d")

# Check if CUDA is available and set the device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
app_logger.info(f"Using device: {device}")

# Load image captioning pipeline
captioner = pipeline("image-to-text", model="nlpconnect/vit-gpt2-image-captioning", device=device)

def analyze_frames(frames):
    """
    Analyze the extracted frames or single image using image captioning.
    
    :param frames: List of PIL Image objects, a single PIL Image object, or a path to an image file
    :return: List of detailed frame descriptions
    """
    try:
        app_logger.debug("Analyzing frames with image captioning")
        frame_descriptions = []

        # If frames is a string (path to an image file), try to open it
        if isinstance(frames, str):
            if not os.path.isfile(frames):
                app_logger.error(f"Invalid file path: {frames}")
                return None
            try:
                frames = [Image.open(frames)]
            except Exception as e:
                app_logger.error(f"Error opening image file: {e}")
                return None

        # If frames is a single PIL Image, convert it to a list
        if isinstance(frames, Image.Image):
            frames = [frames]

        # Ensure frames is a list
        if not isinstance(frames, list):
            app_logger.error("Invalid input: frames must be a list of PIL Image objects, a single PIL Image object, or a path to an image file")
            return None

        for i, frame in enumerate(frames):
            app_logger.debug(f"Analyzing frame {i+1}/{len(frames)}")
            
            # Generate caption using the image captioning pipeline
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                caption = captioner(frame, max_new_tokens=50)[0]['generated_text']
            
            frame_descriptions.append(f"Frame {i+1}: {caption}")
            
        app_logger.debug("Frame analysis completed successfully")
        return frame_descriptions
    except Exception as e:
        app_logger.error(f"Error analyzing frames with image captioning: {e}")
        app_logger.error(traceback.format_exc())
        return None

def save_summary(location, filename, title, story="", source="", panel_summary=""):
    """
    Saves a summary file with event details and panel summary.

    Args:
        location (str): The location of the event.
        filename (str): The name of the file to save.
        title (str): The title of the event.
        story (str, optional): The story of the event. Defaults to "".
        source (str, optional): The source of the event. Defaults to "".
        panel_summary (str, optional): The summary of the comic panel. Defaults to "".
    """
    try:
        comics_dir = os.path.join(OUTPUT_DIR, f"{location.replace(' ', '_')}_comics", TODAY)
        os.makedirs(comics_dir, exist_ok=True)
        summary_path = os.path.join(comics_dir, filename)
        with open(summary_path, "w") as f:
            f.write("-" * 100 + "\n")
            f.write("TITLE:\n" + title + "\n")
            if story:
                f.write("-" * 100 + "\n")
                f.write("STORY:\n" + story + "\n")
            if source:
                f.write("-" * 100 + "\n")
                f.write("SOURCE:\n" + source + "\n")
            f.write("-" * 100 + "\n")
            f.write("PANEL SUMMARY:\n" + panel_summary + "\n")
        app_logger.debug(f"Summary saved successfully: {summary_path}")
    except Exception as e:
        app_logger.error(f"Error saving summary: {e}")

def save_image(image_data, filename, location):
    """
    Saves the generated image locally.
    
    Args:
        image_data (bytes): Image data returned by the image generation API.
        filename (str): Name of the file to save the image as.
        location (str): Location for the comic (used for folder naming).

    Returns:
        str: Path to the saved image file, or None if an error occurred.
    """
    try:
        comics_dir = os.path.join(OUTPUT_DIR, f"{location.replace(' ', '_')}_comics", TODAY)
        os.makedirs(comics_dir, exist_ok=True)
        image_path = os.path.join(comics_dir, filename)

        with open(image_path, "wb") as f:
            f.write(image_data)
        app_logger.debug(f"Image saved successfully: {image_path}")
        return image_path
    except Exception as e:
        app_logger.error(f"Error saving image: {e}")
        return None
    
def generate_safe_prompt(original_prompt):
    filtered_prompt = filter_content(original_prompt)
    safe_prompt = (
        "Create a family-friendly, non-violent, and non-controversial image based on the following description. "
        "Do not include any inappropriate, offensive, or adult content. "
        "The image should be suitable for all ages. Description: " + filtered_prompt
    )
    return safe_prompt, filtered_prompt

def filter_content(text):
    # List of potentially problematic words or phrases
    filtered_words = [
        "nude", "naked", "sex", "porn", "explicit", "violence", "gore",
        "blood", "kill", "murder", "terrorist", "bomb", "weapon", "gun",
        "illegal", "drug", "cocaine", "heroin", "meth", "graphic",
        "disturbing", "offensive", "controversial", "political", "hate speech",
        "racist", "sexist", "discriminatory", "abuse", "assault", "harass",
        "threat", "extremist", "radical", "jihad", "nazi", "holocaust",
        "suicide", "self-harm", "eating disorder", "anorexia", "bulimia"
    ]
    
    # Remove any occurrence of filtered words and surrounding context
    for word in filtered_words:
        pattern = r'.{0,20}\b' + re.escape(word) + r'\b.{0,20}'
        text = re.sub(pattern, '[content removed]', text, flags=re.IGNORECASE)
    
    # Remove any remaining instances of [content removed] at the start or end
    text = re.sub(r'^\[content removed]\s*', '', text)
    text = re.sub(r'\s*\[content removed]$', '', text)
    
    return text

# You can add more utility functions here as needed