'use strict';
// Source-reported release details. Historical timing is deliberately not merged
// with the current ID/OOD evaluation, ranking, plots, or aggregate calculations.
const baseValidate=validate;
validate=function(data){
 baseValidate(data);
 for(const s of data.suites){
  if(s.dgp_results!=null&&!Array.isArray(s.dgp_results))throw Error('Invalid DGP results');
  for(const r of s.dgp_results||[]){
   if(!GROUPS.includes(r.group)||typeof r.dgp!=='string'||!['pfn','classical'].includes(r.family))throw Error('Invalid DGP result row');
   for(const {k} of COLS.slice(2)){const v=r[k];if(v!=null&&(!number(v)||(k!=='bias'&&v<0)||(k==='coverage'&&v>1)))throw Error('Invalid DGP metric');}
  }
  for(const r of [...s.rows,...s.dgp_results||[]]){
   if(r.variance_is_approximate){
    if(r.variance_basis!=='square_of_rounded_reported_se'||!number(r.reported_se)||r.reported_se<0||!number(r.variance)||Math.abs(r.variance-r.reported_se*r.reported_se)>1e-10)throw Error('Invalid variance transcription');
   }
  }
  if(s.timing_comparisons!=null&&!Array.isArray(s.timing_comparisons))throw Error('Invalid timing comparisons');
  for(const t of s.timing_comparisons||[]){
   if(t.scope!=='previous_model_and_test_set'||!Array.isArray(t.rows)||!number(t.tables)||!number(t.threads))throw Error('Timing cohort must be explicit');
   for(const r of t.rows)if(typeof r.method!=='string'||!number(r.median_time_s)||r.median_time_s<=0||!number(r.median_paired_ratio)||r.median_paired_ratio<=0)throw Error('Invalid paired timing');
  }
 }
 return data;
};
function renderReleaseDetails(){
 const s=current(),container=document.getElementById('report-details');
 container.hidden=!s?.source;
 if(!s?.source){container.innerHTML='';return;}
 const filterDGP=r=>(split==='both'||r.group===split)&&(family==='all'||r.family===family)&&(!query||(r.method+' '+r.dgp).toLowerCase().includes(query));
 const dd=(s.dgp_results||[]).filter(filterDGP);
 const dgpHead='<tr><th scope="col">Split</th><th scope="col">DGP configuration</th><th scope="col" class="r">Bias</th><th scope="col" class="r">Reported SE</th><th scope="col" class="r">RMSE</th><th scope="col" class="r">Length</th><th scope="col" class="r">Coverage</th><th scope="col" class="r">Time (s)</th></tr>';
 const dgpRows=dd.map(r=>`<tr><td><span class="group-tag ${r.group.toLowerCase()}">${r.group==='OOD'?'Source-OOD':'ID'}</span></td><td>${esc(r.dgp)}</td><td class="r num">${metric(r,'bias')}</td><td class="r num">${r.reported_se.toFixed(4)}</td>${['rmse','length','coverage','time_s'].map(k=>`<td class="r num">${metric(r,k)}</td>`).join('')}</tr>`).join('');
 const timing=(s.timing_comparisons||[]).map(t=>`<section class="timing-block" aria-label="Previous-run CPU comparison"><h3>${esc(t.label)}</h3><span class="scope-badge">PREVIOUS MODEL &amp; TEST SET · TIMING ONLY</span><p class="timing-note">${esc(t.note)}</p><div class="tbl-wrap" tabindex="0" role="region" aria-label="Scrollable paired CPU timing table"><table class="timing-table"><caption class="sr-only">Previous-run timing on ${t.tables} matched tables; not current ID/OOD accuracy results</caption><thead><tr><th scope="col">Method</th><th scope="col">Configuration</th><th scope="col" class="r">Median time / table</th><th scope="col" class="r">Median paired ratio</th></tr></thead><tbody>${t.rows.map(r=>`<tr><td>${esc(r.method)}</td><td>${esc(r.configuration)}</td><td class="r num">${r.median_time_s.toFixed(3)} s</td><td class="r num">${r.median_paired_ratio.toFixed(2)}×</td></tr>`).join('')}</tbody></table></div><p class="data-footnote">${t.tables} matched tables · ${t.threads} CPU threads · ${esc(t.hardware)}. Source: ${esc(t.source_table)}. These values do not enter the current-run charts or rankings.</p></section>`).join('');
 const facts=[['Target',s.target],['Sampling',s.sample_design],['ID / Source-OOD',s.split_definition],['Generator scope',s.generator_scope],['Aggregation',s.aggregation],['Variance / SE',s.variance_note],['Coverage uncertainty',s.coverage_note],['Runtime',s.hardware+'. '+s.timing_scope+'.'],['Baseline availability',s.comparison_note],['Source status',s.source.verification]];
 container.innerHTML=`<div class="section-label">SOURCE-REPORTED EVALUATION</div><h2>Results, in context.</h2><div class="release-meta"><span>${esc(s.source.title)}</span><span>· ${esc(s.source.author)} · ${esc(s.source.date)}</span><a href="data/results.json" download="statistical-inference-arena-results.json">Download source-reported data ↗</a></div><details><summary>MediPFN results by DGP <span class="muted">· ${dd.length} configurations in the current filter</span></summary><div class="detail-inner"><p>Transcribed from Table 2 (Source-OOD) and Table 5 (ID). SE is shown here exactly as reported, not as Variance. Aggregate results above are taken directly from Table 1; they are not calculated from these rounded rows. RF per-DGP values are not supplied.</p><div class="tbl-wrap" tabindex="0" role="region" aria-label="Scrollable DGP results"><table class="detail-table"><thead>${dgpHead}</thead><tbody>${dgpRows||'<tr><td colspan="8">No reported per-DGP results for this filter.</td></tr>'}</tbody></table></div></div></details>${timing}<details><summary>Evaluation protocol &amp; source notes</summary><div class="detail-inner"><dl class="release-facts">${facts.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v||'Not reported')}</dd>`).join('')}</dl></div></details>`;
}
const baseRenderResults=renderResults;
renderResults=function(){baseRenderResults();renderReleaseDetails();};
const baseRender=render;
render=function(){
 baseRender();
 const s=current(),context=document.getElementById('release-context');
 context.hidden=!s?.source;
 if(s?.source){
  context.innerHTML='<strong>Report date: '+esc(s.source.date)+'.</strong> '+esc(s.sample_design)+' <strong>Random Forest current-run metrics are not reported.</strong> Its previous-run paired CPU timings are shown separately. <a href="#report-details">Source &amp; timing details ↘</a>';
  document.getElementById('view-note').textContent='OOD = Source-OOD · '+s.source.date;
  document.getElementById('table-note').textContent='Variance ≈ (rounded reported SE)², not an exact raw variance. Nominal coverage: 95%; coverage Monte Carlo SE: 0.66 pp (ID), 0.45 pp (Source-OOD). Time: GPU warm-start mean on A40/L40S; excludes loading, warm-up and data generation. Blank Random Forest entries are not reported, not zero. Full protocol below.';
  const measured=new Set((s.rows||[]).filter(r=>number(r.rmse)).map(r=>r.method_id||r.method));
  document.querySelector('[data-card="ranking"] .card-bottom>span').textContent=measured.size===1?'One reported method · no comparative rank':'Within each test split';
 }else{
  context.innerHTML='';
  document.querySelector('[data-card="ranking"] .card-bottom>span').textContent='Within each test split';
 }
 if(DATA.suites.length===1&&DATA.suites[0].domain==='mediation'&&!loadError){
  document.getElementById('release-status').textContent='FIRST RESULTS · MEDIATION';
  document.getElementById('release-description').textContent='MediPFN · November 12 report. Previous-run Random Forest CPU comparison reported separately.';
 }
 for(const b of document.querySelectorAll('[data-t]')){
  const hasResults=DATA.suites.some(x=>x.domain===b.dataset.t&&x.rows.some(r=>number(r.rmse)));
  b.classList.toggle('has-results',hasResults);
  b.title=hasResults?'Reported results available':'Results not yet published';
 }
};
try{DATA=validate(DATA);render();}catch(e){loadError='Unable to validate reported result metadata.';render();console.error(e);}
