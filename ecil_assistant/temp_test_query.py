from engine import KnowledgeEngine
from response_builder import build_response
from conversation import ConversationManager
engine = KnowledgeEngine()
conv = ConversationManager().create_context()
queries = [
    'defense projects done by ecil',
    'how to apply for internship in ecil hyderabad',
    'whats email to contact ecil'
]
for q in queries:
    results, score = engine.search(q)
    answer, confidence, sources = build_response(q, results, score, 'question', conv, engine.get_category_list())
    print('QUERY:', q)
    print('SCORE:', score)
    print('ANSWER:', answer)
    print('SOURCES:', sources)
    print('---')
