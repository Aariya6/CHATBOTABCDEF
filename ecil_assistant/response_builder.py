import math
import random
import re

import config


def normalize_confidence(raw_score: float) -> float:
    """Map a raw BM25 score (0..50+) into a 0..1 confidence for the UI.

    Smooth saturating curve: 5 -> ~0.39, 10 -> ~0.63, 20 -> ~0.86, 30 -> ~0.95.
    """
    if raw_score is None or raw_score <= 0:
        return 0.0
    return round(1.0 - math.exp(-raw_score / 10.0), 4)


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
    if is_faq_doc(doc):
        source = doc.get("source_url") or "ECIL FAQ dataset"
        title = doc.get("question", "ECIL FAQ")
    else:
        source = doc.get("source_url") or "local ECIL knowledge base"
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
    used_sources = set()
    doc_limit = 1 if is_project_query(user_text) or is_internship_query(user_text) or is_contact_query(user_text) else 2

    for doc in results[:doc_limit]:
        doc_paragraphs = build_paragraph(doc, user_text)
        for paragraph in doc_paragraphs:
            paragraphs.append(paragraph)
        source = build_source_block(doc)
        if source not in used_sources:
            source_blocks.append(source)
            used_sources.add(source)

    if intent in {"help", "faq_query", "navigation_help", "contact_query", "internship_query", "recruitment_query", "hr_query", "organization_overview", "procedural_query"}:
        follow_up = extract_topic_suggestions(categories)
        paragraphs.append(f"If you need more assistance, you can also ask about: {follow_up}.")

    response_text = "\n\n".join(paragraphs)
    if config.DEBUG_MODE:
        print(f"[DEBUG] build_response intent={intent} score={score:.4f} results={len(results)} path=full_answer")
    if source_blocks:
        response_text += "\n\n" + "\n".join(source_blocks)
    response_text = re.sub(r"[ \t]+", " ", response_text)
    response_text = re.sub(r"\n\s*\n+", "\n\n", response_text).strip()
    return response_text, confidence, source_blocks


if __name__ == "__main__":
    example = "Explain ECIL EVM security"
    print(build_intro("question", "ECIL EVM"))
