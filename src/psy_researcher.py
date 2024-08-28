import ollama
import json
import re
import requests

from logger import app_logger
from config import load_config

config = load_config()

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
    
    