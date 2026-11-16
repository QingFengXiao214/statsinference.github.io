"""Verify the actual deployed Test-only tables and source-preserving transformations."""
from pathlib import Path
import json,os,time,math,urllib.request
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
out=root/'verification';out.mkdir(exist_ok=True)
base='https://statsinference.github.io/'
sha=os.environ.get('GITHUB_SHA','test-view')
expected=(root/'assets/test-view.js').read_bytes()
for attempt in range(40):
    try:
        url=base+'assets/test-view.js?v='+sha+'-'+str(attempt)
        actual=urllib.request.urlopen(url,timeout=15).read()
        html=urllib.request.urlopen(base+'?v='+sha+'-'+str(attempt),timeout=15).read().decode()
        if actual==expected and 'id="metric-tables"' in html:break
    except Exception:pass
    time.sleep(5)
else:raise AssertionError('Expected Test view was not deployed')
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1050})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'?v='+sha,wait_until='networkidle',timeout=60000)
    page.wait_for_function("document.body.dataset.testView==='ready'")
    assert page.title()=='Statistical Inference Arena'
    assert page.locator('.metric-card').count()==6
    assert page.locator('.overview-grid, #split-chips, [data-split], #contributors').count()==0
    assert page.locator('#main-panel svg').count()==0
    text=page.locator('#metric-tables').inner_text()
    for v in ['+0.0219','−0.1098','0.3303','4.0148','0.5891','2.0533','1.2654','4.3238','97.30%','94.90%','1.50','439.39']:assert v in text,v
    assert '≈' not in text
    suites=page.evaluate('ArenaTestView.getSuites()')
    assert len(suites)==7
    assert len(suites[0]['dgp_results'])==26
    for s in suites:
        for r in s['rows']:
            assert r['group']=='Test'
            if r['family']=='classical':assert r['method']=='RF + bootstrap'
    ate=next(s for s in suites if s['domain']=='ate')['rows'][0]
    assert math.isclose(ate['bias'],.0149)
    assert math.isclose(ate['rmse'],math.sqrt((.1211**2+.07**2)/2))
    assert math.isclose(ate['variance'],(.1069**2+.0629**2)/2)
    iv=next(s for s in suites if s['domain']=='iv')
    assert len(iv['rows'])==3 and all(r['variance'] is None for r in iv['rows'])
    assert iv['rows'][0]['method']=='IV-PFN' and iv['rows'][1]['length']>100000
    did=next(s for s in suites if s['domain']=='did_sc')
    assert len(did['rows'])==5 and did['rows'][-1]['status']=='not_reported'
    assert all(did['rows'][-1][k] is None for k in ['bias','variance','rmse','length','coverage','time_s'])
    prox=next(s for s in suites if s['id']=='proximal-v3-normalized')
    assert prox['rows'][0]['time_s']==1.185 and prox['rows'][1]['time_s']==118.239
    assert math.isclose(prox['rows'][0]['coverage'],.9425)
    page.screenshot(path=str(out/'test-desktop.png'))
    page.locator('#table').screenshot(path=str(out/'mediation-test-tables.png'))
    for domain in ['ate','cate','mediation','iv','proximal','did_sc','nonparametric_regression','quantile','semi_supervised','missing_data']:
        page.locator('[data-t="'+domain+'"]').click()
        assert page.locator('.metric-card').count()==6 and page.locator('#main-panel svg').count()==0
        if domain in ['ate','cate','proximal']:
            assert page.locator('.method-ref-name').count()==6
        if domain in ['nonparametric_regression','quantile','semi_supervised','missing_data']:
            assert page.locator('.empty-cell').count()==6 and page.locator('#export-btn').is_disabled()
    page.locator('[data-t="mediation"]').click()
    page.locator('[data-fam="classical"]').click()
    assert page.locator('[data-metric="bias"] tbody tr').count()==1
    page.locator('[data-fam="all"]').click()
    page.locator('#q').fill('MediPFN')
    assert page.locator('[data-metric="bias"] tbody tr').count()==1
    page.locator('#q').fill('')
    page.locator('[data-sort="rmse"]').click()
    assert page.locator('[data-metric="rmse"] tbody tr').first.get_attribute('data-method')=='MediPFN'
    with page.expect_download() as event:page.locator('#export-btn').click()
    event.value.save_as(out/'mediation-test.csv')
    assert '439.39' in (out/'mediation-test.csv').read_text()
    page.locator('#theme-btn').click()
    assert page.locator('html').get_attribute('data-theme')=='dark'
    mobile=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    mobile.on('pageerror',lambda e:errors.append(str(e)))
    mobile.goto(base+'?v='+sha,wait_until='networkidle',timeout=60000)
    mobile.wait_for_function("document.body.dataset.testView==='ready'")
    assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
    mobile.locator('#menu-btn').click();mobile.locator('[data-t="iv"]').click()
    assert mobile.locator('#hero-title').inner_text()=='Instrumental Variables'
    assert mobile.locator('#menu-btn').get_attribute('aria-expanded')=='false'
    mobile.screenshot(path=str(out/'test-mobile.png'),full_page=True)
    assert not errors,errors
    report={'status':'passed','commit':sha,'tables_per_domain':6,'populated_domains':6,'chart_count':0,'mediation_rows':2,'javascript_errors':errors}
    (out/'test-view-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    browser.close()
