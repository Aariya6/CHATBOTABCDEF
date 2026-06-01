"""Accuracy evaluation harness for the ECIL offline assistant.

Run:
    python eval_engine.py            # full report
    python eval_engine.py --quick    # top-1 accuracy only

Each labeled case lists one or more substrings that MUST appear in the
top-ranked answer (case-insensitive) for the query to count as correct.
Top-1 accuracy is the primary metric; top-3 is reported as a soft metric.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import List, Dict, Tuple

from engine import KnowledgeEngine
from conversation import ConversationManager
from response_builder import build_response


# Each case: (query, list-of-required-substrings, optional intent override)
# A query passes top-1 if ANY of its required substrings appears in the top
# document's title / question / content / answer fields (case-insensitive).
EVAL_CASES: List[Tuple[str, List[str], str]] = [
    # --- Company overview ---
    ("What is ECIL?", ["electronics corporation of india", "ecil"], ""),
    ("When was ECIL founded?", ["1967"], ""),
    ("Where is ECIL headquarters?", ["hyderabad"], ""),
    ("Who is the parent department of ECIL?", ["department of atomic energy", "dae"], ""),
    ("What does ECIL stand for?", ["electronics corporation of india"], ""),
    ("Tell me about ECIL business domains", ["defence", "nuclear", "communication"], ""),
    ("Who owns ECIL?", ["government", "public sector", "dae", "atomic energy"], ""),
    ("ECIL company profile", ["public sector", "electronics"], ""),

    # --- EVM / elections ---
    ("Tell me about EVM", ["voting machine", "evm"], ""),
    ("How secure are ECIL EVMs?", ["secure", "tamper"], ""),
    ("What is VVPAT?", ["voter", "paper", "audit"], ""),
    ("What is ballot unit?", ["ballot"], ""),
    ("What is control unit in EVM?", ["control unit"], ""),
    ("Are ECIL voting machines used in elections?", ["election"], ""),

    # --- Defence ---
    ("ECIL defence electronics", ["defence", "defense"], ""),
    ("What military systems does ECIL build?", ["defence", "military", "surveillance"], ""),
    ("Does ECIL work with DRDO?", ["drdo", "defence"], ""),
    ("Tell me about radar systems by ECIL", ["radar", "surveillance"], ""),
    ("electronic warfare equipment ECIL", ["defence", "electronic warfare", "warfare"], ""),

    # --- Nuclear ---
    ("Tell me about ECIL nuclear systems", ["nuclear"], ""),
    ("Radiation monitoring at ECIL", ["radiation"], ""),
    ("nuclear instrumentation", ["nuclear", "instrumentation"], ""),
    ("ECIL reactor control systems", ["reactor", "control"], ""),

    # --- Communications / Antenna ---
    ("ECIL communication systems", ["communication"], ""),
    ("Does ECIL make antennas?", ["antenna"], ""),
    ("satellite communication ECIL", ["satellite"], ""),
    ("Tetra radio by ECIL", ["tetra", "radio"], ""),

    # --- Security / Components / Misc products ---
    ("X-ray baggage scanner ECIL", ["x-ray", "baggage", "scanner"], ""),
    ("container scanner ECIL", ["container", "scanner"], ""),
    ("Does ECIL make smart cards?", ["smart card"], ""),
    ("ECIL smart meters", ["smart meter"], ""),
    ("Servo systems by ECIL", ["servo"], ""),
    ("Solar electronics ECIL", ["solar"], ""),
    ("Components division ECIL", ["component"], ""),

    # --- Railway ---
    ("railway signaling ECIL", ["railway", "signal"], ""),
    ("Does ECIL do metro projects?", ["metro", "railway"], ""),
    ("automatic fare collection", ["fare collection", "afc"], ""),

    # --- Careers / Recruitment ---
    ("How do I apply for jobs at ECIL?", ["career", "apply", "vacancy", "recruitment"], "recruitment_query"),
    ("Are there current vacancies at ECIL?", ["vacancy", "recruitment", "career"], "recruitment_query"),
    ("ECIL recruitment notification", ["recruitment", "notification"], "recruitment_query"),
    ("How are engineers selected at ECIL?", ["selection", "written test", "interview"], "recruitment_query"),
    ("Walk-in interview ECIL", ["walk-in", "walkin", "interview"], "recruitment_query"),
    ("Management trainee at ECIL", ["management trainee", "trainee"], "recruitment_query"),
    ("ECIL technician recruitment", ["technician"], "recruitment_query"),
    ("graduate engineer trainee", ["graduate", "trainee", "get"], "recruitment_query"),

    # --- Internship / Apprentice ---
    ("How do I apply for an internship at ECIL?", ["internship", "intern"], "internship_query"),
    ("Apprentice training at ECIL", ["apprentice"], "internship_query"),
    ("industrial training ECIL", ["industrial training", "training"], "internship_query"),
    ("student project at ECIL", ["student", "project", "training"], "internship_query"),
    ("Does ECIL offer summer internships?", ["intern", "summer", "training"], "internship_query"),

    # --- Contact ---
    ("ECIL HR email", ["hrrect@ecil.co.in", "@ecil.co.in"], "contact_query"),
    ("ECIL phone number", ["040-", "27182"], "contact_query"),
    ("ECIL Hyderabad office address", ["hyderabad", "kushaiguda", "nagar"], "contact_query"),
    ("Where can I email ECIL?", ["@ecil.co.in", "email"], "contact_query"),
    ("ECIL contact details", ["contact", "email", "phone"], "contact_query"),
    ("ECIL regional office Mumbai", ["regional", "mumbai", "office"], "contact_query"),
    ("ECIL regional office Delhi", ["regional", "delhi", "office"], "contact_query"),

    # --- Tenders ---
    ("Where can I find ECIL tenders?", ["tender"], ""),
    ("ECIL procurement", ["procurement", "tender"], ""),
    ("e-procurement portal ECIL", ["e-procurement", "procurement"], ""),
    ("Vendor registration ECIL", ["vendor", "registration"], ""),
    ("ECIL bid submission", ["bid", "tender"], ""),

    # --- HR / policy ---
    ("ECIL leave policy", ["leave", "policy"], "hr_query"),
    ("ECIL employee benefits", ["benefit", "employee"], "hr_query"),
    ("ECIL training programs for staff", ["training"], "hr_query"),
    ("ECIL CSR activities", ["csr", "social responsibility"], ""),
    ("Vigilance department ECIL", ["vigilance"], ""),

    # --- Org structure ---
    ("Who is the CMD of ECIL?", ["cmd", "chairman", "managing director"], ""),
    ("ECIL divisions list", ["division"], ""),
    ("ECIL strategic electronics division", ["strategic"], ""),
    ("ECIL customer support division", ["customer support"], ""),

    # --- Navigation / FAQ ---
    ("What are common FAQs about ECIL?", ["faq", "frequently asked"], "faq_query"),
    ("How to navigate ECIL website?", ["navigation", "menu", "website"], "navigation_help"),
    ("Help me find information on ECIL", ["help", "information"], "help"),

    # --- Follow-ups / vague ---
    ("Tell me more about it", [], ""),
    ("Explain ECIL projects", ["project"], ""),
    ("Describe ECIL achievements", ["project", "achievement", "ecil"], ""),
]


def is_correct(doc: Dict, required_substrings: List[str]) -> bool:
    if not required_substrings:
        return True  # no-substring cases are pass-through (sanity / vague-query)
    if not doc:
        return False
    blob = " ".join([
        str(doc.get("title", "")),
        str(doc.get("question", "")),
        str(doc.get("content", "")),
        str(doc.get("answer", "")),
        str(doc.get("summary", "")),
        " ".join(doc.get("tags", [])),
        " ".join(doc.get("keywords", [])),
    ]).lower()
    return any(sub.lower() in blob for sub in required_substrings)


def run_eval(quick: bool = False) -> Dict:
    engine = KnowledgeEngine()
    cm = ConversationManager()
    ctx = cm.create_context()

    total = len(EVAL_CASES)
    top1_hits = 0
    top3_hits = 0
    confident_hits = 0  # top-1 correct AND score >= LOW threshold
    failures: List[Tuple[str, List[Dict]]] = []

    t0 = time.time()
    for query, required, intent_hint in EVAL_CASES:
        intent = intent_hint or cm.detect_intent(query)
        results, score = engine.search(query, intent=intent)
        top1 = results[0] if results else None
        top3 = results[:3]

        ok1 = is_correct(top1, required)
        ok3 = any(is_correct(d, required) for d in top3)

        if ok1:
            top1_hits += 1
            if score >= 0.18:
                confident_hits += 1
        if ok3:
            top3_hits += 1
        if not ok1 and required:
            failures.append((query, [{"title": d.get("title") or d.get("question"), "id": d.get("id")} for d in top3]))

    elapsed = time.time() - t0
    report = {
        "total": total,
        "top1_accuracy": round(top1_hits / total * 100, 2),
        "top3_accuracy": round(top3_hits / total * 100, 2),
        "confident_top1_accuracy": round(confident_hits / total * 100, 2),
        "avg_latency_ms": round(elapsed / total * 1000, 2),
        "wall_seconds": round(elapsed, 2),
        "kb_docs": len(engine.documents),
        "faq_docs": len(engine.faq_documents),
        "failures": failures if not quick else failures[:10],
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Show only first 10 failures.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args(argv)

    report = run_eval(quick=args.quick)
    if args.json:
        import json
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("ECIL Offline Assistant - Retrieval Accuracy Report")
    print("=" * 60)
    print(f"KB docs        : {report['kb_docs']}")
    print(f"FAQ entries    : {report['faq_docs']}")
    print(f"Eval set size  : {report['total']}")
    print(f"Top-1 accuracy : {report['top1_accuracy']}%")
    print(f"Top-3 accuracy : {report['top3_accuracy']}%")
    print(f"Confident top-1: {report['confident_top1_accuracy']}%  (score >= 0.18)")
    print(f"Avg latency    : {report['avg_latency_ms']} ms / query")
    print(f"Wall time      : {report['wall_seconds']} s")
    print()
    if report["failures"]:
        print(f"Failures ({len(report['failures'])}):")
        for q, tops in report["failures"]:
            print(f"  - {q!r}")
            for d in tops:
                print(f"      -> {d['id']}: {d['title']}")
    else:
        print("All eval cases passed top-1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
