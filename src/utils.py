import os
import re
import torch
import traceback
import warnings
import requests
import cv2
import io
from PIL import Image
from io import BytesIO
from datetime import datetime
from logger import app_logger
from transformers import pipeline
from config import load_config
from datetime import datetime

config = load_config()

def sanitize_location(location):
    """Sanitize location string for use in directory paths"""
    # Replace spaces with underscores and remove commas
    sanitized = location.replace(' ', '_').replace(',', '')
    # Remove any other problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', sanitized)
    return sanitized

def sanitize_filename(filename):
    """Remove or replace characters that are not allowed in file names"""
    # Remove newlines and markdown characters
    filename = filename.replace('\n', '').replace('\r', '')
    filename = re.sub(r'[#*`]', '', filename)
    # Remove or replace other problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove any trailing/leading whitespace or dots
    filename = filename.strip('. ')
    # Ensure filename is not empty
    if not filename:
        filename = 'untitled'
    return filename

TODAY = datetime.now().strftime("%Y_%m_%d")

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

def analyze_frames(frames):
    """
    Analyze the extracted frames or single image using image captioning.
    
    :param frames: List of PIL Image objects, a single PIL Image object, or a path to an image file
    :return: List of detailed frame descriptions
    """
    try:
        # Load the image captioning pipeline model
        captioner = load_pipeline_model()
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
            caption = captioner(frame, max_new_tokens=50)[0]['generated_text']
            
            frame_descriptions.append(f"Frame {i+1}: {caption}")
            
        app_logger.debug("Frame analysis completed successfully")
        # Call the function to unload
        unload_pipeline_model(captioner)
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
        # Use the same sanitized location as save_image
        location_folder = sanitize_location(location)
        comics_dir = os.path.join(config.OUTPUT_DIR, f"{location_folder}_comics", TODAY)
        os.makedirs(comics_dir, exist_ok=True)
        
        # Sanitize the filename
        sanitized_filename = sanitize_filename(filename)
        summary_path = os.path.join(comics_dir, sanitized_filename)
        
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
    Save an image file with proper path sanitization.
    
    Args:
        image_data: The image data to save (PIL Image, URL, or bytes)
        filename (str): The name of the file to save
        location (str): The location for the directory structure
        
    Returns:
        str: Path to the saved image file, or None if save failed
    """
    try:
        # Sanitize both the filename and location
        sanitized_filename = sanitize_filename(filename)
        location_folder = sanitize_location(location)
        
        # Create the directory structure
        output_dir = os.path.join(config.OUTPUT_DIR, f"{location_folder}_comics", TODAY)
        os.makedirs(output_dir, exist_ok=True)

        image_path = os.path.join(output_dir, sanitized_filename)

        if isinstance(image_data, Image.Image):
            image_data.save(image_path)
        elif isinstance(image_data, str):  # Assume it's a URL
            response = requests.get(image_data)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            img.save(image_path)
        elif isinstance(image_data, bytes):
            with open(image_path, "wb") as f:
                f.write(image_data)
        else:
            raise ValueError("Unsupported image_data type")

        app_logger.debug(f"Image saved successfully: {image_path}")
        return image_path
    except Exception as e:
        app_logger.error(f"Error saving image: {str(e)}")
        app_logger.error(f"Traceback: ", exc_info=True)
        return None

def generate_safe_prompt(original_prompt):
    filtered_prompt = filter_content(original_prompt)
    safe_prompt = (
        "Create a family-friendly, non-violent, and non-controversial image based on the following description. "
        "Do not include any inappropriate, offensive, or adult content. "
        "The image should be suitable for all ages. Description: " + filtered_prompt
    )
    return safe_prompt, filtered_prompt

def filter_content(text, strict=False):
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
    
    if strict:
        # Add more words for stricter filtering
        filtered_words.extend([
            "crime", "criminal", "steal", "theft", "rob", "alcohol", "cigarette",
            "tobacco", "fight", "conflict", "war", "protest", "riot", "arrest",
            "police", "jail", "prison", "death", "die", "corpse", "body", "injury",
            "accident", "disaster", "tragedy", "crisis", "emergency", "danger",
            "hazard", "risk", "threat", "fear", "panic", "terror", "horror"
        ])
    
    # Remove any occurrence of filtered words and surrounding context
    for word in filtered_words:
        pattern = r'.{0,20}\b' + re.escape(word) + r'\b.{0,20}'
        text = re.sub(pattern, '[content removed]', text, flags=re.IGNORECASE)
    
    # Remove any remaining instances of [content removed] at the start or end
    text = re.sub(r'^\[content removed]\s*', '', text)
    text = re.sub(r'\s*\[content removed]$', '', text)
    
    return text

def unload_pipeline_model(captioner):
    # Move the model to CPU
    captioner.model.to('cpu')
    
    # Clear CUDA cache
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # Delete the pipeline and model
    del captioner.model
    del captioner
    
    # Force garbage collection
    import gc
    gc.collect()

def load_pipeline_model():
    # Check if CUDA is available and set the device
    device = 0 if torch.cuda.is_available() else -1
    print(f"{torch.cuda.get_device_name(0) if device == 0 else 'cpu'}")

    # Load image captioning pipeline with fp16 precision for memory optimization
    captioner = pipeline("image-to-text", model=config.TORCH_IMAGE_TO_TEXT_MODEL, device=device, torch_dtype=torch.float16 if torch.cuda.is_available() else None)
    return captioner

def unload_ollama_model(model_name):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": "",
        "keep_alive": 0
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            app_logger.debug(f"Successfully unloaded model: {model_name}")
        else:
            app_logger.error(f"Failed to unload model. Status code: {response.status_code}")
            app_logger.error(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        app_logger.error(f"An error occurred: {e}")

def brave_search(query, num_results=10):
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Authorization": f"Bearer {config.API_KEY_BRAVE_SEARCH}",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": {config.API_KEY_BRAVE_SEARCH}
        }
        params = {"q": query, "count": num_results}
        response = requests.get(url, headers=headers, params=params)
        return response.json()

def capture_live_video(duration=5):
    """
    Captures a live video from the webcam for the specified duration.
    Args:
        duration (int): Duration of the video in seconds.
    Returns:
        str: Path to the saved video file.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Error: Could not open webcam. Please check if the camera is connected."
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    video_path = os.path.join(os.path.expanduser('~'), 'captured_video.avi')
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))
    start_time = cv2.getTickCount()
    while (cv2.getTickCount() - start_time) / cv2.getTickFrequency() < duration:
        ret, frame = cap.read()
        if ret:
            out.write(frame)
            cv2.imshow('Recording...', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    return video_path

def summarize_generated_files(comic_dir):
    """
    Summarizes the comics and files created during the generation process.

    Args:
        comic_dir (str): The directory where the comic files are stored.

    Returns:
        str: A summary of the generated files.
    """
    summary = []
    for filename in os.listdir(comic_dir):
        if filename.endswith('.png'):
            summary.append(f"Comic image: {filename}")
        elif filename.endswith('_summary.txt'):
            summary.append(f"Summary file: {filename}")
    
    return "\n".join(summary)
