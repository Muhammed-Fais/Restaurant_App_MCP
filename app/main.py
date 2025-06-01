import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager # Added for lifespan
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama

# Pydantic models for API request/response
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

# Load your local Ollama model
model = ChatOllama(model="llama3.2")

# Initialize FastAPI app first
app = FastAPI() # Initialize app here

@asynccontextmanager
async def lifespan(app_param: FastAPI): # Pass app if needed, or use global app
    print("Lifespan: Initializing MCP Agent...")
    server_params = StdioServerParameters(
        command="python", # Ensure this command can find python in your PATH
        args=["app/restaurant_server.py"], # Updated path
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            agent = create_react_agent(
                model,
                tools,
                prompt="""You are an automated assistant for our restaurant. Your ONLY function is to help users with our menu and to place food orders. Do not answer any questions or engage in any conversation that is not directly related to this restaurant's menu, food items, or the ordering process.

If a user asks a question outside of these topics, you MUST politely decline and guide them back to ordering. For example, if a user asks 'Do you know about AI?', you should respond with: 'I am an assistant for this restaurant and can only help with menu items and food orders. How can I help you with our menu today?'

IMPORTANT MENU AND ORDERING RULES:
1. ALL information about menu items, categories, and prices MUST come from using your tools (like 'browse_menu'). Do NOT invent or assume items, prices, or categories.
2. When a user asks to see the menu (e.g., "show me your menu", "what do you have?"):
    a. FIRST, call the 'browse_menu' tool WITHOUT any category. This tool will return a list of available food categories.
    b. SECOND, present this list of categories to the user AND explicitly ask them to name ONE category they wish to see items from (e.g., "We have Main, Salads, Desserts. Which single category are you interested in?").
    c. THIRD, once the user clearly states a single category name (e.g., "Main", "Desserts"), your NEXT action MUST be to call 'browse_menu' again, this time providing that exact category name as input to the tool.
    d. FOURTH, after calling 'browse_menu' with the specific category, the tool will return the items in that category. You MUST then present these items (including their names, prices, and item_ids) to the user.
3. When placing or modifying an order, you MUST use the exact 'item_id' (e.g., "1", "5", "12") that is provided by the 'browse_menu' tool for each item. Do not use item names or made-up IDs.

Feel free to ask about our menu, specials, or place an order. To use a tool for specific actions, I might respond with a JSON like:
```json
{
  "tool_name": "browse_menu",
  "tool_input": {"category": "Main"} 
}
```
I'm ready to take your order!"""
            )
            app.state.mcp_agent = agent # Use the global app instance
            print("🧠 MCP Restaurant Agent initialized and ready.")
            yield # Application runs here
    print("Lifespan: MCP Agent shutdown.")

# Assign lifespan to the app
app.router.lifespan_context = lifespan

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static") # Updated path

@app.get("/", response_class=HTMLResponse)
async def get_chat_ui(): # Reverted function name
    try: # Reverted try-except block
        with open("static/index.html", "r", encoding="utf-8") as f: # Updated path, added encoding
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: index.html not found</h1><p>Make sure index.html is in the static directory.</p>", status_code=500) # Updated error message

@app.post("/chat", response_model=list[ChatMessage])
async def chat_endpoint(request: ChatRequest):
    if not hasattr(app.state, 'mcp_agent') or app.state.mcp_agent is None:
        return [ChatMessage(role="assistant", content="Agent not initialized yet or initialization failed. Please check server logs.")]

    # Convert Pydantic models to dicts for the agent
    conversation_history = [msg.dict() for msg in request.messages]
    print(f"\n--- Sending to Agent (conversation_history) ---") # Log 1
    for msg in conversation_history:
        print(f"{msg['role']}: {msg['content']}")
    print("--------------------------------------------------")

    try:
        response = await app.state.mcp_agent.ainvoke({"messages": conversation_history})
        
        print(f"\n--- Raw Agent Response (type: {type(response)}) ---") # Log 2
        if isinstance(response, dict) and "messages" in response:
            for i, msg_obj in enumerate(response["messages"]):
                print(f"Message {i} in response:")
                print(f"  Type: {type(msg_obj)}")
                print(f"  Role: {getattr(msg_obj, 'role', 'N/A')}")
                print(f"  Content: {repr(getattr(msg_obj, 'content', 'N/A'))}") 
                if hasattr(msg_obj, 'tool_calls') and msg_obj.tool_calls:
                    print(f"  Tool Calls: {msg_obj.tool_calls}")
                if hasattr(msg_obj, 'additional_kwargs') and msg_obj.additional_kwargs.get('tool_calls'):
                    print(f"  Tool Calls (from kwargs): {msg_obj.additional_kwargs['tool_calls']}")
        else:
            print(response) 
        print("--------------------------------------------------")

        response_messages = []
        num_history_messages = len(conversation_history)
        newly_added_messages_from_agent = response.get("messages", [])[num_history_messages:]
        
        if newly_added_messages_from_agent:
            for msg_obj in newly_added_messages_from_agent:
                role_to_send = 'assistant' 
                if hasattr(msg_obj, 'role'):
                    role_to_send = msg_obj.role
                if hasattr(msg_obj, 'type'): 
                    if msg_obj.type == 'ai': role_to_send = 'assistant'
                    elif msg_obj.type == 'tool': role_to_send = 'tool'
                
                content_to_send = str(getattr(msg_obj, 'content', ''))
                
                if role_to_send == 'assistant' or role_to_send == 'tool': 
                    if content_to_send or (role_to_send == 'tool' and not content_to_send and hasattr(msg_obj, 'tool_calls')):
                        response_messages.append(ChatMessage(role=role_to_send, content=content_to_send))
        
        if not response_messages and response.get("messages"):
            if len(response["messages"]) > num_history_messages:
                 last_msg_obj = response["messages"][-1]
                 role_to_send = getattr(last_msg_obj, 'role', 'assistant')
                 if hasattr(last_msg_obj, 'type') and getattr(last_msg_obj, 'type') == 'ai': role_to_send = 'assistant'
                 content_to_send = str(getattr(last_msg_obj, 'content', ''))
                 if content_to_send:
                     response_messages.append(ChatMessage(role=role_to_send, content=content_to_send))

        return response_messages
    except Exception as e:
        print(f"❌ Error during agent invocation: {e}")
        import traceback
        traceback.print_exc() 
        return [ChatMessage(role="assistant", content=f"Error: {e}")]

# To run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)