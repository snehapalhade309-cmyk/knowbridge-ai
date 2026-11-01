from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), default='admin')  # admin, outgoing, incoming, reviewer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username, 'email': self.email,
            'full_name': self.full_name, 'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # active, completed, archived
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', backref='created_projects')
    members = db.relationship('ProjectMember', backref='project', cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='project', cascade='all, delete-orphan')
    decisions = db.relationship('Decision', backref='project', cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='project', cascade='all, delete-orphan')
    risks = db.relationship('Risk', backref='project', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'description': self.description,
            'status': self.status, 'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'member_count': len(self.members),
            'document_count': len(self.documents)
        }


class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='member')
    is_outgoing = db.Column(db.Boolean, default=False)
    is_incoming = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='project_memberships')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'user_id': self.user_id,
            'role': self.role, 'is_outgoing': self.is_outgoing, 'is_incoming': self.is_incoming,
            'user_name': self.user.full_name if self.user else None,
            'user_email': self.user.email if self.user else None,
            'added_at': (self.added_at or self.joined_at).isoformat() if (self.added_at or self.joined_at) else None
        }


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    name = db.Column(db.String(255))
    filename = db.Column(db.String(255), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500))
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    processing_status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    extracted_text = db.Column(db.Text)
    error_message = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    uploader = db.relationship('User', backref='uploaded_documents')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id,
            'name': self.name or self.original_filename,
            'filename': self.filename, 'original_filename': self.original_filename,
            'file_type': self.file_type, 'file_size': self.file_size,
            'upload_date': (self.uploaded_at or self.upload_date).isoformat() if (self.uploaded_at or self.upload_date) else None,
            'uploaded_at': (self.uploaded_at or self.upload_date).isoformat() if (self.uploaded_at or self.upload_date) else None,
            'processing_status': self.processing_status,
            'has_text': bool(self.extracted_text),
            'text_length': len(self.extracted_text) if self.extracted_text else 0,
            'uploaded_by': self.uploaded_by,
            'uploader_name': self.uploader.full_name if self.uploader else None
        }


class Decision(db.Model):
    __tablename__ = 'decisions'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    rationale = db.Column(db.Text)
    impact = db.Column(db.String(100), default='medium')
    status = db.Column(db.String(20), default='active')
    decision_date = db.Column(db.String(100))
    responsible_person = db.Column(db.String(150))
    source_excerpt = db.Column(db.Text)
    confidence = db.Column(db.String(20), default='medium')  # high, medium, low
    verification_status = db.Column(db.String(20), default='unverified')  # unverified, approved, rejected, needs_review
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_date = db.Column(db.DateTime)
    review_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship('Document', backref='decisions')
    reviewer = db.relationship('User', backref='reviewed_decisions', foreign_keys=[reviewed_by])

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'document_id': self.document_id,
            'title': self.title, 'description': self.description,
            'rationale': self.rationale, 'impact': self.impact, 'status': self.status,
            'decision_date': self.decision_date, 'responsible_person': self.responsible_person,
            'source_excerpt': self.source_excerpt, 'confidence': self.confidence,
            'verification_status': self.verification_status,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'review_date': self.review_date.isoformat() if self.review_date else None,
            'review_comment': self.review_comment,
            'document_name': self.document.original_filename if self.document else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.String(150))
    deadline = db.Column(db.String(100))
    due_date = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(20), default='medium')  # high, medium, low
    status = db.Column(db.String(20), default='not_started')  # not_started, in_progress, completed, blocked
    source_excerpt = db.Column(db.Text)
    confidence = db.Column(db.String(20), default='medium')
    verification_status = db.Column(db.String(20), default='unverified')
    is_manual = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship('Document', backref='tasks')
    creator = db.relationship('User', backref='created_tasks')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'document_id': self.document_id,
            'title': self.title, 'description': self.description,
            'assigned_to': self.assigned_to, 'deadline': self.deadline,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'priority': self.priority, 'status': self.status,
            'source_excerpt': self.source_excerpt, 'confidence': self.confidence,
            'verification_status': self.verification_status,
            'is_manual': self.is_manual, 'created_by': self.created_by,
            'document_name': self.document.original_filename if self.document else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class Risk(db.Model):
    __tablename__ = 'risks'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20), default='medium')  # critical, high, medium, low
    probability = db.Column(db.String(20), default='medium')
    mitigation = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')
    risk_type = db.Column(db.String(30), default='unresolved_issue')
    source_excerpt = db.Column(db.Text)
    confidence = db.Column(db.String(20), default='medium')
    verification_status = db.Column(db.String(20), default='unverified')
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship('Document', backref='risks')
    reviewer = db.relationship('User', backref='reviewed_risks')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'document_id': self.document_id,
            'title': self.title, 'description': self.description,
            'severity': self.severity, 'probability': self.probability,
            'mitigation': self.mitigation, 'status': self.status,
            'risk_type': self.risk_type,
            'source_excerpt': self.source_excerpt, 'confidence': self.confidence,
            'verification_status': self.verification_status,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'document_name': self.document.original_filename if self.document else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class Dependency(db.Model):
    __tablename__ = 'dependencies'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    from_item = db.Column(db.String(200))
    to_item = db.Column(db.String(200))
    dependency_type = db.Column(db.String(50), default='technical')
    status = db.Column(db.String(20), default='active')  # active, resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id,
            'title': self.title, 'description': self.description,
            'from_item': self.from_item, 'to_item': self.to_item,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class Evidence(db.Model):
    __tablename__ = 'evidence'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    decision_id = db.Column(db.Integer, db.ForeignKey('decisions.id'), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    risk_id = db.Column(db.Integer, db.ForeignKey('risks.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    excerpt = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(255), nullable=True)
    evidence_type = db.Column(db.String(50), default='ai_extracted')
    page_number = db.Column(db.String(20))
    section = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship('Document', backref='evidence_items')

    def to_dict(self):
        return {
            'id': self.id, 'decision_id': self.decision_id,
            'task_id': self.task_id, 'risk_id': self.risk_id,
            'document_id': self.document_id,
            'document_name': self.document.original_filename if self.document else None,
            'excerpt': self.excerpt or self.content,
            'content': self.content or self.excerpt,
            'source': self.source,
            'evidence_type': self.evidence_type,
            'page_number': self.page_number,
            'section': self.section,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20), nullable=False)  # decision, task, risk
    item_id = db.Column(db.Integer, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # approved, rejected, needs_review
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship('User', backref='reviews')

    def to_dict(self):
        return {
            'id': self.id, 'item_type': self.item_type, 'item_id': self.item_id,
            'project_id': self.project_id, 'reviewer_id': self.reviewer_id,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'action': self.action, 'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class HandoverReport(db.Model):
    __tablename__ = 'handover_reports'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(300))
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='draft')  # draft, final, generated
    file_path = db.Column(db.String(500))
    file_name = db.Column(db.String(255))
    completion_percentage = db.Column(db.Float, default=0.0)
    version = db.Column(db.Integer, default=1)
    report_data = db.Column(db.Text)  # JSON string

    project = db.relationship('Project', backref='reports')
    generator = db.relationship('User', backref='generated_reports')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'generated_by': self.generated_by,
            'generator_name': self.generator.full_name if self.generator else None,
            'title': self.title,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'status': self.status, 'version': self.version,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'completion_percentage': self.completion_percentage
        }


class Acknowledgement(db.Model):
    __tablename__ = 'acknowledgements'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('handover_reports.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, acknowledged
    acknowledged_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    report = db.relationship('HandoverReport', backref='acknowledgements')
    user = db.relationship('User', backref='acknowledgements')

    def to_dict(self):
        return {
            'id': self.id, 'report_id': self.report_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'status': self.status,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='activity_logs')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'action': self.action, 'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'timestamp': (self.timestamp or self.created_at).isoformat() if (self.timestamp or self.created_at) else None
        }
