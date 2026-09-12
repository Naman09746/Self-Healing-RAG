import ollama
import asyncio
import time
from typing import AsyncGenerator, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from opentelemetry import trace
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.observability import get_tracer, get_langsmith_client

logger = get_logger(__name__)


def _is_model_error(exc: Exception) -> bool:
    """Check if an exception is due to an unrecognized, deprecated, or decommissioned model."""
    err_str = str(exc).lower()
    return any(
        term in err_str
        for term in (
            "model_decommissioned",
            "model_not_found",
            "does not exist",
            "no longer supported",
            "deprecated",
            "not have access",
            "not_found",
            "404",
            "403",
            "only available on",
            "gated",
            "failed_routing_step",
            "no endpoints",
        )
    ) and "rate limit" not in err_str and "overloaded" not in err_str


def _normalize_model_name(model: str, base_url: str = "", api_key: str = "", provider: str = "") -> str:
    """Normalize local Ollama model names to provider-specific names if using OpenAI/Groq/OpenRouter."""
    base = (base_url or "").lower()
    prov = (provider or "").lower()
    key = api_key or ""

    is_groq = "groq.com" in base or key.startswith("gsk_") or prov in ("groq", "groqcloud")
    is_openrouter = "openrouter.ai" in base or key.startswith("sk-or-") or prov in ("openrouter", "openrouter_ai")
    is_openai = "openai.com" in base or prov == "openai" or (not is_groq and not is_openrouter and bool(key))

    if is_groq:
        groq_mapping = {
            "llama3.2:1b": "llama-3.3-70b-versatile",
            "llama3.2:3b": "llama-3.3-70b-versatile",
            "llama3.2": "llama-3.3-70b-versatile",
            "llama3.1:8b": "llama-3.3-70b-versatile",
            "llama3.1": "llama-3.3-70b-versatile",
            "llama3:8b": "llama-3.3-70b-versatile",
            "llama3": "llama-3.3-70b-versatile",
            "llama-3.1-8b": "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant": "llama-3.3-70b-versatile",
            "llama3:70b": "llama-3.3-70b-versatile",
            "llama3.3:70b": "llama-3.3-70b-versatile",
            "llama3.3": "llama-3.3-70b-versatile",
            "llama-3.3-70b": "llama-3.3-70b-versatile",
            "llama3-8b-8192": "llama-3.3-70b-versatile",
            "llama3-70b-8192": "llama-3.3-70b-versatile",
            "mistral": "gemma2-9b-it",
            "mistral:7b": "gemma2-9b-it",
            "mixtral-8x7b-32768": "gemma2-9b-it",
            "gemma2": "gemma2-9b-it",
            "gemma2:9b": "gemma2-9b-it",
        }
        if not model:
            return "llama-3.3-70b-versatile"
        if model in groq_mapping:
            return groq_mapping[model]
        if ":" in model:
            clean = model.replace(":", "-")
            return groq_mapping.get(clean, "llama-3.3-70b-versatile")
        return model or "llama-3.3-70b-versatile"

    elif is_openai:
        # If calling OpenAI direct, normalize Ollama tags or llama tags to gpt-4o-mini / gpt-4o
        if not model or any(tag in model.lower() for tag in ("llama", "nomic", "mistral", "gemma", "ollama", "qwen", ":")):
            if "70b" in (model or "").lower():
                return "gpt-4o"
            return "gpt-4o-mini"
        return model

    elif is_openrouter:
        if not model or ":" in model:
            return "nvidia/nemotron-3.5-lightning:free"
        return model

    return model or "llama3.2:1b"


class LLMClient:
    """Production-grade async LLM client with retries, hard timeout, and OTel + LangSmith tracing.
    
    Supports Ollama (default) as well as OpenAI-compatible providers (Groq, OpenRouter, OpenAI, vLLM).
    """

    def __init__(self, model: str = None, host: str = None):
        self.host = host or settings.OLLAMA_HOST
        self._timeout = getattr(settings, "LLM_TIMEOUT", 30)  # Configured timeout in seconds
        self.provider = getattr(settings, "LLM_PROVIDER", "ollama").lower()
        self._openai_client = None
        self._async_client = None

        raw_model = model or settings.MODEL_NAME
        api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        base_url = getattr(settings, "OPENAI_BASE_URL", "") or ""

        # Auto-configure base_url if provider or api_key indicates Groq or OpenRouter
        if not base_url:
            if self.provider in ("groq", "groqcloud") or api_key.startswith("gsk_"):
                base_url = "https://api.groq.com/openai/v1"
            elif self.provider in ("openrouter", "openrouter_ai") or api_key.startswith("sk-or-"):
                base_url = "https://openrouter.ai/api/v1"

        if self.provider in ("openai", "groq", "groqcloud", "openrouter") or bool(api_key):
            try:
                from openai import AsyncOpenAI
                default_headers = {}
                if is_openrouter or self.provider in ("openrouter", "openrouter_ai") or "openrouter.ai" in (base_url or ""):
                    default_headers = {
                        "HTTP-Referer": "https://self-healing-rag.onrender.com",
                        "X-Title": "Self-Healing RAG",
                    }
                self._openai_client = AsyncOpenAI(
                    api_key=api_key or "sk-dummy",
                    base_url=base_url or None,
                    default_headers=default_headers if default_headers else None,
                )
                self.model = _normalize_model_name(
                    raw_model,
                    base_url=base_url or "",
                    api_key=api_key,
                    provider=self.provider,
                )
                logger.info(
                    "Initialized AsyncOpenAI client",
                    provider=self.provider,
                    base_url=base_url or "https://api.openai.com/v1",
                    model=self.model,
                )
            except Exception as e:
                logger.warning("Could not initialize AsyncOpenAI, falling back to Ollama", error=str(e))
                self.model = raw_model
                self._async_client = ollama.AsyncClient(host=self.host)
        else:
            self.model = raw_model
            self._async_client = ollama.AsyncClient(host=self.host)

    async def _execute_openai_chat(self, kwargs: dict) -> str:
        """Execute chat completion with automatic model fallback on any model error."""
        models_to_try = [kwargs["model"]]
        
        if self.provider == "openai":
            candidates = ["gpt-4o-mini", "gpt-4o"]
        elif self.provider == "openrouter":
            candidates = [
                "nvidia/nemotron-3.5-lightning:free",
                "inclusionai/ling-3.0-flash-vl:free",
                "nex-agi/nex-n2.5-pro:free",
                "nex-agi/nex-n2.5-mini:free",
                "liquid/lfm-2.5-2.6b:free",
                "openrouter/free",
            ]
        else:
            candidates = ["llama-3.3-70b-versatile", "gemma2-9b-it", "llama-3.1-8b-instant"]

        for c in candidates:
            if c not in models_to_try:
                models_to_try.append(c)

        last_exc = None
        for m in models_to_try:
            try:
                attempt_kwargs = dict(kwargs)
                attempt_kwargs["model"] = m
                response = await asyncio.wait_for(
                    self._openai_client.chat.completions.create(**attempt_kwargs),
                    timeout=self._timeout,
                )
                if m != self.model:
                    logger.info("Successfully recovered with fallback model", previous=self.model, fallback=m)
                    self.model = m
                return response.choices[0].message.content or ""
            except Exception as e:
                if _is_model_error(e):
                    logger.warning("Model error on provider, attempting fallback candidate", model=m, error=str(e))
                    last_exc = e
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("No model candidates succeeded")

    async def _execute_openai_stream(self, kwargs: dict) -> AsyncGenerator[str, None]:
        """Execute chat stream with automatic model fallback on any model error."""
        models_to_try = [kwargs["model"]]
        
        if self.provider == "openai":
            candidates = ["gpt-4o-mini", "gpt-4o"]
        elif self.provider == "openrouter":
            candidates = [
                "nvidia/nemotron-3.5-lightning:free",
                "inclusionai/ling-3.0-flash-vl:free",
                "nex-agi/nex-n2.5-pro:free",
                "nex-agi/nex-n2.5-mini:free",
                "liquid/lfm-2.5-2.6b:free",
                "openrouter/free",
            ]
        else:
            candidates = ["llama-3.3-70b-versatile", "gemma2-9b-it", "llama-3.1-8b-instant"]

        for c in candidates:
            if c not in models_to_try:
                models_to_try.append(c)

        last_exc = None
        stream_resp = None
        for m in models_to_try:
            try:
                attempt_kwargs = dict(kwargs)
                attempt_kwargs["model"] = m
                stream_resp = await self._openai_client.chat.completions.create(**attempt_kwargs)
                if m != self.model:
                    logger.info("Successfully started stream with fallback model", previous=self.model, fallback=m)
                    self.model = m
                break
            except Exception as e:
                if _is_model_error(e):
                    logger.warning("Model error for stream, trying fallback candidate", model=m, error=str(e))
                    last_exc = e
                    continue
                raise

        if stream_resp is None:
            if last_exc:
                raise last_exc
            raise RuntimeError("No model candidates succeeded for streaming")

        async for chunk in stream_resp:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def generate(self, prompt: str, format: str = None, max_tokens: int = None) -> str:
        """Generate with retry logic, hard timeout, and OTel + LangSmith tracing."""
        tracer = get_tracer()
        logger.info("LLM Request", model=self.model)

        token_limit = max_tokens or (512 if format == "json" else 1536)

        # LangSmith run tracking
        ls_client = get_langsmith_client()
        ls_run = None
        if ls_client:
            ls_run = ls_client.create_run(
                name="llm.generate",
                run_type="llm",
                inputs={"prompt": prompt[:500], "model": self.model, "format": format},
            )

        with tracer.start_as_current_span("llm.generate") as span:
            span.set_attribute("model", self.model)
            span.set_attribute("prompt_length", len(prompt))
            span.set_attribute("format", format or "text")
            start_time = time.time()

            try:
                if self._openai_client is not None:
                    kwargs: dict = {
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": token_limit,
                    }
                    if format == "json":
                        kwargs["response_format"] = {"type": "json_object"}
                    result = await self._execute_openai_chat(kwargs)
                else:
                    kwargs: dict = {
                        "model": self.model,
                        "prompt": prompt,
                        "keep_alive": "10m",
                        "options": {
                            "num_predict": token_limit,
                            "temperature": 0.1,
                        },
                    }
                    if format:
                        kwargs["format"] = format

                    async_client = self._async_client
                    response = await asyncio.wait_for(
                        async_client.generate(**kwargs),
                        timeout=self._timeout,
                    )
                    result = response["response"]
                duration_ms = (time.time() - start_time) * 1000

                span.set_attribute("response_length", len(result))
                span.set_attribute("duration_ms", duration_ms)
                span.set_status(trace.Status(trace.StatusCode.OK))

                # Finalize LangSmith run
                if ls_run:
                    ls_run.end(
                        outputs={"response": result[:500]},
                        extra={"duration_ms": duration_ms},
                    )

                return result
            except asyncio.TimeoutError:
                span.set_status(trace.Status(trace.StatusCode.ERROR, "timeout"))
                span.set_attribute("duration_ms", (time.time() - start_time) * 1000)
                if ls_run:
                    ls_run.end(error=f"Timeout after {self._timeout}s")
                logger.error("LLM Request timed out", model=self.model)
                raise RuntimeError(f"LLM generation timed out after {self._timeout}s")
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                if ls_run:
                    ls_run.end(error=str(e))
                logger.error("LLM Request failed", error=str(e))
                raise

    async def generate_stream(
        self, prompt: str, format: str = None, max_tokens: int = None
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM via Ollama or OpenAI-compatible async streaming API.

        Each iteration yields a single decoded token. The caller may cancel
        iteration to implement client-disconnect / backpressure semantics.

        Yields:
            Decoded text tokens as the model produces them.
        """
        logger.info("LLM Streaming request", model=self.model)
        token_limit = max_tokens or (512 if format == "json" else 1536)
        try:
            if self._openai_client is not None:
                kwargs: dict = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": token_limit,
                    "stream": True,
                }
                if format == "json":
                    kwargs["response_format"] = {"type": "json_object"}
                async for token in self._execute_openai_stream(kwargs):
                    yield token
            else:
                kwargs: dict = {
                    "model": self.model,
                    "prompt": prompt,
                    "keep_alive": "10m",
                    "options": {
                        "num_predict": 512,
                        "temperature": 0.1,
                    },
                }
                if format:
                    kwargs["format"] = format

                async_client = self._async_client
                async for chunk in await async_client.generate(**kwargs, stream=True):
                    token: str = chunk.get("response", "") or ""
                    if token:
                        yield token
        except asyncio.CancelledError:
            logger.warning("LLM stream cancelled", model=self.model)
            raise
        except Exception as e:
            logger.error("LLM stream failed", error=str(e))
            raise

    def generate_sync(self, prompt: str, format: str = None) -> str:
        """Synchronous fallback — wraps async in a new event loop.
        Use only when calling from a non-async context (tests, CLI)."""
        return asyncio.run(self.generate(prompt, format))
