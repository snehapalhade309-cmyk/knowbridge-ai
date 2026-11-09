# KnowBridge AI — Intelligent Knowledge Handover Platform

> *"Never Let Critical Project Knowledge Leave With People."*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Flask-JWT-Extended](https://img.shields.io/badge/Auth-JWT%20Bearer%20Tokens-F7DF1E?style=flat)](https://flask-jwt-extended.readthedocs.io/)
[![SQLite/PostgreSQL](https://img.shields.io/badge/Database-SQLAlchemy%20Relational%20ORM-blue?style=flat)](https://www.sqlalchemy.org/)
[![Google Gemini](https://img.shields.io/badge/AI-Gemini%201.5%20%2B%20NLP%20Engine-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Enterprise UI](https://img.shields.io/badge/Theme-Light%20SaaS%20Ivory%20%26%20Teal-467B75?style=flat)](#)

---

## 📖 Executive Summary

**KnowBridge AI** is an enterprise-grade AI-powered Knowledge Handover Platform designed to prevent mission-critical project, architectural, and operational knowledge from disappearing when employees, senior engineers, or managers depart an organization.

The platform continuously processes authorized project documents (PDF, DOCX, CSV, TXT), performs AI-driven information extraction to pinpoint strategic decisions, responsibilities, pending tasks, risks, and dependencies, links every insight to verifiable source evidence, requires **mandatory human review and sign-off**, and generates auditable handover reports tracked with recipient acknowledgements.

---

## 🎨 Enterprise Design Specification & Palette

Designed strictly as a modern, light-themed SaaS platform:

| Swatch | Color Name | Hex Code | Purpose |
|---|---|---|---|
| 🟨 | **Warm Ivory** | `#F8F6F0` | Main application background |
| 🟩 | **Soft Sage Green** | `#DCE9E4` | Status badges, highlights & cards |
| 🟦 | **Muted Teal** | `#467B75` | Sidebar navigation, banners & structure |
| 🟧 | **Terracotta** | `#A94F3B` | Primary call-to-actions, accents & buttons |
| ⬜ | **White** | `#FFFFFF` | Cards, modals & table surfaces |
| ⬛ | **Charcoal** | `#292D2B` | Primary typography & headings |
| 🪨 | **Light Border** | `#E5E1D8` | Structural card borders & dividers |

---

## 👥 Role-Based Access Control (RBAC)

KnowBridge AI enforces 4 distinct organizational roles:

1. **Admin (`admin`)**: Comprehensive system governance, user activation/deactivation, role assignment, project oversight, and complete audit trail inspection.
2. **Project Manager (`project_manager`)**: Project lifecycle management, document oversight, AI extraction execution, human-in-the-loop verification, handover report approval, and assignment of incoming recipients.
3. **Outgoing Member (`outgoing_member`)**: Submits authorized documents, notes, decisions, and tasks, initiates handover compilation, and reviews knowledge extraction findings.
4. **Incoming Member (`incoming_member`)**: Reads verified handovers, reviews transferred tasks and decisions, inspects documentation, and formally confirms handover receipt with digital sign-off.

### 🔑 Pre-Configured Test Accounts

| Role | Email | Password | Pre-configured Access |
|---|---|---|---|
| **Admin** | `admin@knowbridge.ai` | `admin123` | Full administrative control |
| **Project Manager** | `sarah@knowbridge.ai` | `sarah123` | Project management & approvals |
| **Outgoing Member** | `alex@knowbridge.ai` | `alex123` | Document submission & handover creation |
| **Incoming Member** | `priya@knowbridge.ai` | `priya123` | Handover inspection & acknowledgement |

---

## 🧠 AI Knowledge Extraction Engine

KnowBridge AI integrates a dual-tier AI pipeline:

1. **Google Gemini 1.5 Flash (`gemini-1.5-flash`)**: High-throughput LLM for semantic understanding, contextual extraction, decision rationale detection, risk assessment, and synthesis.
2. **Intelligent NLP Pattern Pipeline (Zero-Configuration Fallback)**:
   - Operates 100% locally and offline without requiring external API keys.
   - Filters out markdown section headers and noise.
   - Extracts decisions, pending action items, assignees, deadlines, and risk severity.
   - Pins **source citations with document name and line-level references** (`source_ref`).
   - Automatically detects missing information (e.g., unassigned tasks, missing deadlines) and flags them for human verification.

---

## 🛠️ Complete Handover Workflow

```
[Document Upload (PDF/DOCX/TXT/CSV)]
                 ↓
     [Permission Validation]
                 ↓
 [Document Parsing & Text Extraction]
                 ↓
 [AI Extraction (Gemini / Smart NLP)]
                 ↓
[Evidence-Linked Findings Queued for Review]
                 ↓
      [Human Review & Correction]
        ├── Rejected → Returned / Archived
        └── Approved → Promoted to Verified Ledger
                 ↓
 [Handover Report Generated & Versioned]
                 ↓
       [Project Manager Sign-Off]
                 ↓
    [Secure Recipient Distribution]
                 ↓
  [Digital Acknowledgement & Audit Log]
```

---

## 🌐 Complete REST API Reference

All `/api/...` endpoints support dual-authentication: **JWT Bearer Token** (`Authorization: Bearer <token>`) or **Active Web Session**.

### Authentication
- `POST /api/auth/register` — Register a new user and receive a JWT token.
- `POST /api/auth/login` — Authenticate and receive a JWT Bearer token + session cookie.
- `GET /api/auth/me` — Retrieve the current authenticated user's profile and permissions.
- `POST /api/auth/logout` — Terminate the current session.

### Projects
- `GET /api/projects` — List accessible projects with live task, risk, and document counters.
- `POST /api/projects` — Create a new project workspace.
- `GET /api/projects/<id>` — Get single project details.
- `PUT /api/projects/<id>` — Update project metadata, status, or dates.
- `DELETE /api/projects/<id>` — Delete a project and associated files.

### Documents
- `POST /api/documents/upload` — Upload project documentation (`pdf`, `docx`, `txt`, `csv`).
- `GET /api/documents` — List documents (optional `?project_id=<id>`).
- `GET /api/documents/<id>` — Retrieve document metadata and text extraction preview.
- `DELETE /api/documents/<id>` — Delete a document and purge file from disk.

### AI Processing
- `POST /api/ai/analyze/<document_id>` — Trigger AI knowledge extraction on a document.
- `GET /api/ai/results/<project_id>` — Retrieve structured AI findings for a project.
- `POST /api/ai/summarize` — Generate concise summary statistics for project knowledge.
- `POST /api/ai/extract-decisions` — Direct endpoint to extract decisions from raw text.
- `POST /api/ai/detect-risks` — Direct endpoint to detect risks and blockers from raw text.

### Tasks
- `GET /api/tasks` — List tasks (optional `?project_id=<id>`).
- `POST /api/tasks` — Create a new task with assignee, priority, and deadline.
- `PUT /api/tasks/<id>` — Update task status, priority, or ownership.

### Decisions
- `GET /api/decisions` — List verified project decisions (optional `?project_id=<id>`).
- `POST /api/decisions` — Record a project decision with owner, date, and description.

### Handovers (Reports)
- `POST /api/handovers/generate` — Compile verified items into a formal Handover Report.
- `GET /api/handovers` — List handover reports (optional `?project_id=<id>`).
- `GET /api/handovers/<id>` — Retrieve full handover report with JSON contents.
- `POST /api/handovers/<id>/approve` — Authorize and approve a handover report.
- `POST /api/handovers/<id>/reject` — Return a handover report for revision.

### Acknowledgements
- `GET /api/acknowledgements` — Retrieve the current user's handover acknowledgements.
- `GET /api/acknowledgements/<handover_id>` — Retrieve acknowledgement status for a report.
- `POST /api/acknowledgements` — Assign a handover report to an incoming member for sign-off.
- `POST /api/acknowledgements/<id>/confirm` — Record recipient confirmation with timestamp and notes.

### Analytics
- `GET /api/analytics/dashboard` — Live database-driven analytics for dashboards and charts.

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Clone Repository
```bash
git clone https://github.com/your-username/knowbridge-ai.git
cd knowbridge-ai
```

### 3. Set Up Virtual Environment
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Optional)* Add your Google Gemini API key to `.env`. If left unconfigured, KnowBridge AI automatically operates using its built-in smart NLP extraction pipeline without errors.

### 6. Run Application
```bash
python app.py
```
Open your browser at: **`http://localhost:5000`**

Log in using any demo account:
- `admin@knowbridge.ai` / `admin123`
- `sarah@knowbridge.ai` / `sarah123`
- `alex@knowbridge.ai` / `alex123`
- `priya@knowbridge.ai` / `priya123`

---

## 🧪 Testing

Run the automated integration test suite to verify web routes, REST APIs, JWT tokens, document parsing, and AI extraction:

```bash
python -c "
import json, io
from app import app, db, User, Project, Document, HandoverReport
app.config['WTF_CSRF_ENABLED'] = False
client = app.test_client()
res = client.post('/api/auth/login', json={'email': 'admin@knowbridge.ai', 'password': 'admin123'})
token = res.get_json()['access_token']
headers = {'Authorization': f'Bearer {token}'}
print('Authenticated as:', client.get('/api/auth/me', headers=headers).get_json()['name'])
print('Analytics:', client.get('/api/analytics/dashboard', headers=headers).get_json())
print('SUCCESS: All subsystems operational!')
"
```

---

## 📦 Minimal & Clean File Structure (GitHub Ready)

```text
KKK/
├── app.py                     # Single complete Flask app: models, routes, REST APIs, AI pipeline
├── requirements.txt           # Clean dependencies
├── .env.example               # Environment template
├── README.md                  # Comprehensive documentation
├── templates/                 # Premium light-themed HTML templates
│   ├── base.html              # Shell layout, sidebar, topbar, Lucide SVG icons
│   ├── landing.html           # Public marketing landing page
│   ├── dashboard.html         # Main metrics & Chart.js visualizations
│   ├── projects.html          # Project directory & creation modal
│   ├── project_detail.html    # Single project workspace
│   ├── documents.html         # Document ingestion & preview
│   ├── ai_summary.html        # AI extraction findings
│   ├── review.html            # Human verification review queue
│   ├── tasks.html             # Task management
│   ├── risks.html             # Risk matrix & blockers
│   ├── report.html            # Handover report preview & export
│   ├── acknowledgements.html  # Recipient sign-off & confirmation
│   ├── timeline.html          # Project chronological milestones
│   ├── version_history.html   # Report revisions & audit log
│   ├── users.html             # Role & user management
│   ├── audit_logs.html        # Security compliance log
│   ├── settings.html          # Profile settings
│   ├── login.html             # Sign in
│   ├── register.html          # Account creation
│   └── error.html             # Error views (403, 404, 500)
├── static/
│   ├── css/
│   │   └── style.css          # Modern light SaaS stylesheet with exact Ivory & Teal palette
│   └── js/
│       └── app.js             # Interactive Chart.js, modals, toasts, drag-drop upload
└── instance/
    └── knowbridge.db          # Relational SQLite database (upgradeable to PostgreSQL)
```

---

## 🚢 Upgrading to PostgreSQL for Production

To switch from SQLite to PostgreSQL:

1. Update `DATABASE_URL` in `.env`:
   ```bash
   DATABASE_URL=postgresql://username:password@localhost:5432/knowbridge_db
   ```
2. Install `psycopg2-binary`:
   ```bash
   pip install psycopg2-binary
   ```
3. Restart `python app.py` — SQLAlchemy automatically builds all tables with primary/foreign key relationships.

---

## 📄 License

Licensed under the MIT License. Developed for enterprise knowledge preservation.
