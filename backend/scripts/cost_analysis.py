#!/usr/bin/env python3
"""
Where To Go — LLM cost analysis.

Runs one prompt through each configured tier and prints a cost breakdown.
Demonstrates the theoretical cost savings of Groq's free tier vs Gemini.

Run from backend/:
    python scripts/cost_analysis.py
    python scripts/cost_analysis.py --prompt "Best beaches in Southeast Asia?"
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.services.llm_service import LLMResponse, LLMService

_SEP = "─" * 60
_TEST_PROMPT = "Explain machine learning in one sentence."


def _print_result(label: str, r: LLMResponse) -> None:
    print(f"\n{label}")
    print(_SEP)
    print(f"  Provider : {r.provider}")
    print(f"  Model    : {r.model}")
    print(f"  Tokens   : {r.input_tokens} in / {r.output_tokens} out")
    cost_note = "(theoretical — actual charge: $0)" if r.is_free_tier else "(actual charge)"
    print(f"  Cost     : ${r.actual_cost_usd:.6f} {cost_note}")
    snippet = r.content[:120].replace("\n", " ")
    print(f"  Response : {snippet}{'…' if len(r.content) > 120 else ''}")


async def main(prompt: str) -> None:
    settings = get_settings()
    llm = LLMService(settings)

    print(f"\n{'='*60}")
    print("  Where To Go — LLM Cost Analysis")
    print(f"{'='*60}")
    print(f"  Prompt : \"{prompt}\"")

    # ── Tier 1: cheap (Groq llama-3.1-8b-instant) ────────────────────────────
    cheap = await llm.cheap_call(prompt)
    _print_result("TIER 1 — Cheap  (Groq llama-3.1-8b-instant)", cheap)

    # ── Tier 2: strong (Groq llama-3.3-70b-versatile) ────────────────────────
    strong = await llm.strong_call(prompt)
    _print_result("TIER 2 — Strong (Groq llama-3.3-70b-versatile)", strong)

    # ── Tier 3: demo (Gemini) — only if enabled ───────────────────────────────
    demo: LLMResponse | None = None
    if settings.enable_cost_demo and settings.gemini_api_key:
        demo = await llm.cheap_call(prompt, use_demo=True)
        _print_result("TIER 3 — Demo   (Gemini gemini-1.5-flash)", demo)
    else:
        print(f"\nTIER 3 — Demo (Gemini): skipped")
        print(f"  Set ENABLE_COST_DEMO=true and GEMINI_API_KEY in .env to enable.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  COST SUMMARY (per query)")
    print(f"{'='*60}")
    groq_total = cheap.actual_cost_usd + strong.actual_cost_usd
    print(f"  Groq cheap  : ${cheap.actual_cost_usd:.6f}  (theoretical)")
    print(f"  Groq strong : ${strong.actual_cost_usd:.6f}  (theoretical)")
    print(f"  Groq total  : ${groq_total:.6f}  → actual charge: $0.000000 (FREE)")

    if demo is not None:
        savings = demo.actual_cost_usd - cheap.actual_cost_usd
        print(f"\n  Gemini demo : ${demo.actual_cost_usd:.6f}  (actual charge)")
        print(f"  Savings/query with Groq vs Gemini: ${savings:.6f}")
        monthly_queries = 1_000
        print(f"  At {monthly_queries:,} queries/month:")
        print(f"    Groq  → $0.00")
        print(f"    Gemini → ${demo.actual_cost_usd * monthly_queries:.4f}")

    print()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyse LLM costs across tiers")
    p.add_argument("--prompt", default=_TEST_PROMPT, help="Prompt to test with")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.prompt))
