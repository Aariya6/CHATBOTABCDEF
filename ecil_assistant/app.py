import json
import os
import time
import uuid
from datetime import timedelta

from flask import Flask, render_template, request, jsonify, session

import config
from conversation import ConversationManager
from engine import KnowledgeEngine
from response_builder import build_response

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(hours=8)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Cache-bust token recomputed on each server start. Embedded in template URLs
# as ?v=<token> so browsers reliably re-fetch CSS/JS after we redeploy.
ASSET_VERSION = str(int(time.time()))


@app.context_processor
def _inject_asset_version():
    return {"ASSET_VERSION": ASSET_VERSION}


@app.after_request
def _no_cache_static(response):
    # Force browsers to re-fetch all static + dynamic responses. The combo
    # of meta no-store + these headers + ?v= query string covers every
    # browser caching path we've seen on Windows.
    if request.path.startswith("/static/") or request.path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

def initialize_data_directories():
    for folder in ["data", "cache", "logs"]:
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(config.KNOWLEDGE_BASE_PATH):
        with open(config.KNOWLEDGE_BASE_PATH, "w", encoding="utf-8") as handle:
            json.dump([], handle)
    if not os.path.exists(config.SYNONYM_MAP_PATH):
        with open(config.SYNONYM_MAP_PATH, "w", encoding="utf-8") as handle:
            json.dump(config.SYNONYM_MAP, handle, indent=2, ensure_ascii=False)
    if not os.path.exists(config.PROCESSED_DOCS_PATH):
        with open(config.PROCESSED_DOCS_PATH, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
    if not os.path.exists(config.FAQ_BASE_PATH):
        with open(config.FAQ_BASE_PATH, "w", encoding="utf-8") as handle:
            json.dump([], handle)


initialize_data_directories()
engine = KnowledgeEngine()
conversation_manager = ConversationManager()
if config.DEBUG_MODE:
    print(f"[STARTUP] KB entries={len(engine.documents)} loaded from {config.KNOWLEDGE_BASE_PATH}")
    print(f"[STARTUP] FAQ entries={len(engine.faq_documents)} loaded from {config.FAQ_BASE_PATH}")
print("[ACTIVE_APP] ecil_assistant/app.py")
print(f"[KB_ENTRIES] {len(engine.documents)}")
print(f"[FAQ_ENTRIES] {len(engine.faq_documents)}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "documents": len(engine.documents),
        "faqs": len(engine.faq_documents),
        "categories": len(engine.categories),
    })


@app.route("/api/categories")
def categories():
    return jsonify({"categories": engine.get_category_list(), "hints": config.CATEGORY_HINTS})


@app.route("/api/history")
def history():
    session.permanent = True
    conv = conversation_manager.conversation_state(session)
    return jsonify({"history": conv.history})


@app.route("/api/query", methods=["POST"])
def query():
    payload = request.get_json(force=True)
    message = payload.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty query", "result": None}), 400

    session.permanent = True
    if "uid" not in session:
        session["uid"] = str(uuid.uuid4())

    context = conversation_manager.conversation_state(session)
    intent = conversation_manager.detect_intent(message)
    if config.DEBUG_MODE:
        print(f"[QUERY] message={message}")
        print(f"[QUERY] detected_intent={intent}")
    results, score = engine.search(message, intent=intent)
    if config.DEBUG_MODE:
        titles = [doc.get('title') or doc.get('question') for doc in results[:5]]
        print(f"[SEARCH] results={len(results)} score={score:.4f} top={titles}")
    response_text, confidence, sources = build_response(message, results, score, intent, context, engine.get_category_list())
    if config.DEBUG_MODE:
        print(f"[FINAL] confidence={confidence:.4f} sources={sources}")
    context = conversation_manager.update_context(message, intent, results, context)
    conversation_manager.persist_state(session, context)
    session.modified = True

    debug_info = {
        "intent": intent,
        "query": message,
        "score": round(score, 4),
        "top_matches": [doc.get("title") or doc.get("question") for doc in results[:3]],
        "sources": sources,
    }

    return jsonify({
        "answer": response_text,
        "response": response_text,
        "confidence": round(confidence, 2),
        "sources": sources,
        "intent": intent,
        "debug": debug_info,
        "context": {
            "topic": context.last_topic,
            "entity": context.last_entity,
            "intent": context.last_intent,
        },
    })


if __name__ == "__main__":
    initialize_data_directories()
    port = int(os.environ.get("ECIL_ASSISTANT_PORT", 5020))
    app.run(host="0.0.0.0", port=port, threaded=True)
