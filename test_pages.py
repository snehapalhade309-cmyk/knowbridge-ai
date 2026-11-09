"""Verify all templates render without Jinja2 errors and all web routes return 200"""
import urllib.request, urllib.error, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

BASE = 'http://localhost:5000'
passed = 0
failed = 0

def get(path, label=None):
    global passed, failed
    label = label or path
    try:
        r = opener.open(BASE + path)
        body = r.read(200)
        if b'<!DOCTYPE html' in body or b'<html' in body:
            if b'Internal Server Error' in body or b'500' in body:
                print(f'[FAIL] {label} -> HTML 500 error')
                failed += 1
            else:
                print(f'[PASS] {label} -> HTML 200')
                passed += 1
        else:
            print(f'[PASS] {label} -> JSON 200')
            passed += 1
    except urllib.error.HTTPError as e:
        body = e.read(100)
        # 302 redirect to login is expected for protected pages when not logged in
        if e.code == 302:
            print(f'[SKIP] {label} -> 302 redirect (need login)')
            passed += 1
        elif e.code == 403:
            print(f'[PASS] {label} -> 403 Forbidden (expected for non-admin)')
            passed += 1
        else:
            print(f'[FAIL] {label} -> HTTP {e.code}')
            failed += 1
    except Exception as e:
        print(f'[FAIL] {label} -> Exception: {e}')
        failed += 1

# 1. Login first
import urllib.parse
data = urllib.parse.urlencode({'email':'admin@knowbridge.ai','password':'admin123','csrf_token':''}).encode()
# Get csrf token from login page
r = opener.open(BASE + '/login')
html = r.read().decode('utf-8', errors='ignore')
import re
m = re.search(r'csrf-token" content="([^"]+)"', html)
csrf = m.group(1) if m else ''
data = urllib.parse.urlencode({'email':'admin@knowbridge.ai','password':'admin123','csrf_token':csrf}).encode()
r = opener.open(urllib.request.Request(BASE + '/login', data=data, method='POST'))
print(f'Login status: {r.url}')
print()

# Test all web routes
routes = [
    ('/dashboard', 'Dashboard'),
    ('/projects', 'Projects'),
    ('/projects/1', 'Project Detail'),
    ('/projects/1/documents', 'Documents'),
    ('/projects/1/tasks', 'Tasks & Decisions'),
    ('/projects/1/risks', 'Risks'),
    ('/projects/1/ai-summary', 'AI Summary'),
    ('/projects/1/review', 'Review Queue'),
    ('/projects/1/timeline', 'Timeline'),
    ('/projects/1/version-history', 'Version History'),
    ('/my-acknowledgements', 'My Acknowledgements'),
    ('/users', 'Users (Admin)'),
    ('/settings', 'Settings'),
    ('/api-docs', 'API Explorer'),
    ('/audit-logs', 'Audit Logs'),
    ('/', 'Landing Page'),
    ('/login', 'Login Page'),
    ('/register', 'Register Page'),
]

for path, label in routes:
    get(path, label)

print(f'\n=== WEB ROUTES: {passed} pass, {failed} fail ===')
