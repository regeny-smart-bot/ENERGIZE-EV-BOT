from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ev_info_agent import UAEEVAgent
from langchain_core.messages import HumanMessage, AIMessage
import json
import logging
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections and their agents
active_connections = {}

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("New WebSocket connection request")
    await websocket.accept()
    client_id = id(websocket)
    active_connections[client_id] = {
        "websocket": websocket,
        "agent": UAEEVAgent(thread_id=str(client_id)),
        "state": {"messages": []}
    }
    logger.info(f"WebSocket connection accepted for client {client_id}")
    
    # Send welcome message
    welcome_message = {
        "type": "response",
        "content": "Welcome to Regeny's EV Information Assistant! I can help you with information about electric vehicles in the UAE, including available models, charging infrastructure, incentives, and more. What would you like to know about EVs in the UAE?",
        "streaming": False
    }
    await websocket.send_json(welcome_message)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            logger.info(f"Received message from client {client_id}: {data}")
            query = json.loads(data)["message"]
            
            # Add the new query to the current state
            current_state = active_connections[client_id]["state"]
            current_state["messages"].append(HumanMessage(content=query))
            
            # Process the message through the agent
            agent = active_connections[client_id]["agent"]
            logger.info(f"Processing message through agent for client {client_id}")
            
            try:
                # THIS IS THE NEW/MODIFIED PART
                # Accumulate the entire response
                accumulated_response = ""
                
                # Process the agent's response using the workflow.astream method
                async for output in agent.workflow.astream(current_state, config=agent.get_config()):
                    state = output.get('agent', {})
                    messages = state.get('messages', [])
                    
                    if messages:
                        latest_message = messages[-1]
                        if isinstance(latest_message, AIMessage) and latest_message.content:
                            # Skip tool use messages and empty responses
                            if not latest_message.content.startswith("<tool-use>") and latest_message.content.strip():
                                current_content = latest_message.content
                                
                                # Stream only the new content
                                if len(current_content) > len(accumulated_response):
                                    stream_chunk = current_content[len(accumulated_response):]
                                    response = {
                                        "type": "response",
                                        "content": current_content,
                                        "streaming": True
                                    }
                                    await websocket.send_json(response)
                                    accumulated_response = current_content
                
                # Send final complete message
                if accumulated_response:
                    final_response = {
                        "type": "response",
                        "content": accumulated_response,
                        "streaming": False
                    }
                    await websocket.send_json(final_response)
                
                # Update the state
                if messages:
                    active_connections[client_id]["state"] = {"messages": messages}
                    
            except Exception as e:
                logger.error(f"Error processing agent response: {str(e)}", exc_info=True)
                error_response = {
                    "type": "response",
                    "content": "I encountered an error while processing your request. Please try again.",
                    "streaming": False
                }
                await websocket.send_json(error_response)
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        # Clean up when client disconnects
        if client_id in active_connections:
            del active_connections[client_id]
    except Exception as e:
        logger.error(f"Error for client {client_id}: {str(e)}", exc_info=True)
        if client_id in active_connections:
            del active_connections[client_id]

@app.get("/")
async def root():
    return {"message": "Regeny EV Information Assistant API is running. Connect via WebSocket at /ws/chat"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)