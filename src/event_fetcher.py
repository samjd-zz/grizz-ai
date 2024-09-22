import json
from datetime import datetime
import re

from api_handlers import perplexity_client
from logger import app_logger
from config import load_config

#to web scrape prefix with https://r.jina.ai/ + url

config = load_config()

def extract_events_from_text(text):
    events = []
    event_pattern = r'\d+\.\s+\*\*(.*?)\*\*\s*-\s*\*\*Title\*\*:\s*(.*?)\s*-\s*\*\*Story\*\*:\s*(.*?)\s*-\s*\*\*Full Story Source URL\*\*:\s*(.*?)(?=\n\d+\.|\Z)'
    matches = re.findall(event_pattern, text, re.DOTALL)
    
    for match in matches:
        event = {
            "title": match[1].strip(),
            "story": match[2].strip(),
            "full_story_source_url": match[3].strip().strip('[]')
        }
        events.append(event)
    
    return events

def perplexity_search(query: str, model_name=config.PERPLEXITY_SEARCH_MODEL):
    client = perplexity_client()
    
    messages = [{"role": "system",
         "content": """
    You are an expert helicopter pilot and a seasoned news reporter with deep connections 
    to all local and regional stories. As a valued member of the BC Wildfire Reporting Team, 
    you are always informed with up-to-the-minute details on current events, particularly 
    wildfire incidents, evacuation updates, and other breaking news related to firefighting. 
    You also have access to the local library and calendar of events, as well as the latest
    weather and road condition reports. Your mission is to provide a comprehensive summary
    of the most recent news and events in British Columbia, focusing on the past 7 days.
    
    Please provide your response as a JSON list of events, where each event is an object with 'title', 'story', 
    and 'full_story_source_url' fields. 

    Only return stories and news updates from the past **7 days**, highlighting key updates relevant 
    to the BC wildfire situation, any weather, road conditions, or significant entertainment and local news. 
    If there are no recent updates in a specific category, skip it. Ensure all stories focus on events within the last 7 days.
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
        
        # Attempt to parse JSON
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # If JSON parsing fails, attempt to extract JSON from the text
            start_index = result.find('[')
            end_index = result.rfind(']') + 1
            if start_index != -1 and end_index != -1:
                json_str = result[start_index:end_index]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # If JSON extraction fails, try to parse the text response
                    events = extract_events_from_text(result)
                    if events:
                        return events
                    else:
                        raise ValueError("Unable to extract events from the response")
            else:
                raise ValueError("Unable to extract valid JSON from the response")
    except json.JSONDecodeError as e:
        app_logger.error(f"Error parsing JSON from Perplexity API: {e}")
        app_logger.error(f"Raw response: {result}")
        # Attempt to extract events from the text response
        events = extract_events_from_text(result)
        if events:
            app_logger.info(f"Successfully extracted {len(events)} events from the text response")
            return events
        return None
    except Exception as e:
        app_logger.error(f"Error querying Perplexity API: {e}")
        return None

def get_local_events(location):
    app_logger.debug(f"Getting local events for {location}.")
    
    today_date = datetime.now().strftime("%B %d, %Y")
    query = f"""Please provide a list of current news events happening in {location} during the last 7 days. 
        The events must have occurred within the last 7 days only. 
        Make sure the information is up-to-date and exclude events 7 days prior to {today_date}."""
    
    events = perplexity_search(query)
    if events:
        app_logger.debug(f"Retrieved {len(events)} local events for {location}.")
        return events
    else:
        app_logger.warning(f"Failed to retrieve local events for {location}.")
        return None

