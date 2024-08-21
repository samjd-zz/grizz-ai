# Description: Main script to run the Grizzly News AI-Generated Comics program.
#
# This script provides a command-line interface for generating AI-generated comics based on news articles, custom stories, and video/image content.
# It allows users to choose from different options to generate comics and post them to social media platforms.
#
# The main function handles the main menu loop and user interactions, allowing users to choose between generating daily news comics, custom comics, and media comics.
# The script also provides options to post the generated comics to Twitter and Facebook.
#

import warnings

# Suppress specific UserWarnings related to attention mask in transformers
warnings.filterwarnings("ignore", message="The attention mask is not set and cannot be inferred from input because pad token is same as eos token.")
warnings.filterwarnings("ignore", message="We strongly recommend passing in an `attention_mask` since your input_ids may be padded.")
warnings.filterwarnings("ignore", category=FutureWarning, module='transformers')

import os
import logging
from datetime import datetime

# Custom modules
from config import load_config
from logger import app_logger
from comic_generator import generate_daily_comic, generate_custom_comic, generate_media_comic
from social_media import post_to_twitter, post_to_facebook
from database import close_database, get_all_comics

# Load configuration
config = load_config()

# Set up logging
app_logger.setLevel(logging.INFO)

# Setting today constant
TODAY = datetime.now().strftime("%Y_%m_%d")

def display_menu():
    """
    Displays the main menu options and prompts for user input.

    Returns:
        str: The user's menu choice.
    """
    app_logger.info("\nGrizzly News: Daily AI-Generated Comics")
    app_logger.info("1. News")
    app_logger.info("2. Custom")
    app_logger.info("3. Media Video/Image")
    app_logger.info("4. View All Comics")
    app_logger.info("5. Exit")
    return input("Choose an option (1-5): ")

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

def view_all_comics():
    """
    Displays all comics stored in the database and the output folder.
    """
    comics_from_db = get_all_comics()
    comics_from_folder = []

    # Get comics from the output folder
    for root, dirs, files in os.walk(config.OUTPUT_DIR):
        for file in files:
            if file.endswith('.png'):
                comics_from_folder.append(os.path.join(root, file))

    if not comics_from_db and not comics_from_folder:
        app_logger.info("No comics found in the database or output folder.")
        return

    app_logger.info("\nAll Comics:")

    # Display comics from the database
    for comic in comics_from_db:
        app_logger.info(f"Title: {comic[1]}")
        app_logger.info(f"Location: {comic[2]}")
        app_logger.info(f"Image Path: {comic[6]}")
        app_logger.info(f"Created At: {comic[7]}")
        app_logger.info("-" * 50)

    # Display comics from the output folder that are not in the database
    db_image_paths = set(comic[6] for comic in comics_from_db)
    for image_path in comics_from_folder:
        if image_path not in db_image_paths:
            app_logger.info(f"Title: Unknown (Not in database)")
            app_logger.info(f"Location: Unknown")
            app_logger.info(f"Image Path: {image_path}")
            app_logger.info(f"Created At: Unknown")
            app_logger.info("-" * 50)

def main():
    """
    The main function that runs the Grizzly News AI-Generated Comics program.
    It handles the main menu loop and user interactions.
    """
    app_logger.info("Grizzly News: Daily AI-Generated Comics")
    
    try:
        while True:
            choice = display_menu()
            
            if choice == '1':
                location = input("Enter the location for news (press Enter for default location): ") or config.LOCATION
                app_logger.info("Fetching local events. Please wait...")
                local_events = generate_daily_comic(location)
                if local_events:
                    app_logger.info("-" * 50)
                    app_logger.info(f"Comic generated successfully!")
                    app_logger.info(f"{len(local_events)} NEW local event(s) retrieved today in {location}:")
                    app_logger.info("-" * 50)
                    for i, event in enumerate(local_events, start=1):
                        app_logger.info(f" * {event['title']}")
                    app_logger.info("-" * 50)
                    
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
            
            elif choice == '2':
                title = input("Enter the title for your custom comic: ")
                story = input("Enter the story for your custom comic: ")
                location = input("Enter the location for your custom comic (press Enter for default location): ") or config.LOCATION
                app_logger.info("\nGenerating custom comic... Please wait.")
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
                location = input("Enter the location for news (press Enter for default location): ") or config.LOCATION
                media_type = input("Enter 'video' for video processing or 'image' for image processing: ").lower()
                if media_type not in ['video', 'image']:
                    app_logger.info("Invalid media type. Please choose 'video' or 'image'.")
                    continue
                
                path = input(f"Enter the path to the {media_type} file or directory (press Enter for default SOURCE_DIR): ") or config.SOURCE_DIR
                
                if not os.path.exists(path):
                    app_logger.info(f"The specified path does not exist: {path}")
                    continue
                
                app_logger.info(f"\nGenerating comic from {media_type}. Please wait...")
                
                result = generate_media_comic(media_type, path, location)
                
                if result:
                    image_paths, summary = result
                    app_logger.info(f"Media comic generated successfully!")
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
                view_all_comics()
            
            elif choice == '5':
                app_logger.info("Exiting the program. Goodbye!")
                break
            
            else:
                app_logger.warning("Invalid choice. Please try again.")
    finally:
        close_database()

if __name__ == "__main__":
    main()