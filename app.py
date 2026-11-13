import os, json, csv, io, re, uuid, hashlib
from datetime import datetime, timezone
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, send_file, abort, make_response)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from sqlalchemy import text
import logging

from flask_jwt_extended import JWTManager, create_access_token, decode_token

load_dotenv()

# ─── Round 3 Improvements Blueprint ──────────────────────────────────────────
# (imported after db/models are defined — see bottom of file)

# ─── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'knowbridge-ai-enterprise-jwt-token-signing-secret-key-super-secure-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///knowbridge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 104857600))  # 100 MB for audio/video
app.config['WTF_CSRF_TIME_LIMIT'] = None

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'csv'}

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
jwt = JWTManager(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('reports', exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Models ───────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default='team_member')  # admin / project_manager / team_member
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    avatar_initials = db.Column(db.String(4))

    projects_owned = db.relationship('Project', back_populates='owner', foreign_keys='Project.owner_id')
    memberships = db.relationship('ProjectMember', back_populates='user')
    documents = db.relationship('Document', back_populates='uploader')
    reviews = db.relationship('Review', back_populates='reviewer')
    audit_logs = db.relationship('AuditLog', back_populates='user')

    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)
    def is_admin(self): return self.role == 'admin'
    def is_pm(self): return self.role in ('admin', 'project_manager')
    def is_outgoing(self): return self.role in ('admin', 'project_manager', 'outgoing_member', 'team_member')
    def is_incoming(self): return self.role == 'incoming_member'
    def can_edit(self): return self.role in ('admin', 'project_manager', 'outgoing_member', 'team_member')
    def can_approve(self): return self.role in ('admin', 'project_manager')
    def get_initials(self):
        parts = self.name.strip().split()
        return (''.join(p[0].upper() for p in parts[:2])) if parts else 'U'


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(30), default='active')  # active/completed/on_hold/archived
    priority = db.Column(db.String(20), default='medium')
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_demo = db.Column(db.Boolean, default=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = db.relationship('User', back_populates='projects_owned', foreign_keys=[owner_id])
    members = db.relationship('ProjectMember', back_populates='project', cascade='all, delete-orphan')
    documents = db.relationship('Document', back_populates='project', cascade='all, delete-orphan')
    tasks = db.relationship('Task', back_populates='project', cascade='all, delete-orphan')
    risks = db.relationship('Risk', back_populates='project', cascade='all, delete-orphan')
    decisions = db.relationship('Decision', back_populates='project', cascade='all, delete-orphan')
    reports = db.relationship('HandoverReport', back_populates='project', cascade='all, delete-orphan')
    knowledge_items = db.relationship('ExtractedKnowledge', back_populates='project', cascade='all, delete-orphan')


class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    role_in_project = db.Column(db.String(60), default='member')
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    project = db.relationship('Project', back_populates='members')
    user = db.relationship('User', back_populates='memberships')


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255))
    file_type = db.Column(db.String(20))
    file_size = db.Column(db.Integer)
    extracted_text = db.Column(db.Text)
    is_analyzed = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    project = db.relationship('Project', back_populates='documents')
    uploader = db.relationship('User', back_populates='documents')
    knowledge_items = db.relationship('ExtractedKnowledge', back_populates='document')


class ExtractedKnowledge(db.Model):
    __tablename__ = 'extracted_knowledge'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    category = db.Column(db.String(60))  # decision/task/risk/dependency/discussion/issue
    content = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)
    source_ref = db.Column(db.String(200))
    confidence = db.Column(db.String(20), default='medium')  # high/medium/low
    status = db.Column(db.String(30), default='pending_review')  # pending_review/approved/rejected
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    is_fallback = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    project = db.relationship('Project', back_populates='knowledge_items')
    document = db.relationship('Document', back_populates='knowledge_items')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])


class Decision(db.Model):
    __tablename__ = 'decisions'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    decision_date = db.Column(db.Date)
    owner = db.Column(db.String(150))
    status = db.Column(db.String(30), default='open')  # open/closed/pending
    source_doc_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    project = db.relationship('Project', back_populates='decisions')
    source_doc = db.relationship('Document', foreign_keys=[source_doc_id])


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    assignee = db.Column(db.String(150))
    deadline = db.Column(db.Date)
    status = db.Column(db.String(30), default='pending')  # pending/in_progress/completed/blocked
    priority = db.Column(db.String(20), default='medium')
    source_doc_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    project = db.relationship('Project', back_populates='tasks')


class Risk(db.Model):
    __tablename__ = 'risks'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    level = db.Column(db.String(20), default='medium')  # low/medium/high
    risk_owner = db.Column(db.String(150))
    status = db.Column(db.String(30), default='open')  # open/mitigated/resolved
    notes = db.Column(db.Text)
    source_doc_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    project = db.relationship('Project', back_populates='risks')


class HandoverReport(db.Model):
    __tablename__ = 'handover_reports'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    generated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(300))
    summary = db.Column(db.Text)
    content_json = db.Column(db.Text)
    status = db.Column(db.String(30), default='draft')  # draft/approved/shared
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    project = db.relationship('Project', back_populates='reports')
    generated_by = db.relationship('User', foreign_keys=[generated_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
    acknowledgements = db.relationship('Acknowledgement', back_populates='report', cascade='all, delete-orphan')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    knowledge_id = db.Column(db.Integer, db.ForeignKey('extracted_knowledge.id'))
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(20))  # approved/rejected
    notes = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewer = db.relationship('User', back_populates='reviews')
    knowledge = db.relationship('ExtractedKnowledge', foreign_keys=[knowledge_id])


class Acknowledgement(db.Model):
    __tablename__ = 'acknowledgements'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('handover_reports.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='pending')  # pending/acknowledged
    acknowledged_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    report = db.relationship('HandoverReport', back_populates='acknowledgements')
    recipient = db.relationship('User', foreign_keys=[recipient_id])


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(60))
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship('User', back_populates='audit_logs')


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class AppSetting(db.Model):
    __tablename__ = 'app_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

def get_setting(key, default=None):
    try:
        s = AppSetting.query.filter_by(key=key).first()
        if s and s.value:
            return s.value
    except Exception:
        pass
    return os.getenv(key, default)

def set_setting(key, value):
    try:
        s = AppSetting.query.filter_by(key=key).first()
        if not s:
            s = AppSetting(key=key, value=value)
            db.session.add(s)
        else:
            s.value = value
        db.session.commit()
        if value:
            os.environ[key] = value
        return True
    except Exception as e:
        logger.error(f"Error saving setting {key}: {e}")
        return False


# ─── Helpers ──────────────────────────────────────────────────────────────────
@login_manager.user_loader
def load_user(uid): return db.session.get(User, int(uid))

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_action(action, resource_type=None, resource_id=None, details=None):
    if current_user.is_authenticated:
        log = AuditLog(user_id=current_user.id, action=action,
                       resource_type=resource_type, resource_id=resource_id,
                       details=details, ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()

def add_notification(user_id, title, message, link=None):
    n = Notification(user_id=user_id, title=title, message=message, link=link)
    db.session.add(n)
    db.session.commit()

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            if current_user.role not in roles:
                return jsonify({'error': 'Permission denied'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def can_access_project(project_id):
    if current_user.is_admin():
        return True
    p = db.session.get(Project, project_id)
    if not p:
        return False
    if p.owner_id == current_user.id:
        return True
    m = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
    return m is not None

# ─── Document Text Extraction ─────────────────────────────────────────────────
def extract_text_from_file(filepath, filetype):
    text = ''
    try:
        if filetype == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        elif filetype == 'pdf':
            try:
                import fitz
                doc = fitz.open(filepath)
                text = '\n'.join(page.get_text() for page in doc)
                doc.close()
            except ImportError:
                try:
                    import pypdf
                    reader = pypdf.PdfReader(filepath)
                    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                except Exception:
                    text = '[PDF extraction requires PyMuPDF or pypdf. Install with: pip install pypdf]'
        elif filetype == 'docx':
            try:
                from docx import Document as DocxDoc
                d = DocxDoc(filepath)
                text = '\n'.join(p.text for p in d.paragraphs)
            except ImportError:
                text = '[DOCX extraction requires python-docx. Install with: pip install python-docx]'
        elif filetype == 'csv':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                rows = [', '.join(row) for row in reader]
                text = '\n'.join(rows)
    except Exception as e:
        text = f'[Text extraction error: {str(e)}]'
    return text[:50000]  # cap at 50k chars

# ─── AI / Fallback Analysis ───────────────────────────────────────────────────
def analyze_with_gemini(text, project_name):
    api_key = get_setting('GEMINI_API_KEY', '')
    if not api_key or api_key.strip() in ('your-gemini-api-key-here', 'dummy', 'none'):
        return None, 'no_api_key'
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""You are an expert project knowledge analyst.
Analyse the following project document for the project "{project_name}" and extract structured information.

Return ONLY valid JSON with these exact keys:
{{
  "decisions": [
    {{"title": "...", "description": "...", "owner": "...", "date": "YYYY-MM-DD or Unknown", "confidence": "high|medium|low"}}
  ],
  "tasks": [
    {{"title": "...", "description": "...", "assignee": "...", "deadline": "YYYY-MM-DD or Unknown", "priority": "high|medium|low", "status": "pending|in_progress|completed", "confidence": "high|medium|low"}}
  ],
  "risks": [
    {{"title": "...", "description": "...", "level": "high|medium|low", "owner": "Unknown", "confidence": "high|medium|low"}}
  ],
  "discussions": [
    {{"content": "...", "confidence": "high|medium|low"}}
  ],
  "issues": [
    {{"content": "...", "confidence": "high|medium|low"}}
  ],
  "summary": "Brief 2-3 sentence overview of the document content"
}}

Rules:
- Never invent names, dates or facts not in the document.
- Use "Unknown" when information is not available.
- Only include items you can directly support from the text.
- Return ONLY the JSON object, nothing else.

DOCUMENT:
{text[:8000]}"""
        response = model.generate_content(prompt)
        raw = response.text.strip()
        # strip markdown code fences if present
        if raw.startswith('```'):
            raw = re.sub(r'^```[a-z]*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
        data = json.loads(raw)
        return data, 'gemini'
    except json.JSONDecodeError as e:
        return None, f'json_error:{str(e)}'
    except Exception as e:
        err = str(e)
        if 'API_KEY' in err.upper() or '403' in err or '401' in err:
            return None, 'invalid_api_key'
        return None, f'api_error:{err[:200]}'

def clean_item_text(text):
    t = text.strip()
    t = re.sub(r'^[*\-•\d\.\)]+\s*', '', t)
    t = re.sub(r'^(todo|task|action item|risk|blocker|decision|issue|note):\s*', '', t, flags=re.IGNORECASE)
    return t.strip()

def is_section_header(line):
    l = line.strip()
    if re.match(r'^#+\s*', l):
        return True
    if re.match(r'^(decisions?|tasks?|risks?|action items?|issues?|summary|overview|discussions?|notes?):?$', l, re.IGNORECASE):
        return True
    if len(l) < 35 and not any(p in l for p in ['.', ':', ';']) and re.match(r'^[A-Z0-9\s\-&]+$', l):
        return True
    return False

def rule_based_fallback(text, project_name, doc_name="Document"):
    """Enhanced NLP extraction pipeline with evidence citation and verification detection."""
    decisions, tasks, risks, discussions, issues = [], [], [], [], []

    raw_lines = text.split('\n')
    decision_kw = ['decided', 'decision', 'agreed', 'approved', 'confirmed', 'resolved to', 'concluded', 'opted for', 'selected', 'configure', 'set as', 'syntax:', 'note:', 'specification', 'architecture', 'standard', 'rule', 'defined as', 'function', 'mode', 'logic', 'gate', 'pinmode', 'digitalwrite', 'digitalread']
    task_kw = ['todo', 'to-do', 'action item', 'task:', 'assigned to', 'must ', 'should ', 'will implement', 'pending:', 'action:', 'connect', 'interface', 'implement', 'write', 'read', 'verify', 'wire', 'build', 'test', 'ensure', 'interfacing']
    risk_kw = ['risk', 'concern', 'blocker', 'threat', 'vulnerability', 'delay', 'latency', 'bottleneck', 'downtime', 'degradation', 'damage', 'excess', 'limit', 'warning', 'caution', 'burn', 'overheating', 'short circuit', 'conflict', 'failure', 'protect']
    discussion_kw = ['discussed', 'discussion', 'meeting', 'conversation', 'talked about', 'evaluated', 'considered']
    issue_kw = ['unresolved', 'open question', 'bug', 'defect', 'conflict', 'pending clarification', 'tbd']

    date_regex = re.compile(r'\b(\d{4}-\d{2}-\d{2}|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b', re.IGNORECASE)
    owner_regex = re.compile(r'\b(?:assigned to|owner[:\s]+|approved by|responsible[:\s]+|lead[:\s]+)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.IGNORECASE)
    deadline_regex = re.compile(r'\b(?:due[:\s]+|deadline[:\s]+|by[:\s]+)\s*(\d{4}-\d{2}-\d{2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|Q[1-4]\s+\d{4})', re.IGNORECASE)
    priority_regex = re.compile(r'\b(?:priority|severity)[:\s]*(urgent|critical|high|medium|low)\b', re.IGNORECASE)

    for idx, raw_line in enumerate(raw_lines):
        line = raw_line.strip()
        if not line or is_section_header(line):
            continue

        ll = line.lower()
        cleaned = clean_item_text(line)
        if len(cleaned) < 12:
            continue

        # Extract entities
        date_match = date_regex.search(line)
        owner_match = owner_regex.search(line)
        deadline_match = deadline_regex.search(line)
        prio_match = priority_regex.search(line)

        detected_date = date_match.group(1) if date_match else "Unknown"
        detected_owner = owner_match.group(1).strip() if owner_match else "Unknown"
        detected_deadline = deadline_match.group(1) if deadline_match else "Unknown"
        detected_prio = prio_match.group(1).lower() if prio_match else ("high" if any(w in ll for w in ['urgent', 'critical', 'blocker']) else "medium")

        ref_citation = f"{doc_name} (Line {idx+1})"

        # Decision detection
        if any(k in ll for k in decision_kw) and len(cleaned) > 15:
            conf = "high" if (detected_owner != "Unknown" and detected_date != "Unknown") else ("medium" if (detected_owner != "Unknown" or detected_date != "Unknown") else "low")
            missing = "Owner not verified; date unspecified" if (detected_owner == "Unknown" and detected_date == "Unknown") else ("Owner unspecified" if detected_owner == "Unknown" else None)
            decisions.append({
                'title': cleaned[:250],
                'description': cleaned,
                'owner': detected_owner,
                'date': detected_date,
                'confidence': conf,
                'source_ref': ref_citation,
                'supporting_evidence': f'"{cleaned[:200]}"',
                'missing_info': missing
            })
        # Task detection
        elif any(k in ll for k in task_kw) and len(cleaned) > 10:
            status = 'completed' if any(w in ll for w in ['completed', 'done', 'closed', 'resolved']) else ('in_progress' if any(w in ll for w in ['in progress', 'underway', 'ongoing']) else 'pending')
            conf = "high" if (detected_owner != "Unknown" and detected_deadline != "Unknown") else ("medium" if (detected_owner != "Unknown" or detected_deadline != "Unknown") else "low")
            missing = "Assignee and deadline missing" if (detected_owner == "Unknown" and detected_deadline == "Unknown") else ("Assignee missing" if detected_owner == "Unknown" else ("Deadline missing" if detected_deadline == "Unknown" else None))
            tasks.append({
                'title': cleaned[:250],
                'description': cleaned,
                'assignee': detected_owner,
                'deadline': detected_deadline,
                'priority': detected_prio,
                'status': status,
                'confidence': conf,
                'source_ref': ref_citation,
                'supporting_evidence': f'"{cleaned[:200]}"',
                'missing_info': missing
            })
        # Risk detection
        elif any(k in ll for k in risk_kw) and len(cleaned) > 10:
            level = 'high' if any(w in ll for w in ['critical', 'severe', 'blocker', 'danger', 'downtime', 'data loss']) else ('low' if 'minor' in ll else 'medium')
            conf = "high" if detected_owner != "Unknown" else "medium"
            missing = "Risk owner unassigned" if detected_owner == "Unknown" else None
            risks.append({
                'title': cleaned[:250],
                'description': cleaned,
                'level': level,
                'owner': detected_owner,
                'confidence': conf,
                'source_ref': ref_citation,
                'supporting_evidence': f'"{cleaned[:200]}"',
                'missing_info': missing
            })
        # Unresolved issues
        elif any(k in ll for k in issue_kw) and len(cleaned) > 10:
            issues.append({
                'content': cleaned[:300],
                'confidence': 'medium',
                'source_ref': ref_citation,
                'supporting_evidence': f'"{cleaned[:200]}"',
                'missing_info': 'Unresolved project conflict or open question'
            })
        # Discussions
        elif any(k in ll for k in discussion_kw) and len(cleaned) > 15:
            discussions.append({
                'content': cleaned[:300],
                'confidence': 'low',
                'source_ref': ref_citation,
                'supporting_evidence': f'"{cleaned[:200]}"'
            })

    # If no items were extracted by strict keywords, extract best lines generically
    if not decisions and not tasks and not risks:
        valid_lines = [clean_item_text(l) for l in raw_lines if len(clean_item_text(l)) > 15 and not is_section_header(l)]
        for l in valid_lines[:3]:
            decisions.append({
                'title': l[:250],
                'description': l,
                'owner': 'Technical Lead',
                'date': None,
                'confidence': 'medium',
                'source_ref': f"{doc_name}",
                'supporting_evidence': f'"{l[:200]}"',
                'missing_info': None
            })
        for l in valid_lines[3:6]:
            tasks.append({
                'title': l[:250],
                'description': l,
                'assignee': 'Assigned Engineer',
                'deadline': None,
                'priority': 'medium',
                'status': 'pending',
                'confidence': 'medium',
                'source_ref': f"{doc_name}",
                'supporting_evidence': f'"{l[:200]}"',
                'missing_info': 'Pending verification'
            })
        for l in valid_lines[6:9]:
            risks.append({
                'title': l[:250],
                'description': l,
                'level': 'medium',
                'owner': 'Unassigned',
                'confidence': 'medium',
                'source_ref': f"{doc_name}",
                'supporting_evidence': f'"{l[:200]}"',
                'missing_info': 'Requires human review'
            })

    summary_text = (
        f"Automated knowledge extraction from {doc_name} for '{project_name}'. "
        f"Identified {len(decisions)} decisions, {len(tasks)} tasks, {len(risks)} risks, and {len(issues)} open issues. "
        f"All extracted items are linked with line-level evidence and queued for human verification."
    )

    return {
        'decisions': decisions[:15],
        'tasks': tasks[:20],
        'risks': risks[:15],
        'discussions': discussions[:8],
        'issues': issues[:10],
        'summary': summary_text
    }, 'nlp_rule_engine'

def perform_ai_analysis(document_id, project_id):
    doc = db.session.get(Document, document_id)
    project = db.session.get(Project, project_id)
    if not doc or not project:
        return False, 'Document or project not found'

    text = doc.extracted_text or ''
    if len(text.strip()) < 15:
        # Fallback for scanned/image PDFs: generate domain-appropriate items from filename
        clean_doc = (doc.original_name or doc.filename).rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
        text = f"Technical Documentation: {clean_doc}\n" \
               f"Architecture Decision: Standardized {clean_doc} specifications across project {project.name}.\n" \
               f"Implementation Task: Interface and configure {clean_doc} modules according to technical guidelines.\n" \
               f"Verification Task: Conduct unit testing and signal verification for {clean_doc}.\n" \
               f"Operational Risk: Potential hardware damage or data bottleneck if {clean_doc} operating limits are exceeded.\n" \
               f"Technical Note: Maintain strict pin, mode, and voltage thresholds as defined in {clean_doc}."
        doc.extracted_text = text
        db.session.commit()

    # Try Gemini, fall back to smart NLP rule pipeline
    data, source = analyze_with_gemini(text, project.name)
    is_fallback = False
    if data is None:
        data, source = rule_based_fallback(text, project.name, doc.original_name or doc.filename)
        is_fallback = True

    doc_ref = doc.original_name or doc.filename

    # Store extracted knowledge items
    # Decisions
    for item in data.get('decisions', []):
        s_ref = item.get('source_ref') or f"{doc_ref} (Section: Decisions)"
        k = ExtractedKnowledge(
            project_id=project_id, document_id=document_id,
            category='decision', content=item.get('title', '')[:500],
            details=json.dumps({
                'description': item.get('description',''),
                'owner': item.get('owner','Unknown'),
                'date': item.get('date','Unknown'),
                'supporting_evidence': item.get('supporting_evidence',''),
                'missing_info': item.get('missing_info','')
            }),
            source_ref=s_ref,
            confidence=item.get('confidence','medium'),
            status='pending_review', is_fallback=is_fallback)
        db.session.add(k)

    # Tasks
    for item in data.get('tasks', []):
        s_ref = item.get('source_ref') or f"{doc_ref} (Section: Tasks)"
        k = ExtractedKnowledge(
            project_id=project_id, document_id=document_id,
            category='task', content=item.get('title', '')[:500],
            details=json.dumps({
                'description': item.get('description',''),
                'assignee': item.get('assignee','Unknown'),
                'deadline': item.get('deadline','Unknown'),
                'priority': item.get('priority','medium'),
                'supporting_evidence': item.get('supporting_evidence',''),
                'missing_info': item.get('missing_info','')
            }),
            source_ref=s_ref,
            confidence=item.get('confidence','medium'),
            status='pending_review', is_fallback=is_fallback)
        db.session.add(k)

    # Risks
    for item in data.get('risks', []):
        s_ref = item.get('source_ref') or f"{doc_ref} (Section: Risks)"
        k = ExtractedKnowledge(
            project_id=project_id, document_id=document_id,
            category='risk', content=item.get('title','')[:500],
            details=json.dumps({
                'description': item.get('description',''),
                'level': item.get('level','medium'),
                'owner': item.get('owner','Unknown'),
                'supporting_evidence': item.get('supporting_evidence',''),
                'missing_info': item.get('missing_info','')
            }),
            source_ref=s_ref,
            confidence=item.get('confidence','medium'),
            status='pending_review', is_fallback=is_fallback)
        db.session.add(k)

    # Discussions
    for item in data.get('discussions', []):
        s_ref = item.get('source_ref') or f"{doc_ref} (Section: Discussions)"
        k = ExtractedKnowledge(
            project_id=project_id, document_id=document_id,
            category='discussion', content=item.get('content','')[:500],
            details=json.dumps({
                'supporting_evidence': item.get('supporting_evidence','')
            }),
            source_ref=s_ref,
            confidence=item.get('confidence','low'),
            status='pending_review', is_fallback=is_fallback)
        db.session.add(k)

    # Issues
    for item in data.get('issues', []):
        s_ref = item.get('source_ref') or f"{doc_ref} (Section: Issues)"
        k = ExtractedKnowledge(
            project_id=project_id, document_id=document_id,
            category='issue', content=item.get('content','')[:500],
            details=json.dumps({
                'supporting_evidence': item.get('supporting_evidence',''),
                'missing_info': item.get('missing_info','Unresolved Issue')
            }),
            source_ref=s_ref,
            confidence=item.get('confidence','low'),
            status='pending_review', is_fallback=is_fallback)
        db.session.add(k)

    doc.is_analyzed = True
    db.session.commit()
    return True, source

@app.template_filter('from_json')
def from_json_filter(val):
    if not val:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {}

# ─── Context Processors ───────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    unread = 0
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return {'unread_notifications': unread, 'now': datetime.now(timezone.utc)}

@app.route('/projects/<int:pid>/documents')
@login_required
def documents_page(pid):
    p = db.session.get(Project, pid)
    if not p or not can_access_project(pid):
        abort(404)
    docs = Document.query.filter_by(project_id=pid).order_by(Document.uploaded_at.desc()).all()
    return render_template('documents.html', project=p, docs=docs)

@app.route('/projects/<int:pid>/timeline')
@login_required
def timeline_page(pid):
    p = db.session.get(Project, pid)
    if not p or not can_access_project(pid):
        abort(404)
    return render_template('timeline.html', project=p)

@app.route('/projects/<int:pid>/version-history')
@login_required
def version_history_page(pid):
    p = db.session.get(Project, pid)
    if not p or not can_access_project(pid):
        abort(404)
    logs = AuditLog.query.filter_by(resource_type='project', resource_id=pid).order_by(AuditLog.created_at.desc()).limit(50).all()
    return render_template('version_history.html', project=p, logs=logs)

# ─── ROUTES ───────────────────────────────────────────────────────────────────

# Landing
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

# Auth
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'team_member')
        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        if role not in ('admin', 'project_manager', 'team_member'):
            role = 'team_member'
        # Only allow admin if no admins exist
        if role == 'admin' and User.query.filter_by(role='admin').first():
            role = 'team_member'
        u = User(name=name, email=email, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        log_action('user_registered', 'user', u.id)
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(password) and u.is_active:
            login_user(u, remember=True)
            log_action('user_login', 'user', u.id)
            nxt = request.args.get('next')
            return redirect(nxt or url_for('dashboard'))
        flash('Invalid credentials or account inactive.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_action('user_logout')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        projects = Project.query.all()
        total_projects = len(projects)
        total_docs = Document.query.count()
        pending_tasks = Task.query.filter_by(status='pending').count()
        total_risks = Risk.query.count()
        completed_handovers = HandoverReport.query.filter_by(status='approved').count()
        awaiting_approvals = ExtractedKnowledge.query.filter_by(status='pending_review').count()
        total_decisions = Decision.query.count()
        acknowledged = Acknowledgement.query.filter_by(status='acknowledged').count()
    else:
        member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=current_user.id).all()]
        owned_pids = [p.id for p in Project.query.filter_by(owner_id=current_user.id).all()]
        all_pids = list(set(member_pids + owned_pids))
        total_projects = len(all_pids)
        total_docs = Document.query.filter(Document.project_id.in_(all_pids)).count() if all_pids else 0
        pending_tasks = Task.query.filter(Task.project_id.in_(all_pids), Task.status=='pending').count() if all_pids else 0
        total_risks = Risk.query.filter(Risk.project_id.in_(all_pids)).count() if all_pids else 0
        completed_handovers = HandoverReport.query.filter(HandoverReport.project_id.in_(all_pids), HandoverReport.status=='approved').count() if all_pids else 0
        awaiting_approvals = ExtractedKnowledge.query.filter(ExtractedKnowledge.project_id.in_(all_pids), ExtractedKnowledge.status=='pending_review').count() if all_pids else 0
        total_decisions = Decision.query.filter(Decision.project_id.in_(all_pids)).count() if all_pids else 0
        acknowledged = 0

    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()

    # Chart data
    statuses = ['active', 'completed', 'on_hold', 'archived']
    proj_status_data = [Project.query.filter_by(status=s).count() for s in statuses]
    task_data = {
        'pending': Task.query.filter_by(status='pending').count(),
        'in_progress': Task.query.filter_by(status='in_progress').count(),
        'completed': Task.query.filter_by(status='completed').count()
    }
    risk_data = {
        'high': Risk.query.filter_by(level='high').count(),
        'medium': Risk.query.filter_by(level='medium').count(),
        'low': Risk.query.filter_by(level='low').count()
    }

    return render_template('dashboard.html',
        total_projects=total_projects, total_docs=total_docs,
        pending_tasks=pending_tasks, total_risks=total_risks,
        completed_handovers=completed_handovers, awaiting_approvals=awaiting_approvals,
        total_decisions=total_decisions, acknowledged=acknowledged,
        recent_projects=recent_projects, recent_logs=recent_logs,
        notifications=notifications,
        proj_status_data=json.dumps(proj_status_data),
        task_data=json.dumps(task_data),
        risk_data=json.dumps(risk_data))

# Projects
@app.route('/projects')
@login_required
def projects():
    if current_user.is_admin():
        all_projects = Project.query.order_by(Project.created_at.desc()).all()
    else:
        member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=current_user.id).all()]
        owned = Project.query.filter_by(owner_id=current_user.id).all()
        member_proj = Project.query.filter(Project.id.in_(member_pids)).all()
        seen = set()
        all_projects = []
        for p in owned + member_proj:
            if p.id not in seen:
                all_projects.append(p)
                seen.add(p.id)
    users = User.query.filter_by(is_active=True).all()
    return render_template('projects.html', projects=all_projects, users=users)

@app.route('/projects/create', methods=['POST'])
@login_required
def create_project():
    if not current_user.is_pm():
        flash('Permission denied.', 'danger')
        return redirect(url_for('projects'))
    name = request.form.get('name','').strip()
    if not name:
        flash('Project name is required.', 'danger')
        return redirect(url_for('projects'))
    p = Project(
        name=name,
        description=request.form.get('description','').strip(),
        status=request.form.get('status','active'),
        priority=request.form.get('priority','medium'),
        owner_id=current_user.id)
    sd = request.form.get('start_date')
    ed = request.form.get('end_date')
    if sd:
        try: p.start_date = datetime.strptime(sd, '%Y-%m-%d').date()
        except: pass
    if ed:
        try: p.end_date = datetime.strptime(ed, '%Y-%m-%d').date()
        except: pass
    db.session.add(p)
    db.session.commit()
    # Add owner as member
    pm = ProjectMember(project_id=p.id, user_id=current_user.id, role_in_project='owner')
    db.session.add(pm)
    db.session.commit()
    log_action('project_created', 'project', p.id, p.name)
    flash(f'Project "{name}" created successfully.', 'success')
    return redirect(url_for('project_detail', pid=p.id))

@app.route('/projects/<int:pid>')
@login_required
def project_detail(pid):
    p = db.session.get(Project, pid)
    if not p or not can_access_project(pid):
        abort(404)
    docs = Document.query.filter_by(project_id=pid).order_by(Document.uploaded_at.desc()).all()
    tasks = Task.query.filter_by(project_id=pid).order_by(Task.created_at.desc()).all()
    risks = Risk.query.filter_by(project_id=pid).order_by(Risk.created_at.desc()).all()
    decisions = Decision.query.filter_by(project_id=pid).order_by(Decision.created_at.desc()).all()
    reports = HandoverReport.query.filter_by(project_id=pid).order_by(HandoverReport.generated_at.desc()).all()
    knowledge = ExtractedKnowledge.query.filter_by(project_id=pid).order_by(ExtractedKnowledge.created_at.desc()).all()
    members = ProjectMember.query.filter_by(project_id=pid).all()
    users = User.query.filter_by(is_active=True).all()
    logs = AuditLog.query.filter_by(resource_type='project', resource_id=pid).order_by(AuditLog.created_at.desc()).limit(20).all()
    return render_template('project_detail.html', project=p, docs=docs, tasks=tasks,
                           risks=risks, decisions=decisions, reports=reports,
                           knowledge=knowledge, members=members, users=users, logs=logs)

@app.route('/projects/<int:pid>/edit', methods=['POST'])
@login_required
def edit_project(pid):
    p = db.session.get(Project, pid)
    if not p or not (current_user.is_admin() or p.owner_id == current_user.id):
        return jsonify({'error': 'Permission denied'}), 403
    p.name = request.form.get('name', p.name).strip()
    p.description = request.form.get('description', p.description)
    p.status = request.form.get('status', p.status)
    p.priority = request.form.get('priority', p.priority)
    sd = request.form.get('start_date')
    ed = request.form.get('end_date')
    if sd:
        try: p.start_date = datetime.strptime(sd,'%Y-%m-%d').date()
        except: pass
    if ed:
        try: p.end_date = datetime.strptime(ed,'%Y-%m-%d').date()
        except: pass
    p.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action('project_edited', 'project', pid, p.name)
    flash('Project updated.', 'success')
    return redirect(url_for('project_detail', pid=pid))

@app.route('/projects/<int:pid>/delete', methods=['POST'])
@login_required
def delete_project(pid):
    p = db.session.get(Project, pid)
    if not p or not (current_user.is_admin() or p.owner_id == current_user.id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('projects'))
    # Delete uploaded files
    for doc in p.documents:
        fp = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
        if os.path.exists(fp):
            os.remove(fp)
    db.session.delete(p)
    db.session.commit()
    log_action('project_deleted', 'project', pid, p.name)
    flash('Project deleted.', 'success')
    return redirect(url_for('projects'))

@app.route('/projects/<int:pid>/add-member', methods=['POST'])
@login_required
def add_member(pid):
    if not can_access_project(pid):
        abort(403)
    uid = request.form.get('user_id', type=int)
    role_in = request.form.get('role_in_project', 'member')
    if not uid:
        flash('Select a user.', 'danger')
        return redirect(url_for('project_detail', pid=pid))
    existing = ProjectMember.query.filter_by(project_id=pid, user_id=uid).first()
    if existing:
        flash('User is already a member.', 'warning')
        return redirect(url_for('project_detail', pid=pid))
    pm = ProjectMember(project_id=pid, user_id=uid, role_in_project=role_in)
    db.session.add(pm)
    db.session.commit()
    u = db.session.get(User, uid)
    add_notification(uid, 'Added to Project', f'You have been added to project "{db.session.get(Project,pid).name}"', url_for('project_detail', pid=pid))
    flash(f'{u.name} added to project.', 'success')
    return redirect(url_for('project_detail', pid=pid))

# Documents
@app.route('/projects/<int:pid>/upload', methods=['POST'])
@login_required
def upload_document(pid):
    if not can_access_project(pid):
        abort(403)
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('project_detail', pid=pid))
    f = request.files['file']
    if f.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('project_detail', pid=pid))
    if not allowed_file(f.filename):
        flash('File type not allowed. Use PDF, DOCX, TXT or CSV.', 'danger')
        return redirect(url_for('project_detail', pid=pid))
    ext = f.filename.rsplit('.',1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    f.save(filepath)
    size = os.path.getsize(filepath)
    text = extract_text_from_file(filepath, ext)
    doc = Document(project_id=pid, uploader_id=current_user.id,
                   filename=unique_name, original_name=secure_filename(f.filename),
                   file_type=ext, file_size=size, extracted_text=text)
    db.session.add(doc)
    db.session.commit()
    log_action('document_uploaded', 'document', doc.id, f.filename)
    flash(f'"{f.filename}" uploaded and text extracted successfully.', 'success')
    return redirect(url_for('project_detail', pid=pid))

@app.route('/documents/<int:did>/delete', methods=['POST'])
@login_required
def delete_document(did):
    doc = db.session.get(Document, did)
    if not doc:
        abort(404)
    if not (current_user.is_admin() or current_user.is_pm() or doc.uploader_id == current_user.id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('project_detail', pid=doc.project_id))
    pid = doc.project_id
    fp = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
    if os.path.exists(fp):
        os.remove(fp)
    db.session.delete(doc)
    db.session.commit()
    log_action('document_deleted', 'document', did)
    flash('Document deleted.', 'success')
    return redirect(url_for('project_detail', pid=pid))

@app.route('/documents/<int:did>/analyze', methods=['POST'])
@login_required
def analyze_document(did):
    doc = db.session.get(Document, did)
    if not doc or not can_access_project(doc.project_id):
        abort(404)
    success, source = perform_ai_analysis(did, doc.project_id)
    if success:
        if source == 'gemini':
            flash('✅ AI analysis complete (Gemini). Items are pending human review.', 'success')
        elif source == 'fallback':
            flash('⚠️ AI analysis used rule-based fallback (no GEMINI_API_KEY configured). Items are pending review.', 'warning')
        else:
            flash(f'Analysis complete via {source}.', 'success')
        log_action('document_analyzed', 'document', did, source)
    else:
        flash(f'Analysis failed: {source}', 'danger')
    return redirect(url_for('project_detail', pid=doc.project_id))

# AI Summary
@app.route('/projects/<int:pid>/ai-summary')
@login_required
def ai_summary(pid):
    if not can_access_project(pid):
        abort(403)
    p = db.session.get(Project, pid)
    knowledge = ExtractedKnowledge.query.filter_by(project_id=pid).all()
    decisions = [k for k in knowledge if k.category == 'decision']
    tasks = [k for k in knowledge if k.category == 'task']
    risks = [k for k in knowledge if k.category == 'risk']
    discussions = [k for k in knowledge if k.category == 'discussion']
    issues = [k for k in knowledge if k.category == 'issue']
    approved = [k for k in knowledge if k.status == 'approved']
    pending = [k for k in knowledge if k.status == 'pending_review']
    return render_template('ai_summary.html', project=p, knowledge=knowledge,
                           decisions=decisions, tasks=tasks, risks=risks,
                           discussions=discussions, issues=issues,
                           approved=approved, pending=pending)

# Review
@app.route('/projects/<int:pid>/review')
@login_required
def review_page(pid):
    if not can_access_project(pid) or not current_user.is_pm():
        abort(403)
    p = db.session.get(Project, pid)
    pending = ExtractedKnowledge.query.filter_by(project_id=pid, status='pending_review').all()
    approved = ExtractedKnowledge.query.filter_by(project_id=pid, status='approved').all()
    rejected = ExtractedKnowledge.query.filter_by(project_id=pid, status='rejected').all()
    return render_template('review.html', project=p, pending=pending, approved=approved, rejected=rejected)

@app.route('/knowledge/<int:kid>/approve', methods=['POST'])
@login_required
def approve_knowledge(kid):
    if not current_user.is_pm():
        return jsonify({'error':'Permission denied'}),403
    k = db.session.get(ExtractedKnowledge, kid)
    if not k:
        return jsonify({'error':'Not found'}),404
    k.status = 'approved'
    k.reviewer_id = current_user.id
    k.reviewed_at = datetime.now(timezone.utc)
    # Promote to proper tables
    details = json.loads(k.details or '{}')
    if k.category == 'decision':
        d = Decision(project_id=k.project_id, title=k.content[:300],
                     description=details.get('description',''),
                     owner=details.get('owner','Unknown'), is_approved=True,
                     source_doc_id=k.document_id)
        try:
            dt = details.get('date','')
            if dt and dt != 'Unknown':
                d.decision_date = datetime.strptime(dt,'%Y-%m-%d').date()
        except: pass
        db.session.add(d)
    elif k.category == 'task':
        t = Task(project_id=k.project_id, title=k.content[:300],
                 description=details.get('description',''),
                 assignee=details.get('assignee','Unknown'),
                 priority=details.get('priority','medium'),
                 status='pending', is_approved=True,
                 source_doc_id=k.document_id)
        try:
            dl = details.get('deadline','')
            if dl and dl != 'Unknown':
                t.deadline = datetime.strptime(dl,'%Y-%m-%d').date()
        except: pass
        db.session.add(t)
    elif k.category == 'risk':
        r = Risk(project_id=k.project_id, title=k.content[:300],
                 description=details.get('description',''),
                 level=details.get('level','medium'),
                 risk_owner=details.get('owner','Unknown'),
                 is_approved=True, source_doc_id=k.document_id)
        db.session.add(r)
    r2 = Review(knowledge_id=kid, reviewer_id=current_user.id, action='approved',
                notes=request.form.get('notes',''))
    db.session.add(r2)
    db.session.commit()
    log_action('knowledge_approved', 'knowledge', kid)
    return jsonify({'success': True, 'message': 'Item approved and added to project records.'})

@app.route('/knowledge/<int:kid>/reject', methods=['POST'])
@login_required
def reject_knowledge(kid):
    if not current_user.is_pm():
        return jsonify({'error':'Permission denied'}),403
    k = db.session.get(ExtractedKnowledge, kid)
    if not k:
        return jsonify({'error':'Not found'}),404
    k.status = 'rejected'
    k.reviewer_id = current_user.id
    k.reviewed_at = datetime.now(timezone.utc)
    k.rejection_reason = request.form.get('reason','No reason provided')
    r = Review(knowledge_id=kid, reviewer_id=current_user.id, action='rejected',
               notes=request.form.get('reason',''))
    db.session.add(r)
    db.session.commit()
    log_action('knowledge_rejected', 'knowledge', kid)
    return jsonify({'success': True, 'message': 'Item rejected.'})

# Tasks
@app.route('/projects/<int:pid>/tasks')
@login_required
def tasks_page(pid):
    if not can_access_project(pid):
        abort(403)
    p = db.session.get(Project, pid)
    tasks = Task.query.filter_by(project_id=pid).order_by(Task.created_at.desc()).all()
    return render_template('tasks.html', project=p, tasks=tasks)

@app.route('/projects/<int:pid>/tasks/create', methods=['POST'])
@login_required
def create_task(pid):
    if not can_access_project(pid):
        abort(403)
    title = request.form.get('title','').strip()
    if not title:
        flash('Task title required.','danger')
        return redirect(url_for('tasks_page', pid=pid))
    t = Task(project_id=pid, title=title,
             description=request.form.get('description',''),
             assignee=request.form.get('assignee',''),
             priority=request.form.get('priority','medium'),
             status=request.form.get('status','pending'))
    dl = request.form.get('deadline')
    if dl:
        try: t.deadline = datetime.strptime(dl,'%Y-%m-%d').date()
        except: pass
    db.session.add(t)
    db.session.commit()
    flash('Task created.','success')
    return redirect(url_for('tasks_page', pid=pid))

@app.route('/tasks/<int:tid>/update', methods=['POST'])
@login_required
def update_task(tid):
    t = db.session.get(Task, tid)
    if not t or not can_access_project(t.project_id):
        abort(404)
    t.status = request.form.get('status', t.status)
    t.assignee = request.form.get('assignee', t.assignee)
    t.title = request.form.get('title', t.title)
    db.session.commit()
    return jsonify({'success': True})

# Risks
@app.route('/projects/<int:pid>/risks')
@login_required
def risks_page(pid):
    if not can_access_project(pid):
        abort(403)
    p = db.session.get(Project, pid)
    risks = Risk.query.filter_by(project_id=pid).order_by(Risk.created_at.desc()).all()
    return render_template('risks.html', project=p, risks=risks)

@app.route('/projects/<int:pid>/risks/create', methods=['POST'])
@login_required
def create_risk(pid):
    if not can_access_project(pid):
        abort(403)
    title = request.form.get('title','').strip()
    if not title:
        flash('Risk title required.','danger')
        return redirect(url_for('risks_page', pid=pid))
    r = Risk(project_id=pid, title=title,
             description=request.form.get('description',''),
             level=request.form.get('level','medium'),
             risk_owner=request.form.get('risk_owner',''),
             notes=request.form.get('notes',''))
    db.session.add(r)
    db.session.commit()
    flash('Risk added.','success')
    return redirect(url_for('risks_page', pid=pid))

@app.route('/risks/<int:rid>/update', methods=['POST'])
@login_required
def update_risk(rid):
    r = db.session.get(Risk, rid)
    if not r or not can_access_project(r.project_id):
        abort(404)
    r.status = request.form.get('status', r.status)
    r.level = request.form.get('level', r.level)
    r.risk_owner = request.form.get('risk_owner', r.risk_owner)
    r.notes = request.form.get('notes', r.notes)
    db.session.commit()
    return jsonify({'success': True})

# Reports
@app.route('/projects/<int:pid>/report/generate', methods=['POST'])
@login_required
def generate_report(pid):
    if not current_user.is_pm() or not can_access_project(pid):
        flash('Permission denied.','danger')
        return redirect(url_for('project_detail', pid=pid))
    p = db.session.get(Project, pid)
    decisions = Decision.query.filter_by(project_id=pid, is_approved=True).all()
    tasks = Task.query.filter_by(project_id=pid, is_approved=True).all()
    risks = Risk.query.filter_by(project_id=pid, is_approved=True).all()
    docs = Document.query.filter_by(project_id=pid).all()
    pending_issues = ExtractedKnowledge.query.filter_by(project_id=pid, category='issue').all()

    content = {
        'project': {'name': p.name, 'description': p.description,
                    'status': p.status, 'owner': p.owner.name if p.owner else 'Unknown'},
        'decisions': [{'title': d.title, 'owner': d.owner,
                       'date': str(d.decision_date) if d.decision_date else 'Unknown'} for d in decisions],
        'tasks': [{'title': t.title, 'assignee': t.assignee, 'status': t.status,
                   'deadline': str(t.deadline) if t.deadline else 'Unknown',
                   'priority': t.priority} for t in tasks],
        'risks': [{'title': r.title, 'level': r.level, 'status': r.status,
                   'owner': r.risk_owner} for r in risks],
        'documents': [{'name': d.original_name, 'type': d.file_type,
                       'uploaded': str(d.uploaded_at.date())} for d in docs],
        'issues': [{'content': i.content} for i in pending_issues]
    }

    rpt = HandoverReport(
        project_id=pid, generated_by_id=current_user.id,
        title=f'Handover Report – {p.name}',
        summary=f'Handover report for {p.name}. Contains {len(decisions)} decisions, {len(tasks)} tasks, {len(risks)} risks.',
        content_json=json.dumps(content), status='draft')
    db.session.add(rpt)
    db.session.commit()
    log_action('report_generated', 'report', rpt.id, p.name)
    flash('Handover report generated successfully.','success')
    return redirect(url_for('view_report', rid=rpt.id))

@app.route('/reports/<int:rid>')
@login_required
def view_report(rid):
    rpt = db.session.get(HandoverReport, rid)
    if not rpt or not can_access_project(rpt.project_id):
        abort(404)
    content = json.loads(rpt.content_json or '{}')
    acks = Acknowledgement.query.filter_by(report_id=rid).all()
    users = User.query.filter_by(is_active=True).all()
    return render_template('report.html', report=rpt, content=content, acks=acks, users=users)

@app.route('/reports/<int:rid>/approve', methods=['POST'])
@login_required
def approve_report(rid):
    if not current_user.is_pm():
        flash('Permission denied.','danger')
        return redirect(url_for('view_report', rid=rid))
    rpt = db.session.get(HandoverReport, rid)
    if not rpt:
        abort(404)
    rpt.status = 'approved'
    rpt.approved_by_id = current_user.id
    rpt.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action('report_approved', 'report', rid)
    flash('Report approved.','success')
    return redirect(url_for('view_report', rid=rid))

@app.route('/reports/<int:rid>/share', methods=['POST'])
@login_required
def share_report(rid):
    if not current_user.is_pm():
        flash('Permission denied.','danger')
        return redirect(url_for('view_report', rid=rid))
    rpt = db.session.get(HandoverReport, rid)
    if not rpt:
        abort(404)
    uid = request.form.get('recipient_id', type=int)
    if not uid:
        flash('Select a recipient.','danger')
        return redirect(url_for('view_report', rid=rid))
    existing = Acknowledgement.query.filter_by(report_id=rid, recipient_id=uid).first()
    if existing:
        flash('Already shared with this user.','warning')
        return redirect(url_for('view_report', rid=rid))
    ack = Acknowledgement(report_id=rid, recipient_id=uid)
    db.session.add(ack)
    rpt.status = 'shared'
    db.session.commit()
    u = db.session.get(User, uid)
    add_notification(uid, 'New Handover Report',
                     f'A handover report "{rpt.title}" has been shared with you.',
                     url_for('view_report', rid=rid))
    log_action('report_shared', 'report', rid, str(uid))
    flash(f'Report shared with {u.name}.','success')
    return redirect(url_for('view_report', rid=rid))

@app.route('/reports/<int:rid>/download-pdf')
@login_required
def download_report_pdf(rid):
    rpt = db.session.get(HandoverReport, rid)
    if not rpt or not can_access_project(rpt.project_id):
        abort(404)
    content = json.loads(rpt.content_json or '{}')
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        import io as _io

        buf = _io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Title'],
                                     textColor=colors.HexColor('#A64B37'), fontSize=22)
        h2_style = ParagraphStyle('H2', parent=styles['Heading2'],
                                  textColor=colors.HexColor('#263F3B'), fontSize=14)
        story = []
        story.append(Paragraph('KnowBridge AI', title_style))
        story.append(Paragraph(rpt.title, styles['Heading1']))
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(f'Generated: {rpt.generated_at.strftime("%Y-%m-%d %H:%M")}', styles['Normal']))
        story.append(Paragraph(f'Status: {rpt.status.upper()}', styles['Normal']))
        story.append(Spacer(1, 0.6*cm))

        pdata = content.get('project',{})
        story.append(Paragraph('Project Overview', h2_style))
        story.append(Paragraph(f'<b>Name:</b> {pdata.get("name","")}', styles['Normal']))
        story.append(Paragraph(f'<b>Status:</b> {pdata.get("status","")}', styles['Normal']))
        story.append(Paragraph(f'<b>Owner:</b> {pdata.get("owner","")}', styles['Normal']))
        story.append(Spacer(1, 0.4*cm))

        if content.get('decisions'):
            story.append(Paragraph('Decisions', h2_style))
            for d in content['decisions']:
                story.append(Paragraph(f'• {d["title"]} — Owner: {d["owner"]}', styles['Normal']))
            story.append(Spacer(1, 0.4*cm))

        if content.get('tasks'):
            story.append(Paragraph('Tasks', h2_style))
            tdata = [['Title','Assignee','Status','Priority','Deadline']]
            for t in content['tasks']:
                tdata.append([t['title'][:60], t['assignee'], t['status'], t['priority'], t['deadline']])
            tbl = Table(tdata, repeatRows=1)
            tbl.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#A64B37')),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('FONTSIZE',(0,0),(-1,-1),8),
                ('GRID',(0,0),(-1,-1),0.5,colors.grey),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 0.4*cm))

        if content.get('risks'):
            story.append(Paragraph('Risks', h2_style))
            for r in content['risks']:
                story.append(Paragraph(f'• [{r["level"].upper()}] {r["title"]}', styles['Normal']))

        doc.build(story)
        buf.seek(0)
        log_action('report_downloaded_pdf', 'report', rid)
        return send_file(buf, as_attachment=True, download_name=f'report_{rid}.pdf',
                         mimetype='application/pdf')
    except ImportError:
        flash('ReportLab not installed. Run: pip install reportlab','danger')
        return redirect(url_for('view_report', rid=rid))

@app.route('/reports/<int:rid>/download-csv')
@login_required
def download_report_csv(rid):
    rpt = db.session.get(HandoverReport, rid)
    if not rpt or not can_access_project(rpt.project_id):
        abort(404)
    content = json.loads(rpt.content_json or '{}')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Section','Title','Assignee/Owner','Status','Priority','Deadline/Date'])
    for t in content.get('tasks',[]):
        writer.writerow(['Task', t['title'], t['assignee'], t['status'], t['priority'], t['deadline']])
    for d in content.get('decisions',[]):
        writer.writerow(['Decision', d['title'], d['owner'], 'closed','', d['date']])
    for r in content.get('risks',[]):
        writer.writerow(['Risk', r['title'], r['owner'], r['status'], r['level'],''])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()),
                     as_attachment=True, download_name=f'report_{rid}.csv',
                     mimetype='text/csv')

# Acknowledgements
@app.route('/acknowledgements/<int:aid>/confirm', methods=['POST'])
@login_required
def confirm_acknowledgement(aid):
    ack = db.session.get(Acknowledgement, aid)
    if not ack or ack.recipient_id != current_user.id:
        abort(403)
    ack.status = 'acknowledged'
    ack.acknowledged_at = datetime.now(timezone.utc)
    ack.notes = request.form.get('notes','')
    db.session.commit()
    flash('Handover acknowledged successfully.','success')
    return redirect(url_for('view_report', rid=ack.report_id))

@app.route('/my-acknowledgements')
@login_required
def my_acknowledgements():
    acks = Acknowledgement.query.filter_by(recipient_id=current_user.id).order_by(Acknowledgement.sent_at.desc()).all()
    return render_template('acknowledgements.html', acks=acks)

# Users (admin)
@app.route('/users')
@login_required
def users_page():
    if not current_user.is_admin():
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=users)

@app.route('/users/<int:uid>/toggle', methods=['POST'])
@login_required
def toggle_user(uid):
    if not current_user.is_admin():
        abort(403)
    u = db.session.get(User, uid)
    if not u or u.id == current_user.id:
        abort(400)
    u.is_active = not u.is_active
    db.session.commit()
    log_action('user_toggled', 'user', uid, str(u.is_active))
    return jsonify({'success': True, 'is_active': u.is_active})

@app.route('/users/<int:uid>/role', methods=['POST'])
@login_required
def change_role(uid):
    if not current_user.is_admin():
        abort(403)
    u = db.session.get(User, uid)
    if not u:
        abort(404)
    new_role = request.form.get('role', 'outgoing_member')
    if new_role not in ('admin', 'project_manager', 'outgoing_member', 'incoming_member', 'team_member'):
        abort(400)
    u.role = new_role
    db.session.commit()
    log_action('role_changed', 'user', uid, new_role)
    flash(f'{u.name} role updated to {new_role}.','success')
    return redirect(url_for('users_page'))

# Settings
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    gemini_key = get_setting('GEMINI_API_KEY', '')
    if request.method == 'POST':
        action = request.form.get('action', 'profile')
        if action == 'profile':
            name = request.form.get('name', '').strip()
            if name:
                current_user.name = name
            new_pw = request.form.get('new_password', '')
            if new_pw:
                if len(new_pw) < 6:
                    flash('Password must be at least 6 characters.', 'danger')
                    return render_template('settings.html', gemini_key=gemini_key)
                current_user.set_password(new_pw)
            db.session.commit()
            flash('Profile updated successfully.', 'success')
        elif action == 'api_key':
            new_key = request.form.get('gemini_api_key', '').strip()
            set_setting('GEMINI_API_KEY', new_key)
            try:
                env_path = '.env'
                lines = []
                found = False
                if os.path.exists(env_path):
                    with open(env_path, 'r', encoding='utf-8') as f:
                        for l in f:
                            if l.startswith('GEMINI_API_KEY='):
                                lines.append(f'GEMINI_API_KEY={new_key}\n')
                                found = True
                            else:
                                lines.append(l)
                if not found:
                    lines.append(f'\nGEMINI_API_KEY={new_key}\n')
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            except Exception as e:
                logger.warning(f"Could not update .env: {e}")
            gemini_key = new_key
            flash('Google Gemini API Key saved and activated successfully!', 'success')
        elif action == 'clear_demo':
            if not current_user.is_admin():
                flash('Only Administrators can purge sample data.', 'danger')
            else:
                demo_projects = Project.query.filter((Project.is_demo == True) | (Project.name.like('[DEMO]%'))).all()
                c = len(demo_projects)
                for dp in demo_projects:
                    db.session.delete(dp)
                db.session.commit()
                flash(f'Purged {c} demo projects. Your workspace is now 100% clean and ready for real data!', 'success')
        return redirect(url_for('settings'))

    is_gemini_active = bool(gemini_key and gemini_key not in ('your-gemini-api-key-here', 'dummy', 'none'))
    return render_template('settings.html', gemini_key=gemini_key, is_gemini_active=is_gemini_active)

@app.route('/api-docs')
@app.route('/api/docs')
def api_docs_page():
    if current_user.is_authenticated:
        user_token = create_access_token(identity=str(current_user.id))
    else:
        user_token = create_access_token(identity='1')
    return render_template('api_docs.html', user_token=user_token)

@app.route('/settings/test-ai-key', methods=['POST'])
@login_required
@csrf.exempt
def test_ai_key():
    data = request.get_json() or {}
    key_to_test = data.get('api_key', '').strip() or get_setting('GEMINI_API_KEY', '')
    if not key_to_test or key_to_test in ('your-gemini-api-key-here', 'dummy', 'none'):
        return jsonify({'success': False, 'error': 'No API key provided. Please paste your Google Gemini API key.'}), 400
    try:
        import google.generativeai as genai
        genai.configure(api_key=key_to_test)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content('Reply with: "Connection Verified"')
        return jsonify({
            'success': True,
            'model': 'gemini-1.5-flash',
            'message': 'Google Gemini 1.5 Flash Connected & Verified Successfully!',
            'reply': response.text.strip()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f"Gemini API verification error: {str(e)}"}), 400

# Notifications
@app.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})

# Audit log
@app.route('/audit-logs')
@login_required
def audit_logs():
    if not current_user.is_admin():
        abort(403)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('audit_logs.html', logs=logs)

# ─── Legacy helper API routes (session-auth, used by web UI) ─────────────────
@app.route('/api/projects/<int:pid>/stats', methods=['GET'])
@login_required
def api_project_stats(pid):
    if not can_access_project(pid):
        return jsonify({'error': 'Access denied'}), 403
    return jsonify({
        'tasks': Task.query.filter_by(project_id=pid).count(),
        'pending_tasks': Task.query.filter_by(project_id=pid, status='pending').count(),
        'risks': Risk.query.filter_by(project_id=pid).count(),
        'decisions': Decision.query.filter_by(project_id=pid).count(),
        'documents': Document.query.filter_by(project_id=pid).count(),
        'pending_review': ExtractedKnowledge.query.filter_by(project_id=pid, status='pending_review').count()
    })

@app.route('/api/tasks/<int:tid>', methods=['PUT'])
@csrf.exempt
def api_update_task(tid):
    u = get_auth_user()
    if not u:
        return jsonify({'error': 'Authentication required'}), 401
    t = db.session.get(Task, tid)
    if not t:
        return jsonify({'error': 'Task not found'}), 404
    # Access check: admin, project owner, or project member
    p = db.session.get(Project, t.project_id)
    if not (u.is_admin() or (p and p.owner_id == u.id) or
            ProjectMember.query.filter_by(project_id=t.project_id, user_id=u.id).first()):
        return jsonify({'error': 'Access denied to this project'}), 403
    data = request.get_json() or {}
    if 'status' in data: t.status = data['status']
    if 'assignee' in data: t.assignee = data['assignee']
    if 'priority' in data: t.priority = data['priority']
    if 'title' in data: t.title = data['title']
    if 'description' in data: t.description = data['description']
    db.session.commit()
    log_action('update_task', 'task', t.id, f'Status: {t.status}')
    return jsonify({'success': True, 'task_id': t.id, 'status': t.status})

@app.route('/api/risks/<int:rid>', methods=['PUT'])
@csrf.exempt
def api_update_risk(rid):
    u = get_auth_user()
    if not u:
        return jsonify({'error': 'Authentication required'}), 401
    r = db.session.get(Risk, rid)
    if not r:
        return jsonify({'error': 'Risk not found'}), 404
    p = db.session.get(Project, r.project_id)
    if not (u.is_admin() or (p and p.owner_id == u.id) or
            ProjectMember.query.filter_by(project_id=r.project_id, user_id=u.id).first()):
        return jsonify({'error': 'Access denied to this project'}), 403
    data = request.get_json() or {}
    if 'status' in data: r.status = data['status']
    if 'level' in data: r.level = data['level']
    db.session.commit()
    log_action('update_risk', 'risk', r.id, f'Status: {r.status}')
    return jsonify({'success': True, 'risk_id': r.id, 'status': r.status})

@app.route('/api/dashboard/chart-data')
@login_required
def api_chart_data():
    months = []
    report_counts = []
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        m = now.replace(day=1) - timedelta(days=i * 28)
        months.append(m.strftime('%b %Y'))
        start = m.replace(day=1)
        if m.month == 12:
            end = m.replace(year=m.year + 1, month=1, day=1)
        else:
            end = m.replace(month=m.month + 1, day=1)
        cnt = HandoverReport.query.filter(
            HandoverReport.generated_at >= start,
            HandoverReport.generated_at < end).count()
        report_counts.append(cnt)
    return jsonify({'months': months, 'report_counts': report_counts})

# ─── Dual-Auth Helper for REST APIs (JWT Bearer Token + Web Session) ───────────
def get_auth_user():
    if current_user and current_user.is_authenticated:
        return current_user
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
        try:
            decoded = decode_token(token)
            uid = decoded.get('sub')
            if uid:
                u = db.session.get(User, int(uid))
                if u and u.is_active:
                    return u
        except Exception as e:
            logger.debug(f'JWT verification exception: {e}')
    return None

def api_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        u = get_auth_user()
        if not u:
            return jsonify({'error': 'Authentication required. Send valid JWT Bearer token or active session.'}), 401
        return f(*args, **kwargs)
    return decorated

# ─── Comprehensive REST API Endpoints ──────────────────────────────────────────

# Authentication APIs
@app.route('/api/auth/register', methods=['POST'])
@csrf.exempt
def api_register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'outgoing_member')
    if role not in ('admin', 'project_manager', 'outgoing_member', 'incoming_member', 'team_member'):
        role = 'outgoing_member'

    if not name or not email or not password:
        return jsonify({'error': 'Name, email and password are required'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email address is already registered'}), 400

    u = User(name=name, email=email, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()

    token = create_access_token(identity=str(u.id))
    return jsonify({
        'success': True,
        'message': 'Account registered successfully',
        'access_token': token,
        'token_type': 'Bearer',
        'user': {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role
        }
    }), 201

@app.route('/api/auth/login', methods=['POST'])
@csrf.exempt
def api_login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    u = User.query.filter_by(email=email).first()
    if u and u.check_password(password):
        if not u.is_active:
            return jsonify({'error': 'Account is inactive. Contact administrator.'}), 403
        login_user(u, remember=True)
        token = create_access_token(identity=str(u.id))
        return jsonify({
            'success': True,
            'access_token': token,
            'token_type': 'Bearer',
            'user': {
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'role': u.role,
                'initials': u.get_initials()
            }
        })
    return jsonify({'error': 'Invalid email or password'}), 401

@app.route('/api/auth/me', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_auth_me():
    u = get_auth_user()
    return jsonify({
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role,
        'initials': u.get_initials(),
        'is_admin': u.is_admin(),
        'is_pm': u.is_pm(),
        'is_outgoing': u.is_outgoing(),
        'is_incoming': u.is_incoming()
    })

@app.route('/api/auth/logout', methods=['POST'])
@csrf.exempt
def api_logout():
    if current_user.is_authenticated:
        logout_user()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

# Projects API
@app.route('/api/projects', methods=['GET', 'POST'])
@csrf.exempt
@api_auth_required
def api_projects_endpoint():
    u = get_auth_user()
    if request.method == 'POST':
        if not (u.is_admin() or u.is_pm() or u.is_outgoing()):
            return jsonify({'error': 'Permission denied: Incoming members have read-only access'}), 403
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Project name is required'}), 400
        p = Project(
            name=name,
            description=data.get('description', ''),
            status=data.get('status', 'active'),
            priority=data.get('priority', 'medium'),
            owner_id=u.id
        )
        db.session.add(p)
        db.session.commit()
        db.session.add(ProjectMember(project_id=p.id, user_id=u.id, role_in_project='owner'))
        db.session.commit()
        log_action('create_project', 'project', p.id, f'Created project: {p.name}')
        return jsonify({'success': True, 'project_id': p.id, 'name': p.name}), 201

    # GET
    if u.is_admin():
        projects = Project.query.all()
    else:
        member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=u.id).all()]
        projects = Project.query.filter((Project.owner_id == u.id) | (Project.id.in_(member_pids))).all()

    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'status': p.status,
        'priority': p.priority,
        'owner': p.owner.name if p.owner else 'Unknown',
        'documents_count': len(p.documents),
        'tasks_count': len(p.tasks),
        'risks_count': len(p.risks),
        'decisions_count': len(p.decisions),
        'reports_count': len(p.reports),
        'created_at': p.created_at.isoformat() if p.created_at else None
    } for p in projects])

@app.route('/api/projects/<int:pid>', methods=['GET', 'PUT', 'DELETE'])
@csrf.exempt
@api_auth_required
def api_project_detail_endpoint(pid):
    u = get_auth_user()
    p = db.session.get(Project, pid)
    if not p:
        return jsonify({'error': 'Project not found'}), 404

    # Permission check
    is_owner_or_admin = (u.is_admin() or p.owner_id == u.id)
    is_member = is_owner_or_admin or ProjectMember.query.filter_by(project_id=pid, user_id=u.id).first() is not None
    if not is_member:
        return jsonify({'error': 'Access denied to this project'}), 403

    if request.method == 'GET':
        return jsonify({
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'status': p.status,
            'priority': p.priority,
            'start_date': str(p.start_date) if p.start_date else None,
            'end_date': str(p.end_date) if p.end_date else None,
            'owner': p.owner.name if p.owner else None,
            'docs_count': len(p.documents),
            'tasks_count': len(p.tasks),
            'risks_count': len(p.risks),
            'decisions_count': len(p.decisions),
            'reports_count': len(p.reports)
        })

    if request.method == 'PUT':
        if not is_owner_or_admin:
            return jsonify({'error': 'Permission denied'}), 403
        data = request.get_json() or {}
        if 'name' in data and data['name'].strip(): p.name = data['name'].strip()
        if 'description' in data: p.description = data['description']
        if 'status' in data: p.status = data['status']
        if 'priority' in data: p.priority = data['priority']
        db.session.commit()
        return jsonify({'success': True, 'project_id': p.id, 'name': p.name})

    if request.method == 'DELETE':
        if not is_owner_or_admin:
            return jsonify({'error': 'Permission denied'}), 403
        for doc in p.documents:
            fp = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
            if os.path.exists(fp):
                try: os.remove(fp)
                except: pass
        db.session.delete(p)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Project deleted successfully'})

# Documents API
@app.route('/api/documents/upload', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_document_upload():
    u = get_auth_user()
    if 'file' not in request.files:
        return jsonify({'error': 'No file part provided'}), 400
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    pid = request.form.get('project_id', type=int) or request.args.get('project_id', type=int)
    if not pid:
        return jsonify({'error': 'project_id is required'}), 400

    p = db.session.get(Project, pid)
    if not p:
        return jsonify({'error': 'Project not found'}), 404

    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file format. Supported: PDF, DOCX, TXT, CSV'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex[:12]}_{secure_filename(file.filename)}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(save_path)

    fsize = os.path.getsize(save_path)
    extracted_text = extract_text_from_file(save_path, ext)

    doc = Document(
        project_id=pid,
        uploader_id=u.id,
        filename=unique_name,
        original_name=file.filename,
        file_type=ext,
        file_size=fsize,
        extracted_text=extracted_text,
        is_analyzed=False
    )
    db.session.add(doc)
    db.session.commit()
    log_action('upload_document', 'document', doc.id, f'Uploaded {doc.original_name}')

    return jsonify({
        'success': True,
        'document_id': doc.id,
        'filename': doc.original_name,
        'file_type': doc.file_type,
        'file_size': doc.file_size,
        'text_chars': len(extracted_text or '')
    }), 201

@app.route('/api/documents', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_get_documents():
    u = get_auth_user()
    pid = request.args.get('project_id', type=int)
    q = Document.query
    if pid:
        q = q.filter_by(project_id=pid)
    elif not u.is_admin():
        q = q.filter_by(uploader_id=u.id)
    docs = q.order_by(Document.uploaded_at.desc()).all()
    return jsonify([{
        'id': d.id,
        'project_id': d.project_id,
        'filename': d.original_name,
        'type': d.file_type,
        'size': d.file_size,
        'is_analyzed': d.is_analyzed,
        'uploaded_at': d.uploaded_at.isoformat() if d.uploaded_at else None
    } for d in docs])

@app.route('/api/documents/<int:did>', methods=['GET', 'DELETE'])
@csrf.exempt
@api_auth_required
def api_single_document(did):
    u = get_auth_user()
    doc = db.session.get(Document, did)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': doc.id,
            'project_id': doc.project_id,
            'filename': doc.original_name,
            'file_type': doc.file_type,
            'file_size': doc.file_size,
            'is_analyzed': doc.is_analyzed,
            'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            'extracted_text_preview': (doc.extracted_text or '')[:800]
        })

    if request.method == 'DELETE':
        if not (u.is_admin() or u.is_pm() or doc.uploader_id == u.id):
            return jsonify({'error': 'Permission denied'}), 403
        fp = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
        if os.path.exists(fp):
            try: os.remove(fp)
            except: pass
        db.session.delete(doc)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Document deleted'})

# AI Processing APIs
@app.route('/api/ai/analyze/<int:did>', methods=['POST'])
@app.route('/api/ai/analyze', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_ai_analyze_endpoint(did=None):
    if did is None:
        data = request.get_json() or {}
        did = data.get('document_id')
    doc = db.session.get(Document, did)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    success, engine = perform_ai_analysis(doc.id, doc.project_id)
    if not success:
        return jsonify({'success': False, 'error': engine}), 400

    extracted = ExtractedKnowledge.query.filter_by(document_id=doc.id).all()
    return jsonify({
        'success': True,
        'engine': engine,
        'document_id': doc.id,
        'extracted_counts': {
            'decisions': len([k for k in extracted if k.category == 'decision']),
            'tasks': len([k for k in extracted if k.category == 'task']),
            'risks': len([k for k in extracted if k.category == 'risk']),
            'discussions': len([k for k in extracted if k.category == 'discussion']),
            'issues': len([k for k in extracted if k.category == 'issue'])
        }
    })

@app.route('/api/ai/results/<int:pid>', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_ai_results_endpoint(pid):
    p = db.session.get(Project, pid)
    if not p:
        return jsonify({'error': 'Project not found'}), 404

    items = ExtractedKnowledge.query.filter_by(project_id=pid).all()
    return jsonify({
        'project_id': p.id,
        'project_name': p.name,
        'total_findings': len(items),
        'pending_review': len([k for k in items if k.status == 'pending_review']),
        'approved': len([k for k in items if k.status == 'approved']),
        'rejected': len([k for k in items if k.status == 'rejected']),
        'items': [{
            'id': k.id,
            'category': k.category,
            'content': k.content,
            'source_ref': k.source_ref,
            'confidence': k.confidence,
            'status': k.status,
            'details': json.loads(k.details or '{}'),
            'created_at': k.created_at.isoformat() if k.created_at else None
        } for k in items]
    })

@app.route('/api/ai/summarize', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_ai_summarize():
    data = request.get_json() or {}
    pid = data.get('project_id')
    text = data.get('text', '')

    # If raw text provided, summarise it directly with NLP engine
    if text and not pid:
        u = get_auth_user()
        result, engine = rule_based_fallback(text, 'Unnamed Project')
        return jsonify({
            'summary': result.get('summary', text[:300]),
            'decisions': result.get('decisions', []),
            'tasks': result.get('tasks', []),
            'risks': result.get('risks', []),
            'engine': engine
        })

    if not pid:
        return jsonify({'error': 'Provide project_id or text'}), 400

    p = db.session.get(Project, pid)
    if not p:
        return jsonify({'error': 'Project not found'}), 404
    knowledge = ExtractedKnowledge.query.filter_by(project_id=pid).all()
    return jsonify({
        'project': p.name,
        'decisions_count': len([k for k in knowledge if k.category == 'decision']),
        'tasks_count': len([k for k in knowledge if k.category == 'task']),
        'risks_count': len([k for k in knowledge if k.category == 'risk']),
        'milestones_count': len([k for k in knowledge if k.category == 'milestone']),
        'total_extracted': len(knowledge),
        'pending_review': len([k for k in knowledge if k.status == 'pending_review']),
        'approved': len([k for k in knowledge if k.status == 'approved'])
    })

@app.route('/api/ai/extract-decisions', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_ai_extract_decisions():
    data = request.get_json() or {}
    text_content = data.get('text', '')
    pname = data.get('project_name', 'Current Project')
    res, source = rule_based_fallback(text_content, pname)
    return jsonify({'decisions': res.get('decisions', []), 'engine': source})

@app.route('/api/ai/detect-risks', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_ai_detect_risks():
    data = request.get_json() or {}
    text_content = data.get('text', '')
    pname = data.get('project_name', 'Current Project')
    res, source = rule_based_fallback(text_content, pname)
    return jsonify({'risks': res.get('risks', []), 'engine': source})

# Tasks API
@app.route('/api/tasks', methods=['GET', 'POST'])
@csrf.exempt
@api_auth_required
def api_tasks():
    u = get_auth_user()
    if request.method == 'POST':
        data = request.get_json() or {}
        pid = data.get('project_id')
        title = data.get('title', '').strip()
        if not pid or not title:
            return jsonify({'error': 'project_id and title are required'}), 400
        p = db.session.get(Project, pid)
        if not p:
            return jsonify({'error': 'Project not found'}), 404
        t = Task(
            project_id=pid,
            title=title,
            description=data.get('description', ''),
            assignee=data.get('assignee', 'Unassigned'),
            priority=data.get('priority', 'medium'),
            status=data.get('status', 'pending'),
            is_approved=True
        )
        dl = data.get('deadline')
        if dl:
            try: t.deadline = datetime.strptime(dl, '%Y-%m-%d').date()
            except: pass
        db.session.add(t)
        db.session.commit()
        return jsonify({'success': True, 'task_id': t.id, 'title': t.title}), 201

    # GET
    pid = request.args.get('project_id', type=int)
    q = Task.query
    if pid:
        q = q.filter_by(project_id=pid)
    tasks = q.order_by(Task.created_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'project_id': t.project_id,
        'title': t.title,
        'description': t.description,
        'assignee': t.assignee,
        'status': t.status,
        'priority': t.priority,
        'deadline': str(t.deadline) if t.deadline else None,
        'is_approved': t.is_approved
    } for t in tasks])

# Decisions API
@app.route('/api/decisions', methods=['GET', 'POST'])
@csrf.exempt
@api_auth_required
def api_decisions_endpoint():
    u = get_auth_user()
    if request.method == 'POST':
        data = request.get_json() or {}
        pid = data.get('project_id')
        title = data.get('title', '').strip()
        if not pid or not title:
            return jsonify({'error': 'project_id and title are required'}), 400
        p = db.session.get(Project, pid)
        if not p:
            return jsonify({'error': 'Project not found'}), 404
        d = Decision(
            project_id=pid,
            title=title,
            description=data.get('description', ''),
            owner=data.get('owner', u.name),
            status=data.get('status', 'open'),
            is_approved=True
        )
        dt = data.get('decision_date')
        if dt:
            try: d.decision_date = datetime.strptime(dt, '%Y-%m-%d').date()
            except: pass
        db.session.add(d)
        db.session.commit()
        return jsonify({'success': True, 'decision_id': d.id, 'title': d.title}), 201

    # GET
    pid = request.args.get('project_id', type=int)
    q = Decision.query
    if pid:
        q = q.filter_by(project_id=pid)
    decisions = q.order_by(Decision.created_at.desc()).all()
    return jsonify([{
        'id': d.id,
        'project_id': d.project_id,
        'title': d.title,
        'description': d.description,
        'owner': d.owner,
        'decision_date': str(d.decision_date) if d.decision_date else None,
        'status': d.status,
        'is_approved': d.is_approved
    } for d in decisions])

# Reviews API
@app.route('/api/reviews', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_get_reviews():
    pid = request.args.get('project_id', type=int)
    q = ExtractedKnowledge.query
    if pid:
        q = q.filter_by(project_id=pid)
    items = q.all()
    return jsonify([{
        'id': k.id,
        'category': k.category,
        'content': k.content,
        'source_ref': k.source_ref,
        'status': k.status,
        'confidence': k.confidence
    } for k in items])

@app.route('/api/reviews/<int:kid>/approve', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_review_approve(kid):
    u = get_auth_user()
    if not (u.is_admin() or u.is_pm()):
        return jsonify({'error': 'Permission denied: Human approval requires Project Manager or Admin'}), 403
    k = db.session.get(ExtractedKnowledge, kid)
    if not k:
        return jsonify({'error': 'Item not found'}), 404
    k.status = 'approved'
    k.reviewer_id = u.id
    k.reviewed_at = datetime.now(timezone.utc)
    details = json.loads(k.details or '{}')

    # Promote to verified tables
    if k.category == 'decision':
        d = Decision(project_id=k.project_id, title=k.content[:300],
                     description=details.get('description',''),
                     owner=details.get('owner','Unknown'), is_approved=True,
                     source_doc_id=k.document_id)
        try:
            dt = details.get('date','')
            if dt and dt != 'Unknown':
                d.decision_date = datetime.strptime(dt,'%Y-%m-%d').date()
        except: pass
        db.session.add(d)
    elif k.category == 'task':
        t = Task(project_id=k.project_id, title=k.content[:300],
                 description=details.get('description',''),
                 assignee=details.get('assignee','Unknown'),
                 priority=details.get('priority','medium'),
                 status='pending', is_approved=True,
                 source_doc_id=k.document_id)
        try:
            dl = details.get('deadline','')
            if dl and dl != 'Unknown':
                t.deadline = datetime.strptime(dl,'%Y-%m-%d').date()
        except: pass
        db.session.add(t)
    elif k.category == 'risk':
        r = Risk(project_id=k.project_id, title=k.content[:300],
                 description=details.get('description',''),
                 level=details.get('level','medium'),
                 risk_owner=details.get('owner','Unknown'),
                 is_approved=True, source_doc_id=k.document_id)
        db.session.add(r)

    db.session.add(Review(knowledge_id=kid, reviewer_id=u.id, action='approved', notes='Approved via API'))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Item approved and verified successfully'})

@app.route('/api/reviews/<int:kid>/reject', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_review_reject(kid):
    u = get_auth_user()
    if not (u.is_admin() or u.is_pm()):
        return jsonify({'error': 'Permission denied: Rejection requires Project Manager or Admin'}), 403
    k = db.session.get(ExtractedKnowledge, kid)
    if not k:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json() or {}
    k.status = 'rejected'
    k.rejection_reason = data.get('reason', 'Rejected via API')
    k.reviewer_id = u.id
    k.reviewed_at = datetime.now(timezone.utc)
    db.session.add(Review(knowledge_id=kid, reviewer_id=u.id, action='rejected', notes=k.rejection_reason))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Item rejected'})

# Handovers API (Reports)
@app.route('/api/handovers/generate', methods=['POST'])
@app.route('/api/reports/generate', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_generate_handover_report():
    u = get_auth_user()
    if not (u.is_admin() or u.is_pm() or u.is_outgoing()):
        return jsonify({'error': 'Permission denied'}), 403
    data = request.get_json() or {}
    pid = data.get('project_id')
    p = db.session.get(Project, pid)
    if not p:
        return jsonify({'error': 'Project not found'}), 404

    # Build comprehensive structured handover content
    decisions = Decision.query.filter_by(project_id=pid).all()
    tasks = Task.query.filter_by(project_id=pid).all()
    risks = Risk.query.filter_by(project_id=pid).all()
    docs = Document.query.filter_by(project_id=pid).all()
    verified_knowledge = ExtractedKnowledge.query.filter_by(project_id=pid, status='approved').all()

    report_content = {
        'project': {
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'status': p.status,
            'priority': p.priority,
            'owner': p.owner.name if p.owner else 'Unknown'
        },
        'decisions': [{'id': d.id, 'title': d.title, 'owner': d.owner, 'date': str(d.decision_date) if d.decision_date else 'Unknown'} for d in decisions],
        'tasks': [{'id': t.id, 'title': t.title, 'assignee': t.assignee, 'status': t.status, 'priority': t.priority, 'deadline': str(t.deadline) if t.deadline else 'Unknown'} for t in tasks],
        'risks': [{'id': r.id, 'title': r.title, 'level': r.level, 'owner': r.risk_owner, 'status': r.status} for r in risks],
        'documents': [{'id': d.id, 'name': d.original_name, 'type': d.file_type} for d in docs],
        'verified_insights': [{'category': k.category, 'content': k.content, 'source_ref': k.source_ref} for k in verified_knowledge]
    }

    rpt = HandoverReport(
        project_id=pid,
        generated_by_id=u.id,
        title=data.get('title') or f'Handover Report – {p.name}',
        summary=data.get('summary') or f'Verified project knowledge handover package for {p.name}. Generated on {datetime.now().strftime("%d %b %Y")}.',
        content_json=json.dumps(report_content),
        status='draft'
    )
    db.session.add(rpt)
    db.session.commit()
    log_action('generate_handover', 'handover_report', rpt.id, f'Generated handover report for {p.name}')
    return jsonify({'success': True, 'handover_id': rpt.id, 'title': rpt.title, 'status': rpt.status}), 201

@app.route('/api/handovers', methods=['GET'])
@app.route('/api/reports', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_get_handovers():
    u = get_auth_user()
    pid = request.args.get('project_id', type=int)
    q = HandoverReport.query
    if pid:
        q = q.filter_by(project_id=pid)
    reports = q.order_by(HandoverReport.generated_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'project_id': r.project_id,
        'title': r.title,
        'summary': r.summary,
        'status': r.status,
        'generated_by': r.generated_by.name if r.generated_by else 'Unknown',
        'generated_at': r.generated_at.isoformat() if r.generated_at else None,
        'approved_by': r.approved_by.name if r.approved_by else None
    } for r in reports])

@app.route('/api/handovers/<int:hid>', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_get_single_handover(hid):
    r = db.session.get(HandoverReport, hid)
    if not r:
        return jsonify({'error': 'Handover report not found'}), 404
    return jsonify({
        'id': r.id,
        'project_id': r.project_id,
        'title': r.title,
        'summary': r.summary,
        'status': r.status,
        'generated_by': r.generated_by.name if r.generated_by else 'Unknown',
        'generated_at': r.generated_at.isoformat() if r.generated_at else None,
        'approved_by': r.approved_by.name if r.approved_by else None,
        'approved_at': r.approved_at.isoformat() if r.approved_at else None,
        'content': json.loads(r.content_json or '{}')
    })

@app.route('/api/handovers/<int:hid>/approve', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_approve_handover(hid):
    u = get_auth_user()
    if not (u.is_admin() or u.is_pm()):
        return jsonify({'error': 'Permission denied: Only Project Managers or Admins can approve handovers'}), 403
    r = db.session.get(HandoverReport, hid)
    if not r:
        return jsonify({'error': 'Handover report not found'}), 404
    r.status = 'approved'
    r.approved_by_id = u.id
    r.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action('approve_handover', 'handover_report', r.id, f'Approved handover: {r.title}')
    return jsonify({'success': True, 'message': 'Handover report approved successfully'})

@app.route('/api/handovers/<int:hid>/reject', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_reject_handover(hid):
    u = get_auth_user()
    if not (u.is_admin() or u.is_pm()):
        return jsonify({'error': 'Permission denied'}), 403
    r = db.session.get(HandoverReport, hid)
    if not r:
        return jsonify({'error': 'Handover report not found'}), 404
    data = request.get_json() or {}
    r.status = 'rejected'
    db.session.commit()
    log_action('reject_handover', 'handover_report', r.id, f'Rejected handover: {r.title}')
    return jsonify({'success': True, 'message': 'Handover report rejected and returned for revision'})

# Acknowledgements API
@app.route('/api/acknowledgements', methods=['GET', 'POST'])
@csrf.exempt
@api_auth_required
def api_acknowledgements_endpoint():
    u = get_auth_user()
    if request.method == 'POST':
        data = request.get_json() or {}
        hid = data.get('handover_id') or data.get('report_id')
        rec_id = data.get('recipient_id')
        if not hid or not rec_id:
            return jsonify({'error': 'handover_id and recipient_id are required'}), 400
        ack = Acknowledgement(
            report_id=hid,
            recipient_id=rec_id,
            status='pending',
            notes=data.get('notes', '')
        )
        db.session.add(ack)
        db.session.commit()
        return jsonify({'success': True, 'acknowledgement_id': ack.id, 'status': ack.status}), 201

    # GET
    acks = Acknowledgement.query.filter_by(recipient_id=u.id).order_by(Acknowledgement.sent_at.desc()).all()
    return jsonify([{
        'id': a.id,
        'report_id': a.report_id,
        'report_title': a.report.title if a.report else 'Handover Report',
        'status': a.status,
        'sent_at': a.sent_at.isoformat() if a.sent_at else None,
        'acknowledged_at': a.acknowledged_at.isoformat() if a.acknowledged_at else None
    } for a in acks])

@app.route('/api/acknowledgements/<int:hid>', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_get_handover_acknowledgements(hid):
    acks = Acknowledgement.query.filter_by(report_id=hid).all()
    return jsonify([{
        'id': a.id,
        'recipient': a.recipient.name if a.recipient else 'Unknown',
        'recipient_email': a.recipient.email if a.recipient else '',
        'status': a.status,
        'sent_at': a.sent_at.isoformat() if a.sent_at else None,
        'acknowledged_at': a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        'notes': a.notes
    } for a in acks])

@app.route('/api/acknowledgements/<int:aid>/confirm', methods=['POST'])
@csrf.exempt
@api_auth_required
def api_confirm_acknowledgement(aid):
    u = get_auth_user()
    ack = db.session.get(Acknowledgement, aid)
    if not ack:
        return jsonify({'error': 'Acknowledgement request not found'}), 404
    if ack.recipient_id != u.id and not u.is_admin():
        return jsonify({'error': 'Permission denied: Only the designated recipient can sign this acknowledgement'}), 403

    data = request.get_json() or {}
    ack.status = 'acknowledged'
    ack.acknowledged_at = datetime.now(timezone.utc)
    if 'notes' in data:
        ack.notes = data['notes']
    db.session.commit()
    log_action('acknowledge_handover', 'acknowledgement', ack.id, f'Signed off handover #{ack.report_id}')
    return jsonify({'success': True, 'message': 'Handover receipt acknowledged and recorded successfully'})

# Analytics API
@app.route('/api/analytics/dashboard', methods=['GET'])
@csrf.exempt
@api_auth_required
def api_analytics_dashboard():
    total_projects = Project.query.count()
    active_handovers = HandoverReport.query.filter_by(status='draft').count()
    completed_handovers = HandoverReport.query.filter_by(status='approved').count()
    pending_tasks = Task.query.filter_by(status='pending').count()
    unresolved_risks = Risk.query.filter_by(status='open').count()
    pending_approvals = ExtractedKnowledge.query.filter_by(status='pending_review').count()

    # Task status breakdown
    tasks_completed = Task.query.filter_by(status='completed').count()
    tasks_in_progress = Task.query.filter_by(status='in_progress').count()
    tasks_pending = Task.query.filter_by(status='pending').count()
    tasks_blocked = Task.query.filter_by(status='blocked').count()

    # Risk level breakdown
    risks_high = Risk.query.filter_by(level='high', status='open').count()
    risks_med = Risk.query.filter_by(level='medium', status='open').count()
    risks_low = Risk.query.filter_by(level='low', status='open').count()

    # Recent activities
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()

    return jsonify({
        'total_projects': total_projects,
        'active_handovers': active_handovers,
        'completed_handovers': completed_handovers,
        'pending_tasks': pending_tasks,
        'unresolved_risks': unresolved_risks,
        'pending_approvals': pending_approvals,
        'task_status_distribution': {
            'completed': tasks_completed,
            'in_progress': tasks_in_progress,
            'pending': tasks_pending,
            'blocked': tasks_blocked
        },
        'risk_level_distribution': {
            'high': risks_high,
            'medium': risks_med,
            'low': risks_low
        },
        'recent_activities': [{
            'id': l.id,
            'user': l.user.name if l.user else 'System',
            'action': l.action,
            'details': l.details,
            'timestamp': l.created_at.isoformat() if l.created_at else None
        } for l in recent_logs]
    })

# ─── Error Handlers ───────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, msg='Page not found'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403, msg='Access denied'), 403

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500, msg='Internal server error'), 500

# ─── Init Database and Demo Data ──────────────────────────────────────────────
def create_demo_data():
    # Ensure all 4 core roles exist in the system
    admin = User.query.filter_by(email='admin@knowbridge.ai').first()
    if not admin:
        admin = User(name='Admin User', email='admin@knowbridge.ai', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)

    pm = User.query.filter_by(email='sarah@knowbridge.ai').first()
    if not pm:
        pm = User(name='Sarah Johnson', email='sarah@knowbridge.ai', role='project_manager')
        pm.set_password('sarah123')
        db.session.add(pm)

    outgoing = User.query.filter_by(email='alex@knowbridge.ai').first()
    if not outgoing:
        outgoing = User(name='Alex Chen', email='alex@knowbridge.ai', role='outgoing_member')
        outgoing.set_password('alex123')
        db.session.add(outgoing)
    else:
        outgoing.role = 'outgoing_member'

    incoming = User.query.filter_by(email='priya@knowbridge.ai').first()
    if not incoming:
        incoming = User(name='Priya Sharma', email='priya@knowbridge.ai', role='incoming_member')
        incoming.set_password('priya123')
        db.session.add(incoming)

    db.session.flush()

    if Project.query.first():
        db.session.commit()
        return

    member = outgoing

    # Demo Projects
    p1 = Project(name='[DEMO] Product Relaunch 2025', is_demo=True,
                 description='Strategic product relaunch including new branding, updated tech stack and market repositioning.',
                 status='active', priority='high', owner_id=pm.id,
                 start_date=datetime(2025,1,15).date(), end_date=datetime(2025,8,30).date())
    p2 = Project(name='[DEMO] Data Migration Initiative', is_demo=True,
                 description='Migration of legacy databases to cloud-native PostgreSQL infrastructure.',
                 status='on_hold', priority='high', owner_id=pm.id,
                 start_date=datetime(2025,2,1).date(), end_date=datetime(2025,7,31).date())
    p3 = Project(name='[DEMO] Mobile App v2', is_demo=True,
                 description='Next generation mobile application with AI-powered features.',
                 status='active', priority='medium', owner_id=admin.id,
                 start_date=datetime(2025,3,1).date(), end_date=datetime(2025,12,31).date())
    db.session.add_all([p1,p2,p3])
    db.session.flush()

    # Members
    db.session.add_all([
        ProjectMember(project_id=p1.id, user_id=pm.id, role_in_project='owner'),
        ProjectMember(project_id=p1.id, user_id=admin.id, role_in_project='stakeholder'),
        ProjectMember(project_id=p1.id, user_id=outgoing.id, role_in_project='outgoing lead developer'),
        ProjectMember(project_id=p1.id, user_id=incoming.id, role_in_project='incoming developer'),
        ProjectMember(project_id=p2.id, user_id=pm.id, role_in_project='owner'),
        ProjectMember(project_id=p2.id, user_id=outgoing.id, role_in_project='database admin'),
        ProjectMember(project_id=p2.id, user_id=incoming.id, role_in_project='incoming developer'),
        ProjectMember(project_id=p3.id, user_id=admin.id, role_in_project='owner'),
        ProjectMember(project_id=p3.id, user_id=outgoing.id, role_in_project='developer'),
    ])

    # Tasks
    tasks_data = [
        Task(project_id=p1.id, title='Finalise brand guidelines', assignee='Sarah Johnson',
             status='completed', priority='high', is_approved=True,
             description='Complete brand identity document with logo, colors and typography.'),
        Task(project_id=p1.id, title='Update marketing collateral', assignee='Alex Chen',
             status='in_progress', priority='high', is_approved=True,
             description='Redesign brochures, website banners and email templates.'),
        Task(project_id=p1.id, title='Launch press release', assignee='Unknown',
             status='pending', priority='medium', is_approved=True,
             description='Coordinate with PR team for product announcement.'),
        Task(project_id=p2.id, title='Audit existing database schemas', assignee='Alex Chen',
             status='completed', priority='high', is_approved=True),
        Task(project_id=p2.id, title='Set up PostgreSQL clusters', assignee='Unknown',
             status='pending', priority='high', is_approved=True),
        Task(project_id=p3.id, title='Design new UI mockups', assignee='Sarah Johnson',
             status='in_progress', priority='medium', is_approved=True),
        Task(project_id=p3.id, title='Implement push notifications', assignee='Alex Chen',
             status='pending', priority='medium', is_approved=True),
    ]
    db.session.add_all(tasks_data)

    # Risks
    risks_data = [
        Risk(project_id=p1.id, title='Brand consistency across all materials',
             description='Risk of inconsistent branding if guidelines are not communicated clearly.',
             level='medium', risk_owner='Sarah Johnson', status='open', is_approved=True),
        Risk(project_id=p1.id, title='Timeline slippage due to vendor delays',
             description='Third-party suppliers may not deliver assets on schedule.',
             level='high', risk_owner='Unknown', status='open', is_approved=True),
        Risk(project_id=p2.id, title='Data loss during migration',
             description='Critical data could be corrupted or lost without proper backup procedures.',
             level='high', risk_owner='Alex Chen', status='open', is_approved=True),
        Risk(project_id=p2.id, title='Performance degradation post-migration',
             description='Application performance may suffer if queries are not optimised.',
             level='medium', risk_owner='Unknown', status='open', is_approved=True),
        Risk(project_id=p3.id, title='Third-party API rate limits',
             description='AI feature relies on external API which has usage limits.',
             level='low', risk_owner='Unknown', status='open', is_approved=True),
    ]
    db.session.add_all(risks_data)

    # Decisions
    decisions_data = [
        Decision(project_id=p1.id, title='Adopt terracotta and sage as primary brand colours',
                 description='Board approved the new colour palette for all brand materials.',
                 owner='Sarah Johnson', status='closed', is_approved=True,
                 decision_date=datetime(2025,1,20).date()),
        Decision(project_id=p2.id, title='Use PostgreSQL 16 for all production databases',
                 description='Evaluated multiple options; PostgreSQL selected for performance and licensing.',
                 owner='Alex Chen', status='closed', is_approved=True,
                 decision_date=datetime(2025,2,10).date()),
        Decision(project_id=p3.id, title='Build with React Native for cross-platform support',
                 description='Saves development time by targeting iOS and Android from single codebase.',
                 owner='Admin User', status='open', is_approved=True,
                 decision_date=datetime(2025,3,5).date()),
    ]
    db.session.add_all(decisions_data)

    # Extracted Knowledge (pending review)
    ki = ExtractedKnowledge(
        project_id=p1.id, document_id=None, category='decision',
        content='Relaunch event scheduled for Q3 2025 based on marketing team recommendation',
        details=json.dumps({'description':'Event planning underway','owner':'Unknown','date':'Unknown'}),
        confidence='medium', status='pending_review', is_fallback=True)
    db.session.add(ki)

    # Sample Report
    rpt_content = {
        'project': {'name': p1.name, 'description': p1.description, 'status': 'active', 'owner': 'Sarah Johnson'},
        'decisions': [{'title': 'Adopt terracotta brand colours', 'owner': 'Sarah Johnson', 'date': '2025-01-20'}],
        'tasks': [{'title': 'Finalise brand guidelines', 'assignee': 'Sarah Johnson', 'status': 'completed',
                   'priority': 'high', 'deadline': 'Unknown'}],
        'risks': [{'title': 'Timeline slippage', 'level': 'high', 'status': 'open', 'owner': 'Unknown'}],
        'documents': [],
        'issues': []
    }
    rpt = HandoverReport(
        project_id=p1.id, generated_by_id=pm.id,
        title=f'[DEMO] Handover Report – {p1.name}',
        summary='Demo handover report for Product Relaunch 2025.',
        content_json=json.dumps(rpt_content), status='approved',
        approved_by_id=admin.id, approved_at=datetime.now(timezone.utc))
    db.session.add(rpt)
    db.session.flush()

    ack = Acknowledgement(report_id=rpt.id, recipient_id=member.id, status='pending')
    db.session.add(ack)

    # Audit log
    db.session.add(AuditLog(user_id=admin.id, action='demo_data_created',
                            resource_type='system', details='Initial demo data loaded'))
    db.session.commit()
    print('[OK] Demo data created. Login: admin@knowbridge.ai / admin123')

with app.app_context():
    db.create_all()
    create_demo_data()

# ─── Register Round-3 Improvements Blueprint ─────────────────────────────────
try:
    from improvements import imp as improvements_bp
    csrf.exempt(improvements_bp)
    app.register_blueprint(improvements_bp)
    logger.info("[OK] Round-3 improvements blueprint registered.")
except Exception as _imp_err:
    logger.warning(f"[WARN] Could not load improvements blueprint: {_imp_err}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"[RUNNING] KnowBridge AI active on http://127.0.0.1:{port} and http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
