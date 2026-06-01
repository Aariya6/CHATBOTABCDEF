# ECIL Offline Knowledge Assistant

## Project Overview

The ECIL Offline Knowledge Assistant is a lightweight, enterprise-style internal helpdesk system designed for restricted LAN deployment. It runs fully offline after initial data collection and uses a deterministic retrieval engine built on local ECIL website content.

## Features

- Full offline knowledge retrieval from ECIL website content
- Custom scraper for ECIL pages, including products, services, divisions, projects, and FAQs
- Lightweight TF-IDF search engine with cosine similarity, keyword boosting, and synonyms
- Conversational session memory and follow-up handling
- Dark professional single-page UI with sidebar categories and quick prompts
- Local SQLite query cache and JSON knowledge store
- LAN-ready deployment on Windows 10 with Intel i3 / 4GB RAM

## Architecture Diagram

1. `scraper.py` collects and normalizes ECIL website pages
2. `data/knowledge_base.json` stores structured content
3. `engine.py` preprocesses content, builds TF-IDF index, and retrieves matches
4. `conversation.py` manages user session state and follow-up intent
5. `response_builder.py` composes professional answers
6. `app.py` serves Flask UI and API endpoints

## Folder Structure

```
ecim_assistant/
  app.py
  scraper.py
  engine.py
  conversation.py
  response_builder.py
  config.py
  requirements.txt
  README.md
  test_queries.py
  data/
    knowledge_base.json
    processed_docs.json
    synonym_map.json
  cache/
    query_cache.db
  templates/
    index.html
  static/
    style.css
    app.js
    logo.png
  logs/
    app.log
```

## Installation

1. Ensure Python 3.10+ is installed.
2. Open a terminal in `ecil_assistant`.
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Offline Deployment

1. Run the scraper once while connected to the internet:

```bash
python scraper.py
```

2. Confirm `data/knowledge_base.json` contains entries.
3. Start the Flask app:

```bash
python app.py
```

4. Access locally:

```text
http://localhost:5020
```

If port `5020` is already in use, set a custom port before launch:

```bash
set ECIL_ASSISTANT_PORT=5030
python app.py
```

After this, the system remains offline and continues working with the local knowledge base.

## LAN Deployment

Run the Flask application and access it from other machines on the same network:

```text
http://<machine-ip>:5000
```

Example:

```text
http://192.168.1.100:5000
```

## Updating Scraped Data

To refresh the knowledge base:

```bash
python scraper.py
```

This updates `data/knowledge_base.json` incrementally and preserves existing entries.

## Adding New Knowledge

1. Add a new JSON entry to `data/knowledge_base.json`.
2. Use the same entry format:

```json
{
  "id": "doc-999",
  "title": "Example Page",
  "category": "Services",
  "keywords": ["example", "service"],
  "tags": ["ECIL", "service"],
  "source_url": "https://www.ecil.co.in/example",
  "content": "Detailed content about the topic.",
  "summary": "Short summary of the topic."
}
```

3. Restart `app.py` to reload the index.

## Troubleshooting

- If the page fails to load, verify Flask is running and the port is available.
- If search results are empty, ensure `data/knowledge_base.json` contains structured documents.
- If the scraper misses pages, confirm the network can reach `https://www.ecil.co.in` and try again.
- Use `logs/app.log` for runtime messages and errors.

## Performance Notes

- Startup: under 5 seconds on modern low-memory hardware
- Query response: typically under 2 seconds
- Uses in-memory TF-IDF index and local SQLite cache for speed
- Designed for lightweight CPU and RAM usage

## Limitations

- Retrieval is deterministic; it does not use generative transformers
- Responses depend on the quality of scraped website content
- Pronoun resolution is simple and optimized for follow-up questions only

## Future Improvements

- Add a browser scheduler to refresh data automatically
- Expand synonym mapping with ECIL-specific entities
- Add a lightweight export for PDF or email responses
- Add admin mode for manual knowledge editing

## Technical Design Decisions

- `scraper.py` uses `requests` and `BeautifulSoup4` for reliable offline collection
- `engine.py` implements TF-IDF and cosine similarity without external ML libraries
- `conversation.py` tracks user context and resolves follow-up references
- `response_builder.py` composes paragraphs rather than raw document dumps

## Memory Optimization Strategy

- Data is preprocessed once at startup
- Search indexes are cached in simple dictionaries
- Optional query cache stored in local SQLite database
- Minimal runtime state is kept per user session

## Search Engine Explanation

The engine tokenizes text, removes stopwords, merges synonyms, computes term frequency and inverse document frequency, and ranks documents by cosine similarity. It adds boosting for title matches, tags, and category alignment.

## Conversation Engine Explanation

The conversation layer identifies greetings, thanks, goodbyes, clarifications, and follow-up queries. It stores the last topic and entity so the assistant can answer follow-up questions like "How is it secure?" after an earlier topic.

## to run it ##### IMPORTANT ONE COMMAND RUN
cd "C:\Users\BIT\Downloads\ecil chatbot 2026\ecil_assistant"
>> ..\venv\Scripts\python.exe app.py
