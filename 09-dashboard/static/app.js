/* Same-origin frontend: every metric and action comes from the Python API. */
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = (cents) => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format((cents || 0)/100);
const when = (timestamp) => new Date(timestamp * 1000).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const titles = {overview:['Operations overview','A clear view of the customer journey, from payment to access.'],customers:['Your customers','Membership, payment health and access, in one place.'],events:['Payment events','Trace every simulated event and inspect the data behind it.'],access:['Access & recovery','Find the failed step. Restore the customer journey.'],revenue:['Revenue intelligence','Recurring revenue and collections calculated from your demo records.'],ai:['AI workspace','Try the suite’s offline tools, with their sources and limitations visible.']};
let state = null, page = 'overview', search = '', filter = 'all', toastTimer;
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Demo-Action':'1'},body:JSON.stringify(body)});
  let data; try { data = await response.json(); } catch { throw new Error('The backend returned an unreadable response.'); }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your inputs and try again.');
  return data;
}
function toast(message) { $('#toast').textContent=message; $('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5000); }
function badge(value) {
  const type = ['active','processed','granted','synced','pass'].includes(value) ? 'good' : ['failed','dead','revoked','fail'].includes(value) ? 'bad' : ['past_due','received','skipped'].includes(value) ? 'warn' : 'blue';
  return `<span class="badge ${type}">${esc(value.replaceAll('_',' '))}</span>`;
}
function metric(label,value,note,icon) { return `<article class="metric"><div class="metric-label">${esc(label)}<span class="metric-icon">${icon}</span></div><div class="metric-value">${esc(value)}</div><div class="metric-note">${esc(note)}</div></article>`; }
function panel(title, subtitle, body, action='') { return `<article class="panel"><div class="panel-heading"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div>${action}</div>${body}</article>`; }
function table(headings, rows, empty='No records to show.') { return rows.length ? `<div class="table-wrap"><table><thead><tr>${headings.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>` : `<div class="empty">${esc(empty)}</div>`; }
function person(c) { return `<div class="person"><span class="avatar">${esc(c.name.split(' ').map(x=>x[0]).slice(0,2).join(''))}</span><div><strong>${esc(c.name)}</strong><small>${esc(c.email || c.id)}</small></div></div>`; }
function customerTable(customers) { return table(['Customer','Plan','Status','Community access',''],customers.map(c=>`<tr><td>${person(c)}</td><td>${esc(c.plan)}</td><td>${badge(c.status)}</td><td>${badge(c.access ? 'granted':'revoked')}</td><td><button class="row-link" data-customer="${esc(c.id)}">View journey ↗</button></td></tr>`),'No customers match this search.'); }
function eventTable(events) { return table(['Event','Customer','Status','Attempts',''],events.map(e=>`<tr><td><strong>${esc(e.type)}</strong><div class="event-meta">${when(e.created)} · <span class="mono">${esc(e.id.slice(-12))}</span></div></td><td class="mono">${esc(e.customer_id)}</td><td>${badge(e.status)}</td><td>${e.attempts}</td><td><button class="row-link" data-event="${esc(e.id)}">Inspect ↗</button></td></tr>`),'No events match this filter.'); }
function chart() {
  const data = state.chart, max = Math.max(...data.map(d=>d.collected_cents),10000), width=600, height=145;
  const points = data.map((d,i)=>`${40+i*90},${height-10-(d.collected_cents/max)*(height-35)}`);
  const grid=[0,.5,1].map(n=>`<line x1="40" x2="580" y1="${height-10-n*(height-35)}" y2="${height-10-n*(height-35)}" stroke="#e9eee3" stroke-dasharray="4 5"/><text x="0" y="${height-6-n*(height-35)}" fill="#95a188" font-size="9">${esc(money(max*n))}</text>`).join('');
  return `<div class="chart" role="img" aria-label="Daily simulated collections over the last seven days"><svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#badc9a" stop-opacity=".55"/><stop offset="100%" stop-color="#edf6e3" stop-opacity=".2"/></linearGradient></defs>${grid}<polygon points="40,${height-10} ${points.join(' ')} 580,${height-10}" fill="url(#fill)"/><polyline points="${points.join(' ')}" fill="none" stroke="#7ca559" stroke-width="2.5" vector-effect="non-scaling-stroke"/>${points.map((point,i)=>`<circle cx="${point.split(',')[0]}" cy="${point.split(',')[1]}" r="3.5" fill="#7ca559"><title>${esc(data[i].day)}: ${esc(money(data[i].collected_cents))}</title></circle>`).join('')}</svg></div><div class="chart-labels">${data.map(d=>`<span>${esc(d.day.slice(5))}</span>`).join('')}</div>`;
}
function failedRows() {
  const failures=state.events.filter(e=>['failed','received','dead'].includes(e.status));
  return failures.length ? failures.map(e=>`<div class="alert-row"><div><strong>${esc(e.customer_id)}</strong><p>${esc(e.error || 'Stored event waiting for processing.')}</p><span class="mono">${esc(e.id)} · Attempt ${e.attempts} / 5</span></div>${['failed','received'].includes(e.status)?`<button class="secondary" data-retry="${esc(e.id)}">Retry event ↗</button>`:badge('dead')}</div>`).join('') : '<div class="empty">All clear. No events need recovery.</div>';
}
function renderOverview() {
  const active=state.customers.filter(c=>c.status==='active').length, failed=state.events.filter(e=>e.status==='failed').length;
  return `<div class="metrics">${metric('Monthly recurring revenue',money(state.revenue.mrr_cents),'USD · annual plans normalized monthly','↗')}${metric('Active customers',active,`${state.customers.length} total customer records`,'◎')}${metric('Community members',state.customers.filter(c=>c.access).length,'Includes past-due members during dunning','◇')}${metric('Events needing recovery',failed,failed?'A simulated outage is ready to retry':'All simulated deliveries processed','⇄')}</div><div class="grid-two">${panel('Collections at a glance','Actual values from your synthetic event history',`<div class="panel-body"><div class="chart-key">● Collected · last 7 days</div><div class="chart-total">${money(state.chart.reduce((n,d)=>n+d.collected_cents,0))}</div>${chart()}</div>`, '<button class="text-btn" data-page="revenue">View revenue ↗</button>')}${panel('The customer journey','One connected lifecycle',`<div class="panel-body"><div class="pipeline-step"><span class="step-icon">1</span><div><strong>Payment event</strong><small>Recorded in the event log</small></div><span class="step-stat">${state.events.length} events</span></div><div class="pipeline-step"><span class="step-icon">2</span><div><strong>CRM sync</strong><small>Customer status and plan</small></div><span class="step-stat">${state.customers.filter(c=>c.crm_synced).length} synced</span></div><div class="pipeline-step"><span class="step-icon">3</span><div><strong>Community access</strong><small>Granted or revoked by code</small></div><span class="step-stat">${state.customers.filter(c=>c.access).length} members</span></div><div class="pipeline-note">Simulated payment input → Python processor → local CRM & membership records.</div></div>`)}</div>${panel('Recent customer activity','The latest events flowing through your operations',eventTable(state.events.slice(0,5)),'<button class="text-btn" data-page="events">All events ↗</button>')}${panel('Needs attention','Recover a failed delivery without creating a duplicate customer.',`<div style="height:16px"></div>${failedRows()}`)}`;
}
function renderCustomers() {
  const rows=state.customers.filter(c=>(filter==='all'||c.status===filter)&&[c.name,c.email,c.id].join(' ').toLowerCase().includes(search.toLowerCase()));
  return panel('Customer directory',`${rows.length} matching members · synthetic data`, `<div class="toolbar"><input id="search" aria-label="Search customers" placeholder="Search by name, email or customer ID" value="${esc(search)}"><select id="filter" aria-label="Filter customer status">${['all','active','past_due','canceled'].map(x=>`<option value="${x}" ${filter===x?'selected':''}>${x==='all'?'All statuses':x.replaceAll('_',' ')}</option>`).join('')}</select></div>${customerTable(rows)}`);
}
function renderEvents() {
  const events=state.events.filter(e=>(filter==='all'||e.status===filter)&&[e.id,e.customer_id,e.type].join(' ').toLowerCase().includes(search.toLowerCase()));
  return panel('Event ledger',`${events.length} events · newest first`, `<div class="toolbar"><input id="search" aria-label="Search events" placeholder="Search customer, event ID or event type" value="${esc(search)}"><select id="filter" aria-label="Filter event status">${['all','processed','failed','received','dead','ignored'].map(x=>`<option value="${x}" ${filter===x?'selected':''}>${x==='all'?'All statuses':x}</option>`).join('')}</select></div>${eventTable(events)}`);
}
function renderAccess() {
  return panel('Recovery queue','Failures are persisted. Retries reuse the original event ID.',`<div style="height:16px"></div>${failedRows()}`)+panel('Access reconciliation','Compare customer entitlements, local CRM and community membership.',`<div class="panel-body">${state.issues.length?state.issues.map(i=>`<div class="issue">${badge(i.severity==='high'?'failed':'past_due')} <strong>${esc(i.kind.replaceAll('_',' '))}</strong><p>${esc(i.detail)}</p></div>`).join(''):'<p>✓ No drift detected across the local demo systems.</p>'}<p class="small muted">Past-due customers retain access during dunning. Canceled customers lose access.</p></div>`)+panel('Membership access','Current access records from the local simulated community provider.',customerTable(state.customers));
}
function renderRevenue() {
  const r=state.revenue;
  return `<div class="metrics">${metric('Current MRR',money(r.mrr_cents),'USD · current demo subscription state','↗')}${metric('Collected today',money(r.collected_cents),'Processed signup and invoice events','◇')}${metric('Failed payments today',money(r.failed_cents),`${r.failed_count} failed payment events`,'⇄')}${metric('Customers churned today',r.churned_customers,'Cancellation events recorded today','◎')}</div>${panel('Seven-day collections','Cash collection events, not recurring revenue forecasts.',`<div class="panel-body">${chart()}</div>`)}<div class="grid-two">${panel('Subscription revenue','Monthly contribution by membership plan.',table(['Plan','Paying members','Monthly revenue'],['basic','pro','annual'].map(plan=>{const cs=state.customers.filter(c=>c.plan===plan&&c.status!=='canceled');return `<tr><td>${esc(plan)}</td><td>${cs.length}</td><td>${money(cs.reduce((n,c)=>n+c.monthly_cents,0))}</td></tr>`;})))}${panel('How to read these numbers','Transparent calculations for an interview walkthrough.',`<div class="panel-body"><p class="small">Annual subscriptions are divided by 12. Past-due subscriptions remain in MRR during dunning; canceled subscriptions are excluded.</p><p class="small muted">All prices are illustrative USD. This demo records collections at signup and on simulated paid invoices. It does not model refunds, taxes, expansion, or historical plan changes.</p><p class="small muted">Revenue reporting runs in Python using the existing reporting module.</p></div>`)}</div>`;
}
function renderAI() {
  return '<div class="tool-grid">'+[
    ['classify','Conversation classifier','KEYWORD BASELINE','Classify a customer message into intent, support or churn risk.','This membership is too expensive for my budget.','Classify message'],
    ['coach','Coaching knowledge','RETRIEVAL + CITATIONS','Retrieve sample coaching notes with source references.','How do I decide what to delegate?','Find coaching context'],
    ['copilot','Sales reply copilot','SYNTHETIC WON DEALS','Find replies that preceded wins in the sample conversations.','The price is too expensive for us.','Suggest a reply'],
    ['evaluate','Coaching evaluations','OFFLINE REGRESSION CHECKS','Check retrieval, valid citations and out-of-scope handling.','','Run evaluations']
  ].map(([key,title,tag,desc,value,button])=>panel(title,desc,`<div class="panel-body"><span class="tool-tag">${tag}</span><p class="small muted">${key==='evaluate'?'Live-model cases are skipped; no paid API calls.':'Runs locally. No live model or external API is called.'}</p><form data-tool="${key}">${key==='evaluate'?'':`<label for="text-${key}">${key==='coach'?'Your question':'Message'}</label><textarea id="text-${key}" required maxlength="4000">${esc(value)}</textarea>`}<button class="primary" type="submit">${button} →</button></form><div id="result-${key}" class="tool-result" role="status"></div></div>`)).join('')+'</div>';
}
function render() {
  if(!state)return;
  const [title,desc]=titles[page];$('#page-title').textContent=title;$('#page-description').textContent=desc;$('#crumb').textContent=page==='ai'?'AI workspace':page==='access'?'Access & recovery':page[0].toUpperCase()+page.slice(1);
  document.querySelectorAll('nav button').forEach(b=>{b.classList.toggle('active',b.dataset.page===page);b.setAttribute('aria-current',b.dataset.page===page?'page':'false');});
  $('#failed-count').textContent=state.events.filter(e=>e.status==='failed').length||'';
  $('#view').innerHTML=({overview:renderOverview,customers:renderCustomers,events:renderEvents,access:renderAccess,revenue:renderRevenue,ai:renderAI}[page])();
  $('#last-updated').textContent='Backend connected · updated '+new Date(state.updated_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
}
async function refresh() {
  $('#refresh').disabled=true;
  try { state=await api('/api/dashboard');$('#error-banner').hidden=true;render(); }
  catch(e){$('#error-banner').textContent='Could not load the dashboard: '+e.message+' Use refresh to retry.';$('#error-banner').hidden=false;}
  finally{$('#refresh').disabled=false;}
}
function navigate(next) { if(!titles[next])next='overview';page=next;search='';filter='all';location.hash=page;render(); }
function showSimulator() {
  if(!state)return toast('Wait for the backend connection, then retry.');
  $('#simulation-error').textContent='';$('#customer-select').innerHTML=state.customers.filter(c=>c.status!=='canceled').map(c=>`<option value="${esc(c.id)}">${esc(c.name)} · ${esc(c.id)}</option>`).join('');$('#simulator').showModal();
}
async function inspectEvent(id) {
  const e=await api('/api/events/'+encodeURIComponent(id));$('#detail-title').textContent='Event inspection';
  $('#detail-body').innerHTML=`<p class="mono">${esc(e.id)}</p><div class="summary-line"><span>Processing status</span>${badge(e.status)}</div><div class="summary-line"><span>Attempts</span><strong>${e.attempts} / 5</strong></div>${e.error?`<p class="error-text">${esc(e.error)}</p>`:''}<label>Stored synthetic payload</label><pre>${esc(JSON.stringify(e.payload,null,2))}</pre><div class="modal-actions">${['failed','received'].includes(e.status)?`<button class="primary" data-retry="${esc(e.id)}">Retry this event</button>`:''}<button class="secondary" data-replay="${esc(e.id)}">Check duplicate guard</button></div><p class="small muted">This simulation uses the event processor directly. It does not verify a real Stripe webhook.</p>`;$('#detail').showModal();
}
function inspectCustomer(id) {
  const c=state.customers.find(c=>c.id===id);$('#detail-title').textContent=c.name+' · customer journey';
  $('#detail-body').innerHTML=`<p class="mono">${esc(id)}</p><div class="summary-line"><span>Subscription</span>${badge(c.status)}</div><div class="summary-line"><span>Community access</span>${badge(c.access?'granted':'revoked')}</div><div class="summary-line"><span>CRM</span>${badge(c.crm_synced?'synced':'failed')}</div><label>Event timeline</label><div class="timeline">${state.events.filter(e=>e.customer_id===id).slice().reverse().map(e=>`<div><strong class="small">${esc(e.type)}</strong><p class="small muted">${when(e.created)} · ${badge(e.status)}</p><button class="row-link" data-event="${esc(e.id)}">Inspect event ↗</button></div>`).join('')}</div>`;$('#detail').showModal();
}
document.addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.page)return navigate(b.dataset.page);
  if(b.dataset.close)return $('#'+b.dataset.close).close();
  if(b.dataset.customer)return inspectCustomer(b.dataset.customer);
  b.disabled=true;
  try {
    if(b.dataset.event){if($('#detail').open)$('#detail').close();await inspectEvent(b.dataset.event);}
    if(b.dataset.retry){const r=await api('/api/events/'+encodeURIComponent(b.dataset.retry)+'/retry',{});if($('#detail').open)$('#detail').close();await refresh();toast(r.status==='processed'?'Event recovered. Customer, CRM and access updated.':'Retry recorded: '+r.status);}
    if(b.dataset.replay){const r=await api('/api/events/'+encodeURIComponent(b.dataset.replay)+'/replay',{});toast(r.message);}
  } catch(e){toast(e.message);}finally{b.disabled=false;}
});
document.addEventListener('input',event=>{
  if(event.target.id==='search'){const start=event.target.selectionStart;search=event.target.value;render();$('#search').focus();$('#search').setSelectionRange(start,start);}
});
document.addEventListener('change',event=>{if(event.target.id==='filter'){filter=event.target.value;render();}});
$('#scenario').addEventListener('change',()=>{const isNew=['checkout','access_failure'].includes($('#scenario').value);$('#plan-field').hidden=!isNew;$('#customer-field').hidden=isNew;});
$('#simulate-form').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;$('#simulation-error').textContent='';
  try{const result=await api('/api/simulate',{scenario:$('#scenario').value,plan:$('#plan').value,customer_id:$('#customer-select').value||null});$('#simulator').close();await refresh();toast(result.status==='failed'?'Simulated outage recorded. Open Access & recovery to retry.':'Event processed. Dashboard updated.');}
  catch(error){$('#simulation-error').textContent=error.message;}finally{button.disabled=false;}
});
document.addEventListener('submit',async e=>{
  const tool=e.target.dataset.tool;if(!tool)return;e.preventDefault();const b=e.submitter,box=$('#result-'+tool);b.disabled=true;box.textContent='Running local backend…';
  try{
    const data=await api('/api/tools/'+tool,tool==='evaluate'?{}:{text:$('#text-'+tool).value});
    if(tool==='classify')box.innerHTML=`${badge(data.label)}<small>${esc(data.note)}</small>`;
    if(tool==='coach')box.innerHTML=`<strong>${esc(data.refused?'Outside the sample knowledge base':'Retrieved coaching context')}</strong><p>${esc(data.text)}</p><small>Sources: ${esc(data.retrieved.join(', ')||'none')}<br>${esc(data.note)}</small>`;
    if(tool==='copilot')box.innerHTML=`<strong>${esc(data.objection?'Objection: '+data.objection.replaceAll('_',' '):'No recognized objection')}</strong>${data.suggestions.map(s=>`<p>${esc(s.text)}</p><small>Sample source: ${esc(s.conversation||s.source)}</small>`).join('')}${data.note?`<p>${esc(data.note)}</p>`:''}<small>${esc(data.mode)}</small>`;
    if(tool==='evaluate')box.innerHTML=`<strong>${data.passed} / ${data.total} offline checks passed · ${data.skipped} live-only skipped</strong><small>${esc(data.note)}</small>${data.cases.map(c=>`<div class="eval-case">${badge(c.skipped?'skipped':c.passed?'pass':'fail')}${esc(c.question)}${c.failures.length?'<p>'+esc(c.failures.join('; '))+'</p>':''}</div>`).join('')}`;
  }catch(error){box.textContent=error.message;}finally{b.disabled=false;}
});
$('#refresh').addEventListener('click',refresh);$('#open-simulator').addEventListener('click',showSimulator);
$('#reset').addEventListener('click',async()=>{if(!confirm('Reset all synthetic customers and events to the starting demo?'))return;$('#reset').disabled=true;try{await api('/api/reset',{confirm:true});await refresh();toast('Demo reset. Ready for a new walkthrough.');}catch(e){toast(e.message);}finally{$('#reset').disabled=false;}});
window.addEventListener('hashchange',()=>{const next=location.hash.slice(1);if(titles[next]&&next!==page){page=next;search='';filter='all';render();}});
if(titles[location.hash.slice(1)])page=location.hash.slice(1);
refresh();
