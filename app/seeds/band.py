"""Seed data for Band-type websites."""

from typing import Any, Dict


def get_band_seed() -> Dict[str, Any]:
    """Get seed content for a Band website.
    
    Returns:
        Dictionary containing all seed content for a Band site.
    """
    return {
        "site_type": "band",
        "content": {
            # Hero module
            "hero_headline": "Ihre Band für unvergessliche Momente",
            "hero_cta_text": "Jetzt buchen",
            "hero_cta_target": "contact",
            "hero_bg_image": None,  # To be set by user
            
            # Trust/Proof module
            "trust_images": [],
            "testimonials": [
                {
                    "quote": "Eine fantastische Band, die unser Fest unvergesslich gemacht hat! Die Stimmung war großartig.",
                    "author_name": "Maria Müller",
                    "author_role": "Veranstalterin",
                },
                {
                    "quote": "Professionell, pünktlich und unglaublich talentiert. Wir buchen sie wieder!",
                    "author_name": "Thomas Weber",
                    "author_role": "Hochzeitsgast",
                },
            ],
            "review_source_url": None,
            "review_source_text": None,
            
            # Services module
            "services": [
                {
                    "title": "Hochzeiten",
                    "description": "Wir gestalten Ihren besonderen Tag mit der perfekten musikalischen Begleitung.",
                    "image": None,
                    "icon": "heart",
                },
                {
                    "title": "Firmenevents",
                    "description": "Professionelle Live-Musik für Ihre Firmenfeier, Messe oder Produktpräsentation.",
                    "image": None,
                    "icon": "briefcase",
                },
                {
                    "title": "Private Feiern",
                    "description": "Geburtstage, Jubiläen oder Gartenpartys – wir bringen die richtige Stimmung.",
                    "image": None,
                    "icon": "music",
                },
            ],
            
            # About module
            "about_blocks": [
                {
                    "type": "text",
                    "content": "<p>Wir sind eine leidenschaftliche Band mit jahrelanger Erfahrung. Unser Repertoire reicht von Pop und Rock über Jazz bis hin zu Klassikern, die jede Generation begeistern.</p><p>Mit professionellem Equipment und viel Herzblut sorgen wir dafür, dass Ihr Event zum unvergesslichen Erlebnis wird.</p>",
                },
            ],

            # Repertoire module
            "repertoire_entries": [],
            
            # Media module (enabled for bands)
            "media_blocks": [
                {
                    "type": "text",
                    "content": "<p>Hier finden Sie Videos und Hörproben unserer Auftritte.</p>",
                },
            ],
            
            # FAQ module (available but not enabled by default for bands)
            "faq_items": [
                {
                    "question": "Wie früh sollte ich buchen?",
                    "answer": "Wir empfehlen, mindestens 3-6 Monate im Voraus zu buchen, besonders für beliebte Termine wie Samstage in der Hochzeitssaison.",
                },
                {
                    "question": "Welche Musikrichtungen spielt ihr?",
                    "answer": "Unser Repertoire umfasst Pop, Rock, Jazz, Funk und Klassiker von den 60ern bis heute. Auf Wunsch lernen wir auch Ihre persönlichen Lieblingssongs.",
                },
                {
                    "question": "Bringt ihr eigenes Equipment mit?",
                    "answer": "Ja, wir kommen mit professioneller Ton- und Lichttechnik. Für größere Veranstaltungen arbeiten wir mit erfahrenen Technikern zusammen.",
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
                {
                    "platform": "youtube",
                    "url": "https://youtube.com/",
                    "label": None,
                },
                {
                    "platform": "spotify",
                    "url": "https://spotify.com/",
                    "label": None,
                },
            ],
            
            # Legal pages
            "impressum_content": """<h2>Impressum</h2>
<p><strong>[Firmenname / Name der Band]</strong></p>
<p>[Vorname Nachname]<br>
[Straße Hausnummer]<br>
[PLZ Ort]<br>
[Land]</p>

<h3>Kontakt</h3>
<p>Telefon: [Telefonnummer]<br>
E-Mail: [E-Mail-Adresse]</p>

<h3>Verantwortlich für den Inhalt</h3>
<p>[Vorname Nachname]</p>

<h3>Haftungsausschluss</h3>
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

<h3>4. Ihre Rechte</h3>
<p>Sie haben jederzeit das Recht auf unentgeltliche Auskunft über Ihre gespeicherten personenbezogenen Daten, deren Herkunft und Empfänger und den Zweck der Datenverarbeitung sowie ein Recht auf Berichtigung, Sperrung oder Löschung dieser Daten.</p>

<p><em>[Bitte passen Sie diese Datenschutzerklärung an Ihre spezifischen Bedürfnisse an oder lassen Sie sie von einem Rechtsanwalt überprüfen.]</em></p>
""",
        },
        
        "config": {
            "theme_name": "clean",
            "module_states": {
                "hero": "enabled",
                "trust": "enabled",
                "services": "enabled",
                "about": "enabled",
                "repertoire": "available",
                "media": "enabled",  # Enabled for bands
                "faq": "available",  # Available but not enabled
                "contact": "enabled",
                "footer": "enabled",
            },
            "module_order": [
                "hero",
                "trust",
                "services",
                "about",
                "repertoire",
                "media",
                "faq",
                "contact",
                "footer",
            ],
            "css_variables": {},
            "nav_labels": {},
        },
    }
