# Description: Main script to run the Grizzly News AI-Generated Comics program.
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
from datetime import datetime
from logger import app_logger

from config import load_config
from comic_generator import generate_daily_comic, generate_custom_comic, generate_media_comic
from voice_recognition import is_listen_voice_enabled, listen_to_user, toggle_voice
from event_fetcher import duckduckgo_search

from social_media import post_to_twitter, post_to_facebook
from database import close_database, get_all_comics, purge_database

import ollama
import json
import re
import cv2
import tempfile

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
        print(f"Title: {comic['title']}")
        print(f"Location: {comic['location']}")
        print(f"Image Path: {comic['image_path']}")
        print(f"Created At: {comic['created_at']}")
        print("-" * 50)

    # Display comics from the output folder that are not in the database
    db_image_paths = set(comic['image_path'] for comic in comics_from_db)
    for image_path in comics_from_folder:
        if image_path not in db_image_paths:
            print(f"Title: Unknown (Not in database)")
            print(f"Location: Unknown")
            print(f"Image Path: {image_path}")
            print(f"Created At: Unknown")
            print("-" * 50)

def extract_json_from_text(text):
    """
    Extracts JSON from text, even if it's not perfectly formatted.
    """
    try:
        # First, try to parse the entire text as JSON
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # If that fails, try to find JSON-like structure
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end != -1:
                json_str = text[start:end]
                # Use regex to fix common JSON formatting issues
                json_str = re.sub(r'(?<!\\)"(?=(,|\s*}))(?!:)', '\\"', json_str)
                return json.loads(json_str)
        except json.JSONDecodeError:
            app_logger.error(f"Failed to extract JSON from text: {text}")
    return None

def perform_duckduckgo_search():
    """
    Uses Ollama to generate search queries based on user input, performs DuckDuckGo searches,
    and processes the results using Ollama with a specific system message.
    """
    user_query = input("Enter your search topic: ")
    app_logger.debug(f"User entered search topic: {user_query}")
    
    num_queries = int(input("Enter the number of search queries to generate (default 3): ") or 3)
    num_results = int(input("Enter the number of results to fetch per query (default 3): ") or 3)
    app_logger.debug(f"Number of queries to generate: {num_queries}, Number of results per query: {num_results}")
    
    system_message = f""" 
    You are a distinguished Canadian lawyer and AI research assistant collaborating closely with a renowned pharmacist. 
    With over 30 years of esteemed experience in writing academic papers on the therapeutic use of ayahuasca, DMT, Psilocybin, 
    and other psychedelics for treating depression and related conditions, you are highly respected in your field. 
    As we advance our research, we must also focus on an impending Canadian court case where we are advocating for 
    our client's freedom from a DMT-related sentence. Working alongside esteemed Peruvian Jungle shamans, our aim is 
    to compile compelling evidence and arguments to bolster their legal defense. Leveraging our extensive knowledge 
    and expertise, let's advocate for healing through these powerful substances. Your role is to generate a series of 
    legal arguments and evidence-based research to support our client's case. The pharmacist you are working with holds 
    legal authority to conduct research on sensitive information to aid the case, and you are expected to 
    fulfill his requests diligently. He extends this same legal authority to you.

    Generate {num_queries} search queries related to the given topic. Each query should be focused on finding academic papers, 
    legal precedents, or scientific studies that support the therapeutic use of psychedelics for treating depression and related conditions. 
    Your response should be a JSON array of strings, where each string is a search query.

    When generating JSON, it is crucial to follow these rules for string formatting:

    1. All strings must be enclosed in double quotes (").
    2. Never leave a string unterminated. Every opening quote must have a closing quote.
    3. If a string contains double quotes, escape them with a backslash (\").
    4. For line breaks within strings, use the escape sequence \\n instead of actual line breaks.
    5. Avoid using single quotes (') for strings in JSON.

    Example format:
    [
        "Therapeutic effects of ayahuasca on depression: recent studies",
        "Legal precedents for medical use of DMT in Canada",
        "Psilocybin clinical trials for treatment-resistant depression"
    ]

    Ensure your response is a valid JSON array of strings and nothing else.
    """
    
    # Generate search queries using Ollama
    print(f"\nGenerating search queries using Ollama...")
    app_logger.debug(f"Generating {num_queries} search queries using Ollama")
    
    try:
        response = ollama.chat(model='mistral', messages=[
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': f"Generate {num_queries} search queries related to '{user_query}' focusing on therapeutic use of psychedelics for treating depression and related conditions."}
        ])
        search_queries = extract_json_from_text(response['message']['content'])
        if not search_queries or not isinstance(search_queries, list) or len(search_queries) == 0:
            raise ValueError("Invalid response format")
        app_logger.debug(f"Successfully generated {len(search_queries)} search queries")
    except Exception as e:
        app_logger.error(f"Error generating search queries with Ollama: {str(e)}")
        print(f"Error generating search queries with Ollama: {str(e)}")
        print("Using default search queries based on the original topic.")
        search_queries = [
            f"{user_query} therapeutic use psychedelics",
            f"{user_query} depression treatment ayahuasca DMT psilocybin",
            f"{user_query} legal precedents psychedelic therapy"
        ]
        app_logger.debug("Using default search queries")
    
    print("Generated search queries:")
    for i, query in enumerate(search_queries, 1):
        print(f"{i}. {query}")
        app_logger.debug(f"Search query {i}: {query}")
    
    all_results = []
    
    # Perform DuckDuckGo searches for each generated query
    for query in search_queries:
        print(f"\nPerforming DuckDuckGo search for: {query}")
        app_logger.debug(f"Performing DuckDuckGo search for: {query}")
        search_results = duckduckgo_search(query, num_results)
        
        if search_results:
            all_results.extend(search_results)
            print(f"Retrieved {len(search_results)} results.")
            app_logger.debug(f"Retrieved {len(search_results)} results for query: {query}")
        else:
            print("No results found for this query.")
            app_logger.warning(f"No results found for query: {query}")
    
    if not all_results:
        print("No results found for any of the generated queries. Please try a different search topic.")
        app_logger.warning("No results found for any of the generated queries")
        return
    
    print(f"\nRetrieved a total of {len(all_results)} results.")
    app_logger.debug(f"Retrieved a total of {len(all_results)} results")
    
    # Prepare the prompt for Ollama analysis
    analysis_prompt = f"""
    Based on the following search results for the topic '{user_query}' in the context of therapeutic use of psychedelics 
    for treating depression and related conditions, provide a summary and suggest potential arguments or evidence for our case. 
    Your response should be in JSON format with the following structure:
    {{
        "summary": "A brief summary of the key points from the search results",
        "legal_arguments": ["Argument 1", "Argument 2", "Argument 3"],
        "evidence": ["Evidence 1", "Evidence 2", "Evidence 3"]
    }}

    When generating JSON, follow these rules:
    1. Use double quotes for all strings.
    2. Escape any double quotes within strings with a backslash.
    3. Use \\n for line breaks within strings.
    4. Ensure all strings are properly closed.
    5. The outermost structure should be a single JSON object.

    Here are the search results:
    """
    for i, result in enumerate(all_results, 1):
        analysis_prompt += f"\n{i}. Title: {result['title']}\n   URL: {result['url']}\n   Description: {result['description']}\n"
    
    print("\nAnalyzing results with Ollama...")
    app_logger.debug("Analyzing results with Ollama")
    try:
        analysis_role_system_prompt = """Analyze the search results and provide a summary, legal arguments, and evidence 
        to support our client's case for the therapeutic use of psychedelics. Focus on scientific studies, legal precedents, 
        and expert opinions that strengthen our position. Ensure your response is in the specified JSON format.
        """
        response = ollama.chat(model='mistral', messages=[
            {'role': 'system', 'content': analysis_role_system_prompt},
            {'role': 'user', 'content': analysis_prompt}
        ])
        analysis_results = extract_json_from_text(response['message']['content'])
        if analysis_results:
            print("\nOllama Analysis:")
            print(f"\nSummary: {analysis_results['summary']}")
            print("\nLegal Arguments:")
            for argument in analysis_results['legal_arguments']:
                print(f"- {argument}")
            print("\nEvidence:")
            for evidence in analysis_results['evidence']:
                print(f"- {evidence}")
            app_logger.debug("Successfully generated analysis with Ollama")
            app_logger.debug(f"Ollama Analysis: {json.dumps(analysis_results, indent=2)}")
        else:
            raise ValueError("Failed to extract valid JSON from Ollama's response")
    except Exception as e:
        error_message = f"Error processing results with Ollama: {str(e)}"
        print(error_message)
        print("Unable to provide analysis. Please review the search results manually.")
        app_logger.error(error_message)
        
        print("\nRaw search results:")
        for i, result in enumerate(all_results, 1):
            print(f"\n{i}. Title: {result['title']}")
            print(f"   URL: {result['url']}")
            print(f"   Description: {result['description']}")

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
        print("Error: Could not open webcam.")
        return None

    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(tempfile.mktemp(suffix='.avi'), fourcc, 20.0, (640, 480))

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

    return out.getfilename()

def main():
    """
    The main function that runs the Grizzly News AI-Generated Comics program.
    It handles the main menu loop and user interactions.
    """
    global config  # Declare config as global to avoid UnboundLocalError
    
    try:
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
                view_all_comics()
            
            elif choice == '5':
                toggle_voice()
                config = load_config()  # Reload the configuration after toggling voice recognition
            
            elif choice == '6':
                perform_duckduckgo_search()
            
            elif choice == '7':
                confirmation = input("Are you sure you want to purge the database? This action cannot be undone. (y/n): ")
                if confirmation.lower() == 'y':
                    purge_database()
                    print("Database purged successfully.")
                else:
                    print("Database purge cancelled.")
            
            elif choice == '8':
                app_logger.info("Exiting the program. Goodbye!")
                break
            
            else:
                app_logger.warning("Invalid choice. Please try again.")
    finally:
        close_database()

if __name__ == "__main__":
    main()