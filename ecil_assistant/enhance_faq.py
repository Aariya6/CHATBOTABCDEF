"""
Enhance FAQ base with additional entries covering new content areas.
This script adds new FAQ entries without removing or modifying existing ones.
"""

import json

# Load existing FAQ
with open('data/faq_base.json', 'r', encoding='utf-8') as f:
    faq_base = json.load(f)

# Get the next FAQ ID
next_id = int(max([int(faq['id'].split('-')[1]) for faq in faq_base], default=0)) + 1

# New FAQ entries for enhanced coverage
new_faqs = [
    {
        "id": f"faq-{next_id}",
        "question": "What is ECIL's market reach and client base?",
        "answer": "ECIL serves defence forces (Army, Navy, Air Force, Coast Guard), paramilitary organizations, DRDO, space agencies (ISRO), the Election Commission of India, state governments, private sector and international clients in aerospace, communications and security.",
        "category": "ECIL Overview",
        "tags": ["clients", "market", "defense", "civil"],
        "source_url": "https://www.ecil.co.in/about"
    },
    {
        "id": f"faq-{next_id+1}",
        "question": "Does ECIL export products internationally?",
        "answer": "Yes. ECIL exports electronics and systems to select countries under Government of India export policy guidelines, focusing on regional partners in Asia, Africa and other friendly nations in defence and civilian sectors.",
        "category": "ECIL Overview",
        "tags": ["export", "international", "global"],
        "source_url": "https://www.ecil.co.in/about"
    },
    {
        "id": f"faq-{next_id+2}",
        "question": "What is ECIL's role in India's space program?",
        "answer": "ECIL provides specialized antennas, tracking systems, RF sub-systems and communication payloads for ISRO's satellites and deep-space missions like Chandrayaan and Mangalyaan. ECIL manufactures Deep Space Network Antennas for satellite communication.",
        "category": "Aerospace",
        "tags": ["space", "ISRO", "satellite", "chandrayaan"],
        "source_url": "https://www.ecil.co.in/aerospace_portfolio"
    },
    {
        "id": f"faq-{next_id+3}",
        "question": "Does ECIL make railway electronics?",
        "answer": "Yes. ECIL's Railway Electronics Vertical supplies signaling systems, track instruments, level crossing controls, automated coaching units and real-time supervision systems for Indian Railways modernization and metro systems.",
        "category": "Products",
        "tags": ["railway", "signaling", "metro", "train"],
        "source_url": "https://www.ecil.co.in/products/railway"
    },
    {
        "id": f"faq-{next_id+4}",
        "question": "What solar products does ECIL manufacture?",
        "answer": "ECIL's Solar Photovoltaic Division manufactures solar panels, inverters, charge controllers, monitoring systems and complete solar power solutions for grid-connected and standalone applications. ECIL works on solar projects for central and state governments.",
        "category": "Products",
        "tags": ["solar", "photovoltaic", "renewable", "energy"],
        "source_url": "https://www.ecil.co.in/products/solar"
    },
    {
        "id": f"faq-{next_id+5}",
        "question": "Does ECIL manufacture servo systems?",
        "answer": "Yes. ECIL's Servo Systems Division designs and manufactures servo motors, hydraulic actuators, electro-mechanical actuators, and control systems for aerospace, defence, industrial automation and robotics applications.",
        "category": "Products",
        "tags": ["servo", "actuator", "motion control"],
        "source_url": "https://www.ecil.co.in/products/servo"
    },
    {
        "id": f"faq-{next_id+6}",
        "question": "What computer systems and embedded products does ECIL make?",
        "answer": "ECIL manufactures ruggedized computers, embedded systems, real-time control boards, IO modules, and computing sub-systems for defence, nuclear, aerospace and industrial applications. ECIL also produces the historic TDC series of computers.",
        "category": "Products",
        "tags": ["computer", "embedded", "computing"],
        "source_url": "https://www.ecil.co.in/products/computers"
    },
    {
        "id": f"faq-{next_id+7}",
        "question": "What electronic instruments does ECIL manufacture?",
        "answer": "ECIL produces electronic test and measurement instruments, oscilloscopes, spectrum analyzers, power supplies, radiation detectors, environmental monitors and specialized instrumentation for laboratory, industrial and field use.",
        "category": "Products",
        "tags": ["instrument", "measurement", "testing"],
        "source_url": "https://www.ecil.co.in/products/instruments"
    },
    {
        "id": f"faq-{next_id+8}",
        "question": "What smart meter and automation solutions does ECIL provide?",
        "answer": "ECIL manufactures smart electricity meters with AMI (Advanced Metering Infrastructure), demand-side management systems, IoT-based asset tracking, SCADA solutions and industrial automation products for utilities and manufacturing.",
        "category": "Products",
        "tags": ["smart meter", "IoT", "automation", "energy"],
        "source_url": "https://www.ecil.co.in/products/smartmeter"
    },
    {
        "id": f"faq-{next_id+9}",
        "question": "Does ECIL have quality management certifications?",
        "answer": "Yes. ECIL is ISO 9001 certified for quality management across all divisions. Many divisions hold additional certifications in environmental management (ISO 14001), occupational health & safety (ISO 45001), and information security (ISO 27001). ECIL also holds AS9100 for aerospace.",
        "category": "Quality & Certifications",
        "tags": ["ISO", "certification", "quality", "QMS"],
        "source_url": "https://www.ecil.co.in/quality"
    },
    {
        "id": f"faq-{next_id+10}",
        "question": "What is ECIL's R&D focus?",
        "answer": "ECIL invests heavily in research and development for next-generation defence electronics, nuclear instrumentation, satellite communications, IoT/Industry 4.0, RF technologies, automation and green energy. ECIL operates multiple R&D centers and test facilities.",
        "category": "Research & Development",
        "tags": ["research", "innovation", "technology"],
        "source_url": "https://www.ecil.co.in/rnd"
    },
    {
        "id": f"faq-{next_id+11}",
        "question": "Has ECIL won awards for its products and innovation?",
        "answer": "Yes. ECIL has received multiple national and international awards for innovation, quality, exports, corporate social responsibility and environmental management. ECIL is recognized as a technology leader in Indian defence and atomic energy sectors.",
        "category": "Awards & Achievements",
        "tags": ["awards", "recognition", "excellence"],
        "source_url": "https://www.ecil.co.in/awards"
    },
    {
        "id": f"faq-{next_id+12}",
        "question": "What is ECIL's corporate social responsibility (CSR) program?",
        "answer": "ECIL conducts CSR activities in education, healthcare, skill development, environmental conservation and rural development around its manufacturing locations. ECIL believes in sustainable business practices and community engagement.",
        "category": "Sustainability & CSR",
        "tags": ["CSR", "social responsibility", "sustainability"],
        "source_url": "https://www.ecil.co.in/csr"
    },
    {
        "id": f"faq-{next_id+13}",
        "question": "What are ECIL's manufacturing locations in India?",
        "answer": "ECIL has its head office and main manufacturing complex at Hyderabad (Kushaiguda). ECIL also operates manufacturing and assembly units at Bangalore, Faridabad and other locations. ECIL's facilities employ state-of-the-art production and testing equipment.",
        "category": "Organizational Structure",
        "tags": ["manufacturing", "locations", "plants"],
        "source_url": "https://www.ecil.co.in/manfgunits"
    },
    {
        "id": f"faq-{next_id+14}",
        "question": "How does ECIL approach customer support?",
        "answer": "ECIL's Customer Support Division provides comprehensive after-sales service including commissioning, training, maintenance contracts, spare parts supply, technical support and field service across India and overseas for all ECIL products.",
        "category": "Services & Technologies",
        "tags": ["support", "service", "maintenance"],
        "source_url": "https://www.ecil.co.in/divisions/customer-support"
    },
    {
        "id": f"faq-{next_id+15}",
        "question": "Does ECIL offer professional training programs?",
        "answer": "Yes. ECIL conducts customer training, technical workshops, internship programs and skill development courses in electronics, embedded systems, nuclear instrumentation, communications and other specialized areas. Training is offered on-site and at customer locations.",
        "category": "Training & Development",
        "tags": ["training", "education", "development"],
        "source_url": "https://www.ecil.co.in/training"
    },
    {
        "id": f"faq-{next_id+16}",
        "question": "What are ECIL's business verticals?",
        "answer": "ECIL operates through strategic verticals: Nuclear Instrumentation & Control, Defence Electronics, Aerospace & Satcom, Homeland Security Solutions, IT & e-Governance, and Other Operations. Each vertical serves specific customer segments with specialized products and services.",
        "category": "Organizational Structure",
        "tags": ["verticals", "divisions", "business"],
        "source_url": "https://www.ecil.co.in/verticals"
    },
    {
        "id": f"faq-{next_id+17}",
        "question": "Does ECIL have partnerships or joint ventures?",
        "answer": "Yes. ECIL collaborates with international and domestic technology partners through joint ventures, technology sharing agreements and partnerships to strengthen product offerings and access global markets in defence and civil sectors.",
        "category": "ECIL Overview",
        "tags": ["partnership", "joint venture", "collaboration"],
        "source_url": "https://www.ecil.co.in/jointventures"
    },
    {
        "id": f"faq-{next_id+18}",
        "question": "What is ECIL's environmental management commitment?",
        "answer": "ECIL is committed to environmental sustainability through energy-efficient manufacturing, waste management, water conservation, renewable energy adoption and reducing carbon footprint. ECIL holds ISO 14001 environmental management certification.",
        "category": "Sustainability & CSR",
        "tags": ["environment", "green", "sustainability"],
        "source_url": "https://www.ecil.co.in/environment"
    },
    {
        "id": f"faq-{next_id+19}",
        "question": "What are ECIL's specifications and datasheets?",
        "answer": "ECIL provides comprehensive product datasheets, technical specifications, user manuals and application notes for all products. Detailed documentation is available on ECIL's website and through the customer support division. Custom specifications are available for OEM customers.",
        "category": "Technical Documentation",
        "tags": ["specification", "datasheet", "technical"],
        "source_url": "https://www.ecil.co.in/specifications"
    },
    {
        "id": f"faq-{next_id+20}",
        "question": "How to contact ECIL for product enquiries or support?",
        "answer": "For product enquiries: visit www.ecil.co.in or contact the relevant divisional headquarters. For support: call 040-27120131 or 040-27182470 (Hyderabad). Email inquiries can be sent to the specific division. ECIL has regional offices and dealers across India.",
        "category": "Contact & Support",
        "tags": ["contact", "phone", "email", "support"],
        "source_url": "https://www.ecil.co.in/contact-us"
    },
]

# Add new FAQs to the base
faq_base.extend(new_faqs)

# Save the enhanced FAQ base
with open('data/faq_base.json', 'w', encoding='utf-8') as f:
    json.dump(faq_base, f, ensure_ascii=False, indent=2)

print(f"Enhanced FAQ base: Added {len(new_faqs)} new FAQs")
print(f"Total FAQ entries now: {len(faq_base)}")
