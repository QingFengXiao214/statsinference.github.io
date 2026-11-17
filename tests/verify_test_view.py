"""Verify six compact Test leaderboards, references and the user-supplied IV v0.3 rows.
ARENA_TEST_URL=local runs without external network. Default checks the deployed website.
No scientific DGPs are executed; all metrics are checked against their supplied summaries.
"""
from pathlib import Path
import base64, csv, hashlib, json, os, re, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'verification'
OUT.mkdir(exist_ok=True)
BASE = os.environ.get('ARENA_TEST_URL', 'https://statsinference.github.io/')
LOCAL = BASE == 'local'
SHA = os.environ.get('GITHUB_SHA', 'iv-v03-compact')
KEYS = ['bias', 'variance', 'rmse', 'length', 'coverage', 'time_s']
DOMAINS = ['ate', 'cate', 'mediation', 'iv', 'proximal', 'did_sc', 'nonparametric_regression', 'quantile', 'semi_supervised', 'missing_data']
EXPECTED = {
 'ate': [[.0119,.0097,.1114,.2599,.7763,1.089],[-.0167,.0137,.1284,.5897,.9675,90.490]],
 'cate': [[.0143,.0480,.2966,5.8471,1.,.219],[-.0139,.1560,.5522,1.2689,.8484,55.501]],
 'mediation': [[.0219,.3303,.5891,1.2654,.973,1.5],[-.1098,4.0148,2.0533,4.3238,.949,439.39]],
 'iv': [[.012,.072,.268,.875,.9565,.366],[.022,.099,.316,1.111,.9025,179.9]],
 'proximal': [[.0219,.0146,.1229,.4447,.965,.997],[.0161,.6718,.8196,.8475,.9735,80.873]],
 'did_sc': [[.001012,.018648,.136526,.466152,.9485,.135786],[-.014595,.083437,.289151,.826107,.9565,89.779984]]
}
NEW_HF = 'https://huggingface.co/Brownight/tabpfn-iv-adapter-v0.3'
UNIFIED = json.loads((ROOT/'data/unified-test-2026-11-16.json').read_text())
MED = json.loads((ROOT/'data/mediation-fivefold.json').read_text())
IV = json.loads((ROOT/'data/iv-v03.json').read_text())
assert [[r[k] for k in KEYS] for r in IV['rows']] == EXPECTED['iv']
assert IV['rows'][1]['source_method'] == 'RF trim + bootstrap'
assert IV['variance_definition'].startswith('Reported as Error var.')
assert IV['source']['url'] == NEW_HF
assert next(s for s in UNIFIED['suites'] if s['id']=='proximal-unified-2026-11-16-original')['rows'][1]['variance']==11.7071

if not LOCAL:
    paths = ['index.html','assets/test-view.js','assets/test-references.js','data/iv-v03.json','data/unified-test-2026-11-16.json']
    for attempt in range(40):
        try:
            if all(urllib.request.urlopen(BASE+path+'?verify='+SHA+'-'+str(attempt),timeout=15).read()==(ROOT/path).read_bytes() for path in paths):
                break
        except Exception:
            pass
        time.sleep(5)
    else:
        raise AssertionError('Expected website release not yet deployed')

def load_page(page, fragment=''):
    if not LOCAL:
        page.goto(BASE+'?verify='+SHA+('#'+fragment if fragment else ''),wait_until='networkidle',timeout=60000)
    else:
        html=(ROOT/'index.html').read_text()
        html=re.sub(r'<link[^>]*href="https://fonts[^>]*>','',html)
        html=re.sub(r'<link rel="stylesheet" href="(assets/[^"?]+)[^"]*">',lambda m:'<style>'+(ROOT/m.group(1)).read_text()+'</style>',html)
        html=re.sub(r'<script src="(assets/[^"?]+)[^"]*"></script>',lambda m:'<script>'+(ROOT/m.group(1)).read_text()+'</script>',html)
        html=html.replace('assets/statsarena-logo.webp','data:image/webp;base64,'+base64.b64encode((ROOT/'assets/statsarena-logo.webp').read_bytes()).decode())
        data={str(p.relative_to(ROOT)):json.loads(p.read_text()) for p in (ROOT/'data').glob('*.json')}
        preload='<script>const localData='+json.dumps(data)+';window.fetch=(url)=>Promise.resolve(new Response(JSON.stringify(localData[String(url).split("?")[0]]),{status:200}));</script>'
        page.set_content(html.replace('</head>',preload+'</head>'),wait_until='load')
    page.wait_for_function("document.body.dataset.testView==='ready'")
    if LOCAL and fragment:
        page.evaluate('(h)=>{location.hash=h;readHash();render();}',fragment)

errors=[]
with sync_playwright() as p:
    executable=os.environ.get('CHROMIUM_EXECUTABLE')
    browser=p.chromium.launch(**({'executable_path':executable} if executable else {}))
    page=browser.new_page(viewport={'width':1440,'height':1050})
    page.on('pageerror',lambda e:errors.append(str(e)))
    load_page(page)
    assert page.title()=='Statistical Inference Arena'
    suites=page.evaluate('ArenaTestView.getSuites()')
    assert len(suites)==6 and len({s['domain'] for s in suites})==6
    for domain,values in EXPECTED.items():
        s=next(s for s in suites if s['domain']==domain)
        assert [[r[k] for k in KEYS] for r in s['rows']]==values,domain
        assert all(r['group']=='Test' and not r.get('approximate_metrics') for r in s['rows'])
        if domain not in ['iv','mediation']:
            assert s==next(x for x in UNIFIED['suites'] if x['id']==s['id'])
    assert len(next(s for s in suites if s['domain']=='mediation')['dgp_results'])==26
    assert len(next(s for s in suites if s['domain']=='proximal')['dgp_results'])==8
    assert page.locator('#tabs [data-t]').count()==10
    assert page.locator('[data-t="ate"]').inner_text()=='Average Treatment Effect'
    assert page.locator('[data-t="cate"]').inner_text()=='Conditional Average Treatment Effect'
    for domain in DOMAINS:
        page.locator(f'[data-t="{domain}"]').click()
        assert page.locator('.metric-card').count()==6
        assert page.locator('#main-panel svg, #suite-info, #suite-label, #suite-select, #test-protocol, #dgp-details, #contributors, [data-split]').count()==0
        body=page.locator('body').inner_text()
        for forbidden in ['Synthetic Control','synthetic-control','2,000 tables','Target CATE','Nominal coverage','bootstrap-SE normal interval','IF normal interval','Proximal series-IV/GMM','Five-context distribution mixture','Evaluation details & aggregation','Per-configuration results','Six metrics, presented as tables','Ten research domains. Six metrics. One Test view.']:
            assert forbidden not in body,(domain,forbidden)
        assert all(t=='5-fold' for t in page.locator('.method-config').all_inner_texts())
        if domain in EXPECTED:
            assert page.locator('.method-ref-name').count()==6,domain
            assert page.locator('.method-config').count()==(6 if domain in ['mediation','iv','proximal','did_sc'] else 0)
            assert page.locator('[data-metric="rmse"] tbody tr').count()==2
            for cell in page.locator('#metric-tables td:first-child').all():
                if cell.locator('.mname').count() and cell.locator('.mname').inner_text()=='RF + bootstrap':
                    assert cell.inner_text()=='RF + bootstrap'
                    assert cell.locator('a, .method-config').count()==0
        else:
            assert page.locator('.empty-cell').count()==6 and page.locator('#export-btn').is_disabled()
    page.locator('[data-t="did_sc"]').click()
    assert page.locator('#hero-title').inner_text()=='Difference-in-Differences'
    assert page.locator('.method-ref-name').first.get_attribute('href')=='https://huggingface.co/lisuo/PFN-DiD/tree/b7ab973ce6142e3bf34e11aa6db66b3bc5fc5c6a'
    page.locator('[data-t="iv"]').click()
    exact={'bias':['+0.012','+0.022'],'variance':['0.072','0.099'],'rmse':['0.268','0.316'],'length':['0.875','1.111'],'coverage':['95.65%','90.25%'],'time_s':['0.366','179.9']}
    for key,values in exact.items():
        assert page.locator(f'[data-metric="{key}"] tbody .num').all_inner_texts()==values,key
    assert all(h==NEW_HF for h in page.locator('.method-ref-name').evaluate_all('(els)=>els.map(e=>e.href)'))
    assert 'trim' not in page.locator('#metric-tables').inner_text().lower()
    page.locator('#method-references').evaluate('(el)=>el.open=true')
    assert page.locator('.reference-title').get_attribute('href')==NEW_HF
    page.locator('#method-references').evaluate('(el)=>el.open=false')
    page.screenshot(path=str(OUT/'iv-v03-desktop.png'),full_page=True)
    page.locator('#table').screenshot(path=str(OUT/'iv-v03-tables.png'))
    with page.expect_download() as d:page.locator('#export-btn').click()
    d.value.save_as(OUT/'iv-v03.csv')
    exported=list(csv.DictReader((OUT/'iv-v03.csv').open()))
    assert len(exported)==2 and [[float(r[k]) for k in KEYS] for r in exported]==EXPECTED['iv']
    assert exported[1]['method']=='RF + bootstrap' and exported[1]['source_method']=='RF trim + bootstrap'
    page.locator('[data-fam="classical"]').click()
    assert page.locator('[data-metric="bias"] tbody tr').count()==1
    page.locator('[data-fam="all"]').click()
    page.locator('#q').fill('IV-PFN')
    assert page.locator('[data-metric="bias"] tbody tr').count()==1
    page.locator('#q').fill('')
    page.locator('[data-sort="rmse"]').click()
    assert page.locator('[data-metric="rmse"] tbody .mname').first.inner_text()=='IV-PFN'
    page.locator('[data-sort="rmse"]').click()
    assert page.locator('[data-metric="rmse"] tbody .mname').first.inner_text()=='RF + bootstrap'
    # Stale unit-selection URLs cannot activate an alternate Proximal leaderboard.
    page.evaluate("location.hash='domain=proximal&suite=proximal-unified-2026-11-16-original';readHash();render();")
    assert page.locator('[data-metric="rmse"] tbody .num').all_inner_texts()==['0.8196','0.1229']
    assert page.evaluate('current().id')=='proximal-unified-2026-11-16-normalized'
    assert 'normalized' in page.locator('#metric-tables').inner_text()
    page.locator('#table').screenshot(path=str(OUT/'proximal-single-tables.png'))
    with page.expect_download() as d:page.locator('#export-btn').click()
    d.value.save_as(OUT/'proximal-single.csv')
    exported=list(csv.DictReader((OUT/'proximal-single.csv').open()))
    assert [[float(r[k]) for k in KEYS] for r in exported]==EXPECTED['proximal']
    page.locator('[data-t="ate"]').click()
    assert '77.63%' in page.locator('#metric-tables').inner_text()
    page.locator('#method-references').evaluate('(el)=>el.open=true')
    assert page.locator('.reference-secondary').get_attribute('href')=='https://huggingface.co/fuyao11/CausalPFN-ATE-CATE'
    page.locator('#theme-btn').click()
    assert page.locator('html').get_attribute('data-theme')=='dark'
    assert page.locator('.brand-logo').evaluate('(e)=>e.complete&&e.naturalWidth>0')
    mobile=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    mobile.on('pageerror',lambda e:errors.append(str(e)))
    load_page(mobile,'domain=iv')
    assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert mobile.locator('[data-metric="rmse"] tbody tr').count()==2
    mobile.locator('#menu-btn').click();mobile.locator('[data-t="did_sc"]').click()
    assert mobile.locator('#hero-title').inner_text()=='Difference-in-Differences'
    assert mobile.locator('#menu-btn').get_attribute('aria-expanded')=='false'
    mobile.locator('#menu-btn').click();mobile.locator('[data-t="proximal"]').click()
    assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
    mobile.screenshot(path=str(OUT/'compact-mobile.png'),full_page=True)
    assert not errors,errors
    report={'status':'passed','commit':SHA,'url':BASE,'populated_domains':6,'suites':6,'tables_per_domain':6,'iv_v03_values':EXPECTED['iv'],'iv_reference':NEW_HF,'metadata_and_unit_controls':0,'proximal_active_scale':'normalized','javascript_errors':errors,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data').glob('*.json')}}
    (OUT/'test-view-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    browser.close()
