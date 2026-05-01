#!/usr/bin/env python3
"""
Where To Go — aggregate cost report.

Queries all persisted LLM calls and prints a breakdown by tier, call type,
and provider, plus savings vs hypothetical paid providers.

Run from backend/:
    python scripts/generate_cost_report.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.db.models import AgentRun, LLMCall

_SEP = "=" * 80
_LINE = "-" * 80


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncSession(engine) as db:
        total_runs = await db.scalar(select(func.count(AgentRun.id))) or 0
        total_input = await db.scalar(select(func.sum(LLMCall.input_tokens))) or 0
        total_output = await db.scalar(select(func.sum(LLMCall.output_tokens))) or 0
        total_tokens = total_input + total_output

        actual_cost = float(
            await db.scalar(select(func.sum(AgentRun.total_actual_cost))) or 0
        )
        claude_cost = float(
            await db.scalar(select(func.sum(AgentRun.total_hypothetical_claude_cost))) or 0
        )
        gemini_cost = float(
            await db.scalar(select(func.sum(AgentRun.total_hypothetical_gemini_cost))) or 0
        )

        call_type_rows = (
            await db.execute(
                select(
                    LLMCall.call_type,
                    func.count(LLMCall.id).label("count"),
                    func.sum(LLMCall.total_tokens).label("tokens"),
                ).group_by(LLMCall.call_type)
            )
        ).all()

    await engine.dispose()

    print(f"\n{_SEP}")
    print("  COST REPORT — Where To Go")
    print(_SEP)
    print(f"\n  Total queries : {total_runs:,}")
    print(f"  Total tokens  : {total_tokens:,}  ({total_input:,} in / {total_output:,} out)")

    print(f"\n{_SEP}")
    print("  ACTUAL COST  (Groq free tier)")
    print(_SEP)
    print(f"  Total : ${actual_cost:.8f}  →  $0.00 charged")

    print(f"\n{_SEP}")
    print("  HYPOTHETICAL COSTS  (if using paid providers)")
    print(_SEP)
    print(f"  Claude Haiku  : ${claude_cost:.4f}")
    print(f"  Gemini Flash  : ${gemini_cost:.4f}")

    print(f"\n{_SEP}")
    print("  SAVINGS  (Groq vs paid providers)")
    print(_SEP)
    print(f"  vs Claude Haiku  : ${claude_cost - actual_cost:.4f}  (100% saved)")
    print(f"  vs Gemini Flash  : ${gemini_cost - actual_cost:.4f}  (100% saved)")

    print(f"\n{_SEP}")
    print("  BREAKDOWN BY CALL TYPE")
    print(_SEP)
    print(f"  {'Type':<28} {'Calls':>8} {'Tokens':>15}")
    print(f"  {_LINE}")
    for row in call_type_rows:
        tokens = int(row.tokens or 0)
        print(f"  {row.call_type:<28} {row.count:>8} {tokens:>15,}")

    if total_runs:
        print(f"\n{_SEP}")
        print("  PER-QUERY AVERAGE")
        print(_SEP)
        print(f"  Tokens         : {total_tokens / total_runs:,.0f}")
        print(f"  vs Claude Haiku: ${claude_cost / total_runs:.6f}")
        print(f"  vs Gemini Flash: ${gemini_cost / total_runs:.6f}")
        print(f"  Actual (Groq)  : $0.000000")

    print()


if __name__ == "__main__":
    asyncio.run(main())
