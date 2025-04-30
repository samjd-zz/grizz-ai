import os
import re
import requests
import sqlite3
from datetime import datetime
from PIL import Image

from logger import app_logger
from utils import save_summary, save_image
from text_analysis import analyze_text_ollama, speak_elevenLabs
from database import ComicDatabase
from config import load_config
from .comic_core import is_similar_story, parse_panel_summaries
from .image_generation_handler import generate_images

config = load_config()

def generate_custom_comic(title, story, location, user_id, comic_artist_style, progress_callback=None):
    """
    Generates a custom comic based on user-provided title, story, and location.

    Args:
        title (str): The title of the custom comic.
        story (str): The story for the custom comic.
        location (str): The location setting for the comic.
        user_id (int): The ID of the user generating the comic.
        comic_artist_style (str): The style of the comic artist to emulate.
        progress_callback (function): A callback function to report progress.

    Returns:
        tuple: A tuple containing a list of image paths, panel summaries, comic script, comic summary, and audio path.
        None: If an error occurs during comic generation.
    """
    try:
        if progress_callback:
            progress_callback(0, "Checking for existing comics")
        
        # Check if a similar comic already exists
        existing_comics = ComicDatabase.get_all_comics(user_id)
        similar_comic = next((comic for comic in existing_comics if is_similar_story(story, comic['original_story'])), None)
        if similar_comic:
            app_logger.debug(f"Similar comic already exists for story: {title}. Returning existing comic.")
            panel_summaries = parse_panel_summaries(similar_comic['comic_summary'])
            if progress_callback:
                progress_callback(100, "Existing comic found")
            return similar_comic['image_path'].split(','), panel_summaries, similar_comic['comic_script'], similar_comic['comic_summary'], similar_comic['audio_path']

        if progress_callback:
            progress_callback(10, f"Generating custom comic: {title}")

        app_logger.info(f"Generating custom comic for: {title} in {location}...")

        # Generate comic script for the custom story
        if progress_callback:
            progress_callback(20, "Analyzing custom comic story")
        event_analysis, comic_summary, panel_summaries = analyze_text_ollama(f"Generate a comic script for this event: {title}. {story}", location, comic_artist_style)
        if not event_analysis:
            app_logger.error(f"Failed to analyze custom event: {title}. Aborting comic generation.")
            if progress_callback:
                progress_callback(100, "Failed to analyze story")
            return None

        # If panel_summaries is None or empty, try to parse them from the comic_summary
        if not panel_summaries:
            panel_summaries = parse_panel_summaries(comic_summary)
            
        # Ensure we always have valid panel summaries (at least 3)
        if not panel_summaries or len(panel_summaries) < 3:
            app_logger.debug("Using default panel summaries as none were provided")
            panel_summaries = [
                f"A scene from {title} in {location}",
                f"Characters engaged in action at {location}",
                f"Final scene showing the conclusion at {location}"
            ]

        # Generate comic panel images
        if progress_callback:
            progress_callback(40, "Generating images")
        app_logger.debug(f"Generating images for custom comic: {title}")
        image_results = generate_images(event_analysis, story, comic_artist_style)
        if not image_results:
            app_logger.error(f"Failed to generate comic panels for the custom event: {title}. Aborting comic generation.")
            if progress_callback:
                progress_callback(100, "Failed to generate images")
            return None
        app_logger.debug(f"Generated {len(image_results)} images for custom comic: {title}")

        # Save the generated images
        if progress_callback:
            progress_callback(60, "Saving images")
        app_logger.debug("Saving images...")
        image_paths = []
        relative_image_paths = []  # Store paths relative to the GENERATED_IMAGES_FOLDER
        for i, image_result in enumerate(image_results):
            if image_result:
                # Use the title for the file name, replacing invalid characters and limiting length
                safe_title = re.sub(r'[^\w\-_\. ]', '_', title)
                safe_title = safe_title.replace(' ', '_')
                safe_title = safe_title[:100]  # Limit to 100 characters
                image_filename = f"{safe_title}_{i+1}.png"
                if isinstance(image_result, Image.Image):
                    # If it's a PIL Image object, save it directly
                    image_path = save_image(image_result, image_filename, location)
                elif isinstance(image_result, str):
                    # If it's a URL, download and save
                    image_data = requests.get(image_result).content
                    image_path = save_image(image_data, image_filename, location)
                else:
                    app_logger.error(f"Unexpected image result type for {title}")
                    continue
                
                if image_path:
                    image_paths.append(image_path)
                    # Calculate relative path for the UI
                    relative_path = os.path.relpath(image_path, config.OUTPUT_DIR)
                    relative_image_paths.append(relative_path)
                    app_logger.debug(f"Image saved with relative path: {relative_path}")
                else:
                    app_logger.error(f"Failed to save the generated image {i+1} for {title}.")
            else:
                app_logger.error(f"Failed to generate image {i+1} for {title}.")
        if not image_paths:
            app_logger.error(f"Failed to save any images for {title}. Aborting comic generation.")
            if progress_callback:
                progress_callback(100, "Failed to save images")
            return None

        # Generate audio narration
        if progress_callback:
            progress_callback(80, "Generating audio narration")
        audio_path = ""
        if config.GENERATE_AUDIO:
            audio_path = speak_elevenLabs(story, title)
            if not audio_path:
                app_logger.warning(f"Failed to generate audio narration for {title}.")

        app_logger.debug("Saving summary")
        summary_filename = image_filename.replace(".png", "_summary.txt")
        save_summary(location, summary_filename, title, story, "", comic_summary)

        app_logger.debug(f"Adding custom comic to database: {title}")
        
        # Check if we have image paths
        if not relative_image_paths:
            app_logger.error("No image paths to save to database. Cannot proceed.")
            return None
        
        image_path_str = ",".join(relative_image_paths)
        app_logger.debug(f"Saving image paths to database: {image_path_str}")
        
        # Execute a direct SQL query to ensure the comic is saved correctly
        try:
            conn = sqlite3.connect(config.DB_PATH)
            cursor = conn.cursor()
            
            # Insert using direct SQL to avoid parameter order issues
            cursor.execute('''
                INSERT INTO comics (user_id, title, location, original_story, comic_script, comic_summary, 
                                   story_source_url, image_path, audio_path, date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, 
                title, 
                location, 
                story, 
                event_analysis, 
                comic_summary, 
                "", 
                image_path_str, 
                audio_path, 
                datetime.now().date(), 
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            
            conn.commit()
            conn.close()
            app_logger.debug(f"Successfully saved comic to database with direct SQL: {title}")
        except Exception as e:
            app_logger.error(f"Error saving to database with direct SQL: {e}")
            
            # Fall back to the regular method
            try:
                ComicDatabase.add_comic(
                    user_id=user_id,
                    title=title, 
                    location=location, 
                    original_story=story, 
                    comic_script=event_analysis, 
                    comic_summary=comic_summary, 
                    story_source_url="",
                    image_path=image_path_str,
                    audio_path=audio_path, 
                    date=datetime.now().date()
                )
                app_logger.debug("Fallback to ComicDatabase.add_comic succeeded")
            except Exception as e2:
                app_logger.error(f"Both database save methods failed: {e2}")
                return None

        # Print summary for the user
        app_logger.debug(f"Custom comic generation completed for {title} in {location}!")
        app_logger.debug(f"Title: {title}")
        app_logger.debug(f"Images saved at: {', '.join(image_paths)}")

        if progress_callback:
            progress_callback(100, "Comic generation complete")

        # Return relative paths for URL generation in templates
        return relative_image_paths, panel_summaries, event_analysis, comic_summary, audio_path

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_custom_comic: {e}", exc_info=True)
        if progress_callback:
            progress_callback(100, f"Error occurred: {str(e)}")
        return None
