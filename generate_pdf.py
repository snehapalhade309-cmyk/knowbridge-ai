"""
KnowBridge AI - Final PDF with original title + thank-you pages preserved as images
Middle pages: clean updated content matching website features
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image as RLImage
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# ── Colours ────────────────────────────────────────────────────────────────
C_TERRA  = colors.HexColor('#A64B37')
C_DGREEN = colors.HexColor('#263F3B')
C_SAGE   = colors.HexColor('#DCE9E4')
C_IVORY  = colors.HexColor('#F8F6F0')
C_BORDER = colors.HexColor('#E7E2D8')
C_GREY   = colors.HexColor('#686868')
C_WHITE  = colors.white
C_BLACK  = colors.HexColor('#1C1C1C')
C_LTERRA = colors.HexColor('#FAF0ED')
C_LSAGE  = colors.HexColor('#EEF4F2')

W, H = A4   # 595 x 841

TITLE_IMG  = r"c:\Users\HP\Downloads\KKK\crop_title.jpg"
TY_IMG     = r"c:\Users\HP\Downloads\KKK\crop_thankyou.jpg"
OUTPUT     = r"c:\Users\HP\Downloads\KKK\KnowBridge_AI_Updated.pdf"

# ── Styles ─────────────────────────────────────────────────────────────────
def S(name, **kw):
    return ParagraphStyle(name, **kw)

WBOLD  = S('wb',  fontName='Helvetica-Bold', fontSize=9.5, textColor=C_WHITE)
TBOLD  = S('tb',  fontName='Helvetica-Bold', fontSize=9.5, textColor=C_BLACK)
TNORM  = S('tn',  fontName='Helvetica',      fontSize=9.5, textColor=C_BLACK, leading=15)
TNORM_W= S('tnw', fontName='Helvetica',      fontSize=9.5, textColor=C_WHITE, leading=15)
TSML   = S('ts',  fontName='Helvetica',      fontSize=9,   textColor=C_BLACK, leading=14)
TSML_W = S('tsw', fontName='Helvetica',      fontSize=9,   textColor=C_WHITE, leading=14)
TBSML  = S('tbs', fontName='Helvetica-Bold', fontSize=9,   textColor=C_BLACK)
TBSML_W= S('tbsw',fontName='Helvetica-Bold', fontSize=9,   textColor=C_WHITE)
BODY   = S('bd',  fontName='Helvetica',      fontSize=9.5, textColor=C_BLACK, spaceAfter=4, leading=15, alignment=TA_JUSTIFY)
BULLET = S('bl',  fontName='Helvetica',      fontSize=9.5, textColor=C_BLACK, leftIndent=12, spaceAfter=3, leading=14)
SUB_H  = S('sh',  fontName='Helvetica-Bold', fontSize=11,  textColor=C_DGREEN, spaceBefore=8, spaceAfter=4)
CTR    = S('ctr', fontName='Helvetica',      fontSize=9,   textColor=C_BLACK,  alignment=TA_CENTER)
CTRB   = S('ctrb',fontName='Helvetica-Bold', fontSize=9,   textColor=C_BLACK,  alignment=TA_CENTER)

SP4  = Spacer(1, 4)
SP8  = Spacer(1, 8)
SP12 = Spacer(1, 12)
SP20 = Spacer(1, 20)
HR   = HRFlowable(width='100%', thickness=0.7, color=C_BORDER, spaceAfter=6, spaceBefore=4)

PAGE_W = W - 2.4*cm   # usable width


# ── Helper: banner row ─────────────────────────────────────────────────────
def banner(text, bg=C_DGREEN, fs=14):
    p = Paragraph(text, ParagraphStyle(
        'bn', fontName='Helvetica-Bold', fontSize=fs,
        textColor=C_WHITE, alignment=TA_CENTER))
    t = Table([[p]], colWidths=[PAGE_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,0), bg),
        ('TOPPADDING',    (0,0),(0,0), 11),
        ('BOTTOMPADDING', (0,0),(0,0), 11),
        ('LEFTPADDING',   (0,0),(0,0), 10),
        ('RIGHTPADDING',  (0,0),(0,0), 10),
    ]))
    return t


# ── Helper: label table (dark label | light content) ─────────────────────
def label_table(rows_data, lw=0.28):
    rw = 1 - lw
    rows = [[Paragraph(l, TBSML_W), Paragraph(r, TSML)]
            for l, r in rows_data]
    t = Table(rows, colWidths=[PAGE_W * lw, PAGE_W * rw])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,-1), C_DGREEN),
        ('BACKGROUND',    (1,0),(1,-1), C_SAGE),
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LINEBELOW',     (0,0),(-1,-2), 0.3, C_BORDER),
    ]))
    return t


# ── Helper: step table ────────────────────────────────────────────────────
def step_table(steps, lw=0.26):
    rw = 1 - lw
    rows = [[Paragraph(s, TBSML_W), Paragraph(d, TSML)]
            for s, d in steps]
    t = Table(rows, colWidths=[PAGE_W * lw, PAGE_W * rw])
    s_cmds = [
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ('TOPPADDING',    (0,0),(-1,-1), 7),
        ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ('LINEBELOW',     (0,0),(-1,-2), 0.3, C_BORDER),
    ]
    for i in range(len(rows)):
        bg  = C_DGREEN if i % 2 == 0 else colors.HexColor('#1E332F')
        rbg = C_SAGE   if i % 2 == 0 else C_LSAGE
        s_cmds += [
            ('BACKGROUND', (0,i),(0,i), bg),
            ('BACKGROUND', (1,i),(1,i), rbg),
        ]
    t.setStyle(TableStyle(s_cmds))
    return t


# ── Helper: feature grid ─────────────────────────────────────────────────
def feat_grid(items, cols=3):
    rows, row = [], []
    for item in items:
        row.append(Paragraph(f'  {item}', TBSML))
        if len(row) == cols:
            rows.append(row); row = []
    if row:
        while len(row) < cols:
            row.append(Paragraph('', TSML))
        rows.append(row)
    cw = [PAGE_W / cols] * cols
    t = Table(rows, colWidths=cw)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_SAGE),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0),(-1,-1), 9),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('GRID',          (0,0),(-1,-1), 0.4, C_BORDER),
    ]))
    return t


# ── Helper: two-col comparison ───────────────────────────────────────────
def two_col_cmp(left_title, right_title, left_items, right_items):
    hdr = Table(
        [[Paragraph(left_title, WBOLD), Paragraph(right_title, WBOLD)]],
        colWidths=[PAGE_W * 0.5, PAGE_W * 0.5]
    )
    hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,0), C_TERRA),
        ('BACKGROUND',    (1,0),(1,0), C_DGREEN),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
    ]))
    body_rows = []
    for l, r in zip(left_items, right_items):
        body_rows.append([Paragraph(f'• {l}', TSML), Paragraph(f'• {r}', TSML)])
    body = Table(body_rows, colWidths=[PAGE_W * 0.5, PAGE_W * 0.5])
    body.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,-1), C_LTERRA),
        ('BACKGROUND',    (1,0),(1,-1), C_SAGE),
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('GRID',          (0,0),(-1,-1), 0.4, C_BORDER),
    ]))
    return [hdr, body]


# ── Helper: full-width image ─────────────────────────────────────────────
def full_img(path, max_h=None):
    img = RLImage(path, width=PAGE_W, height=None)   # auto height
    # maintain aspect ratio
    from PIL import Image as PILImage
    pil = PILImage.open(path)
    pw, ph = pil.size
    aspect = ph / pw
    img_h = PAGE_W * aspect
    if max_h and img_h > max_h:
        img_h = max_h
        img_w = max_h / aspect
        img = RLImage(path, width=img_w, height=img_h)
    else:
        img = RLImage(path, width=PAGE_W, height=img_h)
    return img


# ══════════════════════════════════════════════════════════════════════════
def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=1.2*cm, rightMargin=1.2*cm,
        topMargin=1.2*cm, bottomMargin=1.2*cm,
    )
    story = []

    # ═══════════════════════════════════════════════
    # PAGE 1 — TITLE (original image preserved)
    # ═══════════════════════════════════════════════
    story.append(full_img(TITLE_IMG, max_h=H - 2.4*cm))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════
    # PAGE 2 — THE HIDDEN PROBLEM (updated)
    # ═══════════════════════════════════════════════
    story += [
        banner('THE HIDDEN PROBLEM OF KNOWLEDGE LOSS', C_DGREEN),
        SP8,
        Paragraph('• Important project information is scattered across documents, meetings, messages and task-boards.', BULLET),
        Paragraph('• When a team member leaves, their experience and decision-making context may leave with them.', BULLET),
        Paragraph('• Pending tasks and responsibilities become difficult to track for incoming members.', BULLET),
        Paragraph('• New members spend time understanding old decisions; important dependencies can be missed.', BULLET),
        Paragraph('• Manual handovers are inconsistent, incomplete, and impossible to audit.', BULLET),
        SP12,
    ]
    chain = Table([[
        Paragraph('Outgoing\nMember', CTR),
        Paragraph('→', CTR),
        Paragraph('Scattered\nInformation', CTR),
        Paragraph('→', CTR),
        Paragraph('Knowledge\nGaps', CTR),
        Paragraph('→', CTR),
        Paragraph('Unclear\nResponsibilities', CTR),
        Paragraph('→', CTR),
        Paragraph('Delayed\nWork', CTR),
    ]], colWidths=[PAGE_W*p for p in [0.16,0.04,0.16,0.04,0.16,0.04,0.18,0.04,0.18]])
    chain.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,0), colors.HexColor('#E8D5D0')),
        ('BACKGROUND', (2,0),(2,0), colors.HexColor('#F5E8D0')),
        ('BACKGROUND', (4,0),(4,0), colors.HexColor('#E8E8D0')),
        ('BACKGROUND', (6,0),(6,0), colors.HexColor('#D0E0E8')),
        ('BACKGROUND', (8,0),(8,0), colors.HexColor('#E0D0E8')),
        ('FONTNAME',   (0,0),(-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0),(-1,-1), 8),
        ('ALIGN',      (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 10),
        ('BOTTOMPADDING',(0,0),(-1,-1), 10),
    ]))
    story += [chain, PageBreak()]

    # ═══════════════════════════════════════════════
    # PAGE 3 — INTRODUCING KNOWBRIDGE AI
    # ═══════════════════════════════════════════════
    story += [
        banner('INTRODUCING KNOWBRIDGE AI', C_TERRA),
        SP8,
    ]
    for n, item in enumerate([
        'Collect authorised project documents, meeting notes, and communication sources.',
        'Analyse documents and project activities using AI and rule-based NLP.',
        'Identify decisions, responsibilities and pending tasks automatically.',
        'Highlight risks, dependencies and conflicting information.',
        'Link important information to supporting evidence with source references.',
        'Identify missing or conflicting information and flag it clearly.',
        'Generate an organised, evidence-linked handover report (PDF and CSV).',
        'Allow mandatory human review and approval before finalisation.',
        'Enable recipient acknowledgement tracking with audit timestamps.',
    ], 1):
        story.append(Paragraph(f'{n}.  {item}', BULLET))
    story += [SP12]
    story += two_col_cmp(
        'WITHOUT KnowBridge AI', 'WITH KnowBridge AI',
        ['Scattered project information', 'Unclear decision history', 'Manual handover efforts', 'No audit trail', 'Knowledge walks away with people'],
        ['Organised evidence-linked report', 'Linked decisions, risks and tasks', 'Mandatory human review and approval', 'Full audit log and version history', 'Knowledge stays permanently'],
    )
    story += [PageBreak()]

    # ═══════════════════════════════════════════════
    # PAGE 4 — HOW THE SYSTEM IS DESIGNED
    # ═══════════════════════════════════════════════
    story += [
        banner('HOW THE SYSTEM IS DESIGNED', C_DGREEN),
        SP8,
        label_table([
            ('DATA INPUT',         'Project Documents  ·  Meeting Notes  ·  Task Boards  ·  Code Repositories  ·  Authorised Communication Sources'),
            ('DATA PROCESSING',    'Permission Validation  ·  Data Extraction  ·  Text Pre-processing  ·  Data Cleaning  ·  Information Structuring'),
            ('AI INTELLIGENCE',    'Google Gemini API  ·  NLP Text Summarisation  ·  Decision Extraction  ·  Task & Ownership Detection  ·  Risk & Dependency Identification  ·  Rule-Based Fallback Engine'),
            ('TRUST & VERIFICATION','Evidence Linking  ·  Missing Info Detection  ·  Contradiction Detection  ·  Uncertainty Detection  ·  Role-Based Access  ·  Mandatory Human Approval'),
            ('OUTPUT',             'Handover Report (PDF / CSV)  ·  Decision Timeline  ·  Pending Tasks  ·  Risk Summary  ·  Next Action Plan  ·  Role-Specific Views  ·  Acknowledgement Tracking'),
        ], lw=0.27),
        PageBreak(),
    ]

    # ═══════════════════════════════════════════════
    # PAGE 5 — HOW KNOWBRIDGE AI WORKS
    # ═══════════════════════════════════════════════
    story += [
        banner('HOW KNOWBRIDGE AI WORKS', C_TERRA),
        SP8,
        step_table([
            ('1. START',           'User logs in with their role — Admin, Project Manager, or Team Member.'),
            ('2. UPLOAD',          'Upload authorised documents: PDF, DOCX, TXT, or CSV. Drag-and-drop is supported.'),
            ('3. EXTRACT',         'System extracts text using PyMuPDF / pypdf / python-docx libraries automatically.'),
            ('4. AI ANALYSIS',     'Google Gemini API analyses text — extracts decisions, tasks, risks, owners, deadlines and dependencies.'),
            ('5. FALLBACK ENGINE', 'If Gemini API is unavailable, the built-in rule-based NLP engine activates automatically with zero downtime.'),
            ('6. REVIEW QUEUE',    'All AI-extracted items enter a Human Review queue — not published directly to any report.'),
            ('7. HUMAN APPROVAL',  'Reviewer inspects, edits, approves or rejects each item with reason and timestamp recorded.'),
            ('8. REPORT',          'Approved items compile into a professional Handover Report. Download as PDF or export as CSV.'),
            ('9. SECURE SHARING',  'Report shared with incoming members via role-based access control permissions.'),
            ('10. ACKNOWLEDGEMENT','Recipient reads and formally acknowledges the handover. Timestamp recorded in audit log.'),
            ('END',                'Knowledge is permanently preserved and searchable within the platform.'),
        ], lw=0.26),
        PageBreak(),
    ]

    # ═══════════════════════════════════════════════
    # PAGE 6 — WHAT MAKES IT USEFUL
    # ═══════════════════════════════════════════════
    story += [
        banner('WHAT MAKES KNOWBRIDGE AI USEFUL?', C_DGREEN),
        SP8,
        feat_grid([
            'Smart AI Knowledge Extraction',
            'Google Gemini API Integration',
            'Rule-Based NLP Fallback Engine',
            'Decision Tracking',
            'Pending Task Identification',
            'Risk & Dependency Detection',
            'Evidence-Linked Summaries',
            'Human Review & Approval Gate',
            'Role-Based Access Control',
            'Handover Report (PDF & CSV)',
            'Acknowledgement Tracking',
            'Project Timeline View',
            'Version History',
            'Audit Logs',
            'Multi-Format Document Upload',
            'Interactive Analytics Dashboard',
            'Chart.js Visual Analytics',
            'Drag-and-Drop File Upload',
            'Mobile-Responsive Design',
            'REST API Architecture',
            '17 Functional Pages',
            'CSRF & Session Security',
        ], cols=3),
        PageBreak(),
    ]

    # ═══════════════════════════════════════════════
    # PAGE 7 — TECHNOLOGIES
    # ═══════════════════════════════════════════════
    story += [
        banner('TECHNOLOGIES BEHIND OUR PROJECT', C_TERRA),
        SP8,
        label_table([
            ('Frontend',          'HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Chart.js, Lucide Icons, Responsive Layouts'),
            ('Backend',           'Python 3, Flask, Flask-Login, Flask-WTF (CSRF), Flask REST API'),
            ('Database',          'SQLite for local development  ·  SQLAlchemy ORM  ·  Designed for PostgreSQL migration'),
            ('AI and NLP',        'Google Gemini API (gemini-1.5-flash)  ·  Structured JSON schema output  ·  Rule-based NLP fallback engine'),
            ('Document Parsing',  'PyMuPDF / pypdf (PDF)  ·  python-docx (Word)  ·  Python CSV and JSON  ·  Plain TXT'),
            ('Report Generation', 'ReportLab (PDF download)  ·  CSV export  ·  Print-ready online report view'),
            ('Security',          'CSRF protection  ·  Session-based authentication  ·  Backend-enforced RBAC  ·  Permission checks on every API route'),
            ('Deployment',        'Render.com  ·  Gunicorn WSGI server  ·  Environment-variable secrets (.env)'),
            ('Visualisation',     'Dashboard with Chart.js  ·  Project timeline  ·  Risk distribution charts  ·  Task status doughnut chart'),
        ], lw=0.26),
        PageBreak(),
    ]

    # ═══════════════════════════════════════════════
    # PAGE 8 — ROLE-BASED ACCESS CONTROL
    # ═══════════════════════════════════════════════
    story += [banner('ROLE-BASED ACCESS CONTROL', C_DGREEN), SP8]

    role_rows = [
        [Paragraph('ROLE', TBSML_W),       Paragraph('PERMISSIONS', TBSML_W)],
        [Paragraph('ADMIN', TBSML_W),
         Paragraph('Manage all users and roles  ·  Create / delete projects  ·  View full audit logs  ·  Approve / reject handovers  ·  Manage system settings', TSML)],
        [Paragraph('PROJECT\nMANAGER', TBSML_W),
         Paragraph('Manage assigned projects  ·  Upload documents  ·  Trigger AI analysis  ·  Review and approve assigned handovers  ·  Assign responsibilities', TSML)],
        [Paragraph('TEAM\nMEMBER', TBSML_W),
         Paragraph('View authorised projects  ·  Upload permitted documents  ·  View assigned tasks  ·  Acknowledge handovers  ·  Update permitted task statuses', TSML)],
    ]
    rt = Table(role_rows, colWidths=[PAGE_W*0.22, PAGE_W*0.78])
    rt.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  C_DGREEN),
        ('BACKGROUND',    (0,1),(0,1),   C_TERRA),
        ('BACKGROUND',    (0,2),(0,2),   colors.HexColor('#5B7A74')),
        ('BACKGROUND',    (0,3),(0,3),   colors.HexColor('#7A9E99')),
        ('BACKGROUND',    (1,1),(1,1),   C_LTERRA),
        ('BACKGROUND',    (1,2),(1,2),   C_SAGE),
        ('BACKGROUND',    (1,3),(1,3),   C_LSAGE),
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('TOPPADDING',    (0,0),(-1,-1), 9),
        ('BOTTOMPADDING', (0,0),(-1,-1), 9),
        ('GRID',          (0,0),(-1,-1), 0.5, C_BORDER),
    ]))
    story += [rt, SP8]

    # Security note box
    note = Table([[Paragraph(
        'All permissions are enforced at the backend API level — hiding UI buttons is never the only security layer.',
        ParagraphStyle('nt', fontName='Helvetica-Oblique', fontSize=9, textColor=C_DGREEN)
    )]], colWidths=[PAGE_W])
    note.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,0), colors.HexColor('#F5F0EB')),
        ('BOX',           (0,0),(0,0), 0.5, C_BORDER),
        ('LEFTPADDING',   (0,0),(0,0), 12),
        ('TOPPADDING',    (0,0),(0,0), 7),
        ('BOTTOMPADDING', (0,0),(0,0), 7),
    ]))
    story += [note, PageBreak()]

    # ═══════════════════════════════════════════════
    # PAGE 9 — DASHBOARD & ANALYTICS
    # ═══════════════════════════════════════════════
    story += [
        banner('DASHBOARD AND APPLICATION FEATURES', C_TERRA),
        SP8,
        Paragraph('Interactive Analytics Dashboard', SUB_H),
        Paragraph('All statistics are queried live from the database — no hardcoded numbers anywhere.', BODY),
        SP4,
    ]
    dash_rows = [
        [Paragraph('METRIC', TBSML_W),              Paragraph('DESCRIPTION', TBSML_W)],
        [Paragraph('Total Projects', TBSML),         Paragraph('Count of all active projects in the workspace', TSML)],
        [Paragraph('Total Documents', TBSML),        Paragraph('All uploaded and processed documents', TSML)],
        [Paragraph('Extracted Decisions', TBSML),    Paragraph('AI-identified key project decisions', TSML)],
        [Paragraph('Pending Tasks', TBSML),          Paragraph('Open tasks awaiting completion or assignment', TSML)],
        [Paragraph('Identified Risks', TBSML),       Paragraph('Low / Medium / High risks flagged by AI and human reviewers', TSML)],
        [Paragraph('Completed Handovers', TBSML),    Paragraph('Successfully acknowledged handover reports', TSML)],
        [Paragraph('Awaiting Approvals', TBSML),     Paragraph('AI items pending human review and approval', TSML)],
        [Paragraph('Acknowledgement Status', TBSML), Paragraph('Count of pending vs confirmed acknowledgements', TSML)],
    ]
    dm = Table(dash_rows, colWidths=[PAGE_W*0.35, PAGE_W*0.65])
    dm.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  C_DGREEN),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [C_SAGE, C_IVORY]),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('TOPPADDING',    (0,0),(-1,-1), 7),
        ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ('GRID',          (0,0),(-1,-1), 0.3, C_BORDER),
    ]))
    story += [dm, SP8,
        Paragraph('Chart.js Visualisations Included', SUB_H),
        Paragraph('• Project progress bar chart (per-project completion percentage)', BULLET),
        Paragraph('• Pending vs Completed tasks — doughnut chart', BULLET),
        Paragraph('• Risk distribution by severity (Low / Medium / High) — pie chart', BULLET),
        Paragraph('• Handover activity timeline chart', BULLET),
        Paragraph('• Decision status overview (Pending / Approved / Rejected)', BULLET),
        PageBreak(),
    ]

    # ═══════════════════════════════════════════════
    # PAGE 10 — RELIABLE KNOWLEDGE HANDOVER
    # ═══════════════════════════════════════════════
    story += [
        banner('RELIABLE KNOWLEDGE HANDOVER', C_DGREEN),
        SP8,
        Paragraph('• Authorised source access — only permitted documents are analysed.', BULLET),
        Paragraph('• Role-based permissions — each user sees only what they are allowed to see.', BULLET),
        Paragraph('• Confidential information protection — uploads are never publicly accessible.', BULLET),
        Paragraph('• Evidence-linked information — every extracted item links back to its source document.', BULLET),
        Paragraph('• Missing and conflicting information alerts — flagged clearly, never silently ignored.', BULLET),
        Paragraph('• Human verification before approval — no AI output reaches a report without human sign-off.', BULLET),
        Paragraph('• Controlled information sharing — role-based report access and acknowledgement tracking.', BULLET),
        SP12,
    ]
    badges = Table([[
        Paragraph('Authorised Access', CTRB),
        Paragraph('Data Processing', CTRB),
        Paragraph('Permission Check', CTRB),
        Paragraph('Evidence Validation', CTRB),
        Paragraph('Human Review', CTRB),
        Paragraph('Role-Based Sharing', CTRB),
    ]], colWidths=[PAGE_W/6]*6)
    badges.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_SAGE),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('TOPPADDING',    (0,0),(-1,-1), 9),
        ('BOTTOMPADDING', (0,0),(-1,-1), 9),
        ('GRID',          (0,0),(-1,-1), 0.5, C_BORDER),
    ]))
    story += [badges, PageBreak()]

    # ═══════════════════════════════════════════════
    # PAGE 11 — WHERE CAN IT BE USED
    # ═══════════════════════════════════════════════
    story += [
        banner('WHERE CAN KNOWBRIDGE AI BE USED?', C_TERRA),
        SP8,
        label_table([
            ('Corporate IT\n& Software Teams',  'Employee exit knowledge capture; onboarding acceleration for new developers.'),
            ('College\nProject Teams',          'Smooth project handovers across academic batches or semesters.'),
            ('Research\nInstitutions',          'Preserve methodology, data decisions and open questions across researcher transitions.'),
            ('Volunteer\nOrganisations',        'Maintain operational continuity when volunteers rotate or leave.'),
            ('Government &\nPublic Sector',     'Formal documented handovers during departmental transitions with audit compliance.'),
            ('Startups\nand SMEs',              'Prevent founder-dependency and single-point-of-failure knowledge risks.'),
        ], lw=0.28),
        SP12,
    ]
    story += two_col_cmp(
        'WITHOUT KnowBridge AI', 'WITH KnowBridge AI',
        ['Scattered information', 'Manual searching and reading', 'Unclear responsibilities', 'Repeated explanations', 'No audit trail'],
        ['Organised evidence-linked report', 'Instant AI-extracted summaries', 'Clear ownership and timelines', 'Better project continuity', 'Full version history and audit log'],
    )
    story += [PageBreak()]

    # ═══════════════════════════════════════════════
    # PAGE 12 — REST API
    # ═══════════════════════════════════════════════
    story += [
        banner('REST API ARCHITECTURE', C_DGREEN),
        SP8,
        Paragraph('KnowBridge AI exposes a full Flask REST API with JSON responses, used by both the web frontend and external integrations.', BODY),
        SP8,
        label_table([
            ('Authentication',   'POST /api/auth/register  ·  POST /api/auth/login  ·  POST /api/auth/logout'),
            ('Projects',         'GET/POST /api/projects  ·  GET/PUT/DELETE /api/projects/<id>'),
            ('Documents',        'POST /api/documents/upload  ·  GET /api/documents  ·  DELETE /api/documents/<id>'),
            ('AI Processing',    'POST /api/ai/analyze  ·  POST /api/ai/summarize  ·  POST /api/ai/extract-decisions  ·  POST /api/ai/detect-risks'),
            ('Tasks',            'GET/POST /api/tasks  ·  PUT /api/tasks/<id>'),
            ('Reviews',          'GET /api/reviews  ·  POST /api/reviews/<id>/approve  ·  POST /api/reviews/<id>/reject'),
            ('Reports',          'GET/POST /api/reports  ·  GET /api/reports/<id>/download'),
            ('Acknowledgements', 'GET /api/acknowledgements  ·  POST /api/acknowledgements/<id>/confirm'),
        ], lw=0.26),
        PageBreak(),
    ]

    # ═══════════════════════════════════════════════
    # LAST PAGE — THANK YOU (original image preserved)
    # ═══════════════════════════════════════════════
    story.append(full_img(TY_IMG, max_h=H - 2.4*cm))

    doc.build(story)
    print('[OK] PDF saved:', OUTPUT)


if __name__ == '__main__':
    build()
