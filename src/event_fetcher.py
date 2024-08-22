import json
from datetime import datetime

from api_handlers import perplexity_client
from logger import app_logger
from config import load_config

config = load_config()

def perplexity_search(query: str, model_name="llama-3.1-sonar-large-128k-online"):
    client = perplexity_client()
    
    messages = [{"role": "system",
         "content": "You are an expert helicopter pilot and a seasoned news reporter with deep connections to all local and regional stories. As a valued member of the BC Wildfire Reporting Team, you are always informed with up-to-the-minute details on current events, particularly wildfire incidents, evacuation updates, and other breaking news related to firefighting. Please provide your response as a JSON list of events, where each event is an object with 'title', 'story', and 'full_story_source_url' fields. Make sure to highlight key updates relevant to the BC wildfire situation and any other significant news stories happening in the area.",},
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
                return json.loads(json_str)
            else:
                raise ValueError("Unable to extract valid JSON from the response")
    except json.JSONDecodeError as e:
        app_logger.error(f"Error parsing JSON from Perplexity API: {e}")
        app_logger.error(f"Raw response: {result}")
        return None
    except Exception as e:
        app_logger.error(f"Error querying Perplexity API: {e}")
        return None

def get_local_events(location):
    app_logger.debug(f"Getting local events for {location}.")
    
    today_date = datetime.now().strftime("%B %d, %Y")
    query = f"Please provide a list of current news events happening in {location} today ({today_date}). The events must have occurred within the last 24 hours only. Make sure the information is up-to-date and exclude events prior to {today_date}."
    
    events = perplexity_search(query)
    if events:
        app_logger.debug(f"Retrieved {len(events)} local events for {location}.")
        return events
    else:
        app_logger.warning(f"Failed to retrieve local events for {location}.")
        return None