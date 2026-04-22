"""
eval_runner.py — Batch evaluation script for the Berg Research Agent.

Usage:
    python eval_runner.py                    # run all sequences
    python eval_runner.py --sequence B       # run only Sequence B
    python eval_runner.py --report           # print summary of today's results

Each run logs results to evaluation_results/eval_YYYYMMDD.jsonl
"""

import argparse
import sys
import os
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from src.db.vector_store import sync_mongo_to_chroma
from src.agent import get_research_agent
from src.evaluation.callback import ContextCaptureCallback
from src.evaluation.evaluator import (
    get_judge_llm, build_metrics, score, interpret, save_result, load_results,
    print_summary_report, check_exclusion_violations,
)

# ──────────────────────────────────────────────────────────────────────────────
# DEMO QUESTION SEQUENCES
# Each sequence is a list of (label, question) tuples.
# Run them IN ORDER — later questions build on what was downloaded earlier.
# ──────────────────────────────────────────────────────────────────────────────

SEQUENCES = {

    # ── Sequence A: Transformer & Attention ───────────────────────────────────
    # Tests: external search → download → section-level retrieval → comparison
    "A": {
        "name": "Transformer & Attention Mechanisms",
        "questions": [
            ("A1", "Search for papers on transformer attention mechanisms in NLP"),
            ("A2", "Download and summarize the paper Attention Is All You Need"),
            ("A3", "What datasets and metrics were used in the Attention Is All You Need paper?"),
            ("A4", "What are the key differences between self-attention and multi-head attention according to the paper?"),
            ("A5", "Compare BERT and the original Transformer in terms of architecture and training objective"),
        ],
    },

    # ── Sequence B: Robot Training (Exclusion Constraints) ────────────────────
    # Tests: negative constraint adherence — the exact case Gemini flagged
    # The agent MUST NOT mention RL, IL, or VLA in its answers
    "B": {
        "name": "Robot Training Methods (Exclusion Constraints)",
        "questions": [
            ("B1", "Find papers on ways to train robots, excluding reinforcement learning, imitation learning, and VLA models"),
            ("B2", "Among those papers, which ones are specifically about differentiable simulation or trajectory optimization for robots?"),
            ("B3", "What are the key metrics used to evaluate the robot training methods in those papers?"),
            ("B4", "Summarize the methodology section of the most relevant paper you found — make sure it does not involve RL or IL"),
            ("B5", "How do these training approaches compare to each other in terms of sample efficiency and sim-to-real transfer?"),
        ],
    },

    # ── Sequence C: Biomedical / PubMed ───────────────────────────────────────
    # Tests: PubMed tool use, PMC download, biomedical domain specificity
    "C": {
        "name": "Biomedical Research via PubMed",
        "questions": [
            ("C1", "Search PubMed for recent papers on CRISPR-Cas9 gene editing in cancer therapy"),
            ("C2", "What are the main limitations mentioned in those CRISPR papers?"),
            ("C3", "Which datasets or patient cohorts were used in the clinical studies found?"),
            ("C4", "Summarize the results and evaluations section of the most clinically relevant paper"),
            ("C5", "Are there any papers comparing CRISPR-Cas9 to base editing or prime editing approaches?"),
        ],
    },

    # ── Sequence D: LLM Scaling Laws ──────────────────────────────────────────
    # Tests: precise quantitative retrieval — exact numbers from papers
    "D": {
        "name": "LLM Scaling Laws & Compute Efficiency",
        "questions": [
            ("D1", "Search for papers on large language model scaling laws and compute-optimal training"),
            ("D2", "Download and analyze the Chinchilla paper on compute-optimal language models"),
            ("D3", "According to the Chinchilla paper, what is the optimal ratio of training tokens to model parameters?"),
            ("D4", "What specific model sizes and token counts does the Chinchilla paper recommend for different compute budgets?"),
            ("D5", "Compare the scaling predictions of the original GPT-3 scaling laws paper versus Chinchilla"),
        ],
    },

    # ── Sequence E: Multi-turn Citation Chain ─────────────────────────────────
    # Tests: citation tools + knowledge accumulation across turns
    "E": {
        "name": "Citation Chain & Author Discovery",
        "questions": [
            ("E1", "Find papers on contrastive learning for visual representations"),
            ("E2", "Download the SimCLR paper by Chen et al. on self-supervised learning"),
            ("E3", "Find papers that cite SimCLR — what are the top citing works?"),
            ("E4", "What other papers has the author Ting Chen published related to self-supervised learning?"),
            ("E5", "Compare the methodology of SimCLR with MoCo — what are the key algorithmic differences?"),
        ],
    },

    # ── Sequence F: Adversarial / Stress Test ─────────────────────────────────
    # Tests hallucination guardrails — vague queries that tempt the model to fabricate
    "F": {
        "name": "Hallucination Stress Test",
        "questions": [
            ("F1", "Tell me about a 2023 paper called Neural Quantum Robotics by Smith et al."),  # Fake paper
            ("F2", "What is the exact accuracy of GPT-4 on the BIG-Bench Hard benchmark?"),       # Should search, not guess
            ("F3", "Find the best paper on protein folding published in 2024"),
            ("F4", "What training method achieves superhuman dexterity in robotic hands excluding RL?"),
            ("F5", "Compare three papers on federated learning privacy guarantees"),               # Multi-paper comparison
        ],
    },
}

# ──────────────────────────────────────────────────────────────────────────────


def run_sequence(agent, metrics, judge_llm, callback: ContextCaptureCallback, seq_key: str, seq_data: dict):
    print(f"\n{'═'*60}")
    print(f"  SEQUENCE {seq_key}: {seq_data['name']}")
    print(f"{'═'*60}")

    history = []
    records = []

    for label, question in seq_data["questions"]:
        print(f"\n[{label}] {question}")
        print("─" * 60)

        callback.reset()
        chat_history = "\n".join(
            f"{'Human' if r == 'user' else 'AI'}: {c}" for r, c in history
        )

        try:
            result = agent.invoke(
                {"input": question, "chat_history": chat_history},
                config={"callbacks": [callback]},
            )
            answer = result["output"]
        except Exception as e:
            answer = f"[Agent error: {e}]"
            print(f"  ❌ Agent error: {e}")

        print(f"Answer preview: {answer[:300]}...")

        # Score with RAGAS + constraint adherence
        ragas_scores = score(question, answer, callback.retrieved_contexts, metrics, judge_llm)
        agent_summary = callback.summary()
        violations = check_exclusion_violations(question, answer)

        print(interpret(ragas_scores, agent_summary, violations))

        record = {
            "sequence": seq_key,
            "label": label,
            "question": question,
            "answer": answer,
            "retrieved_contexts": callback.retrieved_contexts,
            "ragas_scores": ragas_scores,
            "agent_summary": agent_summary,
            "exclusion_violations": violations,
        }
        save_result(record)
        records.append(record)

        # Carry forward as history for the next turn
        history.append(("user", question))
        history.append(("assistant", answer))

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence", help="Run only this sequence (A-F)", default=None)
    parser.add_argument("--report", action="store_true", help="Print summary of today's results")
    args = parser.parse_args()

    if args.report:
        records = load_results()
        print_summary_report(records)
        return

    print("🔄 Syncing vector database...")
    sync_mongo_to_chroma()

    print("🧠 Loading agent...")
    agent = get_research_agent()

    print("⚖️  Initialising RAGAS judge...")
    judge_llm = get_judge_llm()
    metrics = build_metrics(judge_llm)

    callback = ContextCaptureCallback()

    sequences_to_run = (
        {args.sequence: SEQUENCES[args.sequence]}
        if args.sequence and args.sequence in SEQUENCES
        else SEQUENCES
    )

    all_records = []
    for seq_key, seq_data in sequences_to_run.items():
        records = run_sequence(agent, metrics, judge_llm, callback, seq_key, seq_data)
        all_records.extend(records)

    print("\n")
    print_summary_report(all_records)
    print(f"✅ Results saved to evaluation_results/")


if __name__ == "__main__":
    main()
