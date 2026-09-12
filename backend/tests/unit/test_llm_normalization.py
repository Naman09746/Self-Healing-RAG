import pytest
from backend.agents.generation.llm_client import _normalize_model_name, LLMClient
from backend.core.config import settings


def test_groq_model_normalization():
    # Direct groq provider
    assert _normalize_model_name("llama3.2:1b", provider="groq") == "llama-3.3-70b-versatile"
    assert _normalize_model_name("llama3.3:70b", provider="groq") == "llama-3.3-70b-versatile"
    assert _normalize_model_name("llama-3.1-8b", provider="groq") == "llama-3.3-70b-versatile"
    assert _normalize_model_name("mistral:7b", provider="groq") == "gemma2-9b-it"
    assert _normalize_model_name("gemma2:9b", provider="groq") == "gemma2-9b-it"

    # Groq API key auto-detection
    assert _normalize_model_name("llama3.2:1b", api_key="gsk_test123") == "llama-3.3-70b-versatile"

    # Groq base_url auto-detection
    assert _normalize_model_name("llama3.2:1b", base_url="https://api.groq.com/openai/v1") == "llama-3.3-70b-versatile"


def test_openai_model_normalization():
    # OpenAI provider mapping local Ollama tags to OpenAI models
    assert _normalize_model_name("llama3.2:1b", provider="openai", api_key="sk-test") == "gpt-4o-mini"
    assert _normalize_model_name("llama3.3:70b", provider="openai", api_key="sk-test") == "gpt-4o"
    assert _normalize_model_name("gpt-4o-mini", provider="openai", api_key="sk-test") == "gpt-4o-mini"
    assert _normalize_model_name("gpt-4o", provider="openai", api_key="sk-test") == "gpt-4o"


def test_openrouter_model_normalization():
    assert _normalize_model_name("llama3.2:1b", provider="openrouter") == "openrouter/free"
    assert _normalize_model_name("llama3.2:1b", api_key="sk-or-test123") == "openrouter/free"


def test_ollama_local_preservation():
    assert _normalize_model_name("llama3.2:1b", provider="ollama") == "llama3.2:1b"
    assert _normalize_model_name("mistral:7b", provider="ollama") == "mistral:7b"
