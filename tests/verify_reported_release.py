"""Check deployed summaries and equal contributor presentation; never execute DGPs."""
from pathlib import Path
import json
import os
import re
import time
import urllib.request
from playwright.sync_api import sync_playwright

out = Path('verification')
out.mkdir(exist_ok=True)
expected = json.loads(Path('data/results.json').read_text())
html = Path('index.html').read_text()
inline = re.search(r'<script id="results-data" type="application/json">(.*?)</script>', html, re.S)
assert inline and json.loads(inline.group(1)) == expected, 'Inline and external result data diverged'
suite = next(s for s in expected['suites'] if s['id'] == 'mediation-nie1-meeting-2026-11-12')
measured = [r for r in suite['rows'] if r['status'] == 'reported']
assert len(measured) == 2
for r in measured:
    assert abs(r['variance'] - r['reported_se'] ** 2) < 1e-10
for r in suite['rows']:
    if r['status'] == 'not_reported':
        assert all(r[k] is None for k in ['bias', 'variance', 'rmse', 'length', 'coverage', 'time_s'])
assert len(suite['dgp_results']) == 13
assert suite['timing_comparisons'][0]['scope'] == 'previous_model_and_test_set'
base = 'https://statsinference.github.io/'
# Require the actual new HTML and JSON, not HTTP 200 from an older deployment.
for attempt in range(36):
    try:
        token = f"{os.environ.get('GITHUB_SHA', '')}-{attempt}"
        req = urllib.request.Request(base + '?verify=' + token, headers={'Cache-Control': 'no-cache'})
        live_html = urllib.request.urlopen(req, timeout=15).read().decode()
        data_req = urllib.request.Request(base + 'data/results.json?verify=' + token, headers={'Cache-Control': 'no-cache'})
        live_data = json.load(urllib.request.urlopen(data_req, timeout=15))
        if 'no ranking is implied' in live_html and live_data == expected:
            break
    except Exception:
        pass
    time.sleep(5)
else:
    raise AssertionError('The expected release did not become publicly available')

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    response = page.goto(base + '?verify=' + token, wait_until='networkidle', timeout=60000)
    assert response.status == 200
    assert page.title() == 'Statistical Inference Arena'
    assert page.locator('#hero-title').inner_text() == 'Mediation'
    assert page.locator('#tabs [data-t]').count() == 10
    assert page.locator('#tbody .row-reported').count() == 2
    assert page.locator('#tbody .row-unreported').count() == 2
    table = page.locator('#tbody').inner_text()
    for text in ['+0.0002', '95.39%', '97.90%', '≈0.03968', '≈0.52287']:
        assert text in table, text
    assert '182.175' not in table and '4.571' not in table
    assert page.locator('.timing-table tbody tr').count() == 3
    assert '361.446 s' in page.locator('.timing-table').inner_text()
    assert json.loads(page.evaluate('JSON.stringify(DATA)')) == expected
    assert page.locator('#contributors h3').all_inner_texts() == ['Jiaming Hu', 'Shi Bo', 'Zhiheng Zhang']
    assert 'no ranking is implied' in page.locator('.contributor-note').inner_text()
    cards = page.locator('.contributor-grid article').evaluate_all('(els)=>els.map(e=>({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,font:getComputedStyle(e.querySelector("h3")).font}))')
    assert max(c['width'] for c in cards) - min(c['width'] for c in cards) < 1
    assert max(c['height'] for c in cards) - min(c['height'] for c in cards) < 1
    assert len({c['font'] for c in cards}) == 1
    assert page.locator('.brand-logo').evaluate('(el)=>el.complete && el.naturalWidth>0')
    page.screenshot(path=str(out / 'desktop.png'))
    page.locator('#contributors').screenshot(path=str(out / 'contributors.png'))
    page.locator('#table').screenshot(path=str(out / 'mediation-table.png'))
    page.locator('[data-split="ID"]').click()
    assert page.locator('#tbody tr').count() == 2
    page.locator('[data-split="both"]').click()
    page.locator('[data-fam="classical"]').click()
    assert page.locator('#tbody .row-unreported').count() == 2
    assert page.locator('#pareto svg.chart').count() == 0
    page.locator('[data-fam="all"]').click()
    for domain in ['ate','cate','iv','proximal','did_sc','nonparametric_regression','quantile','semi_supervised','missing_data']:
        page.locator(f'[data-t="{domain}"]').click()
        assert page.locator('#tbody .row-reported').count() == 0
        assert page.locator('#report-details').is_hidden()
    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    mobile.on('pageerror', lambda e: errors.append(str(e)))
    mobile.goto(base + '?verify=' + token, wait_until='networkidle', timeout=60000)
    assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    mobile.locator('#menu-btn').click()
    mobile.locator('[data-t="missing_data"]').click()
    assert mobile.locator('#hero-title').inner_text() == 'Missing Data'
    mobile.locator('#menu-btn').click()
    mobile.locator('[data-t="mediation"]').click()
    mobile.screenshot(path=str(out / 'mobile.png'), full_page=True)
    assert not errors, errors
    report = {'status': 'passed', 'url': base, 'commit': os.environ.get('GITHUB_SHA'), 'contributors': cards, 'javascript_errors': errors, 'reported_current_rows': 2, 'unreported_rf_rows': 2, 'dgp_configurations': 13, 'historical_cpu_rows': 3}
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    browser.close()
