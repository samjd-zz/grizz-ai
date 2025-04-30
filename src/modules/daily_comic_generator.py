from datetime import datetime
import os

from logger import app_logger
from utils import save_summary, save_image, sanitize_filename
from text_analysis import analyze_text_ollama, speak_elevenLabs
from event_fetcher import get_local_events
from database import ComicDatabase
from config import load_config
from .comic_core import parse_panel_summaries
from .image_generation_handler import generate_images

config = load_config()

def generate_daily_comic(location, user_id, comic_artist_style, no_news_event=None, progress_callback=None):
    """
    Generate a daily comic based on local events.
    
    Args:
        location (str): The location to fetch events for.
        user_id (int): The ID of the user generating the comic.
        comic_artist_style (str): The style of comic artist to emulate.
        no_news_event (dict, optional): Pre-formatted event for no news case.
        progress_callback (function, optional): Callback for progress updates.
    
    Returns:
        list: List of generated events with their comic data, or None if generation fails.
    """
    app_logger.info(f"Starting daily comic generation for location: {location}, style: {comic_artist_style}")
    try:
        if progress_callback:
            progress_callback(0, f"Fetching local events for {location}")

        # If we're handling a "no news" case
        if no_news_event:
            local_events = [no_news_event]
        else:
            local_events = get_local_events(location)
            if not local_events:
                app_logger.warning(f"No new local events in the past 7 days for {location}. Aborting comic generation.")
                if progress_callback:
                    progress_callback(100, f"No new events found for {location}")
                return None

            # Check if we got a "no news" event from the event fetcher
            if len(local_events) == 1 and "No Current News Events" in local_events[0]['title']:
                app_logger.info("Converting no news event to proper format")
                no_news_event = {
                    'title': "No Current News Events",
                    'story': "There are no significant news events to report for this area in the past 7 days.",
                    'full_story_source_url': local_events[0].get('full_story_source_url', 'None'),
                    'source_name': local_events[0].get('source_name', 'None')
                }
                return generate_daily_comic(location, user_id, comic_artist_style, no_news_event, progress_callback)
        
        app_logger.info(f"Found {len(local_events)} events for {location}")
        if progress_callback:
            progress_callback(10, f"Found {len(local_events)} events for {location}")

        comic_panels = []
        all_panel_summaries = []
        processed_events = []

        for i, event in enumerate(local_events):
            event_title = sanitize_filename(event['title'])
            event_story = event['story']
            event_source = event.get('full_story_source_url', 'None')
            source_name = event.get('source_name', 'None')
            
            app_logger.info(f"Processing event {i+1}/{len(local_events)}: {event_title}")
            base_progress = 10 + (i * 80 // len(local_events))
            if progress_callback:
                progress_callback(base_progress, f"Processing event {i+1}/{len(local_events)}: {event_title}")
            
            # Skip duplicate stories
            existing_comic = ComicDatabase.get_comic_by_story(event_story)
            if existing_comic:
                app_logger.info(f"Comic already exists for story: {event_title}. Skipping this event.")
                continue
            
            if progress_callback:
                progress_callback(base_progress + 5, f"Analyzing event: {event_title}")

            # Generate comic script and summaries
            result = analyze_text_ollama(f"Generate a comic script for this event: {event_title}. {event_story}", location, comic_artist_style)
            if not result or len(result) != 3:
                app_logger.error(f"Failed to analyze event: {event_title}. Skipping this event.")
                continue
                
            event_analysis, comic_summary, panel_summaries = result

            if progress_callback:
                progress_callback(base_progress + 10, f"Generating images for: {event_title}")
            app_logger.info(f"Generating images for event: {event_title}")
            image_results = generate_images(event_analysis, event_story, comic_artist_style, 
                lambda p, m: progress_callback(base_progress + 10 + int(p * 0.4), m) if progress_callback else None)
            
            if not image_results:
                app_logger.error(f"Failed to generate comic panel for the event: {event_title}. Skipping this event.")
                continue
            
            if progress_callback:
                progress_callback(base_progress + 50, f"Saving images for: {event_title}")
            
            app_logger.info(f"Saving images for event: {event_title}")
            image_paths = []
            for j, image_result in enumerate(image_results):
                if image_result:
                    image_filename = f"ggs_grizzly_news_{event_title}_{j+1}.png"
                    image_path = save_image(image_result, image_filename, location)
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

            if progress_callback:
                progress_callback(base_progress + 60, f"Generating audio for: {event_title}")

            audio_path = ""
            if config.GENERATE_AUDIO:
                app_logger.info(f"Generating audio narration for event: {event_title}")
                audio_path = speak_elevenLabs(event_story, event_title)
                if not audio_path:
                    app_logger.warning(f"Failed to generate audio narration for {event_title}.")

            if progress_callback:
                progress_callback(base_progress + 70, f"Saving comic data for: {event_title}")

            summary_filename = f"ggs_grizzly_news_{event_title}_{len(image_paths)}_summary.txt"
            save_summary(location, summary_filename, event_title, event_story, event_source, comic_summary)

            app_logger.info(f"Adding comic to database: {event_title}")
            
            # Convert absolute paths to relative paths before storing in the database
            relative_image_paths = []
            for path in image_paths:
                # Check if path is absolute
                if os.path.isabs(path):
                    # Make path relative to OUTPUT_DIR
                    rel_path = os.path.relpath(path, config.OUTPUT_DIR)
                    relative_image_paths.append(rel_path)
                else:
                    # Already relative, but ensure it doesn't start with ./output/
                    if path.startswith('./output/'):
                        rel_path = path[9:]  # Remove ./output/ prefix
                        relative_image_paths.append(rel_path)
                    else:
                        relative_image_paths.append(path)
            
            # Make audio path relative if it exists
            relative_audio_path = ""
            if audio_path:
                if os.path.isabs(audio_path):
                    audio_dir = os.path.join(config.OUTPUT_DIR, 'audio')
                    relative_audio_path = os.path.relpath(audio_path, audio_dir)
                else:
                    relative_audio_path = audio_path
            
            app_logger.debug(f"Saving relative image paths to database: {relative_image_paths}")
            ComicDatabase.add_comic(user_id, event_title, location, event_story, event_analysis, comic_summary, event_source, ",".join(relative_image_paths), relative_audio_path, datetime.now().date())

            comic_panels.append((image_paths, panel_summaries))
            all_panel_summaries.extend(panel_summaries)

            processed_event = event.copy()
            processed_event.update({
                'image_paths': relative_image_paths,  # Use relative paths for consistent handling
                'comic_script': event_analysis,
                'comic_summary': comic_summary,
                'panel_summaries': panel_summaries,
                'audio_path': relative_audio_path,  # Use relative audio path
                'story': event_story,
                'full_story_source_url': event_source,
                'source_name': source_name
            })
            processed_events.append(processed_event)

            app_logger.info(f"Completed processing for event: {event_title}")

        if not comic_panels:
            app_logger.error("No comic panels were generated. Aborting comic generation.")
            if progress_callback:
                progress_callback(100, "Failed to generate any comic panels")
            return None

        app_logger.info("Creating final summary")
        if progress_callback:
            progress_callback(95, "Creating final summary")

        final_summary = f"Today's Events in {location}:\n" + "\n".join(all_panel_summaries)
        save_summary(location, "final_summary.txt", final_summary)

        app_logger.info(f"Daily comic generation completed for {location}!")
        
        if progress_callback:
            progress_callback(100, f"Comic generation completed for {location}")
        
        return processed_events

    except Exception as e:
        app_logger.error(f"Unexpected error in generate_daily_comic: {e}", exc_info=True)
        if progress_callback:
            progress_callback(100, f"Error occurred: {str(e)}")
        return None
