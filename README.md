# KnowBridge AI — Intelligent Knowledge Handover Platform

> **"Never Let Critical Project Knowledge Leave With People."**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.3-purple.svg)](https://getbootstrap.com/)
[![Theme](https://img.shields.io/badge/Theme-Light%20SaaS-4F7DF3.svg)]()

---

## 📌 Executive Summary & Problem Statement

When an employee, developer, student, or team member leaves a project, critical context leaves with them. Traditional repositories store *code*, but they fail to capture the **why**, the **what's next**, and the **hidden landmines**:
- **Scattered Project Knowledge:** Dispersed across meeting transcripts, sprint backlogs, architecture notes, and chat logs.
- **Lost Rationale:** New owners have no record of *why* certain architectural trade-offs were made.
- **Zombie Tasks:** Action items without documented owners or deadlines.
- **Unidentified Risks & Blockers:** Tacit dependencies and undocumented pitfalls.
- **Inefficient Onboarding:** Incoming members spend weeks or months deciphering unwritten assumptions.

**KnowBridge AI** automates and certifies knowledge transfers. It aggregates authorized project documentation, uses structured LLM extraction (with automatic local heuristic fallbacks) to identify decisions, tasks, risks, and dependencies, mandates **Human-in-the-Loop Review**, and outputs certified **PDF & CSV Handover Packages** with signed incoming acknowledgements.

---

## 🚀 Key Features

### 1. 📄 Document Ingestion & Live Text Extraction
- Drag-and-drop file ingestion supporting **PDF, DOCX, TXT, and CSV**.
- Secure, sandboxed file processing via **PyMuPDF**, **python-docx**, and **Pandas**.
- In-memory content validation with 50MB safety limits.

### 2. 🧠 AI Knowledge Extraction (Dual-Engine Architecture)
- **Primary Engine:** Compatible with **OpenAI API** (`gpt-3.5-turbo`, `gpt-4o`) and **Google Gemini API** (`gemini-pro`, `gemini-1.5-flash`).
- **Autonomous Local Fallback:** When no cloud API key is configured, KnowBridge AI automatically activates an offline keyword & NLP heuristic processor.
- Extracts:
  - 🏛️ **Important Decisions** (Title, rationale, date, owner, source excerpt)
  - 📋 **Pending Tasks & Responsibilities** (Priority, status, assignee, deadlines)
  - ⚠️ **Project Risks & Blockers** (Severity, risk taxonomy, mitigations)
  - 🔗 **Cross-Module Dependencies** (Source item to target requirement)
  - ❓ **Missing Information Alerts & Contradiction Detection**

### 3. 🔍 Evidence-Linked Traceability
- Zero hallucination policy: Every extracted decision, task, and risk is directly hyperlinked to its raw document excerpt.
- One-click **View Evidence** modal displays original document excerpts with page/section context.

### 4. 🛡️ Human-in-the-Loop Verification Dashboard
- **AI-generated intelligence never auto-verifies.**
- Reviewers and team leads can **Approve**, **Reject**, or flag items as **Needs Review** with human feedback notes.
- Comprehensive audit trail preserving timestamps and reviewer identity.

### 5. 📑 Handover Deliverables (PDF & CSV Generation)
- Instant publication of a formal **Executive Handover Report** via **ReportLab**.
- Formatted tables for overview, team rosters, verified decisions, pending tasks, risk matrices, and dependency graphs.
- One-click CSV export for ingestion into Jira, Linear, or Excel.

### 6. ✍️ Formal Handover Acknowledgement
- Share certified handover packages with incoming team members.
- Cryptographic acknowledgement tracking with timestamped audit logs.

---

## 🎨 UI/UX Design System (Light Theme Only)

KnowBridge AI follows a commercial SaaS dashboard aesthetic:
- **Primary:** Soft Blue (`#4F7DF3`)
- **Secondary / Active:** Light Lavender (`#F0EDFF`)
- **Background:** Crisp Off-White (`#F8FAFC`)
- **Cards & Surfaces:** Pure White (`#FFFFFF`) with subtle elevation shadows (`0 1px 3px rgba(0,0,0,0.04)`)
- **Accent:** Soft Teal (`#43BFA5`)
- **Typography:** Inter (`sans-serif`)
- **Indicators:** Soft Orange (Warning), Soft Red (Critical Risks), Emerald Green (Verified)

---

## 🏗️ Architecture & Clean File Structure

```
knowledgebridge/
├── app.py                   # Main Flask REST API & Web Controller
├── models.py                # Relational SQLite SQLAlchemy Models (12 tables)
├── config.py                # Environment-based Configuration
├── ai_engine.py             # Dual-engine AI (OpenAI, Gemini + Offline Fallback)
├── requirements.txt         # Core production dependencies
├── .env.example             # Configuration template
├── .gitignore               # Ignored cache, databases, and uploaded artifacts
├── test_knowbridge.py       # End-to-end automated verification test suite
├── static/
│   ├── css/
│   │   └── style.css        # Custom responsive SaaS stylesheet (Light theme)
│   └── js/
│       └── app.js           # Shared API client, toasts, and UI helpers
├── templates/
│   ├── base.html            # Core dashboard layout with sidebar & mobile offcanvas
│   ├── index.html           # Public landing page with problem/solution showcase
│   ├── auth.html            # Registration & login portal (Role-based)
│   ├── dashboard.html       # Analytics overview with dynamic Chart.js visualizations
│   ├── projects.html        # Project management & workspace directory
│   ├── project_detail.html  # Single project workspace overview & navigation hub
│   ├── documents.html       # Drag-and-drop document upload & AI extraction
│   ├── decisions.html       # Decision management & evidence tracking
│   ├── tasks.html           # Kanban-style task & ownership tracking
│   ├── risks.html           # Risk severity matrix & dependency mapping
│   ├── review.html          # Human review & verification queue
│   └── reports.html         # PDF/CSV generation & acknowledgement tracker
├── uploads/                 # Storage for authorized uploaded documents
└── reports/                 # Generated PDF handover documents
```

---

## ⚡ Quick Start & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/knowbridge-ai.git
cd knowbridge-ai
```

### 2. Create and Activate a Virtual Environment
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

*(Optional)* To use cloud LLMs, add your API key in `.env`:
```ini
SECRET_KEY=knowbridge-super-secret-key-change-me
AI_PROVIDER=none    # Set to 'openai' or 'gemini' when you have a key
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
```
> **Note:** If `AI_PROVIDER=none`, KnowBridge AI runs in **Offline Heuristic Mode** and performs document extraction without any external API calls.

### 5. Run the Application
```bash
python app.py
```
Open your browser and navigate to:
**`http://127.0.0.1:5000`**

---

## 🧪 Automated Testing

To run the end-to-end test suite verifying all 11 core handover workflows:
```bash
python test_knowbridge.py
```

---

## 👥 User Roles & Access Control

| Role | Permissions |
|---|---|
| **Admin** | Full system access, project deletion, configuration management |
| **Reviewer** | Review queue, verification approval/rejection, audit access |
| **Outgoing Member** | Document upload, AI extraction trigger, task creation |
| **Incoming Member** | Knowledge base access, report inspection, formal handover signoff |

---

## 📄 License
Released under the [MIT License](LICENSE).
