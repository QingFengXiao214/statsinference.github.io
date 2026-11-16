"""Verify deployed Test tables against the supplied DiD/Proximal reports.
Use ARENA_TEST_URL=local for a local render; the CI default verifies GitHub Pages.
Never execute a DGP or change reported metrics.
"""
from pathlib import Path
import re
import base64
import csv
import json
import math
import os
import time
import urllib.request
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root / 'verification'
out.mkdir(exist_ok=True)
sha = os.environ.get('GITHUB_SHA', 'did-proximal-unified-2026-11-16')
base = os.environ.get('ARENA_TEST_URL', 'https://statsinference.github.io/')
expected_data = json.loads((root / 'data/unified-test-2026-11-16.json').read_text())
keys = ['bias', 'variance', 'rmse', 'length', 'coverage', 'time_s']
expected_values = {
    'did-test-2026-11-16': [[.001012, .018648, .136526, .466152, .9485, .135786], [-.014595, .083437, .289151, .826107, .9565, 89.779984]],
    'proximal-unified-2026-11-16-normalized': [[.0219, .0146, .1229, .4447, .965, .997], [.0161, .6718, .8196, .8475, .9735, 80.873]],
    'proximal-unified-2026-11-16-original': [[.0895, .1955, .4511, 1.5574, .965, .997], [.0454, 11.7071, 3.4210, 2.9586, .9735, 80.873]],
}
for s in expected_data['suites']:
    assert len(s['rows']) == 2
    assert [[r[k] for k in keys] for r in s['rows']] == expected_values[s['id']]
    assert all(r['status'] == 'reported' and r['group'] == 'Test' and not r['approximate_metrics'] for r in s['rows'])
    if s['domain'] == 'proximal':
        assert len(s['dgp_results']) == 8
        for family in ['pfn', 'classical']:
            assert sum(r['tables'] for r in s['dgp_results'] if r['family'] == family) == 2000

local = base == 'local'
if local:
    base = 'in-memory local render'
else:
    paths = ['index.html', 'assets/test-view.js', 'assets/test-references.js', 'data/unified-test-2026-11-16.json']
    for attempt in range(40):
        try:
            if all(urllib.request.urlopen(base + path + '?verify=' + sha + '-' + str(attempt), timeout=15).read() == (root / path).read_bytes() for path in paths):
                break
        except Exception:
            pass
        time.sleep(5)
    else:
        raise AssertionError('The expected Test view, references and result JSON were not deployed')

def load_page(page, domain=None):
    if not local:
        page.goto(base + '?verify=' + sha + ('#domain=' + domain if domain else ''), wait_until='networkidle', timeout=60000)
        return
    html = (root / 'index.html').read_text()
    html = re.sub(r'<link[^>]*href="https://fonts[^>]*>', '', html)
    html = re.sub(r'<link rel="stylesheet" href="(assets/[^"?]+)[^"]*">', lambda m: '<style>' + (root / m.group(1)).read_text() + '</style>', html)
    html = re.sub(r'<script src="(assets/[^"?]+)[^"]*"></script>', lambda m: '<script>' + (root / m.group(1)).read_text() + '</script>', html)
    logo = base64.b64encode((root / 'assets/statsarena-logo.webp').read_bytes()).decode()
    html = html.replace('assets/statsarena-logo.webp', 'data:image/webp;base64,' + logo)
    data = {str(p.relative_to(root)): json.loads(p.read_text()) for p in (root / 'data').glob('*.json')}
    preload = '<script>const localData=' + json.dumps(data) + ';window.fetch=(url)=>{const key=String(url).split("?")[0];return Promise.resolve(new Response(JSON.stringify(localData[key]),{status:200,headers:{"Content-Type":"application/json"}}));};</script>'
    html = html.replace('</head>', preload + '</head>')
    page.set_content(html, wait_until='load')
    page.wait_for_function("document.body.dataset.testView==='ready'")
    if domain:
        page.evaluate('(id)=>chooseTask(id)', domain)

errors = []
with sync_playwright() as p:
    executable = os.environ.get('CHROMIUM_EXECUTABLE')
    browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
    page = browser.new_page(viewport={'width': 1440, 'height': 1050})
    page.on('pageerror', lambda e: errors.append(str(e)))
    if local:
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        page.route('https://fonts.gstatic.com/**', lambda route: route.abort())
    load_page(page)
    page.wait_for_function("document.body.dataset.testView==='ready'")
    assert page.title() == 'Statistical Inference Arena'
    assert page.locator('.metric-card').count() == 6
    assert page.locator('.overview-grid, #split-chips, [data-split], #contributors').count() == 0
    assert page.locator('#main-panel svg').count() == 0
    text = page.locator('#metric-tables').inner_text()
    for v in ['+0.0219', '−0.1098', '0.3303', '4.0148', '0.5891', '2.0533', '1.2654', '4.3238', '97.30%', '94.90%', '1.50', '439.39']:
        assert v in text, v
    assert '≈' not in text
    suites = page.evaluate('ArenaTestView.getSuites()')
    assert len(suites) == 7
    assert len(next(s for s in suites if s['domain'] == 'mediation')['dgp_results']) == 26
    for s in expected_data['suites']:
        assert next(x for x in suites if x['id'] == s['id']) == s
    for s in suites:
        for r in s['rows']:
            assert r['group'] == 'Test'
            if r['family'] == 'classical':
                assert r['method'] == 'RF + bootstrap'
    # Existing ATE/CATE/IV/Mediation are not reinterpreted by this release.
    ate = next(s for s in suites if s['domain'] == 'ate')['rows'][0]
    assert math.isclose(ate['bias'], .0149)
    assert math.isclose(ate['rmse'], math.sqrt((.1211**2 + .07**2) / 2))
    assert math.isclose(ate['variance'], (.1069**2 + .0629**2) / 2)
    iv = next(s for s in suites if s['domain'] == 'iv')
    assert len(iv['rows']) == 3 and all(r['variance'] is None for r in iv['rows'])
    assert iv['rows'][0]['method'] == 'IV-PFN' and iv['rows'][1]['length'] > 100000

    for domain in ['ate', 'cate', 'mediation', 'iv', 'proximal', 'did_sc', 'nonparametric_regression', 'quantile', 'semi_supervised', 'missing_data']:
        page.locator('[data-t="' + domain + '"]').click()
        assert page.locator('.metric-card').count() == 6 and page.locator('#main-panel svg').count() == 0
        if domain in ['ate', 'cate', 'mediation', 'proximal', 'did_sc']:
            assert page.locator('.method-ref-name').count() == 6
        if domain in ['nonparametric_regression', 'quantile', 'semi_supervised', 'missing_data']:
            assert page.locator('.empty-cell').count() == 6 and page.locator('#export-btn').is_disabled()

    page.locator('[data-t="did_sc"]').click()
    did_text = page.locator('#metric-tables').inner_text()
    for v in ['+0.001012', '−0.014595', '0.018648', '0.083437', '0.136526', '0.289151', '0.466152', '0.826107', '94.85%', '95.65%', '0.135786', '89.779984']:
        assert v in did_text, v
    assert '≈' not in did_text and 'DirectATT' not in did_text and 'Not evaluated' not in did_text
    assert page.locator('[data-metric="rmse"] tbody tr').count() == 2
    hf = 'https://huggingface.co/lisuo/PFN-DiD/tree/b7ab973ce6142e3bf34e11aa6db66b3bc5fc5c6a'
    assert page.locator('.method-ref-name').first.get_attribute('href') == hf
    assert page.locator('#dgp-details').is_hidden()
    page.locator('#test-protocol').evaluate('(el)=>el.open=true')
    assert 'not a percentile interval' in page.locator('#protocol-content').inner_text()
    assert page.locator('#protocol-content a').get_attribute('href') == 'data/unified-test-2026-11-16.json'
    page.locator('#test-protocol').evaluate('(el)=>el.open=false')
    page.locator('#table').screenshot(path=str(out / 'did-test-tables.png'))
    with page.expect_download() as download:
        page.locator('#export-btn').click()
    download.value.save_as(out / 'did-test.csv')
    with (out / 'did-test.csv').open() as f:
        exported = list(csv.DictReader(f))
    assert len(exported) == 2 and float(exported[1]['time_s']) == 89.779984
    assert exported[0]['source_file'] == 'PFN-DiD test.pdf'

    page.locator('[data-t="proximal"]').click()
    assert page.locator('#suite-select option').count() == 2
    assert page.locator('#suite-select').input_value() == 'proximal-unified-2026-11-16-normalized'
    norm_text = page.locator('#metric-tables').inner_text()
    for v in ['normalized', '+0.0219', '+0.0161', '0.0146', '0.6718', '0.1229', '0.8196', '0.4447', '0.8475', '96.50%', '97.35%', '0.997', '80.873']:
        assert v in norm_text, v
    assert '≈' not in norm_text and 'B = 200' not in norm_text
    assert page.locator('.method-ref-name').first.get_attribute('href') == 'https://arxiv.org/abs/2610.08078v2'
    page.locator('#dgp-details').evaluate('(el)=>el.open=true')
    assert page.locator('#dgp-content tbody tr').count() == 8
    assert 'Variance' in page.locator('#dgp-content thead').inner_text()
    assert 'SE' not in page.locator('#dgp-content th').all_text_contents()
    assert '89.61%' in page.locator('#dgp-content').inner_text()
    page.locator('#dgp-details').evaluate('(el)=>el.open=false')
    page.locator('#table').screenshot(path=str(out / 'proximal-normalized-tables.png'))
    page.locator('#suite-select').select_option('proximal-unified-2026-11-16-original')
    raw_text = page.locator('#metric-tables').inner_text()
    for v in ['+0.0895', '+0.0454', '0.1955', '11.7071', '0.4511', '3.4210', '1.5574', '2.9586']:
        assert v in raw_text, v
    assert 'normalized' not in raw_text
    assert '34.1062' in page.locator('#dgp-content').text_content()
    page.locator('#table').screenshot(path=str(out / 'proximal-original-tables.png'))
    with page.expect_download() as download:
        page.locator('#export-btn').click()
    download.value.save_as(out / 'proximal-original-test.csv')
    with (out / 'proximal-original-test.csv').open() as f:
        exported = list(csv.DictReader(f))
    assert len(exported) == 2 and float(exported[1]['variance']) == 11.7071
    assert exported[0]['source_file'] == 'Proximal_Unified_20261116_PublicReport.pdf'
    # Reference links and table controls survive re-rendering.
    page.locator('[data-fam="classical"]').click()
    assert page.locator('[data-metric="bias"] tbody tr').count() == 1
    page.locator('[data-fam="all"]').click()
    page.locator('#q').fill('ProximalFM')
    assert page.locator('[data-metric="bias"] tbody tr').count() == 1
    page.locator('#q').fill('')
    page.locator('[data-sort="rmse"]').click()
    assert page.locator('[data-metric="rmse"] tbody tr').first.get_attribute('data-method') == 'ProximalFM'
    page.locator('[data-t="mediation"]').click()
    assert 'SE' in page.locator('#dgp-content th').all_text_contents()
    page.locator('#theme-btn').click()
    assert page.locator('html').get_attribute('data-theme') == 'dark'

    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    mobile.on('pageerror', lambda e: errors.append(str(e)))
    if local:
        mobile.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        mobile.route('https://fonts.gstatic.com/**', lambda route: route.abort())
    load_page(mobile, 'did_sc')
    mobile.wait_for_function("document.body.dataset.testView==='ready'")
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert mobile.locator('[data-metric="rmse"] tbody tr').count() == 2
    mobile.locator('#menu-btn').click()
    mobile.locator('[data-t="proximal"]').click()
    assert mobile.locator('#hero-title').inner_text() == 'Proximal Causal Inference'
    assert mobile.locator('#menu-btn').get_attribute('aria-expanded') == 'false'
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile.screenshot(path=str(out / 'unified-test-mobile.png'), full_page=True)
    assert not errors, errors
    report = {'status': 'passed', 'commit': sha, 'url': base, 'tables_per_domain': 6, 'populated_domains': 6, 'suites': 7, 'chart_count': 0, 'new_direct_report_suites': list(expected_values), 'new_proximal_detail_rows': 16, 'pfn_did_reference': hf, 'javascript_errors': errors}
    (out / 'test-view-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    browser.close()
