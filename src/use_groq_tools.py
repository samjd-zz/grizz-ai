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
    }
]

def handle_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    function_name = tool_call['function']['name']
    arguments = json.loads(tool_call['function']['arguments'])
    
    if function_name == "multiply":
        result = multiply(arguments['a'], arguments['b'])
    elif function_name == "add":
        result = add(arguments['a'], arguments['b'])
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
                        - Only use tools when necessary for calculations.
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
        app_logger.info("Unloaded the Ollama model.")
