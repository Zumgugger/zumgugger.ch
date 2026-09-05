"""Seed data for Rolfing-type websites (bodywork/therapy practitioners)."""

from typing import Any, Dict


def get_rolfing_seed() -> Dict[str, Any]:
    """Get seed content for a Rolfing/bodywork website.
    
    Returns:
        Dictionary containing all seed content for a Rolfing site.
    """
    return {
        "site_type": "rolfing",
        "content": {
            # Hero module
            "hero_headline": "Strukturelle Integration für mehr Leichtigkeit im Körper",
            "hero_cta_text": "Termin vereinbaren",
            "hero_cta_target": "contact",
            "hero_bg_image": None,  # To be set by user
            
            # Trust/Proof module
            "trust_images": [],
            "testimonials": [
                {
                    "quote": "Nach der 10er-Serie fühle ich mich wie neu geboren. Meine chronischen Rückenschmerzen sind deutlich besser.",
                    "author_name": "Sandra K.",
                    "author_role": "Kundin seit 2023",
                },
                {
                    "quote": "Einfühlsam, professionell und kompetent. Ich kann die Behandlung nur empfehlen.",
                    "author_name": "Michael B.",
                    "author_role": "Regelmäßiger Klient",
                },
            ],
            "review_source_url": None,
            "review_source_text": None,
            
            # Services module
            "services": [
                {
                    "title": "Die 10er-Serie",
                    "description": "Die klassische Rolfing-Serie in 10 Sitzungen für eine tiefgreifende strukturelle Neuorganisation Ihres Körpers.",
                    "image": None,
                    "icon": "layers",
                },
                {
                    "title": "Einzelsitzungen",
                    "description": "Gezielte Arbeit an spezifischen Themen oder zur Auffrischung nach der Grundserie.",
                    "image": None,
                    "icon": "user",
                },
                {
                    "title": "Rolfing für Sportler",
                    "description": "Optimierung von Bewegungsmustern und Prävention von Verletzungen für aktive Menschen.",
                    "image": None,
                    "icon": "activity",
                },
            ],
            
            # About module
            "about_blocks": [
                {
                    "type": "text",
                    "content": "<p>Als zertifizierte/r Rolfer/in begleite ich Sie auf dem Weg zu mehr körperlichem Wohlbefinden. Rolfing® Strukturelle Integration ist eine Form der manuellen Körperarbeit, die das Bindegewebe (Faszien) anspricht und den Körper im Schwerefeld der Erde neu ausrichtet.</p><p>Mein Ziel ist es, Ihnen zu helfen, sich in Ihrem Körper wieder wohl zu fühlen – aufrecht, beweglich und schmerzfrei.</p>",
                },
            ],
            
            # Media module (available but not enabled by default for rolfing)
            "media_blocks": [],
            
            # FAQ module (enabled for rolfing - clients often have questions)
            "faq_items": [
                {
                    "question": "Was ist Rolfing?",
                    "answer": "Rolfing ist eine Form der manuellen Körperarbeit, die von Dr. Ida Rolf entwickelt wurde. Sie arbeitet mit dem Bindegewebe (Faszien) und zielt darauf ab, den Körper im Schwerefeld der Erde optimal auszurichten.",
                },
                {
                    "question": "Ist Rolfing schmerzhaft?",
                    "answer": "Rolfing kann intensiv sein, sollte aber nie unangenehm schmerzhaft sein. Ich arbeite immer innerhalb Ihrer Komfortzone und passe den Druck Ihren Bedürfnissen an.",
                },
                {
                    "question": "Wie viele Sitzungen brauche ich?",
                    "answer": "Die klassische Rolfing-Serie umfasst 10 Sitzungen. Je nach Ihren Zielen und Bedürfnissen können auch Einzelsitzungen oder kürzere Serien sinnvoll sein.",
                },
                {
                    "question": "Wird Rolfing von der Krankenkasse übernommen?",
                    "answer": "Rolfing wird in der Schweiz von vielen Zusatzversicherungen (Komplementärmedizin) anteilig übernommen. Bitte erkundigen Sie sich bei Ihrer Versicherung.",
                },
                {
                    "question": "Was soll ich zur Sitzung mitbringen?",
                    "answer": "Bequeme Unterwäsche ist ausreichend. Frauen können auch einen Sport-BH oder ein Bikini-Oberteil tragen. Bitte kommen Sie frisch geduscht.",
                },
            ],
            
            # Contact module
            "contact_phone": None,  # To be set
            "contact_email": None,  # To be set
            "contact_address": None,
            "contact_maps_link": None,
            
            # Footer module
            "footer_social_links": [
                {
                    "platform": "instagram",
                    "url": "https://instagram.com/",
                    "label": None,
                },
            ],
            
            # Legal pages (with health-related disclaimers)
            "impressum_content": """<h2>Impressum</h2>
<p><strong>[Praxisname]</strong></p>
<p>[Vorname Nachname]<br>
Zertifizierte/r Rolfer/in<br>
[Straße Hausnummer]<br>
[PLZ Ort]<br>
[Land]</p>

<h3>Kontakt</h3>
<p>Telefon: [Telefonnummer]<br>
E-Mail: [E-Mail-Adresse]</p>

<h3>Berufsbezeichnung und Qualifikation</h3>
<p>Zertifizierte/r Rolfer/in, ausgebildet am [Ausbildungsinstitut]<br>
Mitglied der European Rolfing Association e.V.</p>

<h3>Verantwortlich für den Inhalt</h3>
<p>[Vorname Nachname]</p>

<h3>Haftungsausschluss</h3>
<p>Die Inhalte dieser Website dienen ausschließlich der allgemeinen Information und ersetzen keine professionelle medizinische Beratung, Diagnose oder Behandlung. Bei gesundheitlichen Beschwerden konsultieren Sie bitte einen Arzt.</p>

<p>Trotz sorgfältiger inhaltlicher Kontrolle übernehmen wir keine Haftung für die Inhalte externer Links. Für den Inhalt der verlinkten Seiten sind ausschließlich deren Betreiber verantwortlich.</p>
""",
            
            "datenschutz_content": """<h2>Datenschutzerklärung</h2>

<h3>1. Datenschutz auf einen Blick</h3>
<p>Die folgenden Hinweise geben einen einfachen Überblick darüber, was mit Ihren personenbezogenen Daten passiert, wenn Sie diese Website besuchen.</p>

<h3>2. Datenerfassung auf dieser Website</h3>
<p><strong>Wer ist verantwortlich für die Datenerfassung auf dieser Website?</strong></p>
<p>Die Datenverarbeitung auf dieser Website erfolgt durch den Websitebetreiber. Dessen Kontaktdaten können Sie dem Impressum dieser Website entnehmen.</p>

<h3>3. Kontaktformular</h3>
<p>Wenn Sie uns per Kontaktformular Anfragen zukommen lassen, werden Ihre Angaben aus dem Anfrageformular inklusive der von Ihnen dort angegebenen Kontaktdaten zwecks Bearbeitung der Anfrage und für den Fall von Anschlussfragen bei uns gespeichert. Diese Daten geben wir nicht ohne Ihre Einwilligung weiter.</p>

<h3>4. Gesundheitsbezogene Daten</h3>
<p>Im Rahmen der Terminvereinbarung und Behandlung können gesundheitsbezogene Daten erhoben werden. Diese unterliegen der ärztlichen Schweigepflicht und werden vertraulich behandelt. Eine Weitergabe an Dritte erfolgt nur mit Ihrer ausdrücklichen Einwilligung oder wenn dies gesetzlich vorgeschrieben ist.</p>

<h3>5. Ihre Rechte</h3>
<p>Sie haben jederzeit das Recht auf unentgeltliche Auskunft über Ihre gespeicherten personenbezogenen Daten, deren Herkunft und Empfänger und den Zweck der Datenverarbeitung sowie ein Recht auf Berichtigung, Sperrung oder Löschung dieser Daten.</p>

<p><em>[Bitte passen Sie diese Datenschutzerklärung an Ihre spezifischen Bedürfnisse an oder lassen Sie sie von einem Rechtsanwalt überprüfen.]</em></p>
""",
        },
        
        "config": {
            "theme_name": "elegant",
            "module_states": {
                "hero": "enabled",
                "trust": "enabled",
                "services": "enabled",
                "about": "enabled",
                "media": "available",  # Available but not enabled for rolfing
                "faq": "enabled",      # Enabled for rolfing
                "contact": "enabled",
                "footer": "enabled",
            },
            "module_order": [
                "hero",
                "trust",
                "services",
                "about",
                "media",
                "faq",
                "contact",
                "footer",
            ],
            "css_variables": {},
            "nav_labels": {},
        },
    }
