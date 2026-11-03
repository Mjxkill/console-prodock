'use strict';

// All report content is text, including evidence. Never interpret log HTML.
const $ = id => document.getElementById(id);
const node = (tag, text, cls) => {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = String(text);
  if (cls) item.className = cls;
  return item;
};
const LABELS = {
  PASS: 'Réussi', FAIL: 'Échec', FAILED: 'Échec', RUNNING: 'En cours',
  ACTIVE: 'Actif', PREPARED: 'Préparé', PENDING: 'En attente', TODO: 'À faire',
  UNKNOWN: 'Inconnu', INCONNU: 'Inconnu', IDLE: 'Au repos', BLOCKED: 'Bloqué',
  REVIEW_PENDING: 'À revoir', COMPLETED: 'Terminé, à revoir', VERIFIED: 'Vérifié',
  ACCEPTED: 'Accepté', ACCEPTED_AFTER_CHANGES: 'Accepté après corrections', REJECTED: 'Rejeté',
  REVIEW_INCONCLUSIVE: 'Revue non concluante', REVIEW_UNKNOWN: 'Revue non vérifiable',
  NOT_TESTED: 'Non testé', MIXED: 'Partiel', PARTIAL: 'Partiel', STALE: 'Périmé', INTERRUPTED: 'Interrompu',
  OBSERVED: 'Observé', ROUTED: 'Routé, à qualifier', TIMING_PASS: 'Timing réussi', PLANNED: 'Prévu',
  IMPLEMENTED: 'Implémenté', HOST_VALIDATED: 'Validé sur hôte', NO_GAIN: 'Gain non démontré',
  STARTING: 'Démarrage', FINALIZING: 'Finalisation', STOPPED: 'Arrêté', NO_ACTIVE: 'Inactif', INCOMPLETE: 'Incomplet',
  ABSENT: 'Absent', NO_PROCESS: 'Processus absent', SIMULATION_PASS: 'Simulation réussie'
};
const LEVELS = {simulation: 'Simulation', hardware: 'Sur carte', timing: 'Timing',
  local: 'Logiciel local', visual: 'Visuel', synthesis: 'Synthèse', software: 'Logiciel',
  rtl: 'Simulation RTL', integration: 'Intégration', host: 'Sur hôte',
  performance: 'Performance', planned: 'Prévu', review: 'Revue', transfer: 'Transfert'};
let data = null;
let inFlight = false;
let lastHeartbeat = 0;
let collectionHealthy = false;
let signature = null;

function elapsedNode(tag, worker) {
  const item = node(tag, duration(worker.elapsed_s));
  if (category(worker.state) === 'running' && typeof worker.elapsed_s === 'number') {
    item.dataset.elapsed = worker.elapsed_s;
    item.dataset.observed = Date.now();
  }
  return item;
}

function category(status) {
  const key = String(status || 'UNKNOWN').toUpperCase();
  if (['PASS', 'VERIFIED', 'VALIDATED', 'ACCEPTED', 'ACCEPTED_AFTER_CHANGES', 'DONE'].includes(key)) return 'pass';
  if (['FAIL', 'FAILED', 'BLOCKED', 'ERROR', 'REJECTED'].includes(key)) return 'fail';
  if (['RUNNING', 'ACTIVE'].includes(key)) return 'running';
  if (['PENDING', 'PREPARED', 'TODO', 'PLANNED', 'NOT_TESTED', 'REVIEW_PENDING', 'MIXED', 'PARTIAL', 'STALE'].includes(key)) return 'pending';
  return 'neutral';
}

function badge(status) {
  return node('span', LABELS[String(status).toUpperCase()] || status || 'Inconnu', 'badge ' + category(status));
}

function date(value) {
  if (value === null || value === undefined || value === '') return 'Non renseigné';
  const when = new Date(typeof value === 'number' ? value * 1000 : value);
  return Number.isNaN(when.getTime()) ? String(value) : when.toLocaleString('fr-FR', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'});
}

function duration(value) {
  if (typeof value !== 'number') return '—';
  const seconds = Math.max(0, Math.floor(value));
  if (seconds < 60) return seconds + ' s';
  return (seconds >= 3600 ? Math.floor(seconds / 3600) + ' h ' : '') + Math.floor(seconds / 60) % 60 + ' min';
}

function readable(value) {
  if (value === null || value === undefined) return 'Non renseigné';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(readable).join(' · ');
  return Object.entries(value).map(([key, val]) => key + ' : ' + readable(val)).join(' · ');
}

function evidenceButton(path) {
  if (!path || typeof path !== 'string') return node('span', '—');
  const button = node('button', 'Voir la preuve ↗', 'evidence');
  button.type = 'button'; button.title = path;
  button.onclick = () => openEvidence(path);
  return button;
}

function appendEvidence(parent, evidence) {
  if (evidence && typeof evidence === 'object' && !Array.isArray(evidence)) {
    const button = node('button', 'Détails activité ↗', 'evidence');
    button.type = 'button';
    button.onclick = () => {
      $('evidencePath').textContent = 'Observation du worker';
      $('evidenceMeta').textContent = 'Identité du processus et origine des compteurs ; aucune commande ni clé exposée.';
      $('evidenceText').textContent = JSON.stringify(evidence, null, 2);
      $('evidenceDialog').showModal();
    };
    parent.append(button); return;
  }
  const paths = Array.isArray(evidence) ? evidence : [evidence];
  for (const path of paths) if (typeof path === 'string' && path) parent.append(evidenceButton(path));
}

async function openEvidence(path) {
  $('evidencePath').textContent = path;
  $('evidenceMeta').textContent = '';
  $('evidenceText').textContent = 'Lecture…';
  $('evidenceDialog').showModal();
  try {
    const response = await fetch('/api/evidence?path=' + encodeURIComponent(path));
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Preuve indisponible');
    $('evidenceMeta').textContent = result.bytes + ' octets · ' + (result.truncated ? 'Extrait de fin uniquement' : 'SHA-256 ' + result.sha256);
    $('evidenceText').textContent = result.text;
  } catch (error) { $('evidenceText').textContent = error.message; }
}

function overview() {
  const topics = data.topics || [], workers = data.workers || [];
  const features = topics.flatMap(t => t.features || []);
  const tests = features.flatMap(f => f.tests || []);
  const active = workers.filter(w => category(w.state) === 'running').length;
  $('totals').replaceChildren();
  for (const [label, value, note] of [
    ['Chantiers suivis', topics.length, 'Cartes et logiciel distincts'],
    ['Fonctionnalités recensées', features.length, 'État et périmètre documentés'],
    ['Résultats de tests référencés', tests.length, 'Réussites et échecs conservés'],
    ['Workers actifs vérifiés', active, 'Processus observés, pas supposés']
  ]) {
    const box = node('div', undefined, 'stat');
    box.append(node('span', label), node('strong', value), node('small', note));
    $('totals').append(box);
  }
  $('topics').replaceChildren();
  for (const topic of topics) {
    const article = node('article', undefined, 'topic');
    const top = node('div', undefined, 'topic-top');
    const title = node('div', undefined, 'topic-title');
    title.append(node('h2', topic.title), badge(topic.status));
    const loaded = node('div', undefined, 'loaded');
    loaded.append(node('b', 'VERSION OBSERVÉE SUR CARTE'), node('span', readable(topic.loaded)));
    top.append(title, node('p', topic.summary), loaded);
    const body = node('div', undefined, 'topic-body');
    for (const [key, label] of [['done', 'RÉALISÉ / CONSTATÉ'], ['next', 'PROCHAINES ÉTAPES']]) {
      const group = node('div');
      const list = node('ul', undefined, 'checklist ' + key);
      for (const text of topic[key] || []) list.append(node('li', readable(text)));
      group.append(node('div', label, 'section-label'), list); body.append(group);
    }
    const link = node('a', 'Fonctionnalités, tests et preuves →', 'topic-link');
    link.href = '#features';
    link.onclick = () => { $('topicFilter').value = topic.id; renderFeatures(); };
    body.append(link); article.append(top, body); $('topics').append(article);
  }
  $('workersPreview').replaceChildren();
  const ordered = [...workers].sort((a, b) => (category(b.state) === 'running') - (category(a.state) === 'running')).slice(0, 5);
  if (!ordered.length) $('workersPreview').append(node('p', 'Aucun worker vérifiable dans la collecte actuelle.'));
  for (const worker of ordered) {
    const row = node('div', undefined, 'worker-preview');
    const description = node('span', worker.title || worker.task || 'Mission non renseignée');
    description.append(node('small', worker.model || 'Modèle inconnu'));
    row.append(badge(worker.state), description, elapsedNode('span', worker));
    $('workersPreview').append(row);
  }
  $('workerCount').textContent = active;
}

function renderFeatures() {
  if (!data) return;
  const topicId = $('topicFilter').value, filter = $('stateFilter').value;
  const search = $('search').value.toLocaleLowerCase('fr');
  $('featureList').replaceChildren(); let count = 0;
  for (const topic of data.topics || []) {
    if (topicId !== 'all' && topic.id !== topicId) continue;
    for (const feature of topic.features || []) {
      const tests = feature.tests || [];
      if (filter !== 'all' && category(feature.state) !== filter && !tests.some(t => category(t.status) === filter)) continue;
      if (search && !JSON.stringify([topic.title, feature]).toLocaleLowerCase('fr').includes(search)) continue;
      count++;
      const section = node('article', undefined, 'feature');
      const heading = node('div', undefined, 'feature-heading');
      heading.append(node('h3', feature.name), badge(feature.state), node('small', topic.title));
      section.append(heading);
      if (feature.detail) section.append(node('p', feature.detail));
      if (!tests.length) section.append(node('p', 'Aucun résultat de test référencé.'));
      for (const test of tests) {
        const row = node('div', undefined, 'test-row');
        row.append(node('span', LEVELS[test.level] || test.level || 'Niveau non précisé', 'test-level'), badge(test.status), node('span', test.detail || 'Périmètre non renseigné', 'test-detail'));
        const proof = node('div'); appendEvidence(proof, test.evidence); row.append(proof); section.append(row);
      }
      $('featureList').append(section);
    }
  }
  $('empty').hidden = count > 0;
}

function renderWorkers() {
  const workers = data.workers || [];
  $('workerRows').replaceChildren(); $('modelSummary').replaceChildren();
  for (const model of ['deepseek-v4.1-flash', 'glm-5.3-flash', 'minimax-m3.1-flash', 'beam']) {
    const entries = workers.filter(w => w.model === model);
    const active = entries.filter(w => category(w.state) === 'running').length;
    const card = node('div', model, 'model');
    card.append(node('small', active ? active + ' mission(s) active(s) vérifiée(s)' : entries.length ? 'Aucune mission active vérifiée' : 'Aucune activité documentée'));
    $('modelSummary').append(card);
  }
  for (const worker of workers) {
    const row = node('tr'), title = node('td', worker.model || 'Inconnu');
    title.append(node('small', worker.title || worker.task || 'Mission non renseignée'));
    if (worker.title && worker.task) title.append(node('small', worker.task));
    if (worker.run_id) title.append(node('small', 'Tentative : ' + worker.run_id));
    const state = node('td'); state.append(badge(worker.state));
    if (worker.detail) state.append(node('small', worker.detail));
    const proof = node('td'); appendEvidence(proof, worker.evidence);
    // A review judges one completed attempt; it does not change process state
    // or erase failed tests. Unknown scores stay absent rather than becoming 0.
    if (worker.review) {
      const review = worker.review;
      const score = typeof review.score === 'number' ? ' · ' + review.score + '/100' : '';
      state.append(node('small', 'Revue : ' + (LABELS[review.state] || review.state) + score));
      if (review.evaluated_at) state.append(node('small', date(review.evaluated_at)));
      if (review.evidence) proof.append(evidenceButton(review.evidence));
    }
    row.append(title, state, elapsedNode('td', worker),
      node('td', (worker.requests ?? '—') + ' / ' + (worker.tool_calls ?? '—')),
      node('td', (worker.tests ?? '—') + ' / ' + (worker.failures ?? '—')),
      node('td', date(worker.last_activity)), proof);
    $('workerRows').append(row);
  }
}

function renderActivity() {
  $('builds').replaceChildren(); $('events').replaceChildren();
  for (const build of data.builds || []) {
    const item = node('div', undefined, 'build'), description = node('div');
    description.append(node('h3', build.name), node('p', build.detail));
    if (build.updated_at) description.append(node('p', 'Dernier relevé : ' + date(build.updated_at), 'footnote'));
    appendEvidence(description, build.evidence);
    item.append(badge(build.state), description); $('builds').append(item);
  }
  for (const event of data.events || []) {
    const item = node('article', undefined, 'event');
    item.append(node('time', date(event.time) + (event.topic ? ' · ' + event.topic : '')),
      node('h3', event.title), node('p', event.detail));
    appendEvidence(item, event.evidence); $('events').append(item);
  }
}

function navigate() {
  const key = location.hash.slice(1);
  const view = ['overview', 'features', 'workers', 'activity'].includes(key) ? key : 'overview';
  for (const section of document.querySelectorAll('.view')) section.hidden = section.id !== view;
  for (const link of document.querySelectorAll('nav a')) {
    link.classList.toggle('active', link.dataset.view === view);
    if (link.dataset.view === view) $('pageTitle').textContent = link.textContent.replace(/\s+\d+$/, '');
  }
}

function acceptSnapshot(received) {
  if (!Array.isArray(received.topics)) throw new Error('Format de collecte invalide.');
  data = received;
  const meaningful = {...received};
  delete meaningful.generated_at; delete meaningful.served_at;
  meaningful.workers = (received.workers || []).map(worker => {
    const copy = {...worker}; delete copy.elapsed_s; return copy;
  });
  const nextSignature = JSON.stringify(meaningful);
  if (nextSignature !== signature) {
    const selected = $('topicFilter').value;
    $('topicFilter').replaceChildren(new Option('Tous les sujets', 'all'));
    for (const topic of data.topics) $('topicFilter').append(new Option(topic.title, topic.id));
    $('topicFilter').value = [...$('topicFilter').options].some(o => o.value === selected) ? selected : 'all';
    overview(); renderFeatures(); renderWorkers(); renderActivity();
    signature = nextSignature;
  }
  collectionHealthy = true;
  heartbeat(received.generated_at || received.served_at);
}

function heartbeat(when) {
  lastHeartbeat = Date.now();
  if (!collectionHealthy) return;
  $('connection').textContent = 'En direct'; $('connection').className = 'badge pass';
  $('updated').textContent = 'Observation : ' + date(when);
  $('error').hidden = true;
}

function unavailable(message) {
  collectionHealthy = false;
  $('connection').textContent = 'Données non actualisées'; $('connection').className = 'badge fail';
  $('error').textContent = message + ' Les valeurs affichées sont les dernières reçues, pas un état actuel garanti.';
  $('error').hidden = false;
}

async function refresh() {
  if (inFlight) return;
  inFlight = true; $('refresh').disabled = true;
  try {
    const response = await fetch('/api/status', {cache: 'no-store', signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error('Le serveur ne fournit pas de collecte valide.');
    acceptSnapshot(await response.json());
  } catch (error) {
    unavailable(error.message);
  } finally { inFlight = false; $('refresh').disabled = false; }
}

function connectStream() {
  const stream = new EventSource('/api/events');
  stream.addEventListener('snapshot', event => {
    try { acceptSnapshot(JSON.parse(event.data)); }
    catch (error) { unavailable(error.message); }
  });
  stream.addEventListener('heartbeat', event => {
    try { heartbeat(JSON.parse(event.data).time); }
    catch { unavailable('Battement de collecte invalide.'); }
  });
  stream.addEventListener('collection_error', () => unavailable('Le serveur ne peut plus lire les preuves.'));
  stream.onerror = () => unavailable('Flux interrompu ; reconnexion automatique en cours.');
  window.addEventListener('pagehide', () => stream.close(), {once: true});
}

$('refresh').onclick = refresh;
$('closeEvidence').onclick = () => $('evidenceDialog').close();
for (const id of ['topicFilter', 'stateFilter', 'search']) $(id).addEventListener('input', renderFeatures);
window.addEventListener('hashchange', navigate);
navigate(); refresh(); connectStream();
setInterval(() => {
  if (lastHeartbeat && Date.now() - lastHeartbeat > 4500 && collectionHealthy) unavailable('Aucune observation reçue depuis plus de 4 secondes.');
  if (collectionHealthy) for (const item of document.querySelectorAll('[data-elapsed]')) {
    item.textContent = duration(Number(item.dataset.elapsed) + (Date.now() - Number(item.dataset.observed)) / 1000);
  }
}, 1000);
