"""LangFuse tracing integration for Claude Agent SDK."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Generator

from langfuse import Langfuse
from langfuse.decorators import langfuse_context

from src.config import LangfuseSettings

logger = logging.getLogger(__name__)

# Context variable to store current trace
_current_trace_id: ContextVar[str | None] = ContextVar("langfuse_trace_id", default=None)


class LangfuseTracer:
    """LangFuse tracer for Agent SDK integration."""

    def __init__(self, settings: LangfuseSettings):
        self.settings = settings
        self._client: Langfuse | None = None

        if settings.enabled:
            try:
                self._client = Langfuse(
                    public_key=settings.get_public_key(),
                    secret_key=settings.get_secret_key(),
                    host=settings.get_host(),
                )
                logger.info("LangFuse tracing initialized: %s", settings.get_host())
            except Exception as exc:
                logger.error("Failed to initialize LangFuse: %s", exc)
                self._client = None
        else:
            logger.info("LangFuse tracing disabled")

    @property
    def enabled(self) -> bool:
        """Check if tracing is enabled and client is available."""
        return self._client is not None

    @contextmanager
    def trace_agent_execution(
        self,
        *,
        session_id: str | None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[str | None, None, None]:
        """
        Create a trace for agent execution.

        Args:
            session_id: Session identifier
            user_id: User identifier (optional)
            metadata: Additional metadata to attach to trace

        Yields:
            trace_id if tracing is enabled, None otherwise
        """
        if not self.enabled:
            yield None
            return

        try:
            trace = self._client.trace(
                name="agent_execution",
                session_id=session_id,
                user_id=user_id,
                metadata=metadata or {},
            )
            trace_id = trace.id
            _current_trace_id.set(trace_id)
            logger.debug("Started trace: %s (session: %s)", trace_id, session_id)

            yield trace_id

        except Exception as exc:
            logger.error("Failed to create trace: %s", exc)
            yield None
        finally:
            _current_trace_id.set(None)
            if self.enabled:
                try:
                    self._client.flush()
                except Exception as exc:
                    logger.error("Failed to flush LangFuse: %s", exc)

    def log_agent_generation(
        self,
        *,
        name: str,
        prompt: str | list[dict[str, Any]],
        model: str,
        start_time: datetime,
        end_time: datetime,
        completion: str | None = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, int] | None = None,
        level: str = "DEFAULT",
    ) -> None:
        """
        Log an agent generation event.

        Args:
            name: Name of the generation (e.g., "agent_query", "tool_call")
            prompt: Input prompt (string or messages)
            model: Model name
            start_time: Start timestamp
            end_time: End timestamp
            completion: Generated completion text
            metadata: Additional metadata
            usage: Token usage dict with input/output/total tokens
            level: Log level (DEFAULT, DEBUG, WARNING, ERROR)
        """
        if not self.enabled:
            return

        trace_id = _current_trace_id.get()
        if not trace_id:
            logger.debug("No active trace, skipping generation log")
            return

        try:
            # Format prompt for LangFuse
            if isinstance(prompt, str):
                prompt_data = prompt
            else:
                # Convert message list to LangFuse format
                prompt_data = prompt

            self._client.generation(
                trace_id=trace_id,
                name=name,
                model=model,
                start_time=start_time,
                end_time=end_time,
                input=prompt_data,
                output=completion,
                metadata=metadata or {},
                usage=usage,
                level=level,
            )
            logger.debug("Logged generation: %s", name)
        except Exception as exc:
            logger.error("Failed to log generation: %s", exc)

    def log_agent_span(
        self,
        *,
        name: str,
        start_time: datetime,
        end_time: datetime,
        input_data: Any = None,
        output_data: Any = None,
        metadata: dict[str, Any] | None = None,
        level: str = "DEFAULT",
    ) -> None:
        """
        Log a span (intermediate step) in agent execution.

        Args:
            name: Span name
            start_time: Start timestamp
            end_time: End timestamp
            input_data: Input data
            output_data: Output data
            metadata: Additional metadata
            level: Log level
        """
        if not self.enabled:
            return

        trace_id = _current_trace_id.get()
        if not trace_id:
            logger.debug("No active trace, skipping span log")
            return

        try:
            self._client.span(
                trace_id=trace_id,
                name=name,
                start_time=start_time,
                end_time=end_time,
                input=input_data,
                output=output_data,
                metadata=metadata or {},
                level=level,
            )
            logger.debug("Logged span: %s", name)
        except Exception as exc:
            logger.error("Failed to log span: %s", exc)

    def log_event(
        self,
        *,
        name: str,
        metadata: dict[str, Any] | None = None,
        input_data: Any = None,
        output_data: Any = None,
        level: str = "DEFAULT",
    ) -> None:
        """
        Log a discrete event.

        Args:
            name: Event name
            metadata: Event metadata
            input_data: Input data
            output_data: Output data
            level: Log level
        """
        if not self.enabled:
            return

        trace_id = _current_trace_id.get()
        if not trace_id:
            logger.debug("No active trace, skipping event log")
            return

        try:
            self._client.event(
                trace_id=trace_id,
                name=name,
                metadata=metadata or {},
                input=input_data,
                output=output_data,
                level=level,
            )
            logger.debug("Logged event: %s", name)
        except Exception as exc:
            logger.error("Failed to log event: %s", exc)

    def update_trace(
        self,
        *,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        Update current trace with final data.

        Args:
            output: Final output
            metadata: Additional metadata
            tags: Tags to attach
        """
        if not self.enabled:
            return

        trace_id = _current_trace_id.get()
        if not trace_id:
            return

        try:
            update_data = {}
            if output is not None:
                update_data["output"] = output
            if metadata is not None:
                update_data["metadata"] = metadata
            if tags is not None:
                update_data["tags"] = tags

            if update_data:
                self._client.trace(id=trace_id, **update_data)
                logger.debug("Updated trace: %s", trace_id)
        except Exception as exc:
            logger.error("Failed to update trace: %s", exc)

    def score_trace(
        self,
        *,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        """
        Add a score to current trace.

        Args:
            name: Score name (e.g., "accuracy", "quality")
            value: Score value
            comment: Optional comment
        """
        if not self.enabled:
            return

        trace_id = _current_trace_id.get()
        if not trace_id:
            return

        try:
            self._client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
            )
            logger.debug("Scored trace %s: %s=%f", trace_id, name, value)
        except Exception as exc:
            logger.error("Failed to score trace: %s", exc)

    def shutdown(self) -> None:
        """Flush and shutdown the tracer."""
        if self._client:
            try:
                self._client.flush()
                logger.info("LangFuse client flushed")
            except Exception as exc:
                logger.error("Failed to flush LangFuse on shutdown: %s", exc)
