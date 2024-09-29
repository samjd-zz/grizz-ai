# Description: Main script to run the Grizz-AI-Generated Comics program.
#
# This script provides a command-line interface for generating AI-generated comics based on news articles, custom stories, and video/image content.
# It allows users to choose from different options to generate comics and post them to social media platforms.
#
# The main function handles the main menu loop and user interactions, allowing users to choose between generating daily news comics, custom comics, and media comics.
# The script also provides options to post the generated comics to Twitter and Facebook.
#

import warnings
from numba.core.errors import NumbaDeprecationWarning

warnings.filterwarnings("ignore", message="We strongly recommend passing in an `attention_mask` since your input_ids may be padded.")
warnings.filterwarnings("ignore", category=FutureWarning, module='transformers')

# Suppress specific UserWarnings related to attention mask in transformers
warnings.filterwarnings("ignore", message="The attention mask is not set and cannot be inferred from input because pad token is same as eos token.")
# Suppress NumbaDeprecationWarning related to 'nopython' keyword argument
warnings.filterwarnings("ignore", category=NumbaDeprecationWarning, message="The 'nopython' keyword argument was not supplied to the 'numba.jit' decorator.")
# Suppress FutureWarning related to torch.load with weights_only=False
warnings.filterwarnings("ignore", category=FutureWarning, message="You are using `torch.load` with `weights_only=False`")

import os
import logging
from datetime import datetime, timedelta
from logger import app_logger

from config import load_config
from comic_generator import generate_daily_comic, generate_custom_comic, generate_media_comic
from voice_recognition import is_listen_voice_enabled, listen_to_user, toggle_voice
from psy_researcher import perform_duckduckgo_search
from utils import capture_live_video, summarize_generated_files
from text_analysis import create_yogi_bear_voice

from social_media import post_to_twitter, post_to_facebook
from database import ComicDatabase

# Load configuration
config = load_config()

# Set up logging
app_logger.setLevel(logging.DEBUG)

# Setting today constant
TODAY = datetime.now().strftime("%Y_%m_%d")

def display_menu():
    """
    Displays the main menu options and prompts for user input.

    Returns:
        str: The user's menu choice.
    """
    print("********Grizz-AI-Main Menu********")
    print("1. Create Perplexity News Comics*")
    print("2. Create Custom* Story Comics")
    print("3. Create Media* Video/Image Comics")
    print("4. View* All_Comics*")
    print("5. Toggle* Voice* Recognition(*=spoken command)")
    print("6. Psy-researcher: DuckDuckGo* Search*")
    print("7. Purge Database")
    print("8. Exit* or Quit*")
    return input("Choose an option (1-8): ")

def get_user_choice():
    """
    Gets the user's choice, either through voice command or text input.

    Returns:
        str: The user's choice.
    """
    if is_listen_voice_enabled():
        print("Please say your command...")
        command = listen_to_user(config.LISTEN_VOICE_DURATION_SHORT)
        if command:
            print(f"Recognized command: {command}")
            if "news" in command:
                return "1"
            elif "custom" in command:
                return "2"
            elif "media" in command:
                return "3"
            elif "view" in command or "all comics" in command:
                return "4"
            elif "toggle" in command or "voice" in command:
                return "5"
            elif "duckduckgo" in command or "search" in command:
                return "6"
            elif "purge" in command or "database" in command:
                return "7"
            elif "exit" in command or "quit" in command:
                return "8"
        print("Command not recognized. Please try again or use text input.")
    return display_menu()

def view_filtered_comics():
    """
    Allows users to view comics with optional date and location filters.
    """
    db = ComicDatabase()
    
    # Get filter inputs
    start_date_str = input("Enter start date (YYYY-MM-DD) or press Enter for no start date: ")
    end_date_str = input("Enter end date (YYYY-MM-DD) or press Enter for no end date: ")
    location = input("Enter location or press Enter for all locations: ")

    # Convert date strings to datetime objects
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None

    # Get filtered comics
    comics = db.get_filtered_comics(start_date, end_date, location)

    if not comics:
        print("No comics found matching the specified criteria.")
        return

    print("\nFiltered Comics:")
    print("-" * 50)
    for comic in comics:
        print(f"Title: {comic['title']}")
        print(f"Location: {comic['location']}")
        print(f"Date: {comic['date']}")
        print(f"Image Path: {comic['image_path']}")
        if comic['audio_path']:
            print(f"Audio Path: {comic['audio_path']}")
        print(f"Original Story: {comic['original_story'][:100]}...")  # Display first 100 characters
        print("-" * 50)

def main():
    """
    The main function that runs the Grizzly News AI-Generated Comics program.
    It handles the main menu loop and user interactions.
    """
    global config  # Declare config as global to avoid UnboundLocalError
    
    try:
        # Create Yogi Bear voice at startup
        if config.GENERATE_AUDIO:
            create_yogi_bear_voice()
        
        while True:
            choice = get_user_choice()
            
            if choice == '1':
                if is_listen_voice_enabled():
                    print("Please say your location...")
                    location = listen_to_user(config.LISTEN_VOICE_DURATION_SHORT)
                else:
                    location = input("Enter the location for news (press Enter for default location): ") or config.LOCATION
                print("Fetching local events. Please wait...")
                local_events = generate_daily_comic(location)
                if local_events:
                    print("-" * 50)
                    print(f"Comic generated successfully!")
                    print(f"{len(local_events)} NEW local event(s) retrieved today in {location}:")
                    print("-" * 50)
                    for i, event in enumerate(local_events, start=1):
                        print(f" * {event['title']}")
                    print("-" * 50)
                    
                    comic_dir = os.path.join(config.OUTPUT_DIR, f"{location.replace(' ', '_')}_comics", TODAY)
                    file_summary = summarize_generated_files(comic_dir)
                    app_logger.debug("Summary of generated files:")
                    app_logger.debug(file_summary)
                    app_logger.debug("-" * 50)
                    
                    # Option to post to social media
                    if input("Would you like to post this comic to social media? (y/n): ").lower() == 'y':
                        for filename in os.listdir(comic_dir):
                            if filename.endswith('.png'):
                                image_path = os.path.join(comic_dir, filename)
                                summary_path = os.path.join(comic_dir, filename.replace('.png', '_summary.txt'))
                                with open(summary_path, 'r') as f:
                                    summary = f.read()
                                post_to_twitter(image_path, summary, "https://example.com/comic")  # Replace with your actual comic URL
                                post_to_facebook(image_path, summary, "https://example.com/comic")  # Replace with your actual comic URL
                                app_logger.info(f"Posted comic to social media: {filename}")
                else:
                    print("No new events found or comic generation failed.")
            
            elif choice == '2':
                if is_listen_voice_enabled():
                    print("Please say your story title...")
                    title = listen_to_user(config.LISTEN_VOICE_DURATION_MEDIUM)
                    print("Please tell your story...")
                    story = listen_to_user(config.LISTEN_VOICE_DURATION_LONG)
                else:
                    title = input("Enter the title for your custom comic: ")
                
                story = input("Enter the story for your custom comic: ")
                location = input("Enter the location for your custom comic (press Enter for default location): ") or config.LOCATION
                print("\nGenerating custom comic. Please wait...")
                result = generate_custom_comic(title, story, location)
                if result:
                    image_path, summary = result
                    app_logger.debug("-" * 50)
                    app_logger.debug(f"Custom comic generated successfully!")
                    app_logger.debug(f"Image saved at: {image_path}")
                    app_logger.debug(f"Summary: {summary}")
                    app_logger.debug("-" * 50)
                    
                    comic_dir = os.path.dirname(image_path)
                    file_summary = summarize_generated_files(comic_dir)
                    app_logger.debug("Summary of generated files:")
                    app_logger.debug(file_summary)
                    app_logger.debug("-" * 50)
                    
                    # Option to post to social media
                    if input("Would you like to post this comic to social media? (y/n): ").lower() == 'y':
                        post_to_twitter(image_path, summary, "https://example.com/custom-comic")  # Replace with your actual comic URL
                        post_to_facebook(image_path, summary, "https://example.com/custom-comic")  # Replace with your actual comic URL
                        app_logger.info("Posted custom comic to social media")
            
            elif choice == '3':
                if is_listen_voice_enabled():
                    print("Please say your media type: 'video', 'image', or 'live'...")
                    media_type = listen_to_user(config.LISTEN_VOICE_DURATION_SHORT)
                else:
                    media_type = input("Enter 'video' for video processing, 'image' for image processing, or 'live' for live video capture: ").lower()
                
                if media_type not in ['video', 'image', 'live']:
                    app_logger.info("Invalid media type. Please choose 'video', 'image', or 'live'.")
                    continue
                
                if media_type == 'live':
                    if is_listen_voice_enabled():
                        print("Please say the title for your live video...")
                        title = listen_to_user(config.LISTEN_VOICE_DURATION_MEDIUM)
                    else:
                        title = input("Enter the title for your live video: ")
                    
                    print("Preparing to capture live video. Press 'q' to stop recording early.")
                    video_path = capture_live_video()
                    if video_path is None:
                        print("Failed to capture live video. Please try again.")
                        continue
                    path = video_path
                else:
                    if is_listen_voice_enabled():
                        print(f"Using default input path {config.SOURCE_DIR}...")
                        path = config.SOURCE_DIR
                    else:
                        path = input(f"Enter the path to the {media_type} file or directory (press Enter for default SOURCE_DIR): ") or config.SOURCE_DIR
                
                if not os.path.exists(path):
                    app_logger.info(f"The specified path does not exist: {path}")
                    continue
                
                location = input("Enter the location for your media comic (press Enter for default location): ") or config.LOCATION
                
                app_logger.info(f"\nGenerating comic from {media_type}. Please wait...")
                
                result = generate_media_comic(media_type, path, location)
                
                if result:
                    image_paths, summary = result
                    print(f"Media comic generated successfully!")
                    for i, image_path in enumerate(image_paths, start=1):
                        app_logger.debug(f"Comic {i} saved at: {image_path}")
                    app_logger.debug(f"Summary: {summary}")
                    app_logger.debug("-" * 50)
                    
                    comic_dir = os.path.dirname(image_paths[0])
                    file_summary = summarize_generated_files(comic_dir)
                    app_logger.debug("Summary of generated files:")
                    app_logger.debug(file_summary)
                    app_logger.debug("-" * 50)
                    
                    # Option to post to social media
                    if input("Would you like to post this comic to social media? (y/n): ").lower() == 'y':
                        for image_path in image_paths:
                            post_to_twitter(image_path, summary, "https://example.com/media-comic")  # Replace with your actual comic URL
                            post_to_facebook(image_path, summary, "https://example.com/media-comic")  # Replace with your actual comic URL
                            app_logger.info(f"Posted media comic to social media: {os.path.basename(image_path)}")
            
            elif choice == '4':
                view_filtered_comics()
            
            elif choice == '5':
                toggle_voice()
                config = load_config()  # Reload the configuration after toggling voice recognition
            
            elif choice == '6':
                perform_duckduckgo_search()
            
            elif choice == '7':
                confirmation = input("Are you sure you want to purge the database? This action cannot be undone. (y/n): ")
                if confirmation.lower() == 'y':
                    ComicDatabase.purge_database()
                    print("Database purged successfully.")
                else:
                    print("Database purge cancelled.")
            
            elif choice == '8':
                app_logger.info("Exiting the program. Goodbye!")
                break
            
            else:
                app_logger.warning("Invalid choice. Please try again.")
    finally:
        ComicDatabase.close()

if __name__ == "__main__":
    main()