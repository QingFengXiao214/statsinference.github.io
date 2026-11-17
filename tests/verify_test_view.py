"""Check the shared Test leaderboard without changing source data or running DGPs.
Set ARENA_TEST_URL=local for an offline browser test; CI checks the deployed site.
"""
from pathlib import Path
import base64
import csv
import hashlib
import json
import os
import re
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'verification'
OUT.mkdir(exist_ok=True)
BASE = os.environ.get('ARENA_TEST_URL', 'https://statsinference.github.io/')
LOCAL = BASE == 'local'
SHA = os.environ.get('GITHUB_SHA', 'single-table-1')
KEYS = ['bias', 'variance', 'rmse', 'length', 'coverage', 'time_s']
HEADINGS = ['Rank', 'Method', 'Bias', 'Variance', 'RMSE', 'Length', 'Coverage', 'Time (s)']
DOMAINS = ['ate', 'cate', 'mediation', 'iv', 'proximal', 'did_sc', 'nonparametric_regression', 'quantile', 'semi_supervised', 'missing_data']
EXPECTED = {
    'ate': [[.0119,.0097,.1114,.2599,.7763,1.089],[-.0167,.0137,.1284,.5897,.9675,90.490]],
    'cate': [[.0143,.0480,.2966,5.8471,1.,.219],[-.0139,.1560,.5522,1.2689,.8484,55.501]],
    'mediation': [[.0219,.3303,.5891,1.2654,.973,1.5],[-.1098,4.0148,2.0533,4.3238,.949,439.39]],
    'iv': [[.012,.072,.268,.875,.9565,.366],[.022,.099,.316,1.111,.9025,179.9]],
    'proximal': [[.0219,.0146,.1229,.4447,.965,.997],[.0161,.6718,.8196,.8475,.9735,80.873]],
    'did_sc': [[.001012,.018648,.136526,.466152,.9485,.135786],[-.014595,.083437,.289151,.826107,.9565,89.779984]]
}
SOURCE_HASHES = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data').glob('*.json')}
readme = (ROOT/'README.md').read_text()
for removed in ['Core Contributors', 'Equal recognition', 'First reported results', 'other nine domains', 'ID and OOD', 'November 12, 2026', 'inline `results-data`']:
    assert removed not in readme, removed

if not LOCAL:
    paths = ['index.html', 'assets/test-view.js', 'assets/test-view.css', 'assets/test-references.js', 'data/iv-v03.json', 'data/unified-test-2026-11-16.json']
    for attempt in range(40):
        try:
            if all(urllib.request.urlopen(BASE+path+'?verify='+SHA+'-'+str(attempt), timeout=15).read()==(ROOT/path).read_bytes() for path in paths):
                break
        except Exception:
            pass
        time.sleep(5)
    else:
        raise AssertionError('Expected single-table release not deployed')

def load(page, fragment=''):
    if not LOCAL:
        page.goto(BASE+'?verify='+SHA+('#'+fragment if fragment else ''), wait_until='networkidle', timeout=60000)
    else:
        html = (ROOT/'index.html').read_text()
        html = re.sub(r'<link[^>]*href="https://fonts[^>]*>', '', html)
        html = re.sub(r'<link rel="stylesheet" href="(assets/[^"?]+)[^"]*">', lambda m:'<style>'+(ROOT/m.group(1)).read_text()+'</style>', html)
        html = re.sub(r'<script src="(assets/[^"?]+)[^"]*"></script>', lambda m:'<script>'+(ROOT/m.group(1)).read_text()+'</script>', html)
        html = html.replace('assets/statsarena-logo.webp', 'data:image/webp;base64,'+base64.b64encode((ROOT/'assets/statsarena-logo.webp').read_bytes()).decode())
        data = {str(p.relative_to(ROOT)):json.loads(p.read_text()) for p in (ROOT/'data').glob('*.json')}
        preload = '<script>const localData='+json.dumps(data)+';window.fetch=url=>Promise.resolve(new Response(JSON.stringify(localData[String(url).split("?")[0]]),{status:200}));</script>'
        page.set_content(html.replace('</head>', preload+'</head>'), wait_until='load')
    page.wait_for_function("document.body.dataset.testView==='ready'")
    if LOCAL and fragment:
        page.evaluate('(h)=>{location.hash=h;readHash();render();}', fragment)

def headers(page):
    return [re.sub(r'\s*[↑↓↕]\s*$', '', h).strip() for h in page.locator('#leaderboard thead th').all_inner_texts()]

errors=[]
with sync_playwright() as p:
    exe = os.environ.get('CHROMIUM_EXECUTABLE')
    browser = p.chromium.launch(**({'executable_path':exe} if exe else {}))
    page = browser.new_page(viewport={'width':1440,'height':1050})
    page.on('pageerror', lambda e:errors.append(str(e)))
    load(page)
    assert page.title() == 'Statistical Inference Arena'
    assert page.locator('#rank-metric').input_value() == 'rmse'
    suites = page.evaluate('ArenaTestView.getSuites()')
    assert len(suites)==6
    for domain, values in EXPECTED.items():
        s=next(s for s in suites if s['domain']==domain)
        assert [[r[k] for k in KEYS] for r in s['rows']]==values, domain
    assert page.locator('#tabs [data-t]').count()==10
    for domain in DOMAINS:
        page.locator(f'[data-t="{domain}"]').click()
        assert page.locator('#main-panel table').count()==1
        assert headers(page)==HEADINGS
        assert page.locator('.metric-card, .metric-grid, #main-panel svg, #suite-info, #suite-select, #test-protocol, #dgp-details, #contributors, [data-split]').count()==0
        body=page.locator('body').inner_text()
        for removed in ['normalized','Synthetic Control','2,000 tables','Nominal coverage','bootstrap-SE normal interval','IF normal interval','Proximal series-IV/GMM','Five-context distribution mixture','Evaluation details & aggregation','Per-configuration results']:
            assert removed not in body,(domain,removed)
        if domain not in EXPECTED:
            assert page.locator('.empty-cell').count()==1
            assert page.locator('#export-btn').is_disabled()
            continue
        source=next(s for s in suites if s['domain']==domain)['rows']
        assert page.locator('#leaderboard tbody tr').count()==2
        assert page.locator('.method-ref-name').count()==1
        assert all(x=='5-fold' for x in page.locator('.method-config').all_inner_texts())
        for key in KEYS:
            page.locator('#rank-metric').select_option(key)
            score=lambda r: abs(r[key]) if key=='bias' else abs(r[key]-.95) if key=='coverage' else r[key]
            ordered=sorted(source,key=score)
            assert page.locator('#leaderboard tbody .mname').all_inner_texts()==[r['method'] for r in ordered],(domain,key)
            assert page.locator('#leaderboard tbody .rank-cell').all_inner_texts()==['1','2']
            # All displayed values and precision still match the original formatter.
            for row in page.locator('#leaderboard tbody tr').all():
                identity=row.get_attribute('data-method')
                expected=page.evaluate('(id)=>{const r=current().rows.find(r=>(r.source_method||r.method)===id);return metricKeys.map(k=>formatMetric(r,k));}',identity)
                assert row.locator('td[data-metric]').all_inner_texts()==expected
                method=row.locator('.method-cell')
                if method.locator('.mname').inner_text()=='RF + bootstrap':
                    assert method.inner_text()=='RF + bootstrap'
            page.locator(f'[data-sort="{key}"]').click()
            assert page.locator('#rank-metric').input_value()==key
            assert page.locator('#leaderboard tbody .mname').all_inner_texts()==[r['method'] for r in reversed(ordered)]
            assert page.locator('#leaderboard tbody .rank-cell').all_inner_texts()==['2','1']
    # Comparator edge cases do not modify any published suite.
    assert page.evaluate("compareRows({bias:-.1},{bias:.2},'bias')<0")
    assert page.evaluate("compareRows({rmse:null},{rmse:1},'rmse',-1)>0")
    assert page.evaluate("compareRows({coverage:.90},{coverage:.95},'coverage')>0")
    assert page.evaluate("compareRows({rmse:1},{rmse:1},'rmse')===0")
    page.locator('[data-t="iv"]').click()
    page.locator('#rank-metric').select_option('rmse')
    assert page.locator('.method-ref-name').get_attribute('href')=='https://huggingface.co/Brownight/tabpfn-iv-adapter-v0.3'
    assert 'trim' not in page.locator('#leaderboard').inner_text().lower()
    page.locator('[data-fam="classical"]').click()
    assert page.locator('#leaderboard tbody tr').count()==1
    assert page.locator('#leaderboard tbody .rank-cell').inner_text()=='2'
    page.locator('[data-fam="all"]').click()
    page.locator('#q').fill('IV-PFN')
    assert page.locator('#leaderboard tbody tr').count()==1
    page.locator('#q').fill('no-such-method')
    assert page.locator('.empty-cell').count()==1
    page.locator('#q').fill('')
    with page.expect_download() as d:
        page.locator('#export-btn').click()
    d.value.save_as(OUT/'iv-single-table.csv')
    exported=list(csv.DictReader((OUT/'iv-single-table.csv').open()))
    assert [[float(r[k]) for k in KEYS] for r in exported]==EXPECTED['iv']
    assert exported[1]['source_method']=='RF trim + bootstrap'
    page.locator('#table').screenshot(path=str(OUT/'iv-single-table.png'))
    page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
    page.locator('[data-t="proximal"]').click()
    assert headers(page)==HEADINGS
    page.locator('#table').screenshot(path=str(OUT/'proximal-single-table.png'))
    page.evaluate("location.hash='domain=proximal&suite=proximal-unified-2026-11-16-original';readHash();render();")
    assert page.evaluate('current().metric_scale')=='normalized'
    assert headers(page)==HEADINGS
    page.locator('[data-t="ate"]').click()
    page.locator('#method-references').evaluate('(el)=>el.open=true')
    assert page.locator('.reference-secondary').get_attribute('href')=='https://huggingface.co/fuyao11/CausalPFN-ATE-CATE'
    page.locator('#method-references').evaluate('(el)=>el.open=false')
    page.locator('#theme-btn').click()
    assert page.locator('html').get_attribute('data-theme')=='dark'
    page.locator('#table').screenshot(path=str(OUT/'dark-table.png'))
    mobile=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    mobile.on('pageerror',lambda e:errors.append(str(e)))
    load(mobile,'domain=iv')
    assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
    mobile.locator('#rank-metric').select_option('coverage')
    assert mobile.locator('#leaderboard tbody .mname').first.inner_text()=='IV-PFN'
    mobile.locator('#menu-btn').click()
    mobile.locator('[data-t="proximal"]').click()
    assert mobile.locator('#menu-btn').get_attribute('aria-expanded')=='false'
    assert headers(mobile)==HEADINGS
    assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
    mobile.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    assert not errors,errors
    assert page.evaluate('ArenaTestView.getSuites()')==suites
    assert SOURCE_HASHES=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data').glob('*.json')}
    report={'status':'passed','commit':SHA,'url':BASE,'tables_per_domain':1,'headers':HEADINGS,'rank_metrics':KEYS,'populated_domains':6,'chart_count':0,'javascript_errors':errors,'source_sha256':SOURCE_HASHES}
    (OUT/'test-view-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    browser.close()
