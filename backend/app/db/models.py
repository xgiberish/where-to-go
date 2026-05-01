import uuid
from datetime import datetime
from enum import Enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── LLM call enums ────────────────────────────────────────────────────────────

class LLMCallType(str, Enum):
    PARAMETER_EXTRACTION = "parameter_extraction"
    QUERY_REWRITE = "query_rewrite"
    TOOL_ARGUMENT = "tool_argument"
    SYNTHESIS = "synthesis"
    CLASSIFICATION = "classification"
    OTHER = "other"


class LLMTier(str, Enum):
    CHEAP = "cheap"
    STRONG = "strong"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text)
    tool_trace: Mapped[dict | None] = mapped_column(JSON)
    # pending | running | completed | failed
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Aggregated cost totals (summed from llm_calls)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_actual_cost: Mapped[float] = mapped_column(Numeric(10, 8), default=0.0)
    total_hypothetical_claude_cost: Mapped[float] = mapped_column(Numeric(10, 8), default=0.0)
    total_hypothetical_gemini_cost: Mapped[float] = mapped_column(Numeric(10, 8), default=0.0)

    user: Mapped["User"] = relationship(back_populates="agent_runs")
    llm_calls: Mapped[list["LLMCall"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
        order_by="LLMCall.created_at",
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
        order_by="ToolCall.created_at",
    )

    @property
    def cost_breakdown(self) -> dict:
        """Cost breakdown from individual LLM calls (requires loaded relationship)."""
        cheap_calls = [c for c in self.llm_calls if c.tier == LLMTier.CHEAP.value]
        strong_calls = [c for c in self.llm_calls if c.tier == LLMTier.STRONG.value]
        return {
            "cheap_tier": {
                "calls": len(cheap_calls),
                "tokens": sum(c.total_tokens for c in cheap_calls),
                "actual_cost": float(sum(c.actual_cost_usd for c in cheap_calls)),
            },
            "strong_tier": {
                "calls": len(strong_calls),
                "tokens": sum(c.total_tokens for c in strong_calls),
                "actual_cost": float(sum(c.actual_cost_usd for c in strong_calls)),
            },
            "total": {
                "tokens": self.total_tokens,
                "actual_cost": float(self.total_actual_cost),
                "vs_claude_haiku": float(self.total_hypothetical_claude_cost),
                "vs_gemini_flash": float(self.total_hypothetical_gemini_cost),
                "savings_vs_claude": float(self.total_hypothetical_claude_cost - self.total_actual_cost),
                "savings_vs_gemini": float(self.total_hypothetical_gemini_cost - self.total_actual_cost),
            },
        }


class LLMCall(Base):
    """Individual LLM API call with granular cost tracking."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Call metadata
    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)

    # Provider info
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Token usage
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Actual cost (always $0 for Groq free tier)
    actual_cost_usd: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False, default=0.0)

    # Hypothetical costs for cost comparison
    hypothetical_claude_haiku_cost: Mapped[float] = mapped_column(
        Numeric(10, 8), nullable=False, default=0.0
    )
    hypothetical_claude_sonnet_cost: Mapped[float] = mapped_column(
        Numeric(10, 8), nullable=False, default=0.0
    )
    hypothetical_gemini_flash_cost: Mapped[float] = mapped_column(
        Numeric(10, 8), nullable=False, default=0.0
    )

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent_run: Mapped["AgentRun"] = relationship(back_populates="llm_calls")

    def __repr__(self) -> str:
        return (
            f"<LLMCall(id={self.id}, type={self.call_type}, "
            f"tier={self.tier}, tokens={self.total_tokens})>"
        )


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(default=0)
    destination: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # dim=768 matches sentence-transformers/all-mpnet-base-v2
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ToolCall(Base):
    """One row per tool invocation, linked to the agent run that triggered it."""

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_input: Mapped[dict | None] = mapped_column("input", JSON)
    tool_output: Mapped[str | None] = mapped_column("output", Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent_run: Mapped["AgentRun"] = relationship(back_populates="tool_calls")
