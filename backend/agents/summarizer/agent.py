from typing import List, Dict, Any
from backend.core.logging import get_logger
from backend.agents.generation.llm_client import LLMClient

logger = get_logger(__name__)

class SummarizerAgent:
    def __init__(self, model: str = None):
        self.client = LLMClient(model=model)

    def summarize_context(self, context: List[str], max_words: int = 500) -> str:
        """Compress multiple context chunks into a coherent summary."""
        combined_text = "\n\n".join(context)
        prompt = f"""
        Compress the following information into a concise summary of no more than {max_words} words. 
        Retain all key technical details, names, and metrics.
        
        TEXT:
        {combined_text}
        
        SUMMARY:
        """
        
        return self.client.generate(prompt)

    def summarize_history(self, history: List[Dict[str, str]]) -> str:
        """Summarize a conversation history."""
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        prompt = f"""
        Summarize the following conversation history into a single paragraph that captures the user's intent and the key information provided so far.
        
        HISTORY:
        {history_text}
        
        SUMMARY:
        """
        
        return self.client.generate(prompt)
