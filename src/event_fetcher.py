import json
from datetime import datetime
import re

from api_handlers import perplexity_client
from logger import app_logger
from config import load_config
from utils import sanitize_location

config = load_config()

def clean_text(text):
    """Clean text by removing markdown, extra whitespace, and unwanted characters"""
    # Remove markdown
    text = re.sub(r'[#*`]', '', text)
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Remove any trailing/leading punctuation
    text = text.strip('.,: \n')
    return text

def extract_source(text):
    """Extract source URL and name from text"""
    source_match = re.search(r'Source:\s*\[(.*?)\]\((.*?)\)', text)
    if source_match:
        source_name = clean_text(source_match.group(1))
        source_url = clean_text(source_match.group(2))
    else:
        source_match = re.search(r'Source:\s*(.*?)(?=\n|$)', text)
        if source_match:
            source_text = clean_text(source_match.group(1))
            # If source looks like a URL, use it as URL and extract name
            if source_text.startswith(('http://', 'https://', 'www.')):
                source_url = source_text
                source_name = source_text.split('/')[2]  # Extract domain as name
            else:
                source_url = ''
                source_name = source_text
        else:
            source_url = ''
            source_name = 'None'
    
    return source_url, source_name

def extract_title_story(text):
    """Extract title and story from text block"""
    title_match = re.search(r'Title:\s*(.*?)(?:\s*Story:|$)', text, re.IGNORECASE | re.DOTALL)
    story_match = re.search(r'Story:\s*(.*?)(?:\s*Source:|$)', text, re.IGNORECASE | re.DOTALL)
    
    title = clean_text(title_match.group(1)) if title_match else None
    story = clean_text(story_match.group(1)) if story_match else clean_text(text)
    
    return title, story

def extract_events_from_text(text):
    """Extract events from text using multiple patterns"""
    events = []
    
    # Split text into sections by double newlines
    sections = text.split('\n\n')
    
    for section in sections:
        # Skip empty sections or headers
        if not section.strip() or section.strip().startswith('Based on') or section.strip().startswith('Given the'):
            continue
            
        title, story = extract_title_story(section)
        source_url, source_name = extract_source(section)
        
        # Skip if we couldn't extract a meaningful story
        if not story or any(phrase in story.lower() 
                          for phrase in ['no significant news', 'no current news', 'no events found', 'no news events']):
            continue
            
        # Skip if the story is just a list of sources
        if 'Sources Checked:' in story or story.count('http') > 2:
            continue
            
        if title and story:
            event = {
                "title": title,
                "story": story,
                "full_story_source_url": source_url,
                "source_name": source_name
            }
            events.append(event)
    
    # If no valid events found, return a "no news" event
    if not events:
        return [{
            "title": "No Current News Events",
            "story": "There are no significant news events to report for this area in the past 7 days.",
            "full_story_source_url": "None",
            "source_name": "None"
        }]
    
    return events

def perplexity_search(query: str, model_name=config.PERPLEXITY_SEARCH_MODEL):
    client = perplexity_client()
    
    messages = [{"role": "system",
         "content": """
    You are an expert helicopter pilot and a seasoned news reporter with deep connections 
    to all local and regional stories. As a valued member of the Wildfire Reporting Team, 
    you are always informed with up-to-the-minute details on current events, particularly 
    wildfire incidents, evacuation updates, and other breaking news related to firefighting. 
    You also have access to the local library and calendar of events, as well as the latest
    weather and road condition reports.

    Your task is to provide a comprehensive summary of the most recent news and events in the specified area, 
    focusing on the past 7 days.
    
    For each event, provide:
    Title: [Event Title]
    Story: [Event Details]
    Source: [Source URL]
    
    Guidelines:
    1. Only include events from the past 7 days
    2. Provide specific details and facts
    3. Include source URLs when available
    4. Format consistently for each event
    5. If no current events are found, respond with a single "no news" event
    
    Example format:
    Title: Local Festival Announced
    Story: The annual spring festival will be held next weekend featuring local artists and food vendors.
    Source: [City News](https://citynews.com/festival-announcement)
  """
         ,},
        {"role": "user","content": query},
    ]
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )
        result = response.choices[0].message.content
        result = result.replace("```json", "").replace("```", "").strip()
        
        # Extract events from the text response
        events = extract_events_from_text(result)
        if events:
            app_logger.debug(f"Successfully extracted {len(events)} events from text response")
            return events
        else:
            app_logger.warning("No events found in response")
            return [{
                "title": "No Current News Events",
                "story": "There are no significant news events to report for this area in the past 7 days.",
                "full_story_source_url": "None",
                "source_name": "None"
            }]
    except Exception as e:
        app_logger.error(f"Error querying Perplexity API: {e}")
        return [{
            "title": "No Current News Events",
            "story": "There are no significant news events to report for this area in the past 7 days.",
            "full_story_source_url": "None",
            "source_name": "None"
        }]

def get_local_events(location):
    app_logger.debug(f"Getting local events for {location}.")
    
    today_date = datetime.now().strftime("%B %d, %Y")
    location = location.lower()  # Convert location to lowercase for case-insensitive comparison

    if "lillooet" in location.lower():
        query = f"""Please provide a list of current news events happening in {location} during the last 7 days. 
            The events must have occurred within the last 7 days only. 
            Make sure the information is up-to-date and exclude events 7 days prior to {today_date}.
            
            IMPORTANT: Among others, you must also always check the following news sources for the latest updates:
            https://globalnews.ca/tag/lillooet/
            https://www.lillooet.ca/news-1
            https://bc-cb.rcmp-grc.gc.ca/ViewPage.action?contentId=-1&detachmentDataId=43910&siteNodeId=2259
            https://ground.news/interest/lillooet
            https://www.cbc.ca/cmlink/rss-canada-britishcolumbia
            
            IMPORTANT: You must also check the following twitter accounts for the latest updates:
            @LillooetNews
            @lillooetbc
            @InteriorHealth
            @BCGovFireInfo
            @DriveBC
            @EmergencyInfoBC
            
            Format each event as:
            Title: [Event Title]
            Story: [Event Details]
            Source: [Source Name](Source URL)
        """
    else:
        query = f"""Please provide a list of current news events happening in {location} during the last 7 days. 
            The events must have occurred within the last 7 days only. 
            Make sure the information is up-to-date and exclude events 7 days prior to {today_date}.
            
            IMPORTANT: Be sure to check local news sources, official websites, and social media for the most recent updates.
            
            Format each event as:
            Title: [Event Title]
            Story: [Event Details]
            Source: [Source Name](Source URL)
        """

    events = perplexity_search(query)
    if events:
        app_logger.debug(f"Retrieved {len(events)} local events for {location}.")
        return events
    else:
        app_logger.warning(f"Failed to retrieve local events for {location}.")
        return None
