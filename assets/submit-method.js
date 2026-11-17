'use strict';
/* Separate from the leaderboard. No GitHub credentials, local storage or public inbox. */
(() => {
  const trigger = document.getElementById('submit-method-btn');
  if (!trigger) return;
  const dialog = document.createElement('dialog');
  dialog.id = 'method-submit-dialog';
  dialog.setAttribute('aria-labelledby', 'ms-title');
  dialog.setAttribute('aria-describedby', 'ms-intro');
  dialog.innerHTML = `<div class="ms-heading"><h2 id="ms-title">Submit a method</h2><button type="button" class="ms-close" aria-label="Close submission form">×</button></div>
    <p class="ms-intro" id="ms-intro">Send a Hugging Face model link to the evaluation team. Submissions are not published on the leaderboard.</p>
    <form id="method-submit-form" novalidate>
      <label for="ms-url">Hugging Face model link</label>
      <input id="ms-url" name="huggingface_url" type="url" required maxlength="1024" placeholder="https://huggingface.co/owner/model" autocomplete="off" spellcheck="false" aria-describedby="ms-status">
      <div class="ms-honeypot" aria-hidden="true"><label for="ms-website">Leave empty</label><input id="ms-website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
      <div class="ms-challenge" id="ms-challenge"></div>
      <p class="ms-status" id="ms-status" role="status" aria-live="polite"></p>
      <div class="ms-actions"><button type="button" class="ms-cancel">Cancel</button><button type="submit" class="ms-send" disabled>Submit</button></div>
    </form>`;
  document.body.append(dialog);
  const form = dialog.querySelector('form'), input = dialog.querySelector('#ms-url');
  const status = dialog.querySelector('#ms-status'), send = dialog.querySelector('.ms-send');
  let config = null, widget = null, token = '', busy = false, domain = '', challengePromise;
  const notReady = 'Submissions are not open yet. Nothing has been sent.';
  const message = (text, kind = '') => { status.textContent = text; status.dataset.kind = kind; };
  function canonicalURL(value) {
    if (typeof value !== 'string' || value.length > 1024 || /[\s\\<>\x00-\x1f\x7f]/.test(value.trim())) return null;
    try {
      const u = new URL(value.trim());
      if (u.protocol !== 'https:' || u.hostname !== 'huggingface.co' || u.port || u.username || u.password || u.search || u.hash) return null;
      const path = u.pathname.replace(/\/$/, '');
      if (!/^\/[A-Za-z0-9][A-Za-z0-9_-]*\/[A-Za-z0-9][A-Za-z0-9._-]*(?:\/tree\/[A-Za-z0-9][A-Za-z0-9._-]*)?$/.test(path)) return null;
      if (['spaces','datasets','organizations','api','settings','collections','join','login'].includes(path.split('/')[1].toLowerCase()) || path.includes('..')) return null;
      return 'https://huggingface.co' + path;
    } catch (_) { return null; }
  }
  function updateSend() { send.disabled = !config || !token || busy || !canonicalURL(input.value); }
  function loadChallenge() {
    if (window.turnstile) return Promise.resolve();
    if (challengePromise) return challengePromise;
    challengePromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      const timer = setTimeout(() => reject(new Error('Verification unavailable')), 15000);
      script.onload = () => { clearTimeout(timer); window.turnstile ? resolve() : reject(new Error('Verification unavailable')); };
      script.onerror = () => { clearTimeout(timer); reject(new Error('Verification unavailable')); };
      document.head.append(script);
    });
    return challengePromise;
  }
  async function prepare() {
    message('Checking submission availability…');
    try {
      const response = await fetch('assets/submission-config.json', {cache: 'no-store', credentials: 'omit', signal: AbortSignal.timeout(8000)});
      if (!response.ok) throw new Error('Configuration unavailable');
      const c = await response.json();
      if (c.enabled !== true || !c.endpoint || !c.turnstileSiteKey) { message(notReady); return; }
      const u = new URL(c.endpoint);
      if (u.protocol !== 'https:' || u.username || u.password || u.search || u.hash || u.pathname !== '/api/submit') throw new Error('Invalid endpoint');
      config = {endpoint: u.href, siteKey: c.turnstileSiteKey};
      await loadChallenge();
      if (!dialog.open) return;
      if (widget === null) {
        widget = window.turnstile.render('#ms-challenge', {
          sitekey: config.siteKey, action: 'method_submit', 'response-field': false,
          theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
          callback: value => { token = value; if (!['success','error'].includes(status.dataset.kind)) message(''); updateSend(); },
          'expired-callback': () => { token = ''; message('Please complete verification again.'); updateSend(); },
          'error-callback': () => { token = ''; message('Verification unavailable. Please try again.', 'error'); updateSend(); }
        });
      } else { window.turnstile.reset(widget); }
      message('Complete verification to submit.');
    } catch (_) { config = null; message('The submission service is unavailable. Nothing has been sent.', 'error'); }
    updateSend();
  }
  trigger.addEventListener('click', () => {
    if (dialog.open) return;
    domain = document.querySelector('#tabs [aria-selected="true"]')?.dataset.t || '';
    config = null; token = ''; send.disabled = true;
    dialog.showModal(); trigger.setAttribute('aria-expanded', 'true'); input.focus();
    prepare();
  });
  const close = () => { if (!busy) dialog.close(); };
  dialog.querySelector('.ms-close').addEventListener('click', close);
  dialog.querySelector('.ms-cancel').addEventListener('click', close);
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  dialog.addEventListener('close', () => { trigger.setAttribute('aria-expanded', 'false'); trigger.focus(); });
  input.addEventListener('input', () => { input.setCustomValidity(''); updateSend(); });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    if (!config) { message(notReady); return; }
    const url = canonicalURL(input.value);
    if (!url) { input.setCustomValidity('Enter a Hugging Face model URL without query parameters or credentials.'); input.reportValidity(); return; }
    if (!token) { message('Complete verification before submitting.'); return; }
    busy = true; updateSend(); send.textContent = 'Submitting…';
    message('Sending your link…');
    try {
      const response = await fetch(config.endpoint, {
        method: 'POST', mode: 'cors', credentials: 'omit', referrerPolicy: 'no-referrer',
        headers: {'Content-Type': 'application/json', 'X-Arena-Submission': '1'},
        body: JSON.stringify({huggingface_url: url, domain, turnstile_token: token, website: form.elements.website.value}),
        signal: AbortSignal.timeout(25000)
      });
      const result = await response.json();
      if (response.status !== 201 || result.ok !== true || !/^[0-9a-f-]{36}$/.test(result.receipt || '')) {
        throw new Error(response.status === 429 ? 'Too many attempts. Please try again later.' : 'We could not confirm your submission. Please try again.');
      }
      form.reset();
      message('Submitted privately to the evaluation team. Receipt: ' + result.receipt, 'success');
    } catch (error) {
      message(error.name === 'TimeoutError' || error.name === 'TypeError' ? 'We could not confirm receipt. Please try again later.' : error.message, 'error');
    } finally {
      busy = false; token = ''; send.textContent = 'Submit'; updateSend();
      if (widget !== null && window.turnstile) window.turnstile.reset(widget);
    }
  });
})();
