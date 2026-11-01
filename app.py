"""
KnowBridge AI - Main Flask Application
Complete backend for the intelligent knowledge handover system.
"""

from flask import (
    Flask, render_template, request, jsonify, session,
    send_file, redirect, url_for
)
from functools import wraps
import os
import uuid
import json
import io
import csv
from datetime import datetime, timedelta

from config import Config
from models import (
    db, User, Project, ProjectMember, Document, Decision,
    Task, Risk, Dependency, Evidence, Review, HandoverReport,
    Acknowledgement, ActivityLog
)
from ai_engine import AIEngine

# ---------------------------------------------------------------------------
# App factory / setup
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.from_object(Config)

db.init_app(app)
ai_engine = AIEngine(app.config)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

with app.app_context():
    db.create_all()

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'csv'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def allowed_file(filename):
    """Check whether *filename* has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    """Decorator that returns 401 when no user is logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def check_project_access(project_id, user_id):
    """Return True when *user_id* is the creator or a member of *project_id*."""
    project = Project.query.get(project_id)
    if not project:
        return False
    if project.created_by == user_id:
        return True
    member = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    return member is not None


def log_activity(project_id, user_id, action, details=None):
    """Persist an activity-log row."""
    entry = ActivityLog(
        project_id=project_id,
        user_id=user_id,
        action=action,
        details=details or '',
        timestamp=datetime.utcnow()
    )
    db.session.add(entry)
    db.session.commit()


def extract_text_from_file(filepath, filename):
    """Extract plain text from an uploaded file.

    Returns (text, error_message).  On success error_message is None.
    """
    ext = filename.rsplit('.', 1)[1].lower()

    try:
        if ext == 'pdf':
            import fitz  # PyMuPDF
            doc = fitz.open(filepath)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return '\n'.join(text_parts), None

        elif ext == 'docx':
            from docx import Document as DocxDocument
            doc = DocxDocument(filepath)
            text_parts = [p.text for p in doc.paragraphs]
            return '\n'.join(text_parts), None

        elif ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                return fh.read(), None

        elif ext == 'csv':
            import pandas as pd
            df = pd.read_csv(filepath)
            return df.to_string(), None

        else:
            return '', f'Unsupported file type: {ext}'

    except Exception as exc:
        return '', str(exc)


# ---------------------------------------------------------------------------
# Page routes (serve Jinja2 templates)
# ---------------------------------------------------------------------------

@app.route('/')
def index_page():
    return render_template('index.html')


@app.route('/login')
def login_page():
    return render_template('auth.html')


@app.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html')


@app.route('/projects')
@login_required
def projects_page():
    return render_template('projects.html')


@app.route('/projects/<int:project_id>')
@login_required
def project_detail_page(project_id):
    if not check_project_access(project_id, session['user_id']):
        return redirect(url_for('projects_page'))
    return render_template('project_detail.html', project_id=project_id)


@app.route('/projects/<int:project_id>/documents')
@login_required
def documents_page(project_id):
    return render_template('documents.html', project_id=project_id)


@app.route('/projects/<int:project_id>/decisions')
@login_required
def decisions_page(project_id):
    return render_template('decisions.html', project_id=project_id)


@app.route('/projects/<int:project_id>/tasks')
@login_required
def tasks_page(project_id):
    return render_template('tasks.html', project_id=project_id)


@app.route('/projects/<int:project_id>/risks')
@login_required
def risks_page(project_id):
    return render_template('risks.html', project_id=project_id)


@app.route('/projects/<int:project_id>/review')
@login_required
def review_page(project_id):
    return render_template('review.html', project_id=project_id)


@app.route('/projects/<int:project_id>/reports')
@login_required
def reports_page(project_id):
    return render_template('reports.html', project_id=project_id)


# ===================================================================
#  API  —  Authentication
# ===================================================================

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    full_name = (data.get('full_name') or '').strip()
    role = (data.get('role') or 'member').strip()

    if not username or not email or not password:
        return jsonify({'error': 'Username, email and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    from werkzeug.security import generate_password_hash
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        full_name=full_name or username,
        role=role,
        created_at=datetime.utcnow()
    )
    db.session.add(user)
    db.session.commit()

    session['user_id'] = user.id
    return jsonify({'message': 'Registration successful', 'user': user.to_dict()}), 201


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    from werkzeug.security import check_password_hash
    if not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    session['user_id'] = user.id
    return jsonify({'message': 'Login successful', 'user': user.to_dict()}), 200


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/api/auth/me', methods=['GET'])
def api_me():
    uid = session.get('user_id')
    if not uid:
        return jsonify({'error': 'Not authenticated'}), 401
    user = User.query.get(uid)
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 401
    return jsonify({'user': user.to_dict()}), 200


# ===================================================================
#  API  —  Projects
# ===================================================================

@app.route('/api/projects', methods=['GET'])
@login_required
def api_list_projects():
    uid = session['user_id']
    member_project_ids = [
        m.project_id for m in ProjectMember.query.filter_by(user_id=uid).all()
    ]
    projects = Project.query.filter(
        (Project.created_by == uid) | (Project.id.in_(member_project_ids))
    ).order_by(Project.created_at.desc()).all()
    return jsonify({'projects': [p.to_dict() for p in projects]}), 200


@app.route('/api/projects', methods=['POST'])
@login_required
def api_create_project():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Project name is required'}), 400

    uid = session['user_id']
    project = Project(
        name=name,
        description=(data.get('description') or '').strip(),
        status='active',
        created_by=uid,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(project)
    db.session.flush()

    member = ProjectMember(
        project_id=project.id,
        user_id=uid,
        role='owner',
        is_outgoing=False,
        is_incoming=False,
        joined_at=datetime.utcnow()
    )
    db.session.add(member)
    db.session.commit()

    log_activity(project.id, uid, 'project_created', f'Project "{name}" created')
    return jsonify({'message': 'Project created', 'project': project.to_dict()}), 201


@app.route('/api/projects/<int:project_id>', methods=['GET'])
@login_required
def api_get_project(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    project = Project.query.get_or_404(project_id)
    data = project.to_dict()

    doc_count = Document.query.filter_by(project_id=project_id).count()
    dec_count = Decision.query.filter_by(project_id=project_id).count()
    task_count = Task.query.filter_by(project_id=project_id).count()
    risk_count = Risk.query.filter_by(project_id=project_id).count()

    verified_decisions = Decision.query.filter_by(
        project_id=project_id, verification_status='approved'
    ).count()
    verified_tasks = Task.query.filter_by(
        project_id=project_id, verification_status='approved'
    ).count()
    verified_risks = Risk.query.filter_by(
        project_id=project_id, verification_status='approved'
    ).count()
    total_items = dec_count + task_count + risk_count
    verified_items = verified_decisions + verified_tasks + verified_risks
    completion = round((verified_items / total_items * 100) if total_items else 0, 1)

    members = ProjectMember.query.filter_by(project_id=project_id).all()
    members_data = []
    for m in members:
        u = User.query.get(m.user_id)
        members_data.append({
            'id': m.id,
            'user_id': m.user_id,
            'username': u.username if u else 'Unknown',
            'full_name': u.full_name if u else 'Unknown',
            'email': u.email if u else '',
            'role': m.role,
            'is_outgoing': m.is_outgoing,
            'is_incoming': m.is_incoming,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None
        })

    data.update({
        'doc_count': doc_count,
        'decision_count': dec_count,
        'task_count': task_count,
        'risk_count': risk_count,
        'completion': completion,
        'members': members_data
    })
    return jsonify({'project': data}), 200


@app.route('/api/projects/<int:project_id>', methods=['PUT'])
@login_required
def api_update_project(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    project = Project.query.get_or_404(project_id)
    data = request.get_json(silent=True) or {}

    if 'name' in data:
        project.name = data['name'].strip()
    if 'description' in data:
        project.description = data['description'].strip()
    if 'status' in data:
        project.status = data['status'].strip()
    project.updated_at = datetime.utcnow()

    db.session.commit()
    log_activity(project_id, uid, 'project_updated', f'Project "{project.name}" updated')
    return jsonify({'message': 'Project updated', 'project': project.to_dict()}), 200


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
@login_required
def api_delete_project(project_id):
    uid = session['user_id']
    project = Project.query.get_or_404(project_id)

    if project.created_by != uid:
        return jsonify({'error': 'Only the project creator can delete it'}), 403

    # Delete all related data
    Acknowledgement.query.filter(
        Acknowledgement.report_id.in_(
            db.session.query(HandoverReport.id).filter_by(project_id=project_id)
        )
    ).delete(synchronize_session='fetch')
    HandoverReport.query.filter_by(project_id=project_id).delete()
    ActivityLog.query.filter_by(project_id=project_id).delete()
    Review.query.filter_by(project_id=project_id).delete()
    Evidence.query.filter_by(project_id=project_id).delete()
    Dependency.query.filter_by(project_id=project_id).delete()
    Risk.query.filter_by(project_id=project_id).delete()
    Task.query.filter_by(project_id=project_id).delete()
    Decision.query.filter_by(project_id=project_id).delete()

    # Delete uploaded files
    docs = Document.query.filter_by(project_id=project_id).all()
    for doc in docs:
        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError:
                pass
    Document.query.filter_by(project_id=project_id).delete()

    ProjectMember.query.filter_by(project_id=project_id).delete()
    db.session.delete(project)
    db.session.commit()
    return jsonify({'message': 'Project deleted'}), 200


@app.route('/api/projects/<int:project_id>/members', methods=['POST'])
@login_required
def api_add_member(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    target_user_id = data.get('user_id')
    if not target_user_id:
        # Try lookup by email or username
        email = (data.get('email') or '').strip()
        username = (data.get('username') or '').strip()
        user = None
        if email:
            user = User.query.filter_by(email=email).first()
        elif username:
            user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        target_user_id = user.id

    target_user = User.query.get(target_user_id)
    if not target_user:
        return jsonify({'error': 'User not found'}), 404

    existing = ProjectMember.query.filter_by(
        project_id=project_id, user_id=target_user_id
    ).first()
    if existing:
        return jsonify({'error': 'User is already a member'}), 409

    member = ProjectMember(
        project_id=project_id,
        user_id=target_user_id,
        role=data.get('role', 'member'),
        is_outgoing=bool(data.get('is_outgoing', False)),
        is_incoming=bool(data.get('is_incoming', False)),
        joined_at=datetime.utcnow()
    )
    db.session.add(member)
    db.session.commit()

    log_activity(project_id, uid, 'member_added',
                 f'Added {target_user.full_name} to project')
    return jsonify({'message': 'Member added', 'member_id': member.id}), 201


@app.route('/api/projects/<int:project_id>/members/<int:member_id>', methods=['DELETE'])
@login_required
def api_remove_member(project_id, member_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    member = ProjectMember.query.get_or_404(member_id)
    if member.project_id != project_id:
        return jsonify({'error': 'Member does not belong to this project'}), 400

    db.session.delete(member)
    db.session.commit()

    log_activity(project_id, uid, 'member_removed', f'Removed member #{member_id}')
    return jsonify({'message': 'Member removed'}), 200


@app.route('/api/projects/<int:project_id>/stats', methods=['GET'])
@login_required
def api_project_stats(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    doc_count = Document.query.filter_by(project_id=project_id).count()
    dec_count = Decision.query.filter_by(project_id=project_id).count()
    task_count = Task.query.filter_by(project_id=project_id).count()
    risk_count = Risk.query.filter_by(project_id=project_id).count()
    dep_count = Dependency.query.filter_by(project_id=project_id).count()

    approved_decisions = Decision.query.filter_by(
        project_id=project_id, verification_status='approved').count()
    approved_tasks = Task.query.filter_by(
        project_id=project_id, verification_status='approved').count()
    approved_risks = Risk.query.filter_by(
        project_id=project_id, verification_status='approved').count()

    total_items = dec_count + task_count + risk_count
    verified = approved_decisions + approved_tasks + approved_risks
    completion = round((verified / total_items * 100) if total_items else 0, 1)

    tasks_pending = Task.query.filter_by(project_id=project_id, status='pending').count()
    tasks_progress = Task.query.filter_by(project_id=project_id, status='in_progress').count()
    tasks_done = Task.query.filter_by(project_id=project_id, status='completed').count()

    high_risks = Risk.query.filter_by(project_id=project_id, severity='high').count()
    critical_risks = Risk.query.filter_by(project_id=project_id, severity='critical').count()

    report_count = HandoverReport.query.filter_by(project_id=project_id).count()
    member_count = ProjectMember.query.filter_by(project_id=project_id).count()

    return jsonify({
        'stats': {
            'documents': doc_count,
            'decisions': dec_count,
            'tasks': task_count,
            'risks': risk_count,
            'dependencies': dep_count,
            'completion': completion,
            'approved_decisions': approved_decisions,
            'approved_tasks': approved_tasks,
            'approved_risks': approved_risks,
            'tasks_pending': tasks_pending,
            'tasks_in_progress': tasks_progress,
            'tasks_completed': tasks_done,
            'high_risks': high_risks,
            'critical_risks': critical_risks,
            'reports': report_count,
            'members': member_count
        }
    }), 200


# ===================================================================
#  API  —  Documents
# ===================================================================

@app.route('/api/projects/<int:project_id>/documents', methods=['GET'])
@login_required
def api_list_documents(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403
    docs = Document.query.filter_by(project_id=project_id).order_by(
        Document.uploaded_at.desc()
    ).all()
    return jsonify({'documents': [d.to_dict() for d in docs]}), 200


@app.route('/api/projects/<int:project_id>/documents', methods=['POST'])
@login_required
def api_upload_document(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    # Read contents to check size
    file_data = file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return jsonify({'error': 'File exceeds maximum size of 50 MB'}), 400
    file.seek(0)

    # Save with UUID name
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)

    # Extract text immediately
    extracted, err = extract_text_from_file(filepath, file.filename)
    status = 'completed' if err is None else 'failed'

    doc = Document(
        project_id=project_id,
        name=file.filename,
        filename=unique_name,
        original_filename=file.filename,
        file_path=filepath,
        file_type=ext,
        file_size=len(file_data),
        uploaded_by=uid,
        uploaded_at=datetime.utcnow(),
        processing_status=status,
        extracted_text=extracted or '',
        error_message=err
    )
    db.session.add(doc)
    db.session.commit()

    log_activity(project_id, uid, 'document_uploaded',
                 f'Uploaded "{file.filename}" ({status})')

    return jsonify({'message': 'Document uploaded', 'document': doc.to_dict()}), 201


@app.route('/api/documents/<int:doc_id>', methods=['GET'])
@login_required
def api_get_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    uid = session['user_id']
    if not check_project_access(doc.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403
    return jsonify({'document': doc.to_dict()}), 200


@app.route('/api/documents/<int:doc_id>/download', methods=['GET'])
@login_required
def api_download_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    uid = session['user_id']
    if not check_project_access(doc.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    if not doc.file_path or not os.path.exists(doc.file_path):
        return jsonify({'error': 'File not found on server'}), 404

    return send_file(
        doc.file_path,
        as_attachment=True,
        download_name=doc.original_filename or doc.name
    )


@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def api_delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    uid = session['user_id']
    if not check_project_access(doc.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    project_id = doc.project_id
    db.session.delete(doc)
    db.session.commit()

    log_activity(project_id, uid, 'document_deleted',
                 f'Deleted document "{doc.name}"')
    return jsonify({'message': 'Document deleted'}), 200


@app.route('/api/documents/<int:doc_id>/process', methods=['POST'])
@login_required
def api_process_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    uid = session['user_id']
    if not check_project_access(doc.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    if not doc.extracted_text or doc.extracted_text.strip() == '':
        return jsonify({'error': 'No extracted text available for analysis'}), 400

    doc.processing_status = 'processing'
    db.session.commit()

    try:
        results = ai_engine.analyze_document(doc.extracted_text, doc.name)
    except Exception as exc:
        doc.processing_status = 'failed'
        doc.error_message = str(exc)
        db.session.commit()
        return jsonify({'error': f'AI analysis failed: {exc}'}), 500

    project_id = doc.project_id
    created = {'decisions': [], 'tasks': [], 'risks': [], 'dependencies': [], 'evidence': []}

    # --- Decisions ---
    for item in results.get('decisions', []):
        d = Decision(
            project_id=project_id,
            document_id=doc.id,
            title=item.get('title', 'Untitled Decision'),
            description=item.get('description', ''),
            rationale=item.get('rationale', ''),
            impact=item.get('impact', 'medium'),
            status=item.get('status', 'active'),
            verification_status='pending',
            confidence=item.get('confidence', 0.5),
            created_at=datetime.utcnow()
        )
        db.session.add(d)
        db.session.flush()
        created['decisions'].append(d.to_dict())

        # Create evidence link
        ev = Evidence(
            project_id=project_id,
            decision_id=d.id,
            document_id=doc.id,
            content=item.get('evidence', item.get('description', '')),
            source=doc.name,
            evidence_type='ai_extracted',
            created_at=datetime.utcnow()
        )
        db.session.add(ev)

    # --- Tasks ---
    for item in results.get('tasks', []):
        t = Task(
            project_id=project_id,
            document_id=doc.id,
            title=item.get('title', 'Untitled Task'),
            description=item.get('description', ''),
            priority=item.get('priority', 'medium'),
            status=item.get('status', 'pending'),
            verification_status='pending',
            confidence=item.get('confidence', 0.5),
            is_manual=False,
            created_at=datetime.utcnow()
        )
        db.session.add(t)
        db.session.flush()
        created['tasks'].append(t.to_dict())

        ev = Evidence(
            project_id=project_id,
            task_id=t.id,
            document_id=doc.id,
            content=item.get('evidence', item.get('description', '')),
            source=doc.name,
            evidence_type='ai_extracted',
            created_at=datetime.utcnow()
        )
        db.session.add(ev)

    # --- Risks ---
    for item in results.get('risks', []):
        r = Risk(
            project_id=project_id,
            document_id=doc.id,
            title=item.get('title', 'Untitled Risk'),
            description=item.get('description', ''),
            severity=item.get('severity', 'medium'),
            probability=item.get('probability', 'medium'),
            mitigation=item.get('mitigation', ''),
            status=item.get('status', 'identified'),
            verification_status='pending',
            confidence=item.get('confidence', 0.5),
            created_at=datetime.utcnow()
        )
        db.session.add(r)
        db.session.flush()
        created['risks'].append(r.to_dict())

        ev = Evidence(
            project_id=project_id,
            risk_id=r.id,
            document_id=doc.id,
            content=item.get('evidence', item.get('description', '')),
            source=doc.name,
            evidence_type='ai_extracted',
            created_at=datetime.utcnow()
        )
        db.session.add(ev)

    # --- Dependencies ---
    for item in results.get('dependencies', []):
        dep = Dependency(
            project_id=project_id,
            document_id=doc.id,
            title=item.get('title', 'Untitled Dependency'),
            description=item.get('description', ''),
            dependency_type=item.get('type', 'technical'),
            status=item.get('status', 'active'),
            created_at=datetime.utcnow()
        )
        db.session.add(dep)
        db.session.flush()
        created['dependencies'].append(dep.to_dict())

    doc.processing_status = 'analyzed'
    db.session.commit()

    log_activity(project_id, uid, 'document_analyzed',
                 f'AI analysis of "{doc.name}": {len(created["decisions"])} decisions, '
                 f'{len(created["tasks"])} tasks, {len(created["risks"])} risks, '
                 f'{len(created["dependencies"])} dependencies')

    return jsonify({
        'message': 'Document analyzed successfully',
        'results': created
    }), 200


# ===================================================================
#  API  —  Decisions
# ===================================================================

@app.route('/api/projects/<int:project_id>/decisions', methods=['GET'])
@login_required
def api_list_decisions(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403
    decisions = Decision.query.filter_by(project_id=project_id).order_by(
        Decision.created_at.desc()
    ).all()
    return jsonify({'decisions': [d.to_dict() for d in decisions]}), 200


@app.route('/api/decisions/<int:decision_id>', methods=['PUT'])
@login_required
def api_update_decision(decision_id):
    uid = session['user_id']
    dec = Decision.query.get_or_404(decision_id)
    if not check_project_access(dec.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    for field in ('title', 'description', 'rationale', 'impact', 'status'):
        if field in data:
            setattr(dec, field, data[field])
    dec.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Decision updated', 'decision': dec.to_dict()}), 200


@app.route('/api/decisions/<int:decision_id>/review', methods=['POST'])
@login_required
def api_review_decision(decision_id):
    uid = session['user_id']
    dec = Decision.query.get_or_404(decision_id)
    if not check_project_access(dec.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    action = data.get('action', '').strip()
    comment = data.get('comment', '').strip()

    if action not in ('approved', 'rejected', 'needs_review'):
        return jsonify({'error': 'Invalid action. Use approved, rejected, or needs_review'}), 400

    dec.verification_status = action
    dec.reviewed_by = uid
    dec.review_date = datetime.utcnow()
    dec.updated_at = datetime.utcnow()

    review = Review(
        project_id=dec.project_id,
        item_type='decision',
        item_id=decision_id,
        reviewer_id=uid,
        action=action,
        comment=comment,
        created_at=datetime.utcnow()
    )
    db.session.add(review)
    db.session.commit()

    log_activity(dec.project_id, uid, 'decision_reviewed',
                 f'Decision "{dec.title}" {action}')
    return jsonify({'message': f'Decision {action}', 'decision': dec.to_dict()}), 200


# ===================================================================
#  API  —  Tasks
# ===================================================================

@app.route('/api/projects/<int:project_id>/tasks', methods=['GET'])
@login_required
def api_list_tasks(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403
    tasks = Task.query.filter_by(project_id=project_id).order_by(
        Task.created_at.desc()
    ).all()
    return jsonify({'tasks': [t.to_dict() for t in tasks]}), 200


@app.route('/api/projects/<int:project_id>/tasks', methods=['POST'])
@login_required
def api_create_task(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Task title is required'}), 400

    task = Task(
        project_id=project_id,
        title=title,
        description=(data.get('description') or '').strip(),
        priority=data.get('priority', 'medium'),
        status=data.get('status', 'pending'),
        assigned_to=data.get('assigned_to'),
        due_date=_parse_date(data.get('due_date')),
        verification_status='pending',
        confidence=1.0,
        is_manual=True,
        created_at=datetime.utcnow()
    )
    db.session.add(task)
    db.session.commit()

    log_activity(project_id, uid, 'task_created', f'Created task "{title}"')
    return jsonify({'message': 'Task created', 'task': task.to_dict()}), 201


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@login_required
def api_update_task(task_id):
    uid = session['user_id']
    task = Task.query.get_or_404(task_id)
    if not check_project_access(task.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    for field in ('title', 'description', 'priority', 'status', 'assigned_to'):
        if field in data:
            setattr(task, field, data[field])
    if 'due_date' in data:
        task.due_date = _parse_date(data['due_date'])
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Task updated', 'task': task.to_dict()}), 200


@app.route('/api/tasks/<int:task_id>/review', methods=['POST'])
@login_required
def api_review_task(task_id):
    uid = session['user_id']
    task = Task.query.get_or_404(task_id)
    if not check_project_access(task.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    action = data.get('action', '').strip()
    comment = data.get('comment', '').strip()

    if action not in ('approved', 'rejected', 'needs_review'):
        return jsonify({'error': 'Invalid action'}), 400

    task.verification_status = action
    task.reviewed_by = uid
    task.review_date = datetime.utcnow()
    task.updated_at = datetime.utcnow()

    review = Review(
        project_id=task.project_id,
        item_type='task',
        item_id=task_id,
        reviewer_id=uid,
        action=action,
        comment=comment,
        created_at=datetime.utcnow()
    )
    db.session.add(review)
    db.session.commit()

    log_activity(task.project_id, uid, 'task_reviewed',
                 f'Task "{task.title}" {action}')
    return jsonify({'message': f'Task {action}', 'task': task.to_dict()}), 200


# ===================================================================
#  API  —  Risks
# ===================================================================

@app.route('/api/projects/<int:project_id>/risks', methods=['GET'])
@login_required
def api_list_risks(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403
    risks = Risk.query.filter_by(project_id=project_id).order_by(
        Risk.created_at.desc()
    ).all()
    return jsonify({'risks': [r.to_dict() for r in risks]}), 200


@app.route('/api/risks/<int:risk_id>', methods=['PUT'])
@login_required
def api_update_risk(risk_id):
    uid = session['user_id']
    risk = Risk.query.get_or_404(risk_id)
    if not check_project_access(risk.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    for field in ('title', 'description', 'severity', 'probability',
                  'mitigation', 'status'):
        if field in data:
            setattr(risk, field, data[field])
    risk.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Risk updated', 'risk': risk.to_dict()}), 200


@app.route('/api/risks/<int:risk_id>/review', methods=['POST'])
@login_required
def api_review_risk(risk_id):
    uid = session['user_id']
    risk = Risk.query.get_or_404(risk_id)
    if not check_project_access(risk.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    action = data.get('action', '').strip()
    comment = data.get('comment', '').strip()

    if action not in ('approved', 'rejected', 'needs_review'):
        return jsonify({'error': 'Invalid action'}), 400

    risk.verification_status = action
    risk.reviewed_by = uid
    risk.review_date = datetime.utcnow()
    risk.updated_at = datetime.utcnow()

    review = Review(
        project_id=risk.project_id,
        item_type='risk',
        item_id=risk_id,
        reviewer_id=uid,
        action=action,
        comment=comment,
        created_at=datetime.utcnow()
    )
    db.session.add(review)
    db.session.commit()

    log_activity(risk.project_id, uid, 'risk_reviewed',
                 f'Risk "{risk.title}" {action}')
    return jsonify({'message': f'Risk {action}', 'risk': risk.to_dict()}), 200


# ===================================================================
#  API  —  Evidence
# ===================================================================

@app.route('/api/evidence/<string:item_type>/<int:item_id>', methods=['GET'])
@login_required
def api_get_evidence(item_type, item_id):
    uid = session['user_id']

    if item_type == 'decision':
        evidence = Evidence.query.filter_by(decision_id=item_id).all()
    elif item_type == 'task':
        evidence = Evidence.query.filter_by(task_id=item_id).all()
    elif item_type == 'risk':
        evidence = Evidence.query.filter_by(risk_id=item_id).all()
    else:
        return jsonify({'error': 'Invalid item type. Use decision, task, or risk'}), 400

    # Optional: verify project access via the first evidence item
    if evidence:
        if not check_project_access(evidence[0].project_id, uid):
            return jsonify({'error': 'Access denied'}), 403

    return jsonify({'evidence': [e.to_dict() for e in evidence]}), 200


# ===================================================================
#  API  —  Reviews
# ===================================================================

@app.route('/api/projects/<int:project_id>/reviews', methods=['GET'])
@login_required
def api_list_reviews(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    reviews = Review.query.filter_by(project_id=project_id).order_by(
        Review.created_at.desc()
    ).all()

    result = []
    for r in reviews:
        rd = r.to_dict()
        reviewer = User.query.get(r.reviewer_id)
        rd['reviewer_name'] = reviewer.full_name if reviewer else 'Unknown'
        result.append(rd)

    return jsonify({'reviews': result}), 200


@app.route('/api/projects/<int:project_id>/pending-reviews', methods=['GET'])
@login_required
def api_pending_reviews(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    pending_decisions = Decision.query.filter(
        Decision.project_id == project_id,
        Decision.verification_status.in_(['pending', 'needs_review'])
    ).all()
    pending_tasks = Task.query.filter(
        Task.project_id == project_id,
        Task.verification_status.in_(['pending', 'needs_review'])
    ).all()
    pending_risks = Risk.query.filter(
        Risk.project_id == project_id,
        Risk.verification_status.in_(['pending', 'needs_review'])
    ).all()

    return jsonify({
        'pending': {
            'decisions': [d.to_dict() for d in pending_decisions],
            'tasks': [t.to_dict() for t in pending_tasks],
            'risks': [r.to_dict() for r in pending_risks],
            'total': len(pending_decisions) + len(pending_tasks) + len(pending_risks)
        }
    }), 200


# ===================================================================
#  API  —  Reports
# ===================================================================

@app.route('/api/projects/<int:project_id>/reports/generate', methods=['POST'])
@login_required
def api_generate_report(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    project = Project.query.get_or_404(project_id)
    decisions = Decision.query.filter_by(project_id=project_id).all()
    tasks = Task.query.filter_by(project_id=project_id).all()
    risks = Risk.query.filter_by(project_id=project_id).all()
    dependencies = Dependency.query.filter_by(project_id=project_id).all()
    members = ProjectMember.query.filter_by(project_id=project_id).all()

    # Compute completion
    total_items = len(decisions) + len(tasks) + len(risks)
    verified = sum(1 for d in decisions if d.verification_status == 'approved') + \
               sum(1 for t in tasks if t.verification_status == 'approved') + \
               sum(1 for r in risks if r.verification_status == 'approved')
    completion = round((verified / total_items * 100) if total_items else 0, 1)

    # Build JSON report_data
    report_data = {
        'project': project.to_dict(),
        'decisions': [d.to_dict() for d in decisions],
        'tasks': [t.to_dict() for t in tasks],
        'risks': [r.to_dict() for r in risks],
        'dependencies': [dep.to_dict() for dep in dependencies],
        'completion': completion,
        'generated_at': datetime.utcnow().isoformat(),
        'generated_by': uid
    }

    # Generate PDF
    report_filename = f'handover_{project_id}_{uuid.uuid4().hex[:8]}.pdf'
    report_path = os.path.join(app.config['REPORT_FOLDER'], report_filename)

    try:
        _generate_pdf_report(report_path, project, decisions, tasks, risks,
                             dependencies, members, completion)
    except Exception as exc:
        return jsonify({'error': f'PDF generation failed: {exc}'}), 500

    report = HandoverReport(
        project_id=project_id,
        title=f'Handover Report - {project.name}',
        report_data=json.dumps(report_data),
        file_path=report_path,
        file_name=report_filename,
        generated_by=uid,
        completion_percentage=completion,
        status='generated',
        generated_at=datetime.utcnow()
    )
    db.session.add(report)
    db.session.commit()

    log_activity(project_id, uid, 'report_generated',
                 f'Generated handover report (completion: {completion}%)')

    return jsonify({
        'message': 'Report generated',
        'report': report.to_dict()
    }), 201


@app.route('/api/projects/<int:project_id>/reports', methods=['GET'])
@login_required
def api_list_reports(project_id):
    uid = session['user_id']
    if not check_project_access(project_id, uid):
        return jsonify({'error': 'Access denied'}), 403
    reports = HandoverReport.query.filter_by(project_id=project_id).order_by(
        HandoverReport.generated_at.desc()
    ).all()
    return jsonify({'reports': [r.to_dict() for r in reports]}), 200


@app.route('/api/reports/<int:report_id>/download', methods=['GET'])
@login_required
def api_download_report(report_id):
    report = HandoverReport.query.get_or_404(report_id)
    uid = session['user_id']
    if not check_project_access(report.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    if not report.file_path or not os.path.exists(report.file_path):
        return jsonify({'error': 'Report file not found'}), 404

    return send_file(
        report.file_path,
        as_attachment=True,
        download_name=report.file_name or 'report.pdf'
    )


@app.route('/api/reports/<int:report_id>/download/csv', methods=['GET'])
@login_required
def api_download_report_csv(report_id):
    report = HandoverReport.query.get_or_404(report_id)
    uid = session['user_id']
    if not check_project_access(report.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    project_id = report.project_id
    decisions = Decision.query.filter_by(project_id=project_id).all()
    tasks = Task.query.filter_by(project_id=project_id).all()
    risks = Risk.query.filter_by(project_id=project_id).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Decisions sheet
    writer.writerow(['--- DECISIONS ---'])
    writer.writerow(['ID', 'Title', 'Description', 'Rationale', 'Impact',
                     'Status', 'Verification', 'Confidence', 'Created'])
    for d in decisions:
        writer.writerow([
            d.id, d.title, d.description, d.rationale, d.impact,
            d.status, d.verification_status, d.confidence,
            d.created_at.isoformat() if d.created_at else ''
        ])

    writer.writerow([])
    writer.writerow(['--- TASKS ---'])
    writer.writerow(['ID', 'Title', 'Description', 'Priority', 'Status',
                     'Verification', 'Confidence', 'Assigned To', 'Due Date', 'Created'])
    for t in tasks:
        writer.writerow([
            t.id, t.title, t.description, t.priority, t.status,
            t.verification_status, t.confidence,
            t.assigned_to or '',
            t.due_date.isoformat() if t.due_date else '',
            t.created_at.isoformat() if t.created_at else ''
        ])

    writer.writerow([])
    writer.writerow(['--- RISKS ---'])
    writer.writerow(['ID', 'Title', 'Description', 'Severity', 'Probability',
                     'Mitigation', 'Status', 'Verification', 'Confidence', 'Created'])
    for r in risks:
        writer.writerow([
            r.id, r.title, r.description, r.severity, r.probability,
            r.mitigation, r.status, r.verification_status, r.confidence,
            r.created_at.isoformat() if r.created_at else ''
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'report_{report_id}.csv'
    )


# ===================================================================
#  API  —  Acknowledgements
# ===================================================================

@app.route('/api/reports/<int:report_id>/acknowledge', methods=['POST'])
@login_required
def api_acknowledge_report(report_id):
    uid = session['user_id']
    report = HandoverReport.query.get_or_404(report_id)
    if not check_project_access(report.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    existing = Acknowledgement.query.filter_by(
        report_id=report_id, user_id=uid
    ).first()

    if existing:
        existing.status = 'acknowledged'
        existing.acknowledged_at = datetime.utcnow()
    else:
        ack = Acknowledgement(
            report_id=report_id,
            user_id=uid,
            status='acknowledged',
            acknowledged_at=datetime.utcnow()
        )
        db.session.add(ack)

    db.session.commit()
    log_activity(report.project_id, uid, 'report_acknowledged',
                 f'Acknowledged report #{report_id}')
    return jsonify({'message': 'Report acknowledged'}), 200


@app.route('/api/reports/<int:report_id>/acknowledgements', methods=['GET'])
@login_required
def api_list_acknowledgements(report_id):
    report = HandoverReport.query.get_or_404(report_id)
    uid = session['user_id']
    if not check_project_access(report.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    acks = Acknowledgement.query.filter_by(report_id=report_id).all()
    result = []
    for a in acks:
        ad = a.to_dict()
        user = User.query.get(a.user_id)
        ad['user_name'] = user.full_name if user else 'Unknown'
        ad['user_email'] = user.email if user else ''
        result.append(ad)

    return jsonify({'acknowledgements': result}), 200


@app.route('/api/reports/<int:report_id>/share', methods=['POST'])
@login_required
def api_share_report(report_id):
    uid = session['user_id']
    report = HandoverReport.query.get_or_404(report_id)
    if not check_project_access(report.project_id, uid):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    user_ids = data.get('user_ids', [])

    if not user_ids:
        # Share with all project members
        members = ProjectMember.query.filter_by(project_id=report.project_id).all()
        user_ids = [m.user_id for m in members]

    created_count = 0
    for target_uid in user_ids:
        if target_uid == uid:
            continue
        existing = Acknowledgement.query.filter_by(
            report_id=report_id, user_id=target_uid
        ).first()
        if not existing:
            ack = Acknowledgement(
                report_id=report_id,
                user_id=target_uid,
                status='pending',
                acknowledged_at=None
            )
            db.session.add(ack)
            created_count += 1

    db.session.commit()
    log_activity(report.project_id, uid, 'report_shared',
                 f'Shared report #{report_id} with {created_count} users')
    return jsonify({
        'message': f'Report shared with {created_count} users'
    }), 200


# ===================================================================
#  API  —  Dashboard
# ===================================================================

@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats():
    uid = session['user_id']

    member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=uid).all()]
    created_pids = [p.id for p in Project.query.filter_by(created_by=uid).all()]
    project_ids = list(set(member_pids + created_pids))

    if not project_ids:
        return jsonify({
            'stats': {
                'total_projects': 0,
                'total_documents': 0,
                'total_decisions': 0,
                'total_tasks': 0,
                'pending_tasks': 0,
                'total_risks': 0,
                'handover_completion': 0
            }
        }), 200

    total_docs = Document.query.filter(Document.project_id.in_(project_ids)).count()
    total_decisions = Decision.query.filter(Decision.project_id.in_(project_ids)).count()
    total_tasks = Task.query.filter(Task.project_id.in_(project_ids)).count()
    pending_tasks = Task.query.filter(
        Task.project_id.in_(project_ids), Task.status == 'pending'
    ).count()
    total_risks = Risk.query.filter(Risk.project_id.in_(project_ids)).count()

    total_items = total_decisions + total_tasks + total_risks
    approved_items = (
        Decision.query.filter(
            Decision.project_id.in_(project_ids),
            Decision.verification_status == 'approved'
        ).count() +
        Task.query.filter(
            Task.project_id.in_(project_ids),
            Task.verification_status == 'approved'
        ).count() +
        Risk.query.filter(
            Risk.project_id.in_(project_ids),
            Risk.verification_status == 'approved'
        ).count()
    )
    completion = round((approved_items / total_items * 100) if total_items else 0, 1)

    return jsonify({
        'stats': {
            'total_projects': len(project_ids),
            'total_documents': total_docs,
            'total_decisions': total_decisions,
            'total_tasks': total_tasks,
            'pending_tasks': pending_tasks,
            'total_risks': total_risks,
            'handover_completion': completion
        }
    }), 200


@app.route('/api/dashboard/activity', methods=['GET'])
@login_required
def api_dashboard_activity():
    uid = session['user_id']

    member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=uid).all()]
    created_pids = [p.id for p in Project.query.filter_by(created_by=uid).all()]
    project_ids = list(set(member_pids + created_pids))

    if not project_ids:
        return jsonify({'activity': []}), 200

    logs = ActivityLog.query.filter(
        ActivityLog.project_id.in_(project_ids)
    ).order_by(ActivityLog.timestamp.desc()).limit(50).all()

    result = []
    for log_entry in logs:
        ld = log_entry.to_dict()
        user = User.query.get(log_entry.user_id)
        ld['user_name'] = user.full_name if user else 'Unknown'
        project = Project.query.get(log_entry.project_id)
        ld['project_name'] = project.name if project else 'Unknown'
        result.append(ld)

    return jsonify({'activity': result}), 200


@app.route('/api/dashboard/charts', methods=['GET'])
@login_required
def api_dashboard_charts():
    uid = session['user_id']

    member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=uid).all()]
    created_pids = [p.id for p in Project.query.filter_by(created_by=uid).all()]
    project_ids = list(set(member_pids + created_pids))

    # Tasks by status
    tasks_by_status = {}
    for status_val in ('pending', 'in_progress', 'completed', 'blocked'):
        tasks_by_status[status_val] = Task.query.filter(
            Task.project_id.in_(project_ids), Task.status == status_val
        ).count() if project_ids else 0

    # Risks by severity
    risks_by_severity = {}
    for sev in ('low', 'medium', 'high', 'critical'):
        risks_by_severity[sev] = Risk.query.filter(
            Risk.project_id.in_(project_ids), Risk.severity == sev
        ).count() if project_ids else 0

    # Decisions by status
    decisions_by_status = {}
    for vs in ('pending', 'approved', 'rejected', 'needs_review'):
        decisions_by_status[vs] = Decision.query.filter(
            Decision.project_id.in_(project_ids),
            Decision.verification_status == vs
        ).count() if project_ids else 0

    # Activity timeline (last 7 days)
    activity_timeline = []
    for i in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        count = 0
        if project_ids:
            count = ActivityLog.query.filter(
                ActivityLog.project_id.in_(project_ids),
                ActivityLog.timestamp >= day_start,
                ActivityLog.timestamp < day_end
            ).count()
        activity_timeline.append({
            'date': day.isoformat(),
            'count': count
        })

    return jsonify({
        'charts': {
            'tasks_by_status': tasks_by_status,
            'risks_by_severity': risks_by_severity,
            'decisions_by_status': decisions_by_status,
            'activity_timeline': activity_timeline
        }
    }), 200


# ===================================================================
#  API  —  AI
# ===================================================================

@app.route('/api/ai/status', methods=['GET'])
def api_ai_status():
    status = ai_engine.get_status()
    return jsonify({'ai': status}), 200


# ===================================================================
#  Internal helpers
# ===================================================================

def _parse_date(date_str):
    """Best-effort ISO date parsing.  Returns None on failure."""
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _generate_pdf_report(filepath, project, decisions, tasks, risks,
                         dependencies, members, completion):
    """Create a professional PDF handover report with ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch, mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
        PageBreak, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    KB_BLUE = colors.HexColor('#4F7DF3')
    KB_LIGHT = colors.HexColor('#F0EDFF')
    KB_ACCENT = colors.HexColor('#43BFA5')
    KB_TEXT = colors.HexColor('#24324A')
    KB_BORDER = colors.HexColor('#E7ECF3')

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=60,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='KBTitle',
        parent=styles['Title'],
        fontSize=28,
        leading=34,
        textColor=KB_BLUE,
        alignment=TA_CENTER,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='KBSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        leading=18,
        textColor=KB_TEXT,
        alignment=TA_CENTER,
        spaceAfter=24
    ))
    styles.add(ParagraphStyle(
        name='KBHeading',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=KB_BLUE,
        spaceBefore=18,
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name='KBHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        textColor=KB_TEXT,
        spaceBefore=12,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='KBBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=KB_TEXT
    ))
    styles.add(ParagraphStyle(
        name='KBSmall',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.grey
    ))

    elements = []

    # --- Title page ---
    elements.append(Spacer(1, 2 * inch))
    elements.append(Paragraph('KnowBridge AI', styles['KBTitle']))
    elements.append(Paragraph('Knowledge Handover Report', styles['KBSubtitle']))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(HRFlowable(
        width='60%', thickness=2, color=KB_BLUE, spaceAfter=20, spaceBefore=10
    ))
    elements.append(Paragraph(f'<b>{project.name}</b>', styles['KBSubtitle']))
    if project.description:
        elements.append(Paragraph(project.description, styles['KBBody']))
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        f'Completion: <b>{completion}%</b>', styles['KBSubtitle']
    ))
    elements.append(Paragraph(
        f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}',
        styles['KBSmall']
    ))
    elements.append(PageBreak())

    # --- Table of Contents ---
    elements.append(Paragraph('Table of Contents', styles['KBHeading']))
    toc_items = [
        '1. Project Overview',
        '2. Team Members',
        f'3. Decisions ({len(decisions)})',
        f'4. Tasks ({len(tasks)})',
        f'5. Risks ({len(risks)})',
        f'6. Dependencies ({len(dependencies)})',
        '7. Completion Summary',
    ]
    for item in toc_items:
        elements.append(Paragraph(item, styles['KBBody']))
        elements.append(Spacer(1, 4))
    elements.append(PageBreak())

    # --- 1. Project Overview ---
    elements.append(Paragraph('1. Project Overview', styles['KBHeading']))
    overview_data = [
        ['Project Name', project.name],
        ['Status', project.status or 'active'],
        ['Created', project.created_at.strftime('%Y-%m-%d') if project.created_at else 'N/A'],
        ['Total Decisions', str(len(decisions))],
        ['Total Tasks', str(len(tasks))],
        ['Total Risks', str(len(risks))],
        ['Total Dependencies', str(len(dependencies))],
        ['Handover Completion', f'{completion}%'],
    ]
    overview_table = Table(overview_data, colWidths=[2.5 * inch, 4 * inch])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), KB_LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, -1), KB_TEXT),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, KB_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 0.3 * inch))

    # --- 2. Team Members ---
    elements.append(Paragraph('2. Team Members', styles['KBHeading']))
    if members:
        member_header = ['Name', 'Role', 'Type', 'Joined']
        member_rows = [member_header]
        for m in members:
            u = User.query.get(m.user_id)
            member_type = []
            if m.is_outgoing:
                member_type.append('Outgoing')
            if m.is_incoming:
                member_type.append('Incoming')
            member_rows.append([
                u.full_name if u else 'Unknown',
                m.role,
                ', '.join(member_type) if member_type else 'Current',
                m.joined_at.strftime('%Y-%m-%d') if m.joined_at else 'N/A'
            ])
        member_table = Table(member_rows, colWidths=[2 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
        member_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), KB_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, KB_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, KB_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(member_table)
    else:
        elements.append(Paragraph('No team members assigned.', styles['KBBody']))
    elements.append(Spacer(1, 0.3 * inch))

    # --- 3. Decisions ---
    elements.append(Paragraph('3. Decisions', styles['KBHeading']))
    if decisions:
        dec_header = ['#', 'Title', 'Impact', 'Status', 'Verified', 'Confidence']
        dec_rows = [dec_header]
        for idx, d in enumerate(decisions, 1):
            dec_rows.append([
                str(idx),
                Paragraph(d.title[:60], styles['KBBody']),
                d.impact or 'N/A',
                d.status or 'N/A',
                d.verification_status or 'pending',
                f'{d.confidence}'.capitalize() if isinstance(d.confidence, str) else f'{(d.confidence or 0) * 100:.0f}%'
            ])
        dec_table = Table(dec_rows,
                          colWidths=[0.4 * inch, 2.4 * inch, 0.8 * inch,
                                     0.9 * inch, 0.9 * inch, 0.9 * inch])
        dec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), KB_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, KB_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, KB_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(dec_table)

        # Decision details
        for idx, d in enumerate(decisions, 1):
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(f'Decision {idx}: {d.title}', styles['KBHeading2']))
            if d.description:
                elements.append(Paragraph(f'<b>Description:</b> {d.description}', styles['KBBody']))
            if d.rationale:
                elements.append(Paragraph(f'<b>Rationale:</b> {d.rationale}', styles['KBBody']))
    else:
        elements.append(Paragraph('No decisions recorded.', styles['KBBody']))
    elements.append(Spacer(1, 0.3 * inch))

    # --- 4. Tasks ---
    elements.append(Paragraph('4. Tasks', styles['KBHeading']))
    if tasks:
        task_header = ['#', 'Title', 'Priority', 'Status', 'Verified', 'Confidence']
        task_rows = [task_header]
        for idx, t in enumerate(tasks, 1):
            task_rows.append([
                str(idx),
                Paragraph(t.title[:60], styles['KBBody']),
                t.priority or 'N/A',
                t.status or 'N/A',
                t.verification_status or 'pending',
                f'{t.confidence}'.capitalize() if isinstance(t.confidence, str) else f'{(t.confidence or 0) * 100:.0f}%'
            ])
        task_table = Table(task_rows,
                           colWidths=[0.4 * inch, 2.4 * inch, 0.8 * inch,
                                      0.9 * inch, 0.9 * inch, 0.9 * inch])
        task_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), KB_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, KB_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, KB_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(task_table)
    else:
        elements.append(Paragraph('No tasks recorded.', styles['KBBody']))
    elements.append(Spacer(1, 0.3 * inch))

    # --- 5. Risks ---
    elements.append(Paragraph('5. Risks', styles['KBHeading']))
    if risks:
        risk_header = ['#', 'Title', 'Severity', 'Probability', 'Status', 'Verified']
        risk_rows = [risk_header]
        for idx, r in enumerate(risks, 1):
            risk_rows.append([
                str(idx),
                Paragraph(r.title[:60], styles['KBBody']),
                r.severity or 'N/A',
                r.probability or 'N/A',
                r.status or 'N/A',
                r.verification_status or 'pending'
            ])
        risk_table = Table(risk_rows,
                           colWidths=[0.4 * inch, 2.2 * inch, 0.9 * inch,
                                      0.9 * inch, 0.9 * inch, 0.9 * inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), KB_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, KB_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, KB_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(risk_table)

        # Risk details with mitigation
        for idx, r in enumerate(risks, 1):
            if r.mitigation:
                elements.append(Spacer(1, 6))
                elements.append(Paragraph(
                    f'<b>Risk {idx} Mitigation:</b> {r.mitigation}', styles['KBBody']
                ))
    else:
        elements.append(Paragraph('No risks recorded.', styles['KBBody']))
    elements.append(Spacer(1, 0.3 * inch))

    # --- 6. Dependencies ---
    elements.append(Paragraph('6. Dependencies', styles['KBHeading']))
    if dependencies:
        dep_header = ['#', 'Title', 'Type', 'Status', 'Description']
        dep_rows = [dep_header]
        for idx, dep in enumerate(dependencies, 1):
            dep_rows.append([
                str(idx),
                Paragraph((dep.title or '')[:50], styles['KBBody']),
                dep.dependency_type or 'N/A',
                dep.status or 'N/A',
                Paragraph((dep.description or '')[:80], styles['KBBody'])
            ])
        dep_table = Table(dep_rows,
                          colWidths=[0.4 * inch, 1.6 * inch, 1 * inch,
                                     0.8 * inch, 2.5 * inch])
        dep_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), KB_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, KB_BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, KB_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(dep_table)
    else:
        elements.append(Paragraph('No dependencies recorded.', styles['KBBody']))
    elements.append(Spacer(1, 0.3 * inch))

    # --- 7. Completion Summary ---
    elements.append(Paragraph('7. Completion Summary', styles['KBHeading']))

    approved_d = sum(1 for d in decisions if d.verification_status == 'approved')
    approved_t = sum(1 for t in tasks if t.verification_status == 'approved')
    approved_r = sum(1 for r in risks if r.verification_status == 'approved')

    summary_data = [
        ['Category', 'Total', 'Approved', 'Pending / Other'],
        ['Decisions', str(len(decisions)), str(approved_d),
         str(len(decisions) - approved_d)],
        ['Tasks', str(len(tasks)), str(approved_t),
         str(len(tasks) - approved_t)],
        ['Risks', str(len(risks)), str(approved_r),
         str(len(risks) - approved_r)],
        ['TOTAL', str(len(decisions) + len(tasks) + len(risks)),
         str(approved_d + approved_t + approved_r),
         str((len(decisions) + len(tasks) + len(risks)) -
             (approved_d + approved_t + approved_r))],
    ]
    summary_table = Table(summary_data,
                          colWidths=[2 * inch, 1.2 * inch, 1.2 * inch, 1.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), KB_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), KB_LIGHT),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, KB_BORDER),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph(
        f'Overall Handover Completion: <b>{completion}%</b>', styles['KBSubtitle']
    ))

    # Missing information note
    missing = []
    if not decisions:
        missing.append('No decisions documented')
    if not tasks:
        missing.append('No tasks documented')
    if not risks:
        missing.append('No risks documented')
    if not dependencies:
        missing.append('No dependencies documented')
    pending_count = sum(1 for d in decisions if d.verification_status != 'approved') + \
                    sum(1 for t in tasks if t.verification_status != 'approved') + \
                    sum(1 for r in risks if r.verification_status != 'approved')
    if pending_count:
        missing.append(f'{pending_count} item(s) still awaiting approval')

    if missing:
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph('Missing / Incomplete Information', styles['KBHeading2']))
        for m in missing:
            elements.append(Paragraph(f'• {m}', styles['KBBody']))

    # Footer timestamp
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(HRFlowable(width='100%', thickness=1, color=KB_BORDER))
    elements.append(Paragraph(
        f'Report generated by KnowBridge AI on '
        f'{datetime.utcnow().strftime("%Y-%m-%d at %H:%M UTC")}',
        styles['KBSmall']
    ))

    # Build
    doc.build(elements)


# ===================================================================
#  Run
# ===================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
