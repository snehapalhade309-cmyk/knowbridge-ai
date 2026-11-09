<div align="center">

<img src="https://img.shields.io/badge/KnowBridge-AI-467B75?style=for-the-badge&logo=python&logoColor=white" height="40"/>

# 🌿 KnowBridge AI
### Intelligent Knowledge Handover Platform

**"Never Let Critical Project Knowledge Leave With People."**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![JWT](https://img.shields.io/badge/JWT-Auth-FB015B?style=flat-square&logo=jsonwebtokens&logoColor=white)](https://jwt.io)
[![Gemini](https://img.shields.io/badge/Google-Gemini%20AI-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[🚀 Live Demo](#-quick-start) · [📖 API Docs](#-rest-api-reference) · [🎯 Features](#-features)

</div>

---

## 📌 What is KnowBridge AI?

KnowBridge AI is a **full-stack AI-powered Knowledge Handover Platform** that prevents mission-critical project knowledge from disappearing when team members leave.

It processes project documents, extracts decisions, tasks, risks and dependencies using **Google Gemini AI**, requires **human review and approval**, and generates **auditable handover reports** with digital acknowledgements.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Knowledge Extraction** | Google Gemini 1.5 Flash + local NLP fallback |
| 📄 **Document Processing** | PDF, DOCX, CSV, TXT with text extraction |
| 👁 **Human Review Workflow** | Approve/reject AI findings before they go live |
| 📦 **Handover Reports** | Generate, approve, export as PDF or CSV |
| ✍ **Acknowledgement Tracking** | Digital sign-off with timestamps |
| 🔐 **JWT Authentication** | Bearer token + session dual-auth |
| 👥 **Role-Based Access** | 4 roles: Admin, PM, Outgoing, Incoming |
| 📊 **Live Analytics** | Chart.js dashboards with real data |
| 🗂 **Audit Trail** | Every action logged with user + timestamp |
| 🌐 **34+ REST APIs** | Fully functional, testable from browser |

---

## 🎨 Design

> Light-themed premium SaaS design — no dark backgrounds.

| Color | Hex | Usage |
|-------|-----|-------|
| 🟨 Warm Ivory | `#F8F6F0` | App background |
| 🟩 Soft Sage Green | `#DCE9E4` | Cards & badges |
| 🟦 Muted Teal | `#467B75` | Sidebar & navigation |
| 🟧 Terracotta | `#A94F3B` | Buttons & CTAs |
| ⬛ Charcoal | `#292D2B` | Typography |

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/snehapalhade309-cmyk/knowbridge-ai.git
cd knowbridge-ai
```

### 2. Create virtual environment
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup environment
```bash
cp .env.example .env
```

### 5. Run the server
```bash
python app.py
```

### 6. Open in browser
```
http://localhost:5000
```

---

## 🔑 Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| 👑 Admin | `admin@knowbridge.ai` | `admin123` |
| 📋 Project Manager | `sarah@knowbridge.ai` | `sarah123` |
| 📤 Outgoing Member | `alex@knowbridge.ai` | `alex123` |
| 📥 Incoming Member | `priya@knowbridge.ai` | `priya123` |

---

## 🌐 Application Pages

| URL | Page |
|-----|------|
| `/` | Landing Page |
| `/dashboard` | Dashboard + Charts |
| `/projects` | Project Management |
| `/projects/1/documents` | Document Upload & AI Analysis |
| `/projects/1/tasks` | Tasks & Decisions |
| `/projects/1/review` | Human Review Queue |
| `/api-docs` | Interactive REST API Explorer |
| `/settings` | Settings + Gemini Key Config |

---

## 🔌 REST API Reference

> All `/api/` endpoints support **JWT Bearer Token** + **Web Session** auth.

### Authentication
```
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me
POST   /api/auth/logout
```

### Projects
```
GET    /api/projects
POST   /api/projects
GET    /api/projects/<id>
PUT    /api/projects/<id>
DELETE /api/projects/<id>
```

### Documents
```
POST   /api/documents/upload
GET    /api/documents
GET    /api/documents/<id>
DELETE /api/documents/<id>
```

### AI Processing
```
POST   /api/ai/analyze/<document_id>
GET    /api/ai/results/<project_id>
POST   /api/ai/summarize
POST   /api/ai/extract-decisions
POST   /api/ai/detect-risks
```

### Tasks & Decisions
```
GET    /api/tasks
POST   /api/tasks
PUT    /api/tasks/<id>
GET    /api/decisions
POST   /api/decisions
```

### Handovers
```
POST   /api/handovers/generate
GET    /api/handovers
GET    /api/handovers/<id>
POST   /api/handovers/<id>/approve
POST   /api/handovers/<id>/reject
```

### Acknowledgements & Analytics
```
GET    /api/acknowledgements
POST   /api/acknowledgements/<id>/confirm
GET    /api/analytics/dashboard
```

---

## 🧠 AI Pipeline

```
Document Upload (PDF/DOCX/TXT/CSV)
         ↓
  Permission Validation
         ↓
  Text Extraction & Parsing
         ↓
  AI Analysis (Gemini / NLP)
         ↓
  Evidence-Linked Findings
         ↓
  Human Review & Approval
         ↓
  Handover Report Generated
         ↓
  Project Manager Sign-Off
         ↓
  Digital Acknowledgement
```

**Gemini AI** — Add your key in Settings for semantic extraction
**Local NLP** — Works 100% offline, zero config needed

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js |
| Backend | Python, Flask, Flask-RESTful |
| Database | SQLite (dev) → PostgreSQL ready |
| Auth | Flask-Login + Flask-JWT-Extended |
| AI | Google Gemini 1.5 Flash + NLP Pipeline |
| Documents | PyPDF2, python-docx, pandas |

---

## 📁 Project Structure

```
knowbridge-ai/
├── app.py               # Main Flask app (2700+ lines)
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── templates/           # 18 Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── api_docs.html
│   └── ...
├── static/
│   ├── css/style.css    # Custom SaaS styles
│   └── js/app.js        # Frontend JS
├── uploads/             # Document storage
└── reports/             # Generated PDFs
```

---

## ⚙️ Environment Variables

```env
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
GEMINI_API_KEY=your-gemini-key   # Optional
FLASK_DEBUG=False
PORT=5000
```

---

<div align="center">

**Built with ❤️ using Python, Flask & Google Gemini AI**

⭐ Star this repo if you found it useful!

</div>
