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


class LLMClient:
    """Production-grade async LLM client with retries, hard timeout, and OTel + LangSmith tracing."""

    def __init__(self, model: str = None):
        self.model = model or settings.MODEL_NAME
        self._timeout = 90  # Hard timeout in seconds

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def generate(self, prompt: str, format: str = None) -> str:
        """Generate with retry logic, hard timeout, and OTel + LangSmith tracing."""
        tracer = get_tracer()
        logger.info("LLM Request", model=self.model)

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
                kwargs: dict = {
                    "model": self.model,
                    "prompt": prompt,
                    "options": {
                        "num_predict": 512,
                        "temperature": 0.1,
                    },
                }
                if format:
                    kwargs["format"] = format

                async_client = ollama.AsyncClient()
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
        self, prompt: str, format: str = None
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM via Ollama's async streaming API.

        Each iteration yields a single decoded token.  The caller may cancel
        iteration to implement client-disconnect / backpressure semantics.

        Yields:
            Decoded text tokens as the model produces them.
        """
        logger.info("LLM Streaming request", model=self.model)
        try:
            kwargs: dict = {
                "model": self.model,
                "prompt": prompt,
                "options": {
                    "num_predict": 512,
                    "temperature": 0.1,
                },
            }
            if format:
                kwargs["format"] = format

            async_client = ollama.AsyncClient()
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
