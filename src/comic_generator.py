from datetime import datetime
import os
import re
from logger import app_logger
from image_generation import generate_dalle_images
from utils import analyze_frames
from text_analysis import analyze_text_opai
from event_fetcher import get_local_events
from utils import save_summary, save_image
from config import OUTPUT_DIR, SOURCE_DIR
from tqdm import tqdm # type: ignore
from video_processing import get_video_summary
from database import add_comic, get_comic_by_story, get_all_comics

TODAY = datetime.now().strftime("%Y_%m_%d")

def generate_daily_comic(location):
    """
    Generates a daily comic based on local events for a given location.

    Args:
        location (str): The location to generate the comic for.

    Returns:
        list: A list of local events that were used to generate the comic.
        None: If no events were found or an error occurred during comic generation.
    """
    try:
        # Step 1: Get local events based on user's location
        local_events = get_local_events(location)
        if not local_events:
            app_logger.warning(f"No new local events in the past 24 hours for {location}. Aborting comic generation.")
            return None
        
        # Estimate total steps
        total_steps = len(local_events) * 5 + 1  # 5 steps per event + final summary

        print(f"Generating comics for {len(local_events)} events in {location}...")
        with tqdm(total=total_steps, bar_format='{l_bar}{bar}', ncols=50, colour='#00FF00') as pbar:
            # Step 2: Generate a comic panel for each event
            comic_panels = []
            all_panel_summaries = []
            for event in local_events:
                event_title = event['title']
                event_story = event['story']
                event_source = event['full_story_source_url']
                
                # Check if a comic with this story already exists
                existing_comic = get_comic_by_story(event_story)
                if existing_comic:
                    app_logger.info(f"Comic already exists for story: {event_title}. Skipping this event.")
                    pbar.update(5)
                    continue
                
                # Generate comic script for the event
                app_logger.debug(f"Analyzing event: {event_title}")
                event_analysis = analyze_text_opai(f"Generate a comic script for this event: {event_title}. {event_story}", location)
                if not event_analysis:
                    app_logger.error(f"Failed to analyze event: {event_title}. Skipping this event.")
                    continue
                pbar.update(1)

                # Generate comic panel image
                app_logger.debug(f"Generating image for: {event_title}")
                image_data = generate_dalle_images(event_analysis)
                if not image_data:
                    app_logger.error(f"Failed to generate comic panel for the event: {event_title}. Skipping this event.")
                    continue
                pbar.update(1)

                # Save the generated image
                app_logger.debug(f"Saving image for: {event_title}")
                image_filename = f"ggs_grizzly_news_{event_title.replace(' ', '_')}.png"
                image_path = save_image(image_data, image_filename, location)
                if not image_path:
                    app_logger.error(f"Failed to save the generated image for {event_title}. Skipping this event.")
                    continue
                pbar.update(1)

                # Generate a summary/caption for the comic panel
                app_logger.debug(f"Generating summary for: {event_title}")
                panel_summary = analyze_text_opai(f"Generate a brief summary for this comic panel based on the following event and script: Event: {event_title}. {event_story}. Script: {event_analysis}", location)
                if not panel_summary:
                    app_logger.warning(f"Failed to generate panel summary for {event_title}. Using default summary.")
                    panel_summary = f"Summary of the event: {event_title}"
                pbar.update(1)

                summary_filename = image_filename.replace(".png", "_summary.txt")
                save_summary(location, summary_filename, event_title, event_story, event_source, panel_summary)

                app_logger.debug(f"Adding comic to database: {event_title}")
                add_comic(event_title, location, event_story, event_analysis, event_source, image_path)
                pbar.update(1)

                comic_panels.append((image_path, panel_summary))
                all_panel_summaries.append(panel_summary)

            if not comic_panels:
                app_logger.error("No comic panels were generated. Aborting comic generation.")
                return None

            # Step 3: Combine all panel summaries into one final summary
            app_logger.debug("Creating final summary")
            final_summary = f"Today's Events in {location}:\n" + "\n".join(all_panel_summaries)
            save_summary(location, "final_summary.txt", final_summary)
            pbar.update(1)
        return local_events

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_daily_comic: {e}", exc_info=True)
        return None

def generate_custom_comic(title, story, location):
    """
    Generates a custom comic based on user-provided title, story, and location.

    Args:
        title (str): The title of the custom comic.
        story (str): The story for the custom comic.
        location (str): The location setting for the custom comic.

    Returns:
        tuple: A tuple containing the image path and panel summary of the generated comic.
        None: If an error occurs during comic generation.
    """
    try:
        app_logger.info("Starting custom comic generation process...")

        # Check if a comic with this story already exists
        existing_comic = get_comic_by_story(story)
        if existing_comic:
            app_logger.info(f"Comic already exists for story: {title}. Returning existing comic.")
            return existing_comic[6], existing_comic[4]  # Return image_path and comic_script

        total_steps = 5  # Total number of steps in custom comic generation

        app_logger.info(f"Generating custom comic: {title}")
        with tqdm(total=total_steps, bar_format='{l_bar}{bar}', ncols=50, colour='#00FF00') as pbar:
            # Generate comic script for the custom story
            app_logger.debug("Analyzing custom story")
            event_analysis = analyze_text_opai(f"Generate a comic script for this event: {title}. {story}", location)
            if not event_analysis:
                app_logger.error(f"Failed to analyze custom event: {title}. Aborting comic generation.")
                return None
            pbar.update(1)

            # Generate comic panel image
            app_logger.debug("Generating comic panel image")
            image_data = generate_dalle_images(event_analysis)
            if not image_data:
                app_logger.error(f"Failed to generate comic panel for the custom event: {title}. Aborting comic generation.")
                return None
            pbar.update(1)

            # Save the generated image
            app_logger.debug("Saving generated image")
            # Use the title for the file name, replacing invalid characters and limiting length
            safe_title = re.sub(r'[^\w\-_\. ]', '_', title)
            safe_title = safe_title.replace(' ', '_')
            safe_title = safe_title[:100]  # Limit to 100 characters
            image_filename = f"{safe_title}.png"
            image_path = save_image(image_data, image_filename, location)
            if not image_path:
                app_logger.error(f"Failed to save the generated image for {title}. Aborting comic generation.")
                return None
            pbar.update(1)

            # Generate a summary/caption for the comic panel
            app_logger.debug("Generating panel summary")
            panel_summary = analyze_text_opai(f"Generate a brief summary for this comic panel based on the following event and script: Event: {title}. {story}. Script: {event_analysis}", location)
            if not panel_summary:
                app_logger.warning(f"Failed to generate panel summary for {title}. Using default summary.")
                panel_summary = f"Summary of the custom event: {title}"
            pbar.update(1)

            app_logger.debug("Saving summary")
            summary_filename = image_filename.replace(".png", "_summary.txt")
            save_summary(location, summary_filename, title, story, "", panel_summary)

            app_logger.debug(f"Adding custom comic to database: {title}")
            add_comic(title, location, story, event_analysis, "", image_path)
            pbar.update(1)

        # Print summary for the user
        app_logger.info(f"\nCustom comic generation completed!")
        app_logger.debug(f"Title: {title}")
        app_logger.debug(f"Image saved at: {image_path}")

        return image_path, panel_summary

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_custom_comic: {e}", exc_info=True)
        return None

def generate_media_comic(media_type, path, location):
    """
    Generates a comic based on a video or image file.

    Args:
        media_type (str): The type of media ('video' or 'image').
        path (str): The path to the media file or directory.
        location (str): The location for saving the comic.

    Returns:
        tuple: A tuple containing a list of image paths and a summary of the generated comic.
        None: If an error occurs during comic generation.
    """
    try:
        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if (media_type == 'video' and f.lower().endswith(('.mp4', '.avi', '.mov'))) or (media_type == 'image' and f.lower().endswith(('.jpg', '.png', '.jpeg')))]
            if not files:
                app_logger.warning(f"No valid media files found in the directory: {path}")
                return None
            media_paths = [os.path.join(path, f) for f in files]
        else:
            media_paths = [path]

        comic_images = []
        summaries = []

        total_steps = len(media_paths) * (8 if media_type == "video" else 5)
        with tqdm(total=total_steps, bar_format='{l_bar}{bar}', ncols=50, colour='#00FF00') as pbar:
            for media_path in media_paths:
                if media_type == 'video':
                    # Process video
                    video_summary = get_video_summary(media_path,pbar)
                    if not video_summary:
                        app_logger.error(f"Failed to generate summary for video: {media_path}")
                        continue
                    pbar.update(1)

                    # Check if a comic with this summary already exists
                    existing_comic = get_comic_by_story(video_summary)
                    if existing_comic:
                        app_logger.info(f"Comic already exists for video: {media_path}. Skipping this video.")
                        comic_images.append(existing_comic[6])  # Add existing image path
                        summaries.append(existing_comic[3])  # Add existing comic script
                        pbar.update(7)
                        continue

                    # Generate a single comic for the entire video summary
                    event_analysis = analyze_text_opai(f"Generate a comic script for this event: {video_summary}", location)
                    if not event_analysis:
                        app_logger.error(f"Failed to analyze video. Aborting comic generation.")
                        return None
                    pbar.update(1)

                    image_data = generate_dalle_images(event_analysis)
                    if not image_data:
                        app_logger.error("Failed to generate comic for the video")
                        continue
                    pbar.update(1)

                    image_filename = f"video_comic_{os.path.basename(media_path)}.png"
                    image_path = save_image(image_data, image_filename, location)
                    if not image_path:
                        app_logger.error("Failed to save the generated comic image")
                        continue
                    pbar.update(1)

                    comic_images.append(image_path)
                    summaries.append(video_summary)

                    app_logger.debug(f"Adding video comic to database: {os.path.basename(media_path)}")
                    add_comic(os.path.basename(media_path), location, video_summary, event_analysis, "", image_path)
                    pbar.update(1)

                elif media_type == 'image':
                    # Process image
                    image_analysis = analyze_frames(media_path)
                    if not image_analysis:
                        app_logger.error(f"Failed to analyze image: {media_path}")
                        continue
                    pbar.update(1)

                    # Join the frame descriptions into a single string
                    image_description = " ".join(image_analysis)

                    # Check if a comic with this description already exists
                    existing_comic = get_comic_by_story(image_description)
                    if existing_comic:
                        app_logger.info(f"Comic already exists for image: {media_path}. Skipping this image.")
                        comic_images.append(existing_comic[6])  # Add existing image path
                        summaries.append(existing_comic[3])  # Add existing comic script
                        pbar.update(4)
                        continue

                    # Generate a single comic for the entire image description
                    event_analysis = analyze_text_opai(f"Generate a comic script for this event: {image_description}", location)
                    if not event_analysis:
                        app_logger.error(f"Failed to analyze image. Aborting comic generation.")
                        return None
                    pbar.update(1)

                    image_data = generate_dalle_images(event_analysis)
                    if not image_data:
                        app_logger.error("Failed to generate comic for the image")
                        continue
                    pbar.update(1)

                    image_filename = f"image_comic_{os.path.basename(media_path)}.png"
                    image_path = save_image(image_data, image_filename, location)
                    if not image_path:
                        app_logger.error("Failed to save the generated comic image")
                        continue
                    pbar.update(1)

                    comic_images.append(image_path)
                    summaries.append(image_description)

                    app_logger.debug(f"Adding image comic to database: {os.path.basename(media_path)}")
                    add_comic(os.path.basename(media_path), location, image_description, event_analysis, "", image_path)
                    pbar.update(1)

        if not comic_images:
            app_logger.error("No comic images were generated. Aborting media comic generation.")
            return None

        # Create a final summary
        final_summary = "\n\n".join(summaries)
        save_summary(location, f"{media_type}_comic_summary.txt", f"{media_type.capitalize()} Comic", final_summary, "", "")

        return comic_images, final_summary

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_media_comic: {e}", exc_info=True)
        return None