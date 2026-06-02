import math
import random
import re

import config


def normalize_confidence(raw_score: float) -> float:
    """Map a raw BM25 score (0..50+) into a 0..1 confidence for the UI.

    Smooth saturating curve: 5 -> ~0.46, 10 -> ~0.71, 20 -> ~0.91, 30 -> ~0.97.
    """
    if raw_score is None or raw_score <= 0:
        return 0.0
    # Make the curve slightly steeper so useful BM25 scores map to
    # higher displayed confidence (but still saturate at 1.0).
    val = 1.0 - math.exp(-raw_score / 6.0)
    # tiny safeguard to keep within bounds and round for stable UI display
    return round(max(0.0, min(1.0, val)), 4)


def clean_sentence(text):
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_sentences(text):
    sentence_endings = re.compile(r"(?<=[.!?])\s+")
    return [clean_sentence(sentence) for sentence in sentence_endings.split(text) if sentence]


def join_paragraphs(sentences, max_paragraphs=3):
    paragraphs = []
    index = 0
    current = []
    while index < len(sentences) and len(paragraphs) < max_paragraphs:
        current.append(sentences[index])
        if len(current) >= 2:
            paragraphs.append(" ".join(current))
            current = []
        index += 1
    if current and len(paragraphs) < max_paragraphs:
        paragraphs.append(" ".join(current))
    return paragraphs


def build_intro(intent, topic):
    if intent == "greeting":
        return "Hello! I am the ECIL internal helpdesk assistant. Ask me about company services, internship and recruitment, contact details, or organizational procedures."
    if intent == "thanks":
        return "You are welcome. I am here to help with ECIL-related questions across operations, careers, contacts, and technical domains."
    if intent == "goodbye":
        return "Goodbye. You can ask the ECIL internal assistant again anytime for local helpdesk information."
    if intent == "clarification":
        return "I am clarifying your request and preparing an accurate response from the ECIL knowledge base."
    if intent == "help":
        return "I can help with ECIL policies, contact points, internships, recruitment, organisational overview, tender access, and product domains. What would you like to know?"
    if topic:
        return f"Here is the information I found for {topic}."
    return "I have found relevant ECIL knowledge from the local database and prepared the best answer for your query."


def is_project_query(text):
    text = text.lower()
    return any(keyword in text for keyword in ["project", "projects", "portfolio", "collaboration", "program", "programme"])


def is_internship_query(text):
    text = text.lower()
    return any(keyword in text for keyword in ["intern", "internship", "trainee", "apprentice", "training", "industrial training"])


def is_contact_query(text):
    text = text.lower()
    return any(keyword in text for keyword in ["contact", "email", "phone", "address", "reach", "call", "enquiry"])


def is_faq_doc(doc):
    return "answer" in doc and "question" in doc


def generate_bullet_points(doc, max_points=5):
    content = doc.get("answer", doc.get("content", ""))
    sentences = split_sentences(content)
    bullets = []
    for sentence in sentences:
        if len(sentence) < 50:
            continue
        cleaned = sentence.strip().rstrip(".")
        if cleaned and cleaned not in bullets:
            bullets.append(f"- {cleaned}")
        if len(bullets) >= max_points:
            break
    return bullets


def build_paragraph(doc, query):
    if is_faq_doc(doc):
        answer = clean_sentence(doc.get("answer", ""))
        return [answer] if answer else [doc.get("question", "")] if doc.get("question") else ["No detailed FAQ answer is available."]

    content = doc.get("content", "")
    sentences = split_sentences(content)
    if is_project_query(query) or is_internship_query(query) or is_contact_query(query):
        bullets = generate_bullet_points(doc)
        if bullets:
            return ["\n".join(bullets)]
    if len(sentences) >= 3:
        selected = sentences[:3]
    else:
        selected = sentences
    paragraphs = join_paragraphs(selected)
    if not paragraphs:
        paragraphs = [doc.get("summary", "The document provides helpful details on this topic.")]
    return paragraphs


def build_source_block(doc):
    invalid_sources = {url.rstrip("/") for url in getattr(config, "INVALID_SOURCE_URLS", [])}
    invalid_prefixes = [prefix.rstrip("/") for prefix in getattr(config, "INVALID_SOURCE_PREFIXES", [])]
    def is_invalid(url: str) -> bool:
        if not url:
            return False
        canonical = url.rstrip("/")
        return canonical in invalid_sources or any(canonical.startswith(prefix) for prefix in invalid_prefixes)

    if is_faq_doc(doc):
        source_url = (doc.get("source_url") or "").rstrip("/")
        if source_url and not is_invalid(source_url):
            source = source_url
        else:
            source = "ECIL FAQ dataset"
        title = doc.get("question", "ECIL FAQ")
    else:
        source_url = (doc.get("source_url") or "").rstrip("/")
        if source_url and not is_invalid(source_url) and source_url.startswith(config.SITE_ROOT):
            source = source_url
        else:
            source = "local ECIL knowledge base"
        title = doc.get("title", "ECIL content")
    return f"Source: {title} ({source})"


def extract_topic_suggestions(categories):
    return ", ".join(categories[:4]) if categories else "related ECIL topics"


def build_response(user_text, results, score, intent, context, categories):
    confidence = normalize_confidence(score)
    response_path = ""
    if intent in {"greeting", "thanks", "goodbye"}:
        response_path = "conversation_response"
        response_text = build_intro(intent, context.last_topic)
        if config.DEBUG_MODE:
            print(f"[DEBUG] build_response intent={intent} score={score:.4f} results={len(results)} path={response_path}")
        return response_text, confidence, []

    if not results:
        response_path = "no_results"
        suggestions = extract_topic_suggestions(categories)
        fallback = (
            "I do not have a direct entry for that in the local ECIL knowledge base. "
            "You can ask about any of these topics, or rephrase your question: "
            f"{suggestions}."
        )
        return fallback, confidence, []

    if confidence < 0.20:
        # Loosely related — still surface the best partial match with a
        # short, honest framing rather than a flat "no result" message.
        response_path = "low_confidence"
        primary = results[0]
        topic = primary.get("title") or primary.get("question") or "this topic"
        bullets = generate_bullet_points(primary)
        body = "\n".join(bullets) if bullets else primary.get(
            "summary",
            primary.get("answer", primary.get("content", ""))[:400],
        )
        response = (
            f"I do not have an exact entry for your question, but the closest "
            f"item I have is about {topic}. Here is what it says:\n\n{body}\n\n"
            f"If this is not what you meant, try asking about: "
            f"{extract_topic_suggestions(categories)}."
        )
        if config.DEBUG_MODE:
            print(f"[DEBUG] build_response intent={intent} score={score:.4f} results={len(results)} path={response_path}")
        return response, confidence, [build_source_block(primary)]

    topic = context.last_topic or results[0].get("title", results[0].get("question", "your request"))
    paragraphs = [build_intro(intent, topic)]
    source_blocks = []
    used_source_keys = set()
    doc_limit = 1 if is_project_query(user_text) or is_internship_query(user_text) or is_contact_query(user_text) else 2

    # If the top hit is FAQ-like, synthesize a short explicit answer first.
    primary = results[0]
    if is_faq_doc(primary) and primary.get("answer"):
        short = clean_sentence(primary.get("answer", ""))
        if short:
            paragraphs.append(f"Answer: {short}")
            doc_limit = 1

    for doc in results[:doc_limit]:
        doc_paragraphs = build_paragraph(doc, user_text)
        for paragraph in doc_paragraphs:
            paragraphs.append(paragraph)
        source = build_source_block(doc)
        source_key = doc.get("source_url") or source
        if source_key not in used_source_keys:
            source_blocks.append(source)
            used_source_keys.add(source_key)

    if intent in {"help", "faq_query", "navigation_help", "contact_query", "internship_query", "recruitment_query", "hr_query", "organization_overview", "procedural_query"}:
        follow_up = extract_topic_suggestions(categories)
        paragraphs.append(f"If you need more assistance, you can also ask about: {follow_up}.")

    response_text = "\n\n".join(paragraphs)
    if config.DEBUG_MODE:
        print(f"[DEBUG] build_response intent={intent} score={score:.4f} results={len(results)} path=full_answer")
    response_text = re.sub(r"[ \t]+", " ", response_text)
    response_text = re.sub(r"\n\s*\n+", "\n\n", response_text).strip()

    # Borderline handling: when confidence is modest, include a concise
    # pointer to the runner-up so the user can consider an alternate.
    if confidence < 0.45 and len(results) > 1:
        runner = results[1]
        runner_title = runner.get("title") or runner.get("question") or "another related item"
        runner_snip = (runner.get("summary") or runner.get("answer") or runner.get("content") or "").strip()
        if runner_snip:
            runner_snip = clean_sentence(runner_snip)[:180]
            response_text += f"\n\nAlso see: {runner_title} — {runner_snip}"
            source_blocks.append(build_source_block(runner))

    # Conservative verification: check overlap between query content words
    # and the assembled response; if overlap is tiny, lower confidence and
    # add a short clarifying note.
    def _content_words(text):
        toks = re.sub(r"[^a-z0-9 ]", " ", text.lower())
        toks = [t for t in toks.split() if t and t not in config.STOPWORDS and len(t) > 2]
        return toks

    q_words = _content_words(user_text)
    if q_words:
        body = re.sub(r"\s+", " ", response_text.lower())
        hits = sum(1 for w in set(q_words) if w in body)
        hit_ratio = hits / len(set(q_words)) if q_words else 1.0
        if hit_ratio < 0.25:
            confidence = round(max(0.0, confidence * 0.8), 4)
            response_text += "\n\nNote: I may not have found an exact match for your request — please rephrase or provide more details for a precise answer."

    return response_text, confidence, source_blocks


if __name__ == "__main__":
    example = "Explain ECIL EVM security"
    print(build_intro("question", "ECIL EVM"))
