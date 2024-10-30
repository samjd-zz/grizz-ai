import os
import requests
from datetime import datetime
from PIL import Image

from logger import app_logger
from utils import analyze_frames, save_summary, save_image
from text_analysis import analyze_text_ollama, speak_elevenLabs
from video_processing import get_video_summary
from database import ComicDatabase
from config import load_config
from .comic_core import is_similar_story, parse_panel_summaries
from .image_generation_handler import generate_images

config = load_config()

def generate_media_comic(media_type, path, location, user_id, comic_artist_style, progress_callback=None):
    """
    Generates a comic based on a video or image file.

    Args:
        media_type (str): The type of media ('video' or 'image').
        path (str): The path to the media file or directory.
        location (str): The location for saving the comic.
        user_id (int): The ID of the user generating the comic.
        comic_artist_style (str): The style of the comic artist to emulate.
        progress_callback (function): A callback function to report progress.

    Returns:
        tuple: A tuple containing (image_paths, summary, comic_scripts, panel_summaries, audio_paths).
        None: If an error occurs during comic generation.
    """
    try:
        if progress_callback:
            progress_callback(0, f"Processing {media_type} files")

        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if (media_type == 'video' and f.lower().endswith(('.mp4', '.avi', '.mov'))) or 
                    (media_type == 'image' and f.lower().endswith(('.jpg', '.png', '.jpeg')))]
            if not files:
                app_logger.warning(f"No valid media files found in the directory: {path}")
                if progress_callback:
                    progress_callback(100, "No valid media files found")
                return None
            media_paths = [os.path.join(path, f) for f in files]
        else:
            media_paths = [path]

        comic_images = []
        summaries = []
        comic_scripts = []
        all_panel_summaries = []
        audio_paths = []

        total_steps = len(media_paths)
        for i, media_path in enumerate(media_paths):
            if progress_callback:
                progress_callback(i * 100 // total_steps, f"Processing {media_type} {i+1} of {total_steps}")

            if media_type == 'video':
                result = process_video(media_path, location, user_id, comic_artist_style, progress_callback)
            else:  # image
                result = process_image(media_path, location, user_id, comic_artist_style, progress_callback)

            if result:
                images, summary, script, panels, audio = result
                comic_images.extend(images)
                summaries.append(summary)
                comic_scripts.append(script)
                all_panel_summaries.extend(panels)
                audio_paths.append(audio)

        if not comic_images:
            app_logger.error("No comic images were generated. Aborting media comic generation.")
            if progress_callback:
                progress_callback(100, "Failed to generate any comics")
            return None

        # Create a final summary
        final_summary = "\n\n".join(summaries)
        save_summary(location, f"{media_type}_comic_summary.txt", f"{media_type.capitalize()} Comic", final_summary, "", "")

        if progress_callback:
            progress_callback(100, "Comic generation complete")

        return comic_images, final_summary, comic_scripts, all_panel_summaries, audio_paths

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_media_comic: {e}", exc_info=True)
        if progress_callback:
            progress_callback(100, f"Error occurred: {str(e)}")
        return None

def process_video(media_path, location, user_id, comic_artist_style, progress_callback=None):
    """Helper function to process a video file and generate a comic."""
    video_summary = get_video_summary(media_path)
    if not video_summary:
        app_logger.error(f"Failed to generate summary for video: {media_path}")
        return None

    # Check if a similar comic already exists
    existing_comics = ComicDatabase.get_all_comics(user_id)
    similar_comic = next((comic for comic in existing_comics if is_similar_story(video_summary, comic['original_story'])), None)
    if similar_comic:
        app_logger.info(f"Similar comic already exists for video: {media_path}. Skipping this video.")
        return (similar_comic['image_path'].split(','), 
                similar_comic['comic_script'],
                similar_comic['comic_script'],
                parse_panel_summaries(similar_comic['comic_summary']),
                similar_comic['audio_path'])

    # Generate comic script
    event_analysis, comic_summary = analyze_text_ollama(f"Generate a comic script for this event: {video_summary}", location, comic_artist_style)
    if not event_analysis:
        app_logger.error(f"Failed to analyze video. Aborting comic generation.")
        return None

    # Parse panel summaries
    panel_summaries = parse_panel_summaries(comic_summary)

    # Generate and save images
    image_paths = generate_and_save_images(event_analysis, video_summary, comic_artist_style, media_path, location, "video", progress_callback)
    if not image_paths:
        return None

    # Generate audio narration
    audio_path = ""
    if config.GENERATE_AUDIO:
        audio_path = speak_elevenLabs(video_summary, os.path.basename(media_path))
        if not audio_path:
            app_logger.warning(f"Failed to generate audio narration for video: {media_path}")

    # Save to database
    ComicDatabase.add_comic(user_id, os.path.basename(media_path), location, video_summary, 
                          event_analysis, comic_summary, "", ",".join(image_paths), 
                          audio_path, datetime.now().date())

    return image_paths, video_summary, event_analysis, panel_summaries, audio_path

def process_image(media_path, location, user_id, comic_artist_style, progress_callback=None):
    """Helper function to process an image file and generate a comic."""
    image_analysis = analyze_frames(media_path)
    if not image_analysis:
        app_logger.error(f"Failed to analyze image: {media_path}")
        return None

    # Join the frame descriptions into a single string
    image_description = " ".join(image_analysis)

    # Check if a similar comic already exists
    existing_comics = ComicDatabase.get_all_comics(user_id)
    similar_comic = next((comic for comic in existing_comics if is_similar_story(image_description, comic['original_story'])), None)
    if similar_comic:
        app_logger.info(f"Similar comic already exists for image: {media_path}. Skipping this image.")
        return (similar_comic['image_path'].split(','),
                similar_comic['comic_script'],
                similar_comic['comic_script'],
                parse_panel_summaries(similar_comic['comic_summary']),
                similar_comic['audio_path'])

    # Generate comic script
    event_analysis, comic_summary = analyze_text_ollama(f"Generate a comic script for this event: {image_description}", location, comic_artist_style)
    if not event_analysis:
        app_logger.error(f"Failed to analyze image. Aborting comic generation.")
        return None

    # Parse panel summaries
    panel_summaries = parse_panel_summaries(comic_summary)

    # Generate and save images
    image_paths = generate_and_save_images(event_analysis, image_description, comic_artist_style, media_path, location, "image", progress_callback)
    if not image_paths:
        return None

    # Generate audio narration
    audio_path = ""
    if config.GENERATE_AUDIO:
        audio_path = speak_elevenLabs(image_description, os.path.basename(media_path))
        if not audio_path:
            app_logger.warning(f"Failed to generate audio narration for image: {media_path}")

    # Save to database
    ComicDatabase.add_comic(user_id, os.path.basename(media_path), location, image_description,
                          event_analysis, comic_summary, "", ",".join(image_paths),
                          audio_path, datetime.now().date())

    return image_paths, image_description, event_analysis, panel_summaries, audio_path

def generate_and_save_images(event_analysis, content, comic_artist_style, media_path, location, prefix, progress_callback=None):
    """Helper function to generate and save images for both video and image processing."""
    app_logger.debug(f"Generating images for {prefix}: {os.path.basename(media_path)}")
    image_results = generate_images(event_analysis, content, comic_artist_style)
    if not image_results:
        app_logger.error(f"Failed to generate comic for the {prefix}")
        return None

    app_logger.debug(f"Generated {len(image_results)} images for {prefix}: {os.path.basename(media_path)}")

    image_paths = []
    for j, image_result in enumerate(image_results):
        if image_result:
            image_filename = f"{prefix}_comic_{os.path.basename(media_path)}_{j+1}.png"
            if isinstance(image_result, Image.Image):
                image_path = save_image(image_result, image_filename, location)
            elif isinstance(image_result, str):
                image_data = requests.get(image_result).content
                image_path = save_image(image_data, image_filename, location)
            else:
                app_logger.error(f"Unexpected image result type for {prefix}: {media_path}")
                continue
            
            if image_path:
                image_paths.append(image_path)
            else:
                app_logger.error(f"Failed to save the generated image {j+1} for {prefix}: {media_path}")
        else:
            app_logger.error(f"Failed to generate image {j+1} for {prefix}: {media_path}")

    if not image_paths:
        app_logger.error(f"Failed to save any images for the {prefix}")
        return None

    return image_paths
