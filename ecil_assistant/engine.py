"""ECIL offline knowledge engine.

Lightweight BM25 (Okapi) retrieval over the local JSON knowledge base
and FAQ base. Designed to fit on a 4 GB / Intel i3 office PC: pure
Python, no ML libraries, ~12 MB resident.

Ranking pipeline (per query):
    1. Normalize the query (regex rewrites + lowercase).
    2. Tokenize with stop-words + Porter-lite suffix stripping.
    3. Synonym expansion via the reverse index built from
       data/synonym_map.json.
    4. Bigram extraction from the raw normalized query - helps phrase
       queries like "ballot unit" or "control unit" rank above
       documents that only mention one of the two tokens.
    5. Candidate gathering through an inverted index (postings).
    6. Per-document score = BM25(unigrams) + alpha * BM25(bigrams) +
       field boosts (title / question / category / tag / keyword
       match) + exact-phrase boost.
    7. Sort, take top-k, persist to SQLite query cache.

For FAQs the same pipeline runs against a separate index keyed on the
'question' + 'answer' fields. FAQs are preferred when the query
contains FAQ-prioritisation terms (recruitment, contact, internship,
tenders, etc.) so short-direct questions resolve quickly.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Dict, List, Tuple

import config
import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def load_json_file(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

_WORD_SPLIT = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _stem(token: str) -> str:
    # Conservative stemmer: only strip suffixes if the surviving stem is
    # >= 4 chars. This avoids collapsing distinct content words into common
    # roots (e.g. "training" -> "train" would conflate the HR sense with
    # the railway sense even though the synonym map keeps them separate).
    if len(token) <= 5:
        return token
    for suffix in ("ingly", "ations", "ation", "ings", "ing", "ions", "ion",
                   "ments", "ment", "ness", "ated", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> List[str]:
    raw = normalize_text(text)
    tokens = []
    for word in raw.split():
        if not word or word in config.STOPWORDS or len(word) < 2:
            continue
        # Split hyphenated compounds: "walk-in" -> ["walk", "in"] but keep "walk-in" too.
        if "-" in word:
            tokens.append(word)
            for piece in word.split("-"):
                if piece and piece not in config.STOPWORDS and len(piece) >= 2:
                    tokens.append(_stem(piece))
            continue
        tokens.append(_stem(word))
    return tokens


def bigrams(tokens: List[str]) -> List[str]:
    return [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]


# ---------------------------------------------------------------------------
# Synonym expansion
# ---------------------------------------------------------------------------

def build_synonym_reverse_index(synonym_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Return token -> [alias tokens] map.

    Only SINGLE-TOKEN aliases participate in the reverse index. Multi-token
    aliases (e.g. "smart card", "voter verifiable paper audit trail") are
    intentionally dropped here so they cannot pollute single-token clusters
    by sharing a generic word like "smart" between "smart card" and
    "smart meter". Multi-token phrase matching is handled separately by the
    bigram index and the exact-phrase boost in `_field_boost`.
    """
    reverse: Dict[str, List[str]] = {}
    for key, aliases in synonym_map.items():
        cluster: List[str] = []
        for term in [key] + list(aliases):
            toks = tokenize(term)
            if len(toks) == 1 and toks[0] not in cluster:
                cluster.append(toks[0])
        for tok in cluster:
            existing = reverse.setdefault(tok, [])
            for other in cluster:
                if other != tok and other not in existing:
                    existing.append(other)
    return reverse


def expand_with_synonyms(tokens: List[str], reverse_index: Dict[str, List[str]]) -> List[str]:
    if not reverse_index:
        return list(tokens)
    expanded: List[str] = []
    seen = set()
    for tok in tokens:
        if tok not in seen:
            expanded.append(tok)
            seen.add(tok)
        for alias in reverse_index.get(tok, ()):
            if alias not in seen:
                expanded.append(alias)
                seen.add(alias)
    return expanded


# ---------------------------------------------------------------------------
# HTML fallback fetch (only used when ENABLE_WEBSITE_FALLBACK is true)
# ---------------------------------------------------------------------------

def _extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    parts: List[str] = []
    for selector in ("main", "article"):
        block = soup.find(selector)
        if not block:
            continue
        for p in block.find_all("p"):
            text = re.sub(r"\s+", " ", p.get_text()).strip()
            if len(text) > 30:
                parts.append(text)
        if parts:
            break
    if not parts:
        for p in soup.find_all("p"):
            text = re.sub(r"\s+", " ", p.get_text()).strip()
            if len(text) > 40:
                parts.append(text)
    return "\n\n".join(parts)


def fetch_page_text(url: str, timeout: int = 8) -> str:
    try:
        resp = requests.get(url, timeout=timeout,
                            headers={"User-Agent": "ECIL-Assistant/1.0"})
        resp.raise_for_status()
        return _extract_main_text(resp.text)
    except Exception:  # pragma: no cover - network path
        return ""


# ---------------------------------------------------------------------------
# Knowledge engine
# ---------------------------------------------------------------------------

class _BM25Index:
    """Self-contained Okapi BM25 index over a token-stream collection."""

    K1 = 1.5
    B = 0.75

    def __init__(self) -> None:
        self.doc_tokens: Dict[str, List[str]] = {}
        self.doc_len: Dict[str, int] = {}
        self.tf: Dict[str, Counter] = {}
        self.df: Counter = Counter()
        self.idf: Dict[str, float] = {}
        self.postings: Dict[str, set] = defaultdict(set)
        self.avg_len: float = 0.0
        self.total_docs: int = 0

    def add(self, doc_id: str, tokens: List[str]) -> None:
        self.doc_tokens[doc_id] = tokens
        counts = Counter(tokens)
        self.tf[doc_id] = counts
        self.doc_len[doc_id] = len(tokens)
        for term in counts:
            self.df[term] += 1
            self.postings[term].add(doc_id)

    def finalize(self) -> None:
        self.total_docs = len(self.doc_tokens)
        self.avg_len = (sum(self.doc_len.values()) / self.total_docs) if self.total_docs else 0.0
        # Robertson/Sparck Jones IDF, floored at 0.05 so very common terms
        # still contribute a tiny amount.
        for term, df in self.df.items():
            num = self.total_docs - df + 0.5
            den = df + 0.5
            self.idf[term] = max(0.05, math.log(1.0 + num / den))

    def candidates(self, terms: List[str]) -> set:
        ids: set = set()
        for term in set(terms):
            ids.update(self.postings.get(term, ()))
        return ids

    def score(self, doc_id: str, query_terms: List[str]) -> float:
        counts = self.tf.get(doc_id)
        if not counts:
            return 0.0
        dl = self.doc_len[doc_id] or 1
        if self.avg_len <= 0:
            norm = 1.0
        else:
            norm = 1 - self.B + self.B * dl / self.avg_len
        total = 0.0
        for term in query_terms:
            tf = counts.get(term)
            if not tf:
                continue
            idf = self.idf.get(term, 0.0)
            total += idf * ((tf * (self.K1 + 1)) / (tf + self.K1 * norm))
        return total


class KnowledgeEngine:
    """Search engine over the local KB + FAQ JSON stores."""

    # Weight used to blend bigram BM25 into the unigram score.
    BIGRAM_WEIGHT = 0.65
    # Cap so that field/phrase boosts can't dominate a low-relevance match.
    BOOST_CAP = 4.0

    def __init__(self, knowledge_path=None, faq_path=None,
                 synonym_path=None, cache_db_path=None) -> None:
        self.knowledge_path = knowledge_path or config.KNOWLEDGE_BASE_PATH
        self.faq_path = faq_path or config.FAQ_BASE_PATH
        self.synonym_path = synonym_path or config.SYNONYM_MAP_PATH
        self.cache_db_path = cache_db_path or config.CACHE_DB_PATH

        self.documents: List[dict] = []
        self.faq_documents: List[dict] = []
        self.doc_index: Dict[str, dict] = {}
        self.faq_doc_index: Dict[str, dict] = {}
        self.categories: set = set()

        # Two BM25 indexes per collection: one over unigrams, one over bigrams.
        self.kb_uni = _BM25Index()
        self.kb_bi = _BM25Index()
        self.faq_uni = _BM25Index()
        self.faq_bi = _BM25Index()

        # Cached normalized text for boost computation (avoid re-tokenizing).
        self._doc_norm_blob: Dict[str, str] = {}
        self._doc_norm_title: Dict[str, str] = {}

        self.synonym_map: Dict[str, List[str]] = {}
        self.synonym_reverse_index: Dict[str, List[str]] = {}

        self._initialize_cache()
        self.load_data()

    # -- cache --------------------------------------------------------------

    def _initialize_cache(self) -> None:
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS query_cache ("
                "  query TEXT PRIMARY KEY, response TEXT, "
                "  score REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute("DELETE FROM query_cache")
        conn.close()

    def clear_cache(self) -> None:
        conn = sqlite3.connect(self.cache_db_path)
        with conn:
            conn.execute("DELETE FROM query_cache")
        conn.close()

    def _cache_get(self, query: str):
        conn = sqlite3.connect(self.cache_db_path)
        row = conn.execute(
            "SELECT response, score FROM query_cache WHERE query = ?",
            (query,),
        ).fetchone()
        conn.close()
        return row

    def _cache_put(self, query: str, response: str, score: float) -> None:
        conn = sqlite3.connect(self.cache_db_path)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO query_cache "
                "(query, response, score) VALUES (?, ?, ?)",
                (query, response, score),
            )
        conn.close()

    # -- loading ------------------------------------------------------------

    def load_data(self) -> None:
        self.documents = load_json_file(self.knowledge_path, [])
        self.faq_documents = load_json_file(self.faq_path, [])
        self.doc_index = {d["id"]: d for d in self.documents}
        self.faq_doc_index = {d["id"]: d for d in self.faq_documents}
        self.categories = {d.get("category", "General") for d in self.documents}

        self.synonym_map = load_json_file(self.synonym_path, config.SYNONYM_MAP)
        self.synonym_reverse_index = build_synonym_reverse_index(self.synonym_map)

        self._build_indexes()

        if config.DEBUG_MODE:
            print(f"[ENGINE] KB={len(self.documents)} docs "
                  f"avg_len={self.kb_uni.avg_len:.1f}; "
                  f"FAQ={len(self.faq_documents)} entries "
                  f"avg_len={self.faq_uni.avg_len:.1f}")

    def _doc_text(self, doc: dict) -> str:
        # Title weighted 3x by repetition to give it lexical emphasis.
        title = doc.get("title") or doc.get("question") or ""
        parts = [title, title, title,
                 doc.get("summary", ""),
                 doc.get("answer", ""),
                 doc.get("content", ""),
                 " ".join(doc.get("keywords", []) or []),
                 " ".join(doc.get("tags", []) or []),
                 doc.get("category", "")]
        return " ".join(p for p in parts if p)

    def _build_indexes(self) -> None:
        self.kb_uni = _BM25Index()
        self.kb_bi = _BM25Index()
        self.faq_uni = _BM25Index()
        self.faq_bi = _BM25Index()
        self._doc_norm_blob.clear()
        self._doc_norm_title.clear()

        # Index documents with their own vocabulary only. Synonym expansion
        # happens at query time. Expanding at index time conflates clusters
        # (e.g. doc-19 "smart meter" gets credit for "smart card" queries)
        # and inflates per-term IDF in unhelpful ways.
        for doc in self.documents:
            blob = self._doc_text(doc)
            tokens = tokenize(blob)
            self.kb_uni.add(doc["id"], tokens)
            self.kb_bi.add(doc["id"], bigrams(tokens))
            self._doc_norm_blob[doc["id"]] = normalize_text(blob)
            self._doc_norm_title[doc["id"]] = normalize_text(
                doc.get("title") or doc.get("question") or ""
            )

        for doc in self.faq_documents:
            blob = self._doc_text(doc)
            tokens = tokenize(blob)
            self.faq_uni.add(doc["id"], tokens)
            self.faq_bi.add(doc["id"], bigrams(tokens))
            self._doc_norm_blob[doc["id"]] = normalize_text(blob)
            self._doc_norm_title[doc["id"]] = normalize_text(
                doc.get("title") or doc.get("question") or ""
            )

        self.kb_uni.finalize()
        self.kb_bi.finalize()
        self.faq_uni.finalize()
        self.faq_bi.finalize()

    # -- query handling -----------------------------------------------------

    @lru_cache(maxsize=512)
    def normalize_query(self, query: str) -> str:
        normalized = query.lower()
        for pattern, replacement in config.QUERY_NORMALIZATION.items():
            normalized = re.sub(pattern, replacement, normalized)
        return normalized

    def _build_query(self, query: str) -> Tuple[List[str], List[str], str]:
        normalized = self.normalize_query(query)
        base_tokens = tokenize(normalized)
        expanded = expand_with_synonyms(base_tokens, self.synonym_reverse_index)
        # Bigrams use the un-expanded sequence so phrase boost stays meaningful.
        bg = bigrams(base_tokens)
        return expanded, bg, normalized

    # Question-word stop list used only when computing FAQ overlap.
    _QUESTION_WORDS = {"what", "which", "who", "whom", "where", "when",
                       "why", "how", "is", "are", "do", "does", "did",
                       "can", "could", "should", "would", "will", "shall",
                       "tell", "me", "about", "explain", "describe", "give",
                       "list", "the", "a", "an", "of", "for", "in", "to",
                       "on", "at", "by", "with", "and", "or", "from"}

    def _content_words(self, text: str) -> set:
        """Lower-cased content words with question-words removed."""
        return {w for w in normalize_text(text).split()
                if w and w not in self._QUESTION_WORDS and len(w) > 1}

    def _field_boost(self, doc: dict, query_tokens: List[str],
                     normalized_query: str, intent: str = None) -> float:
        doc_id = doc["id"]
        title_norm = self._doc_norm_title.get(doc_id, "")
        blob_norm = self._doc_norm_blob.get(doc_id, "")
        cat = normalize_text(doc.get("category", ""))
        tags_norm = normalize_text(" ".join(doc.get("tags", []) or []))
        keywords_norm = normalize_text(" ".join(doc.get("keywords", []) or []))

        raw_q_tokens = [t for t in normalized_query.split()
                        if t and t not in config.STOPWORDS]
        q_set = set(raw_q_tokens)
        q_content = self._content_words(normalized_query)

        boost = 0.0
        # Title content-word overlap, normalised by query size. Strong
        # signal because titles are short and topical.
        if q_content and title_norm:
            title_words = self._content_words(title_norm)
            if title_words:
                overlap = q_content & title_words
                if overlap:
                    coverage = len(overlap) / len(q_content)
                    # Up to +2.5 when every content word is in the title.
                    boost += 2.5 * coverage
                    # Bonus when the title also doesn't contain extra
                    # noise relative to the query (tight title match).
                    if len(overlap) == len(title_words):
                        boost += 0.6
        if any(t in tags_norm for t in q_set):
            boost += 0.4
        if any(t in keywords_norm for t in q_set):
            boost += 0.3
        if any(t in cat for t in q_set):
            boost += 0.35

        # Exact / near-exact phrase match.
        phrase = normalized_query.strip()
        if len(phrase) >= 8 and phrase in blob_norm:
            boost += 1.0
        if len(phrase) >= 8 and phrase in title_norm:
            boost += 1.6

        # Contiguous bigram match against title (very high precision).
        for i in range(len(raw_q_tokens) - 1):
            bg = f"{raw_q_tokens[i]} {raw_q_tokens[i + 1]}"
            if bg in title_norm:
                boost += 0.6
            elif bg in blob_norm:
                boost += 0.2

        # Intent-aligned category snaps.
        if intent == "contact_query" and cat in {"contact & support"}:
            boost += 0.8
        if intent == "recruitment_query" and cat in {"recruitment", "hr information"}:
            boost += 0.6
        if intent == "internship_query" and cat in {"internship information"}:
            boost += 0.6
        if intent == "hr_query" and cat in {"hr information"}:
            boost += 0.5
        if intent == "organization_overview" and cat in {"ecil overview", "company history"}:
            boost += 0.5
        if intent == "faq_query" and cat in {"frequently asked questions"}:
            boost += 0.6

        return min(boost, self.BOOST_CAP)

    def _score_collection(self, query_tokens: List[str], bigram_tokens: List[str],
                          normalized_query: str, uni_index: _BM25Index,
                          bi_index: _BM25Index, doc_lookup: Dict[str, dict],
                          intent: str = None) -> List[Tuple[float, dict]]:
        cand_ids = uni_index.candidates(query_tokens)
        if bigram_tokens:
            cand_ids |= bi_index.candidates(bigram_tokens)
        if not cand_ids:
            return []
        scored: List[Tuple[float, dict]] = []
        for doc_id in cand_ids:
            doc = doc_lookup.get(doc_id)
            if not doc:
                continue
            uni = uni_index.score(doc_id, query_tokens)
            bi = bi_index.score(doc_id, bigram_tokens) if bigram_tokens else 0.0
            base = uni + self.BIGRAM_WEIGHT * bi
            boost = self._field_boost(doc, query_tokens, normalized_query, intent=intent)
            scored.append((base + boost, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    # -- public API ---------------------------------------------------------

    def search(self, query: str, intent: str = None) -> Tuple[List[dict], float]:
        if not query or not query.strip():
            return [], 0.0
        cached = self._cache_get(query)
        if cached:
            return json.loads(cached[0]), cached[1]

        expanded_tokens, bg_tokens, normalized = self._build_query(query)

        faq_should_lead = (
            intent in {"faq_query", "procedural_query", "contact_query",
                       "internship_query", "recruitment_query",
                       "navigation_help", "hr_query", "organization_overview",
                       "help"}
            or any(term in normalized for term in config.FAQ_PRIORITIZATION_TERMS)
        )

        faq_scored: List[Tuple[float, dict]] = []
        kb_scored: List[Tuple[float, dict]] = []

        if self.faq_documents:
            faq_scored = self._score_collection(
                expanded_tokens, bg_tokens, normalized,
                self.faq_uni, self.faq_bi, self.faq_doc_index, intent=intent,
            )
        if self.documents:
            kb_scored = self._score_collection(
                expanded_tokens, bg_tokens, normalized,
                self.kb_uni, self.kb_bi, self.doc_index, intent=intent,
            )

        # Merge: when the intent looks FAQ-shaped we give FAQ a small lift
        # so a direct Q&A wins over a paragraph-style doc; otherwise both
        # collections compete on raw BM25 score.
        faq_boost = 0.6 if faq_should_lead else 0.0
        merged: List[Tuple[float, dict]] = (
            [(s + faq_boost, d) for s, d in faq_scored] + list(kb_scored)
        )
        merged.sort(key=lambda item: item[0], reverse=True)

        top = [doc for _, doc in merged[:5]]
        top_score = round(merged[0][0], 4) if merged else 0.0

        # Out-of-vocabulary fallback: if no token in the query matched any
        # posting, BM25 found nothing. Instead of returning an empty list
        # (which gives the user a cold "no results" message), surface the
        # docs that best overlap the raw query string by character n-grams.
        # This is how we keep the chatbot useful for tangential queries
        # like "brahmos", "isro", or "smart city" that don't exist verbatim
        # in our KB but are conceptually adjacent to existing docs.
        if not top:
            fuzzy = self._fuzzy_fallback(normalized)
            if fuzzy:
                top = [d for _, d in fuzzy[:5]]
                top_score = round(fuzzy[0][0], 4)

        if config.DEBUG_MODE:
            titles = [d.get("title") or d.get("question") for d in top[:3]]
            print(f"[SEARCH] intent={intent} q={normalized!r} "
                  f"top_score={top_score:.3f} top={titles}")

        # Optional live website fallback (off by default).
        if (not top or top_score < config.FALLBACK_CONFIDENCE_THRESHOLD) \
                and config.ENABLE_WEBSITE_FALLBACK:
            fb = self._website_fallback(expanded_tokens, bg_tokens, normalized)
            if fb:
                top, top_score = fb[:3], round(fb[0]["score"], 4) if hasattr(fb[0], "get") else top_score
                # store and return
                self._cache_put(query, json.dumps(top, ensure_ascii=False), top_score)
                return top, top_score

        self._cache_put(query, json.dumps(top, ensure_ascii=False), top_score)
        return top, top_score

    def _fuzzy_fallback(self, normalized_query: str) -> List[Tuple[float, dict]]:
        """Character-trigram overlap fallback for OOV queries.

        Returns up to 10 (score, doc) tuples ranked by Jaccard similarity
        between the query's char trigrams and each doc's title trigrams,
        with a small bonus for query terms appearing anywhere in the doc
        blob. Score is mapped into roughly the BM25 numeric range so the
        confidence display behaves sensibly (typically 0.3-1.5, meaning
        the UI shows ~20-40% confidence - honest for a fuzzy hit).
        """
        q = (normalized_query or "").strip().lower()
        if len(q) < 2:
            return []
        q_trigrams = self._trigrams(q)
        if not q_trigrams:
            return []

        q_words = [w for w in q.split() if w and w not in config.STOPWORDS and len(w) >= 3]

        scored: List[Tuple[float, dict]] = []
        for doc_id, blob in self._doc_norm_blob.items():
            title = self._doc_norm_title.get(doc_id, "")
            t_trigrams = self._trigrams(title)
            if not t_trigrams:
                continue
            inter = len(q_trigrams & t_trigrams)
            if inter == 0 and not any(w in blob for w in q_words):
                continue
            union = max(1, len(q_trigrams | t_trigrams))
            jacc = inter / union
            word_hits = sum(1 for w in q_words if w in blob)
            # Scale into ~BM25 range; jacc 0.3 -> ~1.5, plus 0.5 per word hit
            score = jacc * 5.0 + 0.5 * word_hits
            if score <= 0:
                continue
            doc = self.doc_index.get(doc_id) or self.faq_doc_index.get(doc_id)
            if doc:
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:10]

    @staticmethod
    def _trigrams(text: str) -> set:
        if not text:
            return set()
        clean = re.sub(r"[^a-z0-9 ]", " ", text.lower())
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            return set()
        padded = f" {clean} "
        return {padded[i:i + 3] for i in range(len(padded) - 2)}

    def _website_fallback(self, query_tokens, bg_tokens, normalized):
        # Minimal, opt-in. Keeps the original behaviour but uses the BM25
        # index built on-the-fly for each page.
        results = []
        for url in config.FALLBACK_URLS:
            text = fetch_page_text(url)
            if not text:
                continue
            idx_u = _BM25Index()
            idx_b = _BM25Index()
            tokens = expand_with_synonyms(tokenize(text), self.synonym_reverse_index)
            idx_u.add(url, tokens)
            idx_b.add(url, bigrams(tokens))
            idx_u.finalize()
            idx_b.finalize()
            score = idx_u.score(url, query_tokens) + self.BIGRAM_WEIGHT * idx_b.score(url, bg_tokens)
            if score > 0:
                results.append({"id": f"live-{abs(hash(url)) % 10000}",
                                "title": url, "content": text,
                                "source_url": url, "score": score})
        results.sort(key=lambda d: d["score"], reverse=True)
        return results

    # -- convenience --------------------------------------------------------

    def suggest_topics(self, score: float):
        if score < config.LOW_CONFIDENCE_THRESHOLD:
            return sorted(self.categories)[:6]
        return []

    def get_category_list(self):
        return sorted(self.categories)

    def reload(self):
        self.normalize_query.cache_clear()
        self.clear_cache()
        self.load_data()

    # ---- compatibility shims (callers in tools/ and old tests) ------------

    @lru_cache(maxsize=1024)
    def tokenize(self, text):  # pragma: no cover - exposed for tests
        return tokenize(text)

    def get_query_vector(self, query, idf_map=None):  # pragma: no cover
        tokens = expand_with_synonyms(tokenize(self.normalize_query(query)),
                                      self.synonym_reverse_index)
        return Counter(tokens), tokens

    def score_document(self, query_vector, doc, query_tokens,
                       normalized_query="", use_faq=False, intent=None):  # pragma: no cover
        uni = self.faq_uni if use_faq else self.kb_uni
        bi = self.faq_bi if use_faq else self.kb_bi
        bg = bigrams(tokenize(normalized_query))
        base = uni.score(doc["id"], query_tokens) + self.BIGRAM_WEIGHT * bi.score(doc["id"], bg)
        return round(base + self._field_boost(doc, query_tokens, normalized_query, intent=intent), 4)


if __name__ == "__main__":
    engine = KnowledgeEngine()
    print(f"Loaded {len(engine.documents)} KB docs, "
          f"{len(engine.faq_documents)} FAQs.")
