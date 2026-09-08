from typing import List, Dict, Any
from backend.core.logging import get_logger
from backend.agents.generation.llm_client import LLMClient
from backend.core.config import settings
import json

logger = get_logger(__name__)

class PlannerAgent:
    def __init__(self, model: str = None):
        self.model = model or settings.SMALL_MODEL_NAME
        self.client = LLMClient(model=self.model)

    async def create_plan(self, query: str) -> Dict[str, Any]:
        """Analyze the query and create an execution plan."""
        prompt = f"""
        You are an expert AI Query Planner. Analyze the user's query and decide the best retrieval strategy.
        
        QUERY: {query}
        
        Respond ONLY with a JSON object in this format:
        {{
            "is_complex": boolean,
            "strategy": "VECTOR" | "GRAPH" | "HYBRID",
            "reasoning": "string",
            "sub_queries": ["string", "string"],
            "expected_entities": ["string"]
        }}
        """
        
        try:
            response = await self.client.generate(prompt, format="json")
            # Simple JSON extraction
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
            return json.loads(response)
        except Exception as e:
            logger.error(f"Failed to parse planner response: {str(e)}")
            return {
                "is_complex": False,
                "strategy": "HYBRID",
                "reasoning": "Fallback due to parsing error",
                "sub_queries": [query],
                "expected_entities": []
            }
