# ═══════════════════════════════════════════════════════════════════════════════
# improvements.py  — KnowBridge AI  Round 3 Improvements
#
# Improvement 1 : Audio/Video Exit-Interview Ingestion Engine
# Improvement 2 : Semantic Handover Search (RAG / ChromaDB)
# Improvement 3 : Two-Way Issue Tracker Sync (GitHub · Slack · Jira)
# ═══════════════════════════════════════════════════════════════════════════════
import os, json, re, uuid, tempfile, logging
from datetime import datetime, timezone
from functools import wraps

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, current_app)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

imp = Blueprint('imp', __name__)   # registered in app.py as   app.register_blueprint(imp)

# ── lazy imports (avoid startup crash if library missing) ───────────────────
def _try_import(mod):
    try:
        import importlib
        return importlib.import_module(mod)
    except ImportError:
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _get_gemini():
    """Return configured Gemini model or None."""
    genai = _try_import('google.generativeai')
    if not genai:
        return None, "google-generativeai not installed"
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return None, "GEMINI_API_KEY not set"
    genai.configure(api_key=api_key)
    return genai, None


def _db():
    """Access the shared SQLAlchemy db from app context."""
    from app import db
    return db


def _models():
    from app import (db, Project, Task, Risk, Decision, ExtractedKnowledge,
                     Document, AuditLog, AppSetting, log_action)
    return db, Project, Task, Risk, Decision, ExtractedKnowledge, Document, AuditLog, AppSetting, log_action


def _get_setting(key, default=''):
    from app import AppSetting
    s = AppSetting.query.filter_by(key=key).first()
    return s.value if (s and s.value) else os.getenv(key, default)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def pm_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('admin', 'project_manager'):
            flash('Project Manager or Admin access required.', 'warning')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 1 — AUDIO / VIDEO TRANSCRIPTION
# ═══════════════════════════════════════════════════════════════════════════════
AUDIO_EXTENSIONS = {'mp3', 'mp4', 'wav', 'ogg', 'm4a', 'webm', 'flac'}
AUDIO_MIME = {
    'mp3': 'audio/mp3', 'mp4': 'video/mp4', 'wav': 'audio/wav',
    'ogg': 'audio/ogg', 'm4a': 'audio/m4a', 'webm': 'video/webm',
    'flac': 'audio/flac',
}
MAX_AUDIO_MB = 100


@imp.route('/transcribe')
@login_required
def transcribe_page():
    db, Project, *_ = _models()
    if current_user.role == 'admin':
        projects = Project.query.order_by(Project.name).all()
    else:
        from app import ProjectMember
        memberships = ProjectMember.query.filter_by(user_id=current_user.id).all()
        pids = [m.project_id for m in memberships]
        projects = Project.query.filter(Project.id.in_(pids)).order_by(Project.name).all()
    return render_template('transcribe.html', projects=projects)


@imp.route('/api/transcribe/upload', methods=['POST'])
@login_required
def api_transcribe_upload():
    """Upload an audio/video file and transcribe with Gemini."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Empty filename'}), 400

    ext = f.filename.rsplit('.', 1)[-1].lower()
    if ext not in AUDIO_EXTENSIONS:
        return jsonify({'error': f'Unsupported format. Allowed: {", ".join(AUDIO_EXTENSIONS)}'}), 400

    # Size check
    f.seek(0, 2); size_mb = f.tell() / (1024*1024); f.seek(0)
    if size_mb > MAX_AUDIO_MB:
        return jsonify({'error': f'File too large ({size_mb:.1f} MB). Max {MAX_AUDIO_MB} MB.'}), 400

    project_id = request.form.get('project_id', type=int)
    interview_type = request.form.get('interview_type', 'exit_interview')

    # Save temp
    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    fname = f"audio_{uuid.uuid4().hex[:8]}.{ext}"
    fpath = os.path.join(upload_dir, fname)
    f.save(fpath)

    try:
        result = _transcribe_with_gemini(fpath, ext, interview_type, project_id)
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        result = _transcribe_fallback(fpath)
    finally:
        # clean up temp audio file after extraction
        try:
            os.remove(fpath)
        except Exception:
            pass

    if project_id and result.get('knowledge_items'):
        _save_transcription_knowledge(project_id, result, f.filename)

    return jsonify(result)


def _transcribe_with_gemini(fpath, ext, interview_type, project_id):
    genai, err = _get_gemini()
    if err:
        raise RuntimeError(err)

    mime = AUDIO_MIME.get(ext, 'audio/mp3')
    prompt = f"""You are analysing a {interview_type.replace('_', ' ')} recording for a knowledge handover platform.

Task:
1. Transcribe the audio content verbatim (summarise if too long).
2. Extract structured knowledge into these categories:
   - decisions: key decisions made or mentioned
   - tasks: pending tasks or action items
   - risks: risks or concerns mentioned
   - dependencies: dependencies or blockers
   - discussions: important discussion points
   - context: tacit/unwritten project knowledge

Return ONLY valid JSON:
{{
  "transcript_summary": "...",
  "duration_estimate": "...",
  "knowledge_items": [
    {{"category": "decision|task|risk|dependency|discussion|context",
      "content": "...",
      "owner": "...",
      "deadline": "...",
      "confidence": "high|medium|low"}}
  ],
  "missing_info": ["..."],
  "recommended_followups": ["..."]
}}"""

    model = genai.GenerativeModel('gemini-1.5-flash')
    with open(fpath, 'rb') as audio_f:
        audio_data = audio_f.read()

    response = model.generate_content([
        {'mime_type': mime, 'data': audio_data},
        prompt
    ])

    raw = response.text.strip()
    # Strip markdown code fences
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE)
    result = json.loads(raw)
    result['method'] = 'gemini_multimodal'
    result['success'] = True
    return result


def _transcribe_fallback(fpath):
    """Rule-based fallback when Gemini is unavailable."""
    return {
        'success': True,
        'method': 'fallback',
        'transcript_summary': (
            'Audio file received. Gemini API unavailable — automatic transcription could not be performed. '
            'Please review the file manually and enter knowledge items below.'
        ),
        'duration_estimate': 'Unknown',
        'knowledge_items': [],
        'missing_info': ['Full transcription requires Gemini API key'],
        'recommended_followups': ['Configure GEMINI_API_KEY in Settings to enable automatic transcription'],
    }


def _save_transcription_knowledge(project_id, result, original_filename):
    """Persist extracted knowledge items into ExtractedKnowledge table."""
    from app import db, ExtractedKnowledge
    items = result.get('knowledge_items', [])
    for item in items:
        ek = ExtractedKnowledge(
            project_id=project_id,
            document_id=None,
            category=item.get('category', 'discussion'),
            content=item.get('content', ''),
            details=json.dumps({
                'owner': item.get('owner', 'Unknown'),
                'deadline': item.get('deadline', 'Not specified'),
                'source_file': original_filename,
                'extraction_method': result.get('method', 'gemini_multimodal'),
            }),
            source_ref=f"Audio/Video: {original_filename}",
            confidence=item.get('confidence', 'medium'),
            status='pending_review',
            is_fallback=(result.get('method') == 'fallback'),
        )
        db.session.add(ek)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving transcription knowledge: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 2 — SEMANTIC SEARCH / RAG (ChromaDB)
# ═══════════════════════════════════════════════════════════════════════════════
_chroma_client = None
_chroma_collection = None


def _get_chroma():
    """Lazy-init ChromaDB persistent client."""
    global _chroma_client, _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection, None
    chromadb = _try_import('chromadb')
    if not chromadb:
        return None, "chromadb not installed (pip install chromadb)"
    try:
        db_path = os.path.join(os.getcwd(), 'chroma_db')
        os.makedirs(db_path, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=db_path)
        _chroma_collection = _chroma_client.get_or_create_collection(
            name="knowbridge_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        return _chroma_collection, None
    except Exception as e:
        return None, str(e)


def _embed_text(text):
    """Get embedding via Gemini or fallback to keyword hash."""
    genai, err = _get_gemini()
    if genai and not err:
        try:
            result = genai.embed_content(
                model='models/text-embedding-004',
                content=text,
                task_type='retrieval_document',
            )
            return result['embedding']
        except Exception as e:
            logger.warning(f"Gemini embedding failed: {e}")
    # Fallback: simple TF-style 128-dim hash embedding
    import hashlib, math
    vec = [0.0] * 128
    words = re.findall(r'\w+', text.lower())
    for w in words:
        idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % 128
        vec[idx] += 1.0
    norm = math.sqrt(sum(x*x for x in vec)) or 1
    return [x/norm for x in vec]


@imp.route('/semantic-search')
@login_required
def semantic_search_page():
    db, Project, *_ = _models()
    if current_user.role == 'admin':
        projects = Project.query.order_by(Project.name).all()
    else:
        from app import ProjectMember
        mems = ProjectMember.query.filter_by(user_id=current_user.id).all()
        pids = [m.project_id for m in mems]
        projects = Project.query.filter(Project.id.in_(pids)).order_by(Project.name).all()
    collection, err = _get_chroma()
    chroma_ok = collection is not None
    chroma_count = collection.count() if chroma_ok else 0
    return render_template('semantic_search.html', projects=projects,
                           chroma_ok=chroma_ok, chroma_count=chroma_count, chroma_err=err)


@imp.route('/api/semantic/index', methods=['POST'])
@login_required
def api_semantic_index():
    """Index all approved knowledge for a project into ChromaDB."""
    data = request.get_json() or {}
    project_id = data.get('project_id')

    collection, err = _get_chroma()
    if not collection:
        return jsonify({'error': err}), 500

    from app import ExtractedKnowledge, Document, Project
    q = ExtractedKnowledge.query.filter_by(project_id=project_id, status='approved') if project_id \
        else ExtractedKnowledge.query.filter_by(status='approved')

    items = q.all()
    if not items:
        return jsonify({'indexed': 0, 'message': 'No approved knowledge items found to index.'})

    indexed = 0
    for item in items:
        doc_name = ''
        if item.document_id:
            doc = Document.query.get(item.document_id)
            if doc:
                doc_name = doc.original_name or doc.filename

        text_to_embed = f"{item.category}: {item.content}"
        try:
            embedding = _embed_text(text_to_embed)
            vec_id = f"ki_{item.id}"
            collection.upsert(
                ids=[vec_id],
                embeddings=[embedding],
                documents=[item.content],
                metadatas=[{
                    'id': item.id,
                    'project_id': item.project_id or 0,
                    'category': item.category or '',
                    'source_doc': doc_name,
                    'source_ref': item.source_ref or '',
                    'confidence': item.confidence or 'medium',
                    'created_at': str(item.created_at),
                }],
            )
            indexed += 1
        except Exception as e:
            logger.error(f"Error indexing item {item.id}: {e}")

    return jsonify({'indexed': indexed, 'total': len(items),
                    'message': f'Successfully indexed {indexed} knowledge items.'})


@imp.route('/api/semantic/search', methods=['POST'])
@login_required
def api_semantic_search():
    """Semantic similarity search across indexed knowledge."""
    data = request.get_json() or {}
    query   = data.get('query', '').strip()
    project_id = data.get('project_id')   # None = search all projects
    n_results  = min(int(data.get('n_results', 8)), 20)

    if not query:
        return jsonify({'error': 'Query cannot be empty'}), 400

    collection, err = _get_chroma()
    if not collection:
        return jsonify({'error': err}), 500

    if collection.count() == 0:
        return jsonify({'results': [], 'message': 'Knowledge base is empty. Index some projects first.'})

    try:
        query_embedding = _embed_text(query)
        where_filter = {'project_id': project_id} if project_id else None
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=['documents', 'metadatas', 'distances'],
        )

        hits = []
        docs      = results.get('documents', [[]])[0]
        metas     = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            similarity = max(0, round((1 - dist) * 100, 1))
            hits.append({
                'content':    doc,
                'category':   meta.get('category', ''),
                'project_id': meta.get('project_id'),
                'source_doc': meta.get('source_doc', ''),
                'source_ref': meta.get('source_ref', ''),
                'confidence': meta.get('confidence', 'medium'),
                'similarity': similarity,
                'knowledge_id': meta.get('id'),
            })

        return jsonify({'results': hits, 'query': query, 'total': len(hits)})
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVEMENT 3 — ISSUE TRACKER & COMMUNICATION SYNC
# ═══════════════════════════════════════════════════════════════════════════════

# ── 3a: GitHub ────────────────────────────────────────────────────────────────
@imp.route('/api/integrations/github/push-task', methods=['POST'])
@login_required
def api_github_push_task():
    """Push a task as a GitHub Issue."""
    data = request.get_json() or {}
    task_id  = data.get('task_id')
    repo_str = data.get('repo') or _get_setting('GITHUB_REPO')
    token    = _get_setting('GITHUB_TOKEN')

    if not token:
        return jsonify({'error': 'GitHub token not configured. Go to Settings → Integrations.'}), 400
    if not repo_str:
        return jsonify({'error': 'GitHub repo (owner/repo) not configured.'}), 400

    from app import Task
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    Github = _try_import('github')
    if not Github:
        return jsonify({'error': 'PyGithub not installed'}), 500

    try:
        from github import Github as GH
        g = GH(token)
        repo = g.get_repo(repo_str)

        body = (
            f"**KnowBridge AI — Handover Task**\n\n"
            f"**Description:** {task.description or 'No description'}\n\n"
            f"**Assignee:** {task.assignee or 'Unassigned'}\n"
            f"**Priority:** {task.priority}\n"
            f"**Deadline:** {task.deadline or 'Not set'}\n"
            f"**Status:** {task.status}\n\n"
            f"*Pushed from KnowBridge AI — Project #{task.project_id}*"
        )

        # Create or find label
        try:
            repo.create_label(name='knowbridge-handover', color='A64B37')
        except Exception:
            pass

        issue = repo.create_issue(
            title=f"[Handover] {task.title}",
            body=body,
            labels=['knowbridge-handover'],
        )

        # Save issue URL to task description
        from app import db, log_action
        task.description = (task.description or '') + f"\n\n[GitHub Issue #{issue.number}]({issue.html_url})"
        db.session.commit()
        log_action('github_push_task', 'task', task.id, f"Issue #{issue.number}: {issue.html_url}")

        return jsonify({'success': True, 'issue_url': issue.html_url,
                        'issue_number': issue.number})
    except Exception as e:
        logger.error(f"GitHub push error: {e}")
        return jsonify({'error': str(e)}), 500


@imp.route('/api/integrations/github/push-risk', methods=['POST'])
@login_required
def api_github_push_risk():
    """Push a risk as a GitHub Issue."""
    data = request.get_json() or {}
    risk_id  = data.get('risk_id')
    repo_str = data.get('repo') or _get_setting('GITHUB_REPO')
    token    = _get_setting('GITHUB_TOKEN')

    if not token or not repo_str:
        return jsonify({'error': 'GitHub not configured in Settings.'}), 400

    from app import Risk
    risk = Risk.query.get(risk_id)
    if not risk:
        return jsonify({'error': 'Risk not found'}), 404

    try:
        from github import Github as GH
        g = GH(token)
        repo = g.get_repo(repo_str)
        body = (
            f"**KnowBridge AI — Project Risk**\n\n"
            f"**Level:** {risk.level.upper()}\n"
            f"**Description:** {risk.description or 'No description'}\n"
            f"**Owner:** {risk.risk_owner or 'Unassigned'}\n"
            f"**Status:** {risk.status}\n\n"
            f"*Pushed from KnowBridge AI — Project #{risk.project_id}*"
        )
        try:
            repo.create_label(name='knowbridge-risk', color='FF6B35')
        except Exception:
            pass
        issue = repo.create_issue(
            title=f"[Risk/{risk.level.upper()}] {risk.title}",
            body=body,
            labels=['knowbridge-risk'],
        )
        from app import db
        db.session.commit()
        return jsonify({'success': True, 'issue_url': issue.html_url, 'issue_number': issue.number})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 3b: Slack ─────────────────────────────────────────────────────────────────
@imp.route('/api/integrations/slack/notify', methods=['POST'])
@login_required
def api_slack_notify():
    """Send a handover notification to Slack."""
    data        = request.get_json() or {}
    message     = data.get('message', '')
    channel     = data.get('channel') or _get_setting('SLACK_CHANNEL', '#handovers')
    token       = _get_setting('SLACK_BOT_TOKEN')
    report_id   = data.get('report_id')

    if not token:
        return jsonify({'error': 'Slack Bot Token not configured. Go to Settings → Integrations.'}), 400

    if not message and report_id:
        from app import HandoverReport, Project
        report = HandoverReport.query.get(report_id)
        if report:
            project = Project.query.get(report.project_id)
            message = (
                f":handshake: *KnowBridge AI — Handover Report Ready*\n"
                f"*Project:* {project.name if project else 'Unknown'}\n"
                f"*Report:* {report.title or 'Handover Report'}\n"
                f"*Status:* {report.status.upper()}\n"
                f"*Generated:* {report.generated_at.strftime('%Y-%m-%d %H:%M') if report.generated_at else 'N/A'}\n"
                f"Please review and acknowledge this handover in KnowBridge AI."
            )

    if not message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        slack_sdk = _try_import('slack_sdk')
        if not slack_sdk:
            return jsonify({'error': 'slack-sdk not installed'}), 500

        from slack_sdk import WebClient
        client = WebClient(token=token)
        resp = client.chat_postMessage(channel=channel, text=message,
                                       unfurl_links=False)
        from app import log_action
        log_action('slack_notification_sent', 'report', report_id,
                   f"Channel: {channel}")
        return jsonify({'success': True, 'ts': resp.get('ts'),
                        'channel': resp.get('channel')})
    except Exception as e:
        logger.error(f"Slack notify error: {e}")
        return jsonify({'error': str(e)}), 500


@imp.route('/api/integrations/slack/notify-task', methods=['POST'])
@login_required
def api_slack_notify_task():
    """Send a task notification to Slack."""
    data    = request.get_json() or {}
    task_id = data.get('task_id')
    channel = data.get('channel') or _get_setting('SLACK_CHANNEL', '#handovers')
    token   = _get_setting('SLACK_BOT_TOKEN')

    if not token:
        return jsonify({'error': 'Slack Bot Token not configured.'}), 400

    from app import Task
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    priority_emoji = {'high': ':red_circle:', 'medium': ':yellow_circle:', 'low': ':green_circle:'}
    emoji = priority_emoji.get(task.priority, ':white_circle:')

    message = (
        f"{emoji} *KnowBridge AI — Pending Handover Task*\n"
        f"*Task:* {task.title}\n"
        f"*Assignee:* {task.assignee or 'Unassigned'}\n"
        f"*Priority:* {task.priority.upper()}\n"
        f"*Deadline:* {task.deadline or 'Not set'}\n"
        f"*Status:* {task.status.replace('_', ' ').title()}\n"
        f"_Please complete or acknowledge this task in KnowBridge AI._"
    )

    try:
        from slack_sdk import WebClient
        client = WebClient(token=token)
        resp = client.chat_postMessage(channel=channel, text=message, unfurl_links=False)
        return jsonify({'success': True, 'ts': resp.get('ts')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 3c: Jira ──────────────────────────────────────────────────────────────────
@imp.route('/api/integrations/jira/push-task', methods=['POST'])
@login_required
def api_jira_push_task():
    """Create a Jira issue from a handover task."""
    data = request.get_json() or {}
    task_id = data.get('task_id')

    jira_url   = _get_setting('JIRA_URL')
    jira_email = _get_setting('JIRA_EMAIL')
    jira_token = _get_setting('JIRA_API_TOKEN')
    jira_proj  = data.get('project_key') or _get_setting('JIRA_PROJECT_KEY')

    if not all([jira_url, jira_email, jira_token, jira_proj]):
        return jsonify({'error': 'Jira not fully configured. Go to Settings → Integrations.'}), 400

    from app import Task
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    jira_lib = _try_import('jira')
    if not jira_lib:
        return jsonify({'error': 'jira library not installed'}), 500

    priority_map = {'high': 'High', 'medium': 'Medium', 'low': 'Low'}

    try:
        from jira import JIRA
        jira = JIRA(server=jira_url, basic_auth=(jira_email, jira_token))

        issue_dict = {
            'project':   {'key': jira_proj},
            'summary':   f"[Handover] {task.title}",
            'description': (
                f"*KnowBridge AI Handover Task*\n\n"
                f"{task.description or 'No description provided.'}\n\n"
                f"||Field||Value||\n"
                f"|Assignee|{task.assignee or 'Unassigned'}|\n"
                f"|Priority|{task.priority}|\n"
                f"|Deadline|{task.deadline or 'Not set'}|\n"
                f"|Status|{task.status}|\n"
                f"|Project ID|{task.project_id}|\n"
            ),
            'issuetype': {'name': 'Task'},
            'priority':  {'name': priority_map.get(task.priority, 'Medium')},
        }

        new_issue = jira.create_issue(fields=issue_dict)

        from app import db, log_action
        task.description = (task.description or '') + f"\n\n[Jira: {new_issue.key}]({jira_url}/browse/{new_issue.key})"
        db.session.commit()
        log_action('jira_push_task', 'task', task.id, f"Jira issue: {new_issue.key}")

        return jsonify({'success': True, 'issue_key': new_issue.key,
                        'issue_url': f"{jira_url}/browse/{new_issue.key}"})
    except Exception as e:
        logger.error(f"Jira push error: {e}")
        return jsonify({'error': str(e)}), 500


# ── Integration test endpoints ─────────────────────────────────────────────────
@imp.route('/api/integrations/test/github', methods=['POST'])
@login_required
def api_test_github():
    token = _get_setting('GITHUB_TOKEN')
    if not token:
        return jsonify({'ok': False, 'error': 'Token not set'})
    try:
        from github import Github as GH
        g = GH(token)
        user = g.get_user()
        return jsonify({'ok': True, 'user': user.login, 'name': user.name})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@imp.route('/api/integrations/test/slack', methods=['POST'])
@login_required
def api_test_slack():
    token = _get_setting('SLACK_BOT_TOKEN')
    if not token:
        return jsonify({'ok': False, 'error': 'Token not set'})
    try:
        from slack_sdk import WebClient
        client = WebClient(token=token)
        resp = client.auth_test()
        return jsonify({'ok': True, 'user': resp.get('user'),
                        'team': resp.get('team')})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@imp.route('/api/integrations/test/jira', methods=['POST'])
@login_required
def api_test_jira():
    jira_url   = _get_setting('JIRA_URL')
    jira_email = _get_setting('JIRA_EMAIL')
    jira_token = _get_setting('JIRA_API_TOKEN')
    if not all([jira_url, jira_email, jira_token]):
        return jsonify({'ok': False, 'error': 'Jira credentials incomplete'})
    try:
        from jira import JIRA
        jira = JIRA(server=jira_url, basic_auth=(jira_email, jira_token))
        me = jira.myself()
        return jsonify({'ok': True, 'user': me.get('displayName'),
                        'email': me.get('emailAddress')})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


# ── Integration settings save ─────────────────────────────────────────────────
@imp.route('/api/integrations/save-settings', methods=['POST'])
@login_required
def api_save_integration_settings():
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin only'}), 403

    data = request.get_json() or {}
    from app import AppSetting, db

    keys_to_save = [
        'GITHUB_TOKEN', 'GITHUB_REPO',
        'SLACK_BOT_TOKEN', 'SLACK_CHANNEL',
        'JIRA_URL', 'JIRA_EMAIL', 'JIRA_API_TOKEN', 'JIRA_PROJECT_KEY',
    ]
    saved = []
    for key in keys_to_save:
        if key in data:
            val = data[key].strip()
            s = AppSetting.query.filter_by(key=key).first()
            if not s:
                s = AppSetting(key=key, value=val)
                db.session.add(s)
            else:
                s.value = val
            if val:
                os.environ[key] = val
            saved.append(key)

    try:
        db.session.commit()
        return jsonify({'success': True, 'saved': saved})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@imp.route('/api/integrations/get-settings', methods=['GET'])
@login_required
def api_get_integration_settings():
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin only'}), 403

    keys = ['GITHUB_REPO', 'SLACK_CHANNEL', 'JIRA_URL', 'JIRA_EMAIL', 'JIRA_PROJECT_KEY']
    # Note: tokens are never returned to frontend for security
    result = {}
    for k in keys:
        result[k] = _get_setting(k, '')
    return jsonify(result)


# ── Integration dashboard page ─────────────────────────────────────────────────
@imp.route('/integrations')
@login_required
def integrations_page():
    return render_template('integrations.html')
