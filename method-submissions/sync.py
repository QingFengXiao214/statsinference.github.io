"""Archive validated public model-link issues. Submitted model code is never fetched or run."""
from __future__ import annotations
import json
import os
import re
import urllib.request
from pathlib import Path

SOURCE = 'Statsinference/statsinference.github.io'
ROOT = Path(__file__).resolve().parent
DOMAINS = {'ate', 'cate', 'mediation', 'iv', 'proximal', 'did_sc', 'nonparametric_regression', 'quantile', 'semi_supervised', 'missing_data', 'unspecified'}
URL_RE = re.compile(r'https://huggingface\.co/[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9][A-Za-z0-9._-]*(?:/tree/[A-Za-z0-9][A-Za-z0-9._-]*)?/?\Z')
RESERVED = {'spaces', 'datasets', 'organizations', 'api', 'settings', 'collections', 'join', 'login'}
MARKER = '<!-- arena-method-submission:v1 -->'


def canonical_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 1024:
        return None
    value = value.strip()
    if not URL_RE.fullmatch(value) or '..' in value or value.split('/')[3].lower() in RESERVED:
        return None
    return value.rstrip('/')


def parse_issue(issue: dict) -> dict | None:
    """Only typed link submissions are accepted; all fields are data, never commands."""
    if issue.get('pull_request') or not str(issue.get('title', '')).startswith('[Method submission] '):
        return None
    body = issue.get('body') or ''
    if not isinstance(body, str) or len(body) > 10000 or MARKER not in body:
        return None
    body = body.replace('\r\n', '\n')
    match = re.search(r'^### Hugging Face model link\n+([^\n]+)\s*\n', body, re.M)
    url = canonical_url(match.group(1)) if match else None
    number = issue.get('number')
    author = (issue.get('user') or {}).get('login', '')
    if not url or type(number) is not int or number < 1 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:\[bot\])?', author):
        return None
    domain_match = re.search(r'^### Research domain\n+([a-z_]+)\s*\n', body, re.M)
    domain = domain_match.group(1) if domain_match else 'unspecified'
    if domain not in DOMAINS:
        domain = 'unspecified'
    dates = [issue.get(k, '') for k in ['created_at', 'updated_at']]
    if not all(isinstance(d, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', d) for d in dates):
        return None
    state = issue.get('state')
    if state not in ['open', 'closed']:
        return None
    is_test = str(issue['title']).startswith('[Method submission] [TEST] ')
    return {
        'schema_version': 1, 'issue_number': number,
        'model': '/'.join(url.split('/')[3:5]), 'huggingface_url': url,
        'domain': domain, 'submitted_by': author, 'created_at': dates[0], 'updated_at': dates[1],
        'status': state, 'issue_url': f'https://github.com/{SOURCE}/issues/{number}',
        'is_test': is_test,
    }


def fetch_issues() -> list[dict]:
    """Read only the fixed public intake repository, following all result pages."""
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Statistical-Inference-Arena-Submission-Archive', 'X-GitHub-Api-Version': '2022-11-28'}
    # Private mirror reads the public intake anonymously; no cross-repo credential is required.
    if os.environ.get('GITHUB_REPOSITORY') == SOURCE and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    issues = []
    page = 1
    while True:
        url = f'https://api.github.com/repos/{SOURCE}/issues?state=all&sort=created&direction=asc&per_page=100&page={page}'
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise ValueError('Unexpected issue response')
        issues.extend(batch)
        if len(batch) < 100:
            return issues
        page += 1


def write_archive(issues: list[dict], root: Path = ROOT) -> int:
    records = [r for issue in issues if (r := parse_issue(issue)) is not None]
    for record in records:
        directory = root / ('checks' if record['is_test'] else 'received')
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"issue-{record['issue_number']:06d}.json"
        path.write_text(json.dumps(record, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    received = root / 'received'
    received.mkdir(parents=True, exist_ok=True)
    # Retain previously received submissions even if their source issue is subsequently deleted.
    saved = [json.loads(p.read_text(encoding='utf-8')) for p in received.glob('issue-*.json')]
    saved.sort(key=lambda r: r['issue_number'], reverse=True)
    lines = ['# Method submissions', '', '| Method | Domain | Submitted by | Date | Status | Submission |', '| --- | --- | --- | --- | --- | --- |']
    for r in saved:
        lines.append(f"| [{r['model']}]({r['huggingface_url']}) | {r['domain']} | {r['submitted_by']} | {r['created_at'][:10]} | {r['status']} | [#{r['issue_number']}]({r['issue_url']}) |")
    if not saved:
        lines += ['', 'No method submissions yet.']
    (received / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return len(records)


if __name__ == '__main__':
    count = write_archive(fetch_issues())
    print(f'Archived {count} validated submission records.')
