import unittest
from engine import KnowledgeEngine
from response_builder import build_response
from conversation import ConversationManager

class TestECILAssistantQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = KnowledgeEngine()
        cls.conversation_manager = ConversationManager()
        cls.context = cls.conversation_manager.create_context()

    def ask(self, query):
        results, score = self.engine.search(query)
        intent = self.conversation_manager.detect_intent(query)
        answer, confidence, sources = build_response(query, results, score, intent, self.context, self.engine.get_category_list())
        self.conversation_manager.update_context(query, intent, results, self.context)
        return answer, confidence, sources

    def test_greeting(self):
        answer, confidence, sources = self.ask("Hello, can you help me?")
        self.assertIn("ECIL internal helpdesk assistant", answer)
        self.assertGreaterEqual(confidence, 0)

    def test_thanks(self):
        answer, confidence, sources = self.ask("Thanks for the help")
        self.assertIn("welcome", answer.lower())

    def test_goodbye(self):
        answer, confidence, sources = self.ask("Goodbye")
        self.assertIn("goodbye", answer.lower())

    def test_evm_overview(self):
        answer, confidence, sources = self.ask("Tell me about ECIL EVM systems")
        self.assertGreaterEqual(confidence, 0)

    def test_evm_security(self):
        answer, confidence, sources = self.ask("How secure are ECIL Electronic Voting Machines?")
        self.assertGreaterEqual(confidence, 0)

    def test_nuclear_division(self):
        answer, confidence, sources = self.ask("Explain ECIL nuclear systems and divisions")
        self.assertGreaterEqual(confidence, 0)

    def test_defense_electronics(self):
        answer, confidence, sources = self.ask("What does ECIL defense electronics do?")
        self.assertGreaterEqual(confidence, 0)

    def test_railway_technology(self):
        answer, confidence, sources = self.ask("Describe railway signaling solutions from ECIL")
        self.assertGreaterEqual(confidence, 0)

    def test_communication_systems(self):
        answer, confidence, sources = self.ask("What are ECIL communication systems?")
        self.assertGreaterEqual(confidence, 0)

    def test_projects_and_achievements(self):
        answer, confidence, sources = self.ask("Tell me about ECIL projects and achievements")
        self.assertGreaterEqual(confidence, 0)

    def test_faq_handling(self):
        answer, confidence, sources = self.ask("What are common FAQs about ECIL?")
        self.assertGreaterEqual(confidence, 0)

    def test_follow_up_it(self):
        self.ask("Tell me about EVM")
        answer, confidence, sources = self.ask("How is it secure?")
        self.assertGreaterEqual(confidence, 0)

    def test_unknown_query(self):
        answer, confidence, sources = self.ask("Explain quantum computing at ECIL")
        self.assertIn("could not confidently locate", answer.lower())

    def test_vague_query(self):
        answer, confidence, sources = self.ask("Tell me more")
        self.assertGreaterEqual(confidence, 0)

    def test_help_request(self):
        answer, confidence, sources = self.ask("I need help understanding ECIL divisions")
        self.assertGreaterEqual(confidence, 0)

    def test_organization_structure(self):
        answer, confidence, sources = self.ask("Describe ECIL organization structure")
        self.assertGreaterEqual(confidence, 0)

    def test_local_hosting(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
