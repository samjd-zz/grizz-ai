import json
import ollama
import psycopg2
import os

from logger import app_logger
from typing import Dict, Any
from utils import unload_ollama_model
from config import load_config

config = load_config()

# Define your tools

#def query_sql(query: str) -> Any:
    # Placeholder function to query an SQL database
    # Implement your SQL connection and qu
    #return f"SQL query result for: {query}"

def query_sql(query: str) -> Any:
    conn = psycopg2.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result

def query_rag(question: str) -> Any:
    # Placeholder function to perform a RAG query
    # Implement your RAG retrieval and generation logic here
    return f"RAG response for: {question}"

def save_to_disk(file_path: str, data: str) -> str:
    try:
        with open(file_path, 'w') as file:
            file.write(data)
        return f"Data successfully saved to {file_path}"
    except Exception as e:
        return f"Failed to save data: {str(e)}"

def fetch_from_disk(file_path: str) -> str:
    try:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
        with open(file_path, 'r') as file:
            data = file.read()
        return data
    except Exception as e:
        return f"Failed to fetch data: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "query_sql",
            "description": "Query an SQL database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_rag",
            "description": "Query a RAG (Retrieval-Augmented Generation) system",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_from_disk",
            "description": "Fetch data from a specified file on the disk",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_disk",
            "description": "Save data to a specified file on the disk",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "data": {"type": "string"}
                },
                "required": ["file_path", "data"]
            }
        }
    }
]

def handle_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    function_name = tool_call['function']['name']
    arguments = json.loads(tool_call['function']['arguments'])
    
    if function_name == "query_sql":
        result = query_sql(arguments['query'])
    elif function_name == "query_rag":
        result = query_rag(arguments['question'])
    elif function_name == "save_to_disk":
        result = save_to_disk(arguments['file_path'], arguments['data'])
    elif function_name == "fetch_from_disk":
        result = fetch_from_disk(arguments['file_path'])    
    else:
        raise ValueError(f"Unknown function: {function_name}")
    
    return {
        "tool_call_id": tool_call['id'],
        "function": {"name": function_name, "arguments": tool_call['function']['arguments']},
        "output": str(result)
    }

def chat_with_tools(query: str) -> str:
    system_prompt = """You are an AI assistant with access to specific tools to help you complete tasks. 
                        Here are the tools available to you:

                        1. query_sql: This tool queries an SQL database.
                        - Input: A SQL query string
                        - Output: The result of the SQL query

                        2. query_rag: This tool queries a Retrieval-Augmented Generation system.
                        - Input: A question string
                        - Output: The RAG-generated response

                        When you need to use a tool, format your response like this:
                        {
                        "tool": "tool_name",
                        "input": {
                            "a": number,
                            "b": number
                        }
                        }

                        After using a tool, I will provide you with the result. You can then use this result in your response or use another tool if needed.

                        Remember:
                        - Only use tools when necessary for data retrieval.
                        - Provide clear explanations along with your tool usage.
                        - Be concise and precise in your responses.
                        - Use the tools in a logical order to achieve the desired outcome.
                        - If you need help or have any questions, feel free to ask me."""

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': query}
    ]
    
    try:
        while True:
            response = ollama.chat(
                model=config.OLLAMA_GROQ_TOOL_MODEL,
                messages=messages
            )

            assistant_message = response.choices[0].message

            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    tool_response = handle_tool_call(tool_call.dict())
                    messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call.dict()]})
                    messages.append({"role": "tool", "content": json.dumps(tool_response), "tool_call_id": tool_call.id})
            else:
                return assistant_message.content

    except Exception as e:
        app_logger.error(f"Error during conversation with Ollama: {e}.")
        return None

    finally:
        # Ensure model gets unloaded after the conversation is complete or in case of errors
        unload_ollama_model(config.OLLAMA_GROQ_TOOL_MODEL)
        app_logger.debug("Unloaded the Ollama model.")
