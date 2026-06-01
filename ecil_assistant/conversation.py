import re
from datetime import datetime

import config


def normalize_text(text):
    return text.lower().strip() if text else ""


def contains_pattern(text, patterns):
    text = normalize_text(text)
    for pattern in patterns:
        escaped = re.escape(pattern)
        if re.search(fr"\b{escaped}\b", text):
            return True
    return False


class ConversationContext:
    def __init__(self):
        self.last_query = ""
        self.last_intent = ""
        self.last_topic = ""
        self.last_entity = ""
        self.history = []
        self.updated_at = datetime.utcnow().isoformat()

    def add_turn(self, user_text, bot_text, intent, entity=""):
        self.history.append({
            "user": user_text,
            "bot": bot_text,
            "intent": intent,
            "entity": entity,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.last_query = user_text
        self.last_intent = intent
        self.last_entity = entity or self.last_entity
        self.updated_at = datetime.utcnow().isoformat()

    def set_topic(self, topic):
        self.last_topic = topic
        self.updated_at = datetime.utcnow().isoformat()


class ConversationManager:
    def __init__(self):
        self.default_context = ConversationContext()

    def create_context(self):
        return ConversationContext()

    def detect_intent(self, user_text):
        normalized = normalize_text(user_text)
        if contains_pattern(normalized, config.INTENT_PATTERNS["greeting"]):
            return "greeting"
        if contains_pattern(normalized, config.INTENT_PATTERNS["thanks"]):
            return "thanks"
        if contains_pattern(normalized, config.INTENT_PATTERNS["goodbye"]):
            return "goodbye"
        if contains_pattern(normalized, config.INTENT_PATTERNS["contact_query"]):
            return "contact_query"
        if contains_pattern(normalized, config.INTENT_PATTERNS["internship_query"]):
            return "internship_query"
        if contains_pattern(normalized, config.INTENT_PATTERNS["recruitment_query"]):
            return "recruitment_query"
        if contains_pattern(normalized, config.INTENT_PATTERNS["organization_overview"]):
            return "organization_overview"
        if contains_pattern(normalized, config.INTENT_PATTERNS["navigation_help"]):
            return "navigation_help"
        if contains_pattern(normalized, config.INTENT_PATTERNS["hr_query"]):
            return "hr_query"
        if contains_pattern(normalized, config.INTENT_PATTERNS["faq_query"]):
            return "faq_query"
        if contains_pattern(normalized, config.INTENT_PATTERNS["procedural_query"]):
            return "procedural_query"
        if contains_pattern(normalized, config.INTENT_PATTERNS["clarify"]):
            return "clarification"
        if contains_pattern(normalized, config.INTENT_PATTERNS["help"]):
            return "help"
        if len(normalized.split()) <= 2 and normalized in {"who", "what", "where", "when", "why", "how", "tell me", "describe"}:
            return "clarification"
        if any(question in normalized for question in ["how", "what", "why", "when", "where", "who"]):
            return "question"
        return "query"

    def resolve_reference(self, user_text, context):
        normalized = normalize_text(user_text)
        if any(word in normalized for word in ["it", "this", "that", "they", "them", "its", "their"]):
            return context.last_entity or context.last_topic
        return ""

    def identify_topic(self, user_text, search_results):
        if not search_results:
            return ""
        first_doc = search_results[0]
        return first_doc.get("title") or first_doc.get("category")

    def summarize_entity(self, user_text):
        nouns = re.findall(r"[A-Za-z]{3,}", user_text)
        return nouns[-1] if nouns else user_text

    def update_context(self, user_text, intent, search_results, context):
        entity = self.resolve_reference(user_text, context)
        if not entity and search_results:
            entity = self.identify_topic(user_text, search_results)
        if entity:
            context.last_entity = entity
        topic = self.identify_topic(user_text, search_results)
        if topic:
            context.set_topic(topic)
        context.last_query = user_text
        context.last_intent = intent
        context.updated_at = datetime.utcnow().isoformat()
        return context

    def conversation_state(self, session):
        if "conversation" not in session:
            session["conversation"] = self.create_context().__dict__
            session["history"] = []
        stored = session.get("conversation", {})
        context = ConversationContext()
        context.__dict__.update(stored)
        return context

    def persist_state(self, session, context):
        session["conversation"] = context.__dict__


if __name__ == "__main__":
    manager = ConversationManager()
    context = manager.create_context()
    intent = manager.detect_intent("Tell me about EVM")
    print(intent)
