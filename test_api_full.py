"""Full API integration test for KnowBridge AI"""
import urllib.request, urllib.error, json, time, sys

BASE = 'http://localhost:5000'
passed = 0
failed = 0

def req(method, path, data=None, token=None, expect=None):
    global passed, failed
    url = BASE + path
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        res = urllib.request.urlopen(r)
        status = res.status
        raw = res.read()
        resp = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        resp = {}
        try: resp = json.loads(raw)
        except: pass

    ok = True
    if expect and status != expect:
        ok = False

    # Fail if HTML returned (login redirect)
    if isinstance(resp, dict) and not resp and raw and raw.strip().startswith(b'<'):
        ok = False
        resp = {'error': 'Got HTML redirect instead of JSON'}

    icon = 'PASS' if ok else 'FAIL'
    if ok: passed += 1
    else: failed += 1
    print(f'[{icon}] {method} {path} -> {status} | {str(resp)[:100]}')
    return resp, status

time.sleep(1)

print('\n=== AUTH TESTS ===')
r, _ = req('POST', '/api/auth/login', {'email':'admin@knowbridge.ai','password':'admin123'}, expect=200)
TOKEN = r.get('access_token','')
print(f'Token: {"YES ("+TOKEN[:20]+"...)" if TOKEN else "MISSING"}')

r2, _ = req('POST', '/api/auth/login', {'email':'sarah@knowbridge.ai','password':'sarah123'}, expect=200)
PM_TOKEN = r2.get('access_token','')

r3, _ = req('POST', '/api/auth/login', {'email':'priya@knowbridge.ai','password':'priya123'}, expect=200)
PRIYA_TOKEN = r3.get('access_token','')

req('GET', '/api/auth/me', token=TOKEN, expect=200)
req('GET', '/api/auth/me', expect=401)   # No token -> 401

print('\n=== PROJECTS TESTS ===')
req('GET', '/api/projects', token=TOKEN, expect=200)
req('GET', '/api/projects', expect=401)  # No auth -> 401 JSON
r, _ = req('POST', '/api/projects', {'name':'Test Project API','description':'Created via REST API','status':'active','priority':'high'}, token=TOKEN, expect=201)
NEW_PID = r.get('project_id')
print(f'New project id: {NEW_PID}')
if NEW_PID:
    req('GET', f'/api/projects/{NEW_PID}', token=TOKEN, expect=200)
    req('PUT', f'/api/projects/{NEW_PID}', {'name':'Updated Project API','status':'on_hold'}, token=TOKEN, expect=200)

print('\n=== ANALYTICS TESTS ===')
req('GET', '/api/analytics/dashboard', token=TOKEN, expect=200)
req('GET', '/api/analytics/dashboard', expect=401)

print('\n=== TASKS TESTS ===')
if NEW_PID:
    r, _ = req('POST', '/api/tasks', {'project_id': NEW_PID, 'title':'API Task','description':'Test task','priority':'high','status':'pending'}, token=TOKEN, expect=201)
    TID = r.get('task_id')
    if TID:
        req('PUT', f'/api/tasks/{TID}', {'status':'in_progress'}, token=TOKEN, expect=200)

print('\n=== DECISIONS TESTS ===')
if NEW_PID:
    req('POST', '/api/decisions', {'project_id': NEW_PID, 'title':'API Decision','description':'Test decision','status':'approved'}, token=TOKEN, expect=201)
req('GET', '/api/decisions', token=TOKEN, expect=200)

print('\n=== REVIEWS TESTS ===')
req('GET', '/api/reviews', token=TOKEN, expect=200)

print('\n=== HANDOVERS TESTS ===')
req('GET', '/api/handovers', token=TOKEN, expect=200)
if NEW_PID:
    r, _ = req('POST', '/api/handovers/generate', {'project_id': NEW_PID}, token=TOKEN, expect=201)
    HID = r.get('report_id')
    if HID:
        req('GET', f'/api/handovers/{HID}', token=TOKEN, expect=200)
        req('POST', f'/api/handovers/{HID}/approve', {'notes':'LGTM'}, token=TOKEN, expect=200)

print('\n=== ACKNOWLEDGEMENTS TESTS ===')
req('GET', '/api/acknowledgements', token=TOKEN, expect=200)

print('\n=== AI ENDPOINTS TESTS ===')
req('POST', '/api/ai/summarize', {'text':'This is a test project update. John will handle deployment by Friday.'}, token=TOKEN, expect=200)
req('POST', '/api/ai/extract-decisions', {'text':'Decision: We will use PostgreSQL for production. Owner: Alice. Date: 2024-01-15.'}, token=TOKEN, expect=200)
req('POST', '/api/ai/detect-risks', {'text':'The deadline is tight. No backup plan exists. Single point of failure.'}, token=TOKEN, expect=200)

print(f'\n========================================')
print(f'RESULTS: {passed} passed, {failed} failed')
print(f'========================================')
sys.exit(0 if failed == 0 else 1)
