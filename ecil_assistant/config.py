import re

SITE_ROOT = "https://www.ecil.co.in"
DATA_FOLDER = "data"
KNOWLEDGE_BASE_PATH = "data/knowledge_base.json"
FAQ_BASE_PATH = "data/faq_base.json"
PROCESSED_DOCS_PATH = "data/processed_docs.json"
SYNONYM_MAP_PATH = "data/synonym_map.json"
CACHE_DB_PATH = "cache/query_cache.db"
LOG_FILE = "logs/app.log"

USER_AGENT = "ECIL-Offline-Assistant/1.0 (+https://www.ecil.co.in)"
REQUEST_TIMEOUT = 12
MAX_CRAWL_PAGES = 300  # ENHANCED: Increased from 120 to 300 for deeper content coverage

STOPWORDS = set([
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "this", "these", "those",
    "can", "may", "also", "into", "within", "which", "or", "but", "if",
    "such", "per", "each", "their", "they", "them", "then", "than",
    "when", "what", "who", "whom", "how", "why", "do", "does", "did",
    "have", "having", "should", "would", "could", "been", "over", "under",
    "more", "most", "other", "some", "any", "all", "no", "not", "only",
])

SYNONYM_MAP = {
    "evm": ["electronic voting machine", "voting machine", "ballot unit", "control unit", "election commission"],
    "nuclear": ["nuclear systems", "radiation", "reactor", "strategic electronics", "atomic energy", "nuclear power", "npcil", "barc"],
    "defense": ["defence", "military", "army", "navy", "air force", "drdo", "make-ii", "strategic", "aerospace", "weapons"],
    "railway": ["train", "signaling", "transportation", "track", "metro", "rail", "locomotive", "railway systems"],
    "communication": ["telecom", "radio", "satellite", "network", "link", "satcom", "communications", "wireless", "frequency"],
    "internship": ["intern", "internship", "training", "trainee", "apprentice", "student program", "industrial training", "itt", "gst"],
    "recruitment": ["job", "jobs", "career", "careers", "vacancy", "hiring", "employment", "application", "freshers", "freshers hiring", "walk-in", "walkin", "selection"],
    "contact": ["reach", "phone", "email", "address", "call", "enquiry", "inquiry", "office", "location"],
    "tenders": ["procurement", "bids", "notices", "contract", "vendor", "sourcing", "quotation", "rfq", "rfi"],
    "product": ["solution", "system", "platform", "product line", "product family", "offering"],
    "service": ["support", "maintenance", "installation", "service center", "customer support", "after-sales"],
    "project": ["initiative", "program", "collaboration", "portfolio", "program", "execution", "deployment"],
    "faq": ["question", "questions", "help", "faq", "frequently asked", "common question"],
    "hr": ["human resources", "payroll", "leave", "policy", "employee services", "benefits", "grievance", "welfare"],
    # ENHANCED: Additional synonyms for better coverage
    "quality": ["qms", "quality management system", "iso", "certification", "standard", "compliance", "quality assurance", "qa"],
    "research": ["r&d", "research and development", "innovation", "technical", "development", "lab", "laboratory"],
    "awards": ["achievement", "award", "recognition", "honour", "honor", "excellence", "certificate"],
    "sustainability": ["csr", "corporate social responsibility", "environment", "green", "eco-friendly", "renewable", "solar"],
    "division": ["division", "sbu", "strategic business unit", "department", "vertical", "business unit"],
    "component": ["electronic component", "semiconductor", "resistor", "capacitor", "transistor", "ic", "integrated circuit"],
    "antenna": ["antenna system", "rf", "radio frequency", "satellite antenna", "microwave", "communication antenna"],
    "security": ["x-ray", "scanner", "baggage scanner", "security system", "threat detection", "surveillance"],
    "smartcard": ["card", "smart card technology", "chip card", "identification", "payment card"],
    "smartmeter": ["meter", "smart meter", "energy meter", "electricity meter", "metering solution"],
    "servo": ["servo motor", "servo system", "motion control", "automation", "positioning"],
    "automation": ["control system", "industrial automation", "iot", "internet of things", "scada"],
    "solar": ["solar panel", "photovoltaic", "pv", "solar energy", "renewable energy", "solar system"],
    "computer": ["computer system", "embedded system", "computing", "processor", "server"],
    "instrument": ["electronic instrument", "measurement", "testing", "instrumentation", "oscilloscope"],
    "specification": ["spec", "technical spec", "datasheet", "brochure", "manual", "documentation"],
    "client": ["customer", "client", "end-user", "buyer", "consumer"],
    "supplier": ["vendor", "supplier", "distributor", "dealer", "reseller"],
}


QUERY_NORMALIZATION = {
    # Conservative: only fix surface-form variations. We DO NOT rewrite
    # one content word into a different one (e.g. apply -> application,
    # training -> internship) because that hides the original word from
    # documents that use the original form and is handled better by the
    # synonym map at query time.
    r"\bheadoffice\b": "head office",
    r"\bemail-id\b": "email",
}

FAQ_PRIORITIZATION_TERMS = [
    "internship",
    "intern",
    "recruitment",
    "job",
    "jobs",
    "careers",
    "career",
    "hr",
    "human resources",
    "contact",
    "email",
    "phone",
    "address",
    "tenders",
    "procurement",
    "vendor",
    "circular",
    "policy",
    "application",
    "apply",
    "faq",
    "frequently asked",
    "question",
    "questions",
    # ENHANCED: Additional prioritization terms for expanded content
    "how",
    "what",
    "when",
    "where",
    "why",
    "support",
    "help",
    "service",
    "care",
    "award",
    "achievement",
    "quality",
    "certification",
    "iso",
    "product",
    "specification",
    "datasheet",
    "technical",
    "research",
    "innovation",
    "training",
    "program",
    "benefits",
    "leave",
    "payroll",
    "grievance",
    "supplier",
    "dealer",
    "distributor",
    "case study",
    "project",
]

CATEGORY_MAP = {
    "products": "Product & Systems",
    "services": "Services & Technologies",
    "divisions": "Organizational Divisions",
    "solutions": "Solutions",
    "news": "News & Achievements",
    "contact": "Contact & Support",
    "internship": "Internship Information",
    "recruitment": "Recruitment",
    "hr": "HR Information",
    "overview": "ECIL Overview",
    "history": "Company History",
    "tenders": "Tender Information",
    "circular": "Circular Access",
    "navigation": "Website Navigation Help",
    "structure": "Organizational Structure",
    "faq": "Frequently Asked Questions",
    # ENHANCED: Additional category mappings for expanded content
    "press": "Press & Media",
    "media": "Press & Media",
    "awards": "Awards & Achievements",
    "achievements": "Awards & Achievements",
    "research": "Research & Development",
    "innovation": "Research & Development",
    "training": "Training & Development",
    "quality": "Quality & Certifications",
    "certifications": "Quality & Certifications",
    "iso": "Quality & Certifications",
    "sustainability": "Sustainability & CSR",
    "environment": "Sustainability & CSR",
    "policies": "Policies & Guidelines",
    "procurement": "Procurement & Supply Chain",
    "suppliers": "Procurement & Supply Chain",
    "clients": "Client & Customer Info",
    "case-studies": "Case Studies & Portfolio",
    "case_studies": "Case Studies & Portfolio",
    "projects": "Case Studies & Portfolio",
    "portfolio": "Case Studies & Portfolio",
    "technical": "Technical Documentation",
    "documentation": "Technical Documentation",
    "specifications": "Technical Documentation",
    "datasheet": "Technical Documentation",
    "downloads": "Downloads & Resources",
    "brochure": "Downloads & Resources",
    "annual-report": "Annual Reports & Financial",
    "annual_report": "Annual Reports & Financial",
    "financial": "Annual Reports & Financial",
    "freshers": "Recruitment",
    "job-vacancies": "Recruitment",
    "grievance": "HR Information",
    "help": "Frequently Asked Questions",
    "support": "Contact & Support",
    "customer-care": "Contact & Support",
    "service-centers": "Contact & Support",
    "dealers": "Procurement & Supply Chain",
    "distributors": "Procurement & Supply Chain",
}

PHRASE_OVERRIDES = {
    "evm": "Electronic Voting Machine",
    "ecil": "ECIL",
    "nuclear": "Nuclear",
    "hr": "HR",
    "drdo": "DRDO",
}

INTENT_PATTERNS = {
    "greeting": ["hello", "hi", "good morning", "good afternoon", "good evening", "hey"],
    "thanks": ["thank", "thanks", "appreciate", "thank you"],
    "goodbye": ["bye", "goodbye", "see you", "exit", "quit", "close"],
    "clarify": ["more", "explain", "how", "why", "detail", "information", "describe"],
    "help": ["help", "support", "assist", "direction", "guide", "navigation"],
    "internship_query": ["intern", "internship", "trainee", "apprentice", "training", "industrial training"],
    "recruitment_query": ["recruit", "hiring", "vacancy", "walk-in", "selection", "jobs", "job", "career", "careers", "freshers"],
    "contact_query": ["contact", "email", "phone", "address", "reach", "call", "enquiry"],
    "organization_overview": ["what does ecil do", "what is ecil", "company overview", "about ecil", "business vertical", "domain"],
    "navigation_help": ["where can i", "how do i", "where is", "how to access", "where are"],
    "hr_query": ["hr", "human resources", "payroll", "leave", "policy"],
    "faq_query": ["faq", "frequently asked", "common questions", "questions"],
    "procedural_query": ["procedure", "process", "steps", "apply", "submit", "register"],
    "fallback": ["not sure", "don\'t know", "unknown", "help me find"],
}

CATEGORY_HINTS = [
    "Internship & Careers",
    "Defense Electronics",
    "Nuclear Systems",
    "Railway Electronics",
    "Communication Systems",
    "Tenders & Circulars",
    "Contact Information",
    "Products & Services",
    "Organizational Structure",
    "HR & Recruitment",
]

DEBUG_MODE = True

URL_IGNORE_PATTERNS = [
    "#", "?", ".pdf", ".jpg", ".png", ".jpeg", ".svg", ".gif", "mailto:", "tel:", "facebook.com",
    "twitter.com", "linkedin.com", "youtube.com", "instagram.com"
]

NORMALIZE_WHITESPACE = re.compile(r"\s+")

DEFAULT_CONFIDENCE_THRESHOLD = 0.28
HIGH_CONFIDENCE_THRESHOLD = 0.60
LOW_CONFIDENCE_THRESHOLD = 0.18

# Website fallback: opt-in. When enabled, the engine will attempt to fetch
# configured ECIL pages when local FAQ/KB cannot provide a confident answer.
ENABLE_WEBSITE_FALLBACK = False
FALLBACK_CONFIDENCE_THRESHOLD = 0.20
FALLBACK_URLS = [
    "https://www.ecil.co.in/careers",
    "https://www.ecil.co.in/contact-us",
    "https://www.ecil.co.in/about-us",
    "https://www.ecil.co.in/divisions/defense",
    "https://www.ecil.co.in/tenders",
]
