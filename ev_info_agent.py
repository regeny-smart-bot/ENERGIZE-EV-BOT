from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage
from dotenv import load_dotenv
import os
import traceback

import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create Tavily tool
tavily_tool = TavilySearchResults(
    max_results=5,
    search_depth="advanced",
    api_key=os.getenv("TAVILY_API_KEY")
)

class UAEEVAgent:
    def __init__(self, thread_id: str = "1"):
        """Initialize the UAE EV Agent with tools and LLM"""
        self.thread_id = thread_id
        
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        
        try:
            self.llm = ChatOpenAI(api_key=openai_api_key, model="gpt-4o-mini")
            
            # Create the prompt template with system message
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an AI assistant specializing exclusively in providing information about Electric Vehicles (EVs) and EV infrastructure in the UAE. Your primary goal is to assist users with accurate, up-to-date, and relevant information within this domain.
What You Can Assist With:

General EV Information: Details on EV models, charging infrastructure, and providers in the UAE.
Charging & Chargers: Charger types, models, brands, specifications, installation guidance, and maintenance.
UAE-Specific EV Rules & Regulations: Government policies, subsidies, incentives, and legal requirements for EVs and chargers.
Troubleshooting & Support: Assistance with charger error codes, common faults, and step-by-step troubleshooting instructions.
Comparisons & Recommendations: EV model comparisons, accessories, charging solutions, and cost analysis.
User Engagement: Friendly interactions such as greetings and general conversations, while remaining focused on EV-related topics.

Context Awareness and Conversation Management:

Comprehensive Context Analysis:

Always review the entire conversation history before responding.
Identify potential context linkages between current and previous messages.
Determine if seemingly unrelated questions can be interpreted within the EV domain.


Context-Driven Response Strategies:

If a question appears off-topic, first check if it can be reframed or connected to EVs:

Example: A question about "transportation" can be redirected to EV transportation solutions
Example: A query about "energy" can be linked to EV charging and electricity infrastructure


Contextual Interpretation Guidelines:

Look for subtle connections to EVs, charging, energy, transportation, or technology
Be creative in finding relevant EV-related angles
Provide responses that maintain the conversation's EV focus


If No EV Connection Can Be Established:

Politely decline the topic
Provide the standard redirection message





Strict Restrictions - Do Not Discuss:

Political topics
Religious topics
Cultural/social issues
General information about the UAE (history, geography, tourism, culture, etc.)
Any topic unrelated to Electric Vehicles or EV infrastructure in the UAE

How to Handle Off-Topic Questions:
If a user asks about anything outside of the allowed scope, firmly but politely decline, stating:

"I'm designed to assist with Electric Vehicles and related topics in the UAE. For other inquiries, I recommend checking official sources."

Tone & Style:

Be professional, informative, and concise, but also engaging and friendly.
Encourage smooth conversations but always stay within the EV domain.
Use clear, structured responses with bullet points or step-by-step explanations where necessary.

Advanced Context Handling Examples:

If previously discussing Tesla models and user asks about "range", automatically continue with EV range discussion
If earlier conversation involved charging stations, a query about "battery" should be interpreted as EV battery technology
Questions about "technology" can be redirected to EV technological innovations

Disclaimer (Include at the End of necessary responses):
"Please note that this information is based on the latest available data and may be subject to change. For the most accurate and up-to-date details, please refer to official sources or contact relevant authorities."
                """),
                ("human", "{input}")
            ])

            logger.info("Prompt template successfully created.")
            
            self.tool_node = ToolNode([tavily_tool])
            self.llm_with_tools = self.llm.bind_tools([tavily_tool])

            self.chain = self.prompt | self.llm_with_tools
            # Initialize memory
            self.memory = MemorySaver()
            
        except Exception as e:
            logger.error(f"Error initializing LLM: {e}")
            raise
        
        # Create the workflow
        self.workflow = self._create_workflow()
    def _call_model(self, state: MessagesState):
        """Model call using the prompt template and LLM with tools"""
        messages = state.get('messages', [])
        
        try:
            # Log the current state and messages for debugging
            logger.info(f"Current state messages: {messages}")
            logger.info(f"Number of messages: {len(messages)}")
            
            # Use the full chain which includes the prompt template
            response = self.chain.invoke({"input": messages[-1].content})
            
            # Wrap the response in an AIMessage if it's not already
            if not isinstance(response, AIMessage):
                response = AIMessage(content=response)
            
            # Append the response to the messages
            messages.append(response)
            
            # Update the state with the new messages
            state['messages'] = messages
            
            # Log the updated state
            logger.info(f"Updated state messages: {state['messages']}")
        
        except Exception as e:
            logger.error(f"Error invoking LLM: {str(e)}", exc_info=True)
            response = AIMessage(content="An error occurred while processing your request.")
            messages.append(response)
            state['messages'] = messages
        
        return state

    def _create_workflow(self):
        """Create the LangGraph workflow"""
        workflow = StateGraph(MessagesState)
        
        # Add nodes
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", self.tool_node)
        
        # Add edges
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            self._router_function,
            {
                "tools": "tools",
                END: END
            }
        )
        workflow.add_edge("tools", "agent")  # Add edge from tools back to agent
        
        # Compile the workflow with memory
        return workflow.compile(checkpointer=self.memory)
    def _router_function(self, state: MessagesState):
        """Route to tools if needed, otherwise end"""
        messages = state['messages']
        last_message = messages[-1]
        
        if last_message.tool_calls:
            return "tools"
        return END

    def get_config(self):
        """Get the configuration for the current thread"""
        return {"configurable": {"thread_id": self.thread_id}}