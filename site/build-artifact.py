"""Derive the Claude Artifact source from site/index.html.

site/index.html is a standalone document (doctype + head + body) because that is
what GitHub Pages serves. The Artifact publisher supplies its own
<!doctype>/<head>/<body> skeleton, so it needs the same page without them.
This strips the wrapper and keeps <title>, <style> and the body content.

    uv run python site/build-artifact.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / 'index.html').read_text(encoding='utf8')

title = re.search(r'<title>.*?</title>', src, re.S)
style = re.search(r'<style>.*?</style>', src, re.S)
body = re.search(r'<body>(.*)</body>', src, re.S)

if not (title and style and body):
    sys.exit('index.html is not in the expected standalone shape')

out = f'{title.group(0)}\n\n{style.group(0)}\n{body.group(1)}'
dest = ROOT / 'artifact.html'
dest.write_text(out, encoding='utf8')

# the skeleton is supplied at publish time — none of it may survive here
low = out.lower()
assert not low.lstrip().startswith('<!doctype'), 'doctype leaked into the artifact source'
for tag in ('<html', '</html>', '<head>', '</head>', '<body>', '</body>'):
    assert tag not in low, f'{tag} leaked into the artifact source'

print(f'{dest}: {len(out):,} bytes')
