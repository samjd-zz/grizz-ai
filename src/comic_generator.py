import warnings

from sympy import im
# Suppress the specific LangChain deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*BaseChatModel.__call__.*")

import os
import re
import requests
from datetime import datetime 
from PIL import Image
import io

from logger import app_logger
from utils import analyze_frames, save_summary, save_image, filter_content

from image_generation import generate_dalle_images, generate_flux1_images
from text_analysis import analyze_text_ollama, speak_elevenLabs
from event_fetcher import get_local_events
from video_processing import get_video_summary
from config import load_config
from database import ComicDatabase

config = load_config()

TODAY = datetime.now().strftime("%Y_%m_%d")

def parse_panel_summaries(comic_summary):
    """
    Parse the comic summary to extract individual panel summaries.
    
    Args:
        comic_summary (str): The full comic summary.
    
    Returns:
        list: A list of panel summaries.
    """
    panel_summaries = []
    summary_start = comic_summary.find("Summary:")
    if summary_start != -1:
        # New format with explicit Summary section
        summary_text = comic_summary[summary_start:]
        for line in summary_text.split('\n'):
            if line.startswith('Panel '):
                parts = line.split(': ', 1)
                if len(parts) > 1:
                    panel_summaries.append(parts[1])
    else:
        # Original format
        for line in comic_summary.split('\n'):
            if line.startswith('Panel '):
                parts = line.split(': ', 1)
                if len(parts) > 1:
                    panel_summaries.append(parts[1])
    
    # If we didn't find any summaries or found less than 3, add default ones
    while len(panel_summaries) < 3:
        panel_summaries.append("No summary available for this panel.")
    
    return panel_summaries[:3]  # Ensure we only return 3 summaries

def generate_daily_comic(location, progress_callback=None):
    """
    Generates a daily comic based on local events for a given location.

    Args:
        location (str): The location to generate the comic for.
        progress_callback (function): A callback function to report progress.

    Returns:
        list: A list of local events that were used to generate the comic.
        None: If no events were found or an error occurred during comic generation.
    """
    app_logger.info(f"Starting daily comic generation for location: {location}")
    try:
        if progress_callback:
            progress_callback(0, f"Fetching local events for {location}")

        # Step 1: Get local events based on user's location
        app_logger.info(f"Fetching local events for {location}")
        local_events = get_local_events(location)
        if not local_events:
            app_logger.warning(f"No new local events in the past 7 days for {location}. Aborting comic generation.")
            if progress_callback:
                progress_callback(100, f"No new events found for {location}")
            return None
        
        app_logger.info(f"Found {len(local_events)} events for {location}")
        if progress_callback:
            progress_callback(10, f"Found {len(local_events)} events for {location}")

        # Step 2: Generate a comic panel for each event
        comic_panels = []
        all_panel_summaries = []
        for i, event in enumerate(local_events):
            event_title = event['title']
            event_story = event['story']
            event_source = event['full_story_source_url']
            
            app_logger.info(f"Processing event {i+1}/{len(local_events)}: {event_title}")
            if progress_callback:
                progress_callback(10 + (i * 80 // len(local_events)), f"Processing event: {event_title}")
            
            # Check if a comic with this story already exists
            existing_comic = ComicDatabase.get_comic_by_story(event_story)
            if existing_comic:
                app_logger.info(f"Comic already exists for story: {event_title}. Skipping this event.")
                continue
            
            # Generate comic script for the event
            app_logger.info(f"Generating comic script for event: {event_title}")
            event_analysis, comic_summary = analyze_text_ollama(f"Generate a comic script for this event: {event_title}. {event_story}", location)
            if not event_analysis:
                app_logger.error(f"Failed to analyze event: {event_title}. Skipping this event.")
                continue

            # Parse panel summaries
            app_logger.info(f"Parsing panel summaries for event: {event_title}")
            panel_summaries = parse_panel_summaries(comic_summary)

            # Generate comic panel image
            app_logger.info(f"Generating images for event: {event_title}")
            #image_results = generate_flux1_images(filter_content(event_analysis), event_story)
            image_results = generate_dalle_images(filter_content(event_analysis), event_story)
            if not image_results:
                app_logger.error(f"Failed to generate comic panel for the event: {event_title}. Skipping this event.")
                continue
            app_logger.info(f"Generated {len(image_results)} images for event: {event_title}")

            # Save the generated images
            app_logger.info(f"Saving images for event: {event_title}")
            image_paths = []
            for j, image_result in enumerate(image_results):
                if image_result:
                    image_filename = f"ggs_grizzly_news_{event_title.replace(' ', '_')}_{j+1}.png"
                    if isinstance(image_result, Image.Image):
                        # If it's a PIL Image object, save it directly
                        image_path = save_image(image_result, image_filename, location)
                    elif isinstance(image_result, str):
                        # If it's a URL, download and save
                        image_data = requests.get(image_result).content
                        image_path = save_image(image_data, image_filename, location)
                    else:
                        app_logger.error(f"Unexpected image result type for {event_title}")
                        continue
                    
                    if image_path:
                        image_paths.append(image_path)
                        app_logger.info(f"Saved image {j+1} for event: {event_title}")
                    else:
                        app_logger.error(f"Failed to save the generated image {j+1} for {event_title}.")
                else:
                    app_logger.error(f"Failed to generate image {j+1} for {event_title}.")
            if not image_paths:
                app_logger.error(f"Failed to save any images for {event_title}. Skipping this event.")
                continue

            # Generate audio narration
            audio_path = ""
            if config.GENERATE_AUDIO:
                app_logger.info(f"Generating audio narration for event: {event_title}")
                audio_path = speak_elevenLabs(event_story, event_title)
                if not audio_path:
                    app_logger.warning(f"Failed to generate audio narration for {event_title}.")

            summary_filename = image_filename.replace(".png", "_summary.txt")
            save_summary(location, summary_filename, event_title, event_story, event_source, comic_summary)

            app_logger.info(f"Adding comic to database: {event_title}")
            ComicDatabase.add_comic(event_title, location, event_story, event_analysis, comic_summary, event_source, ",".join(image_paths), audio_path, datetime.now().date())

            comic_panels.append((image_paths, panel_summaries))
            all_panel_summaries.extend(panel_summaries)

            # Add image_paths, comic_script, comic_summary, and audio_path to the event dictionary
            event['image_paths'] = image_paths
            event['comic_script'] = event_analysis
            event['comic_summary'] = comic_summary
            event['panel_summaries'] = panel_summaries
            event['audio_path'] = audio_path
            # Ensure the original story and story source are preserved
            event['story'] = event_story
            event['story_source'] = event_source

            app_logger.info(f"Completed processing for event: {event_title}")

        if not comic_panels:
            app_logger.error("No comic panels were generated. Aborting comic generation.")
            if progress_callback:
                progress_callback(100, "Failed to generate any comic panels")
            return None

        # Step 3: Combine all panel summaries into one final summary
        app_logger.info("Creating final summary")
        final_summary = f"Today's Events in {location}:\n" + "\n".join(all_panel_summaries)
        save_summary(location, "final_summary.txt", final_summary)

        # Print summary for the user
        app_logger.info(f"Daily comic generation completed for {location}!")
        
        if progress_callback:
            progress_callback(100, f"Comic generation completed for {location}")
        
        return local_events

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_daily_comic: {e}", exc_info=True)
        if progress_callback:
            progress_callback(100, f"Error occurred: {str(e)}")
        return None

def generate_custom_comic(title, story, location, progress_callback=None):
    """
    Generates a custom comic based on user-provided title, story, and location.

    Args:
        title (str): The title of the custom comic.
        story (str): The story for the custom comic.
        location (str): The location setting for the custom comic.
        progress_callback (function): A callback function to report progress.

    Returns:
        tuple: A tuple containing a list of image paths, panel summaries, comic script, comic summary, and audio path of the generated comic.
        None: If an error occurs during comic generation.
    """
    try:
        if progress_callback:
            progress_callback(0, "Checking for existing comics")
        
        # Check if a comic with this story already exists
        existing_comic = ComicDatabase.get_comic_by_story(story)
        if existing_comic:
            app_logger.debug(f"Comic already exists for story: {title}. Returning existing comic.")
            panel_summaries = parse_panel_summaries(existing_comic['comic_summary'])
            if progress_callback:
                progress_callback(100, "Existing comic found")
            return existing_comic['image_path'].split(','), panel_summaries, existing_comic['comic_script'], existing_comic['comic_summary'], existing_comic['audio_path']

        if progress_callback:
            progress_callback(10, f"Generating custom comic: {title}")

        app_logger.info(f"Generating custom comic for: {title} in {location}...")

        # Generate comic script for the custom story
        if progress_callback:
            progress_callback(20, "Analyzing custom comic story")
        event_analysis, comic_summary = analyze_text_ollama(f"Generate a comic script for this event: {title}. {story}", location)
        if not event_analysis:
            app_logger.error(f"Failed to analyze custom event: {title}. Aborting comic generation.")
            if progress_callback:
                progress_callback(100, "Failed to analyze story")
            return None

        # Parse panel summaries
        panel_summaries = parse_panel_summaries(comic_summary)

        # Generate comic panel images
        if progress_callback:
            progress_callback(40, "Generating images")
        app_logger.debug(f"Generating images for custom comic: {title}")
        #image_results = generate_flux1_images(filter_content(event_analysis), story)
        image_results = generate_dalle_images(filter_content(event_analysis), story)
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
        ComicDatabase.add_comic(title, location, story, event_analysis, comic_summary, "", ",".join(image_paths), audio_path, datetime.now().date())

        # Print summary for the user
        app_logger.debug(f"Custom comic generation completed for {title} in {location}!")

        app_logger.debug(f"Title: {title}")
        app_logger.debug(f"Images saved at: {', '.join(image_paths)}")

        if progress_callback:
            progress_callback(100, "Comic generation complete")

        return image_paths, panel_summaries, event_analysis, comic_summary, audio_path

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_custom_comic: {e}", exc_info=True)
        if progress_callback:
            progress_callback(100, f"Error occurred: {str(e)}")
        return None

def generate_media_comic(media_type, path, location, progress_callback=None):
    """
    Generates a comic based on a video or image file.

    Args:
        media_type (str): The type of media ('video' or 'image').
        path (str): The path to the media file or directory.
        location (str): The location for saving the comic.
        progress_callback (function): A callback function to report progress.

    Returns:
        tuple: A tuple containing a list of image paths, a summary of the generated comic, a list of comic scripts, a list of panel summaries, and a list of audio paths.
        None: If an error occurs during comic generation.
    """
    try:
        if progress_callback:
            progress_callback(0, f"Processing {media_type} files")

        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if (media_type == 'video' and f.lower().endswith(('.mp4', '.avi', '.mov'))) or (media_type == 'image' and f.lower().endswith(('.jpg', '.png', '.jpeg')))]
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
                # Process video
                video_summary = get_video_summary(media_path)
                if not video_summary:
                    app_logger.error(f"Failed to generate summary for video: {media_path}")
                    continue

                # Check if a comic with this summary already exists
                existing_comic = ComicDatabase.get_comic_by_story(video_summary)
                if existing_comic:
                    app_logger.info(f"Comic already exists for video: {media_path}. Skipping this video.")
                    comic_images.extend(existing_comic['image_path'].split(','))
                    summaries.append(existing_comic['comic_script'])
                    comic_scripts.append(existing_comic['comic_script'])
                    all_panel_summaries.extend(parse_panel_summaries(existing_comic['comic_summary']))
                    audio_paths.append(existing_comic['audio_path'])
                    continue

                # Generate a single comic for the entire video summary
                event_analysis, comic_summary = analyze_text_ollama(f"Generate a comic script for this event: {video_summary}", location)
                if not event_analysis:
                    app_logger.error(f"Failed to analyze video. Aborting comic generation.")
                    continue

                # Parse panel summaries
                panel_summaries = parse_panel_summaries(comic_summary)

                app_logger.debug(f"Generating images for video: {os.path.basename(media_path)}")
                i#mage_results = generate_flux1_images(filter_content(event_analysis), video_summary)
                image_results = generate_dalle_images(filter_content(event_analysis), video_summary)
                if not image_results:
                    app_logger.error("Failed to generate comic for the video")
                    continue
                app_logger.debug(f"Generated {len(image_results)} images for video: {os.path.basename(media_path)}")

                image_paths = []
                for j, image_result in enumerate(image_results):
                    if image_result:
                        image_filename = f"video_comic_{os.path.basename(media_path)}_{j+1}.png"
                        if isinstance(image_result, Image.Image):
                            # If it's a PIL Image object, save it directly
                            image_path = save_image(image_result, image_filename, location)
                        elif isinstance(image_result, str):
                            # If it's a URL, download and save
                            image_data = requests.get(image_result).content
                            image_path = save_image(image_data, image_filename, location)
                        else:
                            app_logger.error(f"Unexpected image result type for video: {media_path}")
                            continue
                        
                        if image_path:
                            image_paths.append(image_path)
                        else:
                            app_logger.error(f"Failed to save the generated image {j+1} for video: {media_path}")
                    else:
                        app_logger.error(f"Failed to generate image {j+1} for video: {media_path}")
                if not image_paths:
                    app_logger.error("Failed to save any images for the video")
                    continue

                # Generate audio narration
                audio_path = ""
                if config.GENERATE_AUDIO:
                    audio_path = speak_elevenLabs(video_summary, os.path.basename(media_path))
                    if not audio_path:
                        app_logger.warning(f"Failed to generate audio narration for video: {media_path}")

                comic_images.extend(image_paths)
                summaries.append(video_summary)
                comic_scripts.append(event_analysis)
                all_panel_summaries.extend(panel_summaries)
                audio_paths.append(audio_path)

                app_logger.debug(f"Adding video comic to database: {os.path.basename(media_path)}")
                ComicDatabase.add_comic(os.path.basename(media_path), location, video_summary, event_analysis, comic_summary, "", ",".join(image_paths), audio_path, datetime.now().date())

            elif media_type == 'image':
                # Process image
                image_analysis = analyze_frames(media_path)
                if not image_analysis:
                    app_logger.error(f"Failed to analyze image: {media_path}")
                    continue

                # Join the frame descriptions into a single string
                image_description = " ".join(image_analysis)

                # Check if a comic with this description already exists
                existing_comic = ComicDatabase.get_comic_by_story(image_description)
                if existing_comic:
                    app_logger.info(f"Comic already exists for image: {media_path}. Skipping this image.")
                    comic_images.extend(existing_comic['image_path'].split(','))
                    summaries.append(existing_comic['comic_script'])
                    comic_scripts.append(existing_comic['comic_script'])
                    all_panel_summaries.extend(parse_panel_summaries(existing_comic['comic_summary']))
                    audio_paths.append(existing_comic['audio_path'])
                    continue

                # Generate a single comic for the entire image description
                event_analysis, comic_summary = analyze_text_ollama(f"Generate a comic script for this event: {image_description}", location)
                if not event_analysis:
                    app_logger.error(f"Failed to analyze image. Aborting comic generation.")
                    continue

                # Parse panel summaries
                panel_summaries = parse_panel_summaries(comic_summary)

                app_logger.debug(f"Generating images for image: {os.path.basename(media_path)}")
                #image_results = generate_flux1_images(filter_content(event_analysis), image_description)
                image_results = generate_dalle_images(filter_content(event_analysis), image_description)
                if not image_results:
                    app_logger.error("Failed to generate comic for the image")
                    continue
                app_logger.debug(f"Generated {len(image_results)} images for image: {os.path.basename(media_path)}")

                image_paths = []
                for j, image_result in enumerate(image_results):
                    if image_result:
                        image_filename = f"image_comic_{os.path.basename(media_path)}_{j+1}.png"
                        if isinstance(image_result, Image.Image):
                            # If it's a PIL Image object, save it directly
                            image_path = save_image(image_result, image_filename, location)
                        elif isinstance(image_result, str):
                            # If it's a URL, download and save
                            image_data = requests.get(image_result).content
                            image_path = save_image(image_data, image_filename, location)
                        else:
                            app_logger.error(f"Unexpected image result type for image: {media_path}")
                            continue
                        
                        if image_path:
                            image_paths.append(image_path)
                        else:
                            app_logger.error(f"Failed to save the generated image {j+1} for image: {media_path}")
                    else:
                        app_logger.error(f"Failed to generate image {j+1} for image: {media_path}")
                if not image_paths:
                    app_logger.error("Failed to save any images for the image")
                    continue

                # Generate audio narration
                audio_path = ""
                if config.GENERATE_AUDIO:
                    audio_path = speak_elevenLabs(image_description, os.path.basename(media_path))
                    if not audio_path:
                        app_logger.warning(f"Failed to generate audio narration for image: {media_path}")

                comic_images.extend(image_paths)
                summaries.append(image_description)
                comic_scripts.append(event_analysis)
                all_panel_summaries.extend(panel_summaries)
                audio_paths.append(audio_path)

                app_logger.debug(f"Adding image comic to database: {os.path.basename(media_path)}")
                ComicDatabase.add_comic(os.path.basename(media_path), location, image_description, event_analysis, comic_summary, "", ",".join(image_paths), audio_path, datetime.now().date())

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