import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from ragas.dataset_schema import SingleTurnSample
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecisionWithoutReference
from ragas.llms import LangchainLLMWrapper
from ragas.run_config import RunConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from src.guardrails.exclusions import extract_exclusions, check_exclusion_violations

RESULTS_DIR = Path("evaluation_results")

# Score thresholds — below these we flag issues
THRESHOLDS = {
    "faithfulness": 0.70,
    "answer_relevancy": 0.60,
    "context_precision_without_reference": 0.50,
    "constraint_adherence": 0.70,
}


def get_judge_llm() -> ChatGoogleGenerativeAI:
    """
    Judge LLM for RAGAS — uses Gemini Flash as an independent evaluator.
    Different model family from Qwen avoids self-serving bias in scores.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables.")
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0.0,
        max_tokens=1024,
    )


def build_metrics(llm: ChatGoogleGenerativeAI) -> list:
    """Creates and initialises the three no-reference RAGAS metrics."""
    wrapped = LangchainLLMWrapper(llm)
    metrics = [
        Faithfulness(),
        AnswerRelevancy(),
        ContextPrecisionWithoutReference(),
    ]
    for m in metrics:
        m.llm = wrapped
        m.init(RunConfig())
    return metrics


async def _score_async(
    question: str,
    answer: str,
    contexts: list[str],
    metrics: list,
) -> dict:
    if not contexts:
        # No context → agent answered from memory → faithfulness is meaningless,
        # but we still record it so the 0.0 score surfaces in the report.
        contexts = ["[No context retrieved — agent answered from training memory]"]

    sample = SingleTurnSample(
        user_input=question,
        response=answer,
        retrieved_contexts=contexts,
    )

    results = {}
    for m in metrics:
        try:
            results[m.name] = round(await m.single_turn_ascore(sample), 3)
        except Exception as e:
            results[m.name] = f"error: {str(e)[:100]}"
    return results


async def _score_constraint_adherence_async(
    question: str,
    answer: str,
    llm: ChatGoogleGenerativeAI,
) -> float:
    """LLM judge: returns 0.0–1.0 for how well the answer respects question constraints."""
    exclusions = extract_exclusions(question)
    violations = check_exclusion_violations(question, answer)

    # Fast path: no constraints in the question
    if not exclusions:
        return 1.0

    prompt = (
        f"Question: {question}\n\n"
        f"Answer: {answer[:1500]}\n\n"
        f"The question explicitly excludes: {', '.join(exclusions)}.\n"
        f"Does the answer respect these exclusions? "
        "Reply with a single decimal score from 0.0 (completely ignores constraints) "
        "to 1.0 (fully respects all constraints). Output ONLY the number, nothing else."
    )
    try:
        resp = await llm.ainvoke(prompt)
        text = resp.content.strip()
        return round(min(1.0, max(0.0, float(text))), 3)
    except Exception:
        # Fallback: heuristic based on detected violations
        return round(1.0 - (len(violations) / max(len(exclusions), 1)), 3)


def score(
    question: str,
    answer: str,
    contexts: list[str],
    metrics: list,
    llm: ChatGoogleGenerativeAI | None = None,
) -> dict:
    """Synchronous wrapper — safe to call from scripts and notebooks."""
    return asyncio.run(_score_all_async(question, answer, contexts, metrics, llm))


async def _score_all_async(
    question: str,
    answer: str,
    contexts: list[str],
    metrics: list,
    llm: ChatGoogleGenerativeAI | None,
) -> dict:
    ragas = await _score_async(question, answer, contexts, metrics)
    if llm is not None:
        ragas["constraint_adherence"] = await _score_constraint_adherence_async(question, answer, llm)
    return ragas


def interpret(
    ragas_scores: dict,
    agent_summary: dict | None = None,
    exclusion_violations: list[str] | None = None,
) -> str:
    """Returns a human-readable verdict string for a single sample."""
    lines = ["── RAGAS Scores ──────────────────────────"]
    for name, val in ragas_scores.items():
        if isinstance(val, float):
            threshold = THRESHOLDS.get(name, 0.6)
            if val >= threshold:
                flag = "✅"
            elif val >= threshold * 0.75:
                flag = "⚠️ "
            else:
                flag = "🔴"
            lines.append(f"  {flag}  {name:<48} {val:.3f}")
        else:
            lines.append(f"  ❓  {name:<48} {val}")

    if exclusion_violations:
        lines.append("── Constraint Violations ─────────────────")
        lines.append(f"  🔴  Excluded topics found in answer: {', '.join(exclusion_violations)}")

    if agent_summary:
        lines.append("── Agent Behaviour ───────────────────────")
        if agent_summary.get("answered_from_memory"):
            lines.append("  🔴  Agent answered WITHOUT calling any tool (hallucination risk)")
        else:
            lines.append(f"  ℹ️   Tools called: {', '.join(agent_summary.get('tools_called', []))}")
            lines.append(f"  ℹ️   Contexts captured: {agent_summary.get('num_contexts_captured', 0)}")
    lines.append("──────────────────────────────────────────")
    return "\n".join(lines)


def save_result(record: dict) -> Path:
    """Appends one evaluation record to a daily results file."""
    RESULTS_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    fname = RESULTS_DIR / f"eval_{today}.jsonl"
    with open(fname, "a") as f:
        f.write(json.dumps(record) + "\n")
    return fname


def load_results(date: str | None = None) -> list[dict]:
    """Loads all evaluation records for a given date (default: today)."""
    date = date or datetime.now().strftime("%Y%m%d")
    fname = RESULTS_DIR / f"eval_{date}.jsonl"
    if not fname.exists():
        return []
    with open(fname) as f:
        return [json.loads(line) for line in f if line.strip()]


def print_summary_report(records: list[dict]) -> None:
    """Prints an aggregate summary table across all evaluated records."""
    if not records:
        print("No evaluation records found.")
        return

    metric_names = [k for k in records[0].get("ragas_scores", {}) if isinstance(records[0]["ragas_scores"][k], float)]
    from_memory_count = sum(1 for r in records if r.get("agent_summary", {}).get("answered_from_memory"))

    print(f"\n{'═'*55}")
    print(f"  EVALUATION SUMMARY  ({len(records)} questions)")
    print(f"{'═'*55}")

    for name in metric_names:
        vals = [r["ragas_scores"][name] for r in records if isinstance(r["ragas_scores"].get(name), float)]
        if vals:
            avg = sum(vals) / len(vals)
            mn, mx = min(vals), max(vals)
            threshold = THRESHOLDS.get(name, 0.6)
            flag = "✅" if avg >= threshold else "🔴"
            short = name.replace("llm_context_precision_without_reference", "context_precision").replace("answer_relevancy", "answer_relevancy")
            print(f"  {flag}  {short:<40}  avg={avg:.3f}  min={mn:.3f}  max={mx:.3f}")

    print(f"\n  🔴  Answered from memory (no tools): {from_memory_count}/{len(records)}")
    violation_count = sum(1 for r in records if r.get("exclusion_violations"))
    if violation_count:
        print(f"  🔴  Exclusion constraint violations:  {violation_count}/{len(records)}")
    else:
        print(f"  ✅  Exclusion constraint violations:  0/{len(records)}")
    print(f"{'═'*55}\n")
