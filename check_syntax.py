import ast, re
from collections import defaultdict

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

print('Lines:', src.count('\n'))
try:
    ast.parse(src)
    print('Syntax OK')
except SyntaxError as e:
    print('SYNTAX ERROR:', e)

# Check for duplicate routes
routes_found = re.findall(r"@app\.route\('([^']+)',\s*methods=(\[[^\]]+\])\)", src)
by_route = defaultdict(list)
for path, methods_str in routes_found:
    methods = [m.strip().strip("'\"") for m in methods_str.strip('[]').split(',')]
    for m in methods:
        by_route[(path, m)].append(1)
dups = {str(k): len(v) for k, v in by_route.items() if len(v) > 1}
if dups:
    print('DUPLICATE ROUTES:', dups)
else:
    print('No duplicate routes found')
print('Total routes registered:', len(routes_found))
