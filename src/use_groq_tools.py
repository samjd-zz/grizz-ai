import json
import ollama

from logger import app_logger
from typing import Dict, Any
from utils import unload_ollama_model
from config import load_config

config = load_config()

# Define your tools
def multiply(a: float, b: float) -> float:
    return a * b

def add(a: float, b: float) -> float:
    return a + b

import psycopg2

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

tools = [
    {
        "type": "function",
        "function": {
            "name": "multiply",
            "description": "Multiply two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }
    },
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
    }
]

def handle_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    function_name = tool_call['function']['name']
    arguments = json.loads(tool_call['function']['arguments'])
    
    if function_name == "multiply":
        result = multiply(arguments['a'], arguments['b'])
    elif function_name == "add":
        result = add(arguments['a'], arguments['b'])
    elif function_name == "query_sql":
        result = query_sql(arguments['query'])
    elif function_name == "query_rag":
        result = query_rag(arguments['question'])
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

                        1. multiply: This tool multiplies two numbers.
                        - Input: Two numbers (a and b)
                        - Output: The product of a and b

                        2. add: This tool adds two numbers.
                        - Input: Two numbers (a and b)
                        - Output: The sum of a and b

                        3. query_sql: This tool queries an SQL database.
                        - Input: A SQL query string
                        - Output: The result of the SQL query

                        4. query_rag: This tool queries a Retrieval-Augmented Generation system.
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
                        - Only use tools when necessary for calculations or data retrieval.
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
