from typing import TypedDict, List, Dict, Optional, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.config import settings
from app.services.rag_service import rag_service
from app.services.langfuse_service import langfuse_service


logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    """State for the conversation agent."""
    messages: List[Dict]
    contact_id: str
    conversation_id: str
    user_input: str
    intent: Optional[str]
    response: Optional[str]
    should_handoff: bool
    context: Dict


class ConversationAgent:
    """LangGraph-based conversational agent for WhatsApp."""

    def __init__(self):
        # Initialize LLM with OpenRouter
        self.llm = ChatOpenAI(
            model=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=0.7
        )

        # Build the graph
        self.graph = self._build_graph()
        logger.info("Conversation agent initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(ConversationState)

        # Add nodes
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("search_knowledge", self.search_knowledge)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("check_handoff", self.check_handoff)

        # Define edges
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "search_knowledge")
        workflow.add_edge("search_knowledge", "generate_response")
        workflow.add_edge("generate_response", "check_handoff")
        workflow.add_conditional_edges(
            "check_handoff",
            self.should_route_to_human,
            {
                "end": END,
                "handoff": END
            }
        )

        return workflow.compile()

    async def classify_intent(self, state: ConversationState) -> ConversationState:
        """Classify the user's intent."""
        try:
            user_input = state["user_input"]

            # Simple intent classification using LLM
            prompt = f"""Classify the intent of this message into one of these categories:
            - question: User is asking for information
            - purchase: User wants to buy something
            - support: User needs help with an existing order
            - greeting: Just saying hello
            - other: Doesn't fit other categories

            Message: "{user_input}"

            Respond with only the category name."""

            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            intent = response.content.strip().lower()

            logger.info(f"Classified intent: {intent}")
            state["intent"] = intent
            return state

        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            state["intent"] = "other"
            return state

    async def search_knowledge(
        self,
        state: ConversationState,
        session: Optional[AsyncSession] = None
    ) -> ConversationState:
        """Search knowledge base for relevant information."""
        try:
            # Only search if it's a question or needs more info
            if state["intent"] not in ["question", "purchase"]:
                state["context"]["knowledge_results"] = []
                return state

            if session:
                knowledge_items = await rag_service.search_knowledge_base(
                    query=state["user_input"],
                    session=session
                )
                state["context"]["knowledge_results"] = knowledge_items
                logger.info(f"Found {len(knowledge_items)} knowledge items")
            else:
                state["context"]["knowledge_results"] = []

            return state

        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            state["context"]["knowledge_results"] = []
            return state

    async def generate_response(self, state: ConversationState) -> ConversationState:
        """Generate the response to the user."""
        try:
            # Build system prompt
            system_prompt = self._get_system_prompt()

            # Build context
            context_parts = [system_prompt]

            # Add knowledge base results if available
            if state["context"].get("knowledge_results"):
                knowledge_context = await rag_service.format_context(
                    state["context"]["knowledge_results"]
                )
                if knowledge_context:
                    context_parts.append(f"Contexto da base de conhecimento:\n{knowledge_context}")

            # Add conversation context
            if state.get("messages"):
                conversation_history = "\n".join([
                    f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content')}"
                    for m in state["messages"][-5:]  # Last 5 messages
                ])
                context_parts.append(f"Histórico recente:\n{conversation_history}")

            # Create messages
            messages = [
                SystemMessage(content="\n\n".join(context_parts)),
                HumanMessage(content=state["user_input"])
            ]

            # Generate response
            response = await self.llm.ainvoke(messages)
            state["response"] = response.content

            logger.info(f"Generated response: {state["response"][:100]}...")
            return state

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            state["response"] = "Desculpe, tive um problema ao processar sua mensagem. Pode repetir?"
            return state

    async def check_handoff(self, state: ConversationState) -> ConversationState:
        """Check if the conversation should be handed off to a human."""
        # Determine if human handoff is needed
        # This can be based on:
        # - User explicitly asking for a human
        # - Agent failing multiple times
        # - Complex issues that require human intervention

        user_input_lower = state["user_input"].lower()
        handoff_keywords = ["humano", "atendente", "pessoa", "falar com alguém"]

        state["should_handoff"] = any(
            keyword in user_input_lower for keyword in handoff_keywords
        )

        if state["should_handoff"]:
            logger.info("Conversation marked for human handoff")
            state["response"] = "Vou transferir você para um atendente humano. Um momento, por favor."

        return state

    def should_route_to_human(self, state: ConversationState) -> Literal["end", "handoff"]:
        """Determine routing based on handoff status."""
        return "handoff" if state["should_handoff"] else "end"

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """Você é um assistente de vendas e atendimento ao cliente para uma empresa que vende produtos/serviços via WhatsApp.

Seu objetivo é:
1. Atender amigavelmente e profissionalmente
2. Entender o que o cliente precisa
3. Oferecer produtos/serviços adequados
4. Facilitar o pagamento via Pix
5. Fazer follow-up quando necessário

Regras:
- Seja sempre cordial e profissional
- Use emojis moderadamente para tornar a conversa mais amigável
- Não invente informações que você não tem
- Se não souber algo, diga que vai verificar e retorne em breve
- Quando o cliente quiser comprar, guie-o para o pagamento via Pix
- Responda de forma concisa e direta
- Evite blocos de texto muito longos"""

    async def process_message(
        self,
        user_input: str,
        contact_id: str,
        conversation_id: str,
        conversation_history: List[Dict],
        session: Optional[AsyncSession] = None
    ) -> Dict:
        """
        Process a message through the agent.

        Args:
            user_input: User's message
            contact_id: Contact ID
            conversation_id: Conversation ID
            conversation_history: Previous messages
            session: Optional database session for RAG

        Returns:
            Response dict with response, intent, should_handoff
        """
        try:
            # Create trace for observability
            trace = langfuse_service.create_trace(
                name="conversation",
                session_id=conversation_id,
                user_id=contact_id
            )

            # Initialize state
            initial_state: ConversationState = {
                "messages": conversation_history,
                "contact_id": contact_id,
                "conversation_id": conversation_id,
                "user_input": user_input,
                "intent": None,
                "response": None,
                "should_handoff": False,
                "context": {"knowledge_results": []}
            }

            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)

            result = {
                "response": final_state.get("response", ""),
                "intent": final_state.get("intent", "unknown"),
                "should_handoff": final_state.get("should_handoff", False)
            }

            # Log to Langfuse
            if trace:
                langfuse_service.log_generation(
                    trace=trace,
                    model=settings.openrouter_model,
                    prompt=user_input,
                    completion=result["response"],
                    latency_ms=0,
                    metadata={"intent": result["intent"]}
                )

            return result

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "response": "Desculpe, tive um problema. Pode repetir?",
                "intent": "error",
                "should_handoff": False
            }


# Singleton instance
conversation_agent = ConversationAgent()
