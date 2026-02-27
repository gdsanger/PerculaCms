PerculaCMS ist ein KI/AI zentriertes CMS System für Homepage. 

## Technologiestack
Backend: Python, Django
UI: Django Admin + HTMX + Bootstrap (Dark + Light Mode)
Datenbank: PostgreSQL
Storage: Lokaler Filesystem-Storage (keine Cloud-Abhängigkeit)
Vektor-Datenbank: Weaviate
Integrationen:
- E-Mail (Mail In/Out) mit GraphAPI
- KI: Agentenbasierte Architektur (adaptiert aus KIGate)

## Zentrale Domänen (Model)
### MediaBib

## KI-Integration
PerculaCMS ist von Anfang an KI-ready, und KI-zentriert.

KI kann:
- Homepage Texte erstellen, verbessern, optimieren
- Meta Tags bestimmen
- Meta Description festlegen
- Frage von Besucher beantworten
- Tipps und Tricks vorschlagen aufgrund Besucherverhalten
- Zusammenfassungen erstellen und wiedergeben

## Zentrale Domänen (Model)
### HomepageSetting
> Globale EInstellungen zur Homepage wie Site Titel, Domain/BaseUrl, Impressumsangaben, Datenschutz uvm.

### Categories
> Key/Value Pair of Categories mit Hauptkategorie und Unterkategorien

### Sections
> Homepage

### Pages
> Definiert die einzelnen Seiten eine Homepage mit Url Routing (Seo friendly) mit Titel, Description, Content, und Image

### MediaLibary
> Lokales Storage mit medien wie Images, Audio und Video Files, PDF Dateien usw. 

## Core Services

### AgentService (core/services/agents/agent_service.py)
- Service for managing and executing AI agents from YAML configuration files.

### AI (core/services/ai)
- OpenAI provider implementation.
- Google Gemini provider implementation.
- AI Router - Main entry point for AI services in Agira.
- Data schemas for AI service requests and responses.

### GraphAPI (core/services/graph)
- Microsoft Graph API Mail Service for PerculaCMS
- Microsoft Graph API client for Agira.

### RAG (core/services/rag/service.py)
- RAG Pipeline Service implementation.
- Data models for RAG Pipeline responses.
- Extended RAG Pipeline Service with Question Optimization, Hybrid Search and A/B/C-Fusion.
- Configuration for RAG Pipeline Service.

### Weaviate (core/services/weaviate/service.py)
* Weaviate service layer for PerculaCMS.
* Weaviate serializers for PerculaCMS models.
* Weaviate schema management for PerculaCMS.
* Weaviate client management for PerculaCMS.
* Django signals for automatic Weaviate synchronization.
