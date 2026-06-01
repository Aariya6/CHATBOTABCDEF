import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from engine import KnowledgeEngine
engine = KnowledgeEngine()
test_cases = [
    ('How do I apply for jobs at ECIL?', 'recruitment_query'),
    ('How do I apply for an internship at ECIL?', 'internship_query'),
]
for q, intent in test_cases:
    results, score = engine.search(q, intent=intent)
    query_vector, query_tokens = engine.get_query_vector(q, idf_map=engine.faq_idf)
    print('QUERY:', q)
    print('INTENT:', intent)
    print('TOKENS:', query_tokens)
    print('SCORE:', score)
    for r in results[:5]:
        doc_id = r.get('id')
        doc = engine.faq_doc_index.get(doc_id) or engine.doc_index.get(doc_id)
        query_vector, query_tokens = engine.get_query_vector(q, idf_map=engine.faq_idf)
        doc_score = engine.score_document(query_vector, r, query_tokens, normalized_query=q, use_faq=True, intent=intent)
        print('  id=', r.get('id'), 'title=', r.get('title') or r.get('question'), 'score=', doc_score)
    print()
