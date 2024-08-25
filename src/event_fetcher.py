import json
from datetime import datetime
import requests

from api_handlers import perplexity_client
from logger import app_logger
from config import load_config

config = load_config()

def perplexity_search(query: str, model_name=PERPLEXITY_SEARCH_MODEL):
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

def duckduckgo_search(query: str, num_results: int = 5):
    app_logger.debug(f"Performing DuckDuckGo search for: {query}")
    
    url = "https://api.duckduckgo.com/"
    params = {
        'q': query,
        'format': 'json',
        'pretty': '1',
        'no_html': '1',
        'skip_disambig': '1',
        't': config.DUCKDUCKGO_APP_NAME
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = []
        # Check Abstract
        if data.get('Abstract'):
            results.append({
                'title': data.get('Heading', 'Abstract'),
                'url': data.get('AbstractURL', ''),
                'description': data.get('Abstract', '')
            })
        
        # Check RelatedTopics
        for topic in data.get('RelatedTopics', []):
            if len(results) >= num_results:
                break
            if isinstance(topic, dict) and 'Text' in topic:
                results.append({
                    'title': topic['Text'].split(' - ')[0] if ' - ' in topic['Text'] else topic['Text'],
                    'url': topic.get('FirstURL', ''),
                    'description': topic['Text'].split(' - ')[1] if ' - ' in topic['Text'] else ''
                })
            elif isinstance(topic, dict) and 'Name' in topic:
                # Handle grouped topics
                for subtopic in topic.get('Topics', []):
                    if len(results) >= num_results:
                        break
                    if 'Text' in subtopic:
                        results.append({
                            'title': subtopic['Text'].split(' - ')[0] if ' - ' in subtopic['Text'] else subtopic['Text'],
                            'url': subtopic.get('FirstURL', ''),
                            'description': subtopic['Text'].split(' - ')[1] if ' - ' in subtopic['Text'] else ''
                        })
        
        # If we still don't have enough results, try to use the Definition
        if len(results) < num_results and data.get('Definition'):
            results.append({
                'title': 'Definition',
                'url': data.get('DefinitionURL', ''),
                'description': data.get('Definition', '')
            })
        
        app_logger.debug(f"Retrieved {len(results)} results from DuckDuckGo search.")
        return results
    except requests.RequestException as e:
        app_logger.error(f"Error performing DuckDuckGo search: {e}")
        return None
    except Exception as e:
        app_logger.error(f"Unexpected error in DuckDuckGo search: {e}")
        return None