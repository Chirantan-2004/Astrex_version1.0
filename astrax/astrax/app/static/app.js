let state = null;
let session = null;
const $ = id => document.getElementById(id);

async function api(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(url, { credentials: 'same-origin', ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function textCell(row, value, className = '') {
  const cell = document.createElement('td');
  cell.textContent = value ?? '—';
  if (className) cell.className = className;
  row.append(cell);
}

function render(s) {
  state = s;
  const id = encodeURIComponent(s.experiment_id);
  $('experimentId').textContent = s.experiment_id;
  $('jsonExport').href = `/api/logs/${id}.json`;
  $('csvExport').href = `/api/logs/${id}.csv`;

  const progress = s.total_steps ? Math.min((s.current_step - 1) / s.total_steps, 1) * 100 : 0;
  $('statusBadge').textContent = s.status;
  $('stepNo').textContent = Math.min(s.current_step, s.total_steps);
  $('completionPct').textContent = `${progress.toFixed(0)}%`;
  $('progressBar').style.width = `${progress}%`;
  $('activity').textContent = s.detected_activity || '—';
  $('confidence').textContent = `${((s.confidence || 0) * 100).toFixed(1)}%`;

  const expected = s.protocol.find(step => step.activity === s.expected_activity);
  $('nextAction').textContent = s.status === 'COMPLETED' ? 'Experiment complete' : expected?.instruction || 'Start the experiment';
  $('stateOrb').textContent = s.status;
  $('stateOrb').className = `state-label ${s.status === 'ALERT' ? 'alert' : s.status === 'COMPLETED' ? 'completed' : ''}`;

  const camera = s.camera || {};
  $('cameraMeta').textContent = camera.running ? `SENSOR LIVE / ${camera.fps || 0} FPS` : 'SENSOR STANDBY';
  $('fpsHud').textContent = camera.running ? camera.fps || 0 : '—';
  $('framesHud').textContent = camera.running ? camera.frames_seen || 0 : '—';
  $('recHud').textContent = camera.recording ? 'ON' : 'OFF';
  $('cameraRecord').textContent = camera.recording ? 'Stop recording' : 'Start recording';
  showLiveFeed(camera.running);

  const candidate = s.candidate || {};
  const candidateReady = candidate.fresh && candidate.confidence >= 0.7 && candidate.activity !== 'IDLE';
  $('candidateActivity').textContent = candidateReady ? candidate.activity : candidate.fresh ? 'HOLD / LOW CONFIDENCE' : camera.running ? 'STALE / WAITING' : 'NO SIGNAL';
  $('candidateConfidence').textContent = candidate.confidence == null ? '—' : `${(candidate.confidence * 100).toFixed(1)}% CONFIDENCE`;
  $('candidateAge').textContent = candidate.age_ms == null ? 'FRAME AGE —' : `FRAME AGE ${Math.max(0, candidate.age_ms).toFixed(0)} MS`;
  $('candidateDot').className = `signal-dot ${candidateReady ? 'fresh' : camera.running ? 'hold' : ''}`;
  $('engineBadge').textContent = s.vision?.model_loaded ? 'YOLO POSE' : 'OPENCV FALLBACK';
  $('inferenceHud').textContent = s.vision?.model_loaded ? 'YOLO POSE' : 'OPENCV FALLBACK';

  const vision = s.vision?.last || {};
  $('personState').textContent = vision.person_detected ? 'DETECTED' : '—';
  $('objectCount').textContent = (vision.objects || []).length;
  $('interaction').textContent = vision.interaction || '—';
  $('latency').textContent = vision.latency_ms ? `${vision.latency_ms} ms` : '—';
  const coverageNotice = ' Pose is not an action classifier; OPEN/CLOSE are unsupported. OpenCV-only PICK/ROTATE estimates are below 70%; pose-assisted estimates may pass, but full-procedure recognition is unavailable.';
  $('visionNote').textContent = `${vision.note || 'Waiting for camera frames.'}${coverageNotice}`;
  $('simulationControls').hidden = !session?.demo_mode;

  renderProtocol(s);
  renderEvents(s.events || []);
  const lastEvent = (s.events || []).at(-1);
  if (lastEvent?.status === 'OUT_OF_ORDER') setAlert('danger', 'SEQUENCE MISMATCH', lastEvent.message, '!');
  else if (s.status === 'COMPLETED') setAlert('good', 'PROCEDURE COMPLETE', 'All demonstration steps were verified.', 'OK');
  else if (lastEvent?.status === 'VALID') setAlert('good', 'STEP VERIFIED', s.last_message, 'OK');
  else if (!camera.running && s.status === 'RUNNING') setAlert('hold', 'SUPERVISION ON HOLD', 'Camera unavailable. No fresh activity can be confirmed.', 'HOLD');
  else setAlert('hold', 'SUPERVISOR STANDBY', s.last_message, 'WAIT');
}

function renderProtocol(s) {
  const list = $('protocolList');
  list.replaceChildren();
  s.protocol.forEach((step, index) => {
    const complete = index < s.current_step - 1 || s.status === 'COMPLETED';
    const active = index === s.current_step - 1 && s.status !== 'COMPLETED';
    const row = document.createElement('li');
    row.className = `protocol-row${complete ? ' done' : ''}${active ? ' active' : ''}`;
    const number = document.createElement('span');
    number.className = 'step-dot';
    number.textContent = complete ? 'OK' : step.step;
    const description = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = step.activity;
    const detail = document.createElement('small');
    detail.textContent = step.instruction;
    description.append(title, detail);
    const stateLabel = document.createElement('small');
    stateLabel.textContent = complete ? 'VERIFIED' : active ? 'CURRENT' : 'PENDING';
    row.append(number, description, stateLabel);
    list.append(row);
  });
}

function renderEvents(events) {
  const body = $('eventRows');
  body.replaceChildren();
  if (!events.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 8;
    cell.className = 'empty-state';
    cell.textContent = 'No experiment events.';
    row.append(cell);
    body.append(row);
    return;
  }
  events.slice(-20).reverse().forEach(event => {
    const row = document.createElement('tr');
    textCell(row, event.timestamp ? new Date(event.timestamp).toLocaleTimeString([], { hour12: false }) : '—');
    textCell(row, event.step);
    textCell(row, event.expected_activity);
    textCell(row, event.detected_activity);
    textCell(row, `${(event.confidence * 100).toFixed(1)}%`);
    textCell(row, event.status, event.status === 'OUT_OF_ORDER' ? 'result-bad' : 'result-good');
    textCell(row, event.source);
    textCell(row, event.message);
    body.append(row);
  });
}

function renderCommunications(messages) {
  const list = $('commsList');
  list.replaceChildren();
  const queued = messages.filter(message => message.delivery_status === 'QUEUED_LOCAL').length;
  const queueStatus = `${queued} QUEUED`;
  if ($('queueCount').textContent !== queueStatus) $('queueCount').textContent = queueStatus;
  if (!messages.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'No crew messages in this session.';
    list.append(empty);
    return;
  }
  messages.slice(-20).reverse().forEach(message => {
    const item = document.createElement('article');
    item.className = 'comms-item';
    const timestamp = document.createElement('time');
    timestamp.textContent = new Date(message.created_at).toLocaleTimeString([], { hour12: false });
    const body = document.createElement('p');
    body.textContent = message.message;
    const status = document.createElement('small');
    status.textContent = message.delivery_status;
    item.append(timestamp, body, status);
    list.append(item);
  });
}

function setAlert(type, title, message, marker) {
  $('alertPanel').className = `guidance${type === 'danger' ? ' danger' : ''}`;
  $('alertIcon').textContent = marker;
  $('alertTitle').textContent = title;
  $('alertText').textContent = message;
}

function showLiveFeed(running) {
  const frame = $('cameraFrame');
  const placeholder = frame.querySelector('.camera-placeholder');
  let image = frame.querySelector('img');
  if (running && !image) {
    image = document.createElement('img');
    image.src = `/video_feed?frame=${Date.now()}`;
    image.alt = 'Live payload camera';
    frame.prepend(image);
  } else if (!running && image) {
    image.remove();
  }
  placeholder.hidden = running;
}

function showSession(currentSession) {
  session = currentSession;
  const authenticated = currentSession.authenticated;
  $('authGate').hidden = authenticated;
  $('missionConsole').hidden = !authenticated;
  $('loginLink').hidden = authenticated || !currentSession.login_available;
  $('authAction').hidden = authenticated || !currentSession.login_available;
  $('logoutForm').hidden = !authenticated || currentSession.local_auth;
  $('userName').textContent = currentSession.user?.name || '';
  $('authSetupState').hidden = currentSession.login_available || authenticated;
  $('authMessage').textContent = currentSession.login_available
    ? 'Use your organization-issued mission identity. Mission controls remain locked until sign-in is verified.'
    : 'Mission controls are locked. Configure an OpenID Connect provider or explicitly enable local demo mode.';
}

async function refresh() {
  try {
    showSession(await api('/api/auth/session'));
    if (!session.authenticated) return;
    render(await api('/api/status'));
    renderCommunications(await api('/api/comms/messages'));
  } catch (error) {
    if (error.message.includes('401')) {
      showSession({ authenticated: false, login_available: true, user: null });
      return;
    }
    $('systemText').textContent = 'BACKEND LINK LOST';
    setAlert('danger', 'SUPERVISOR UNAVAILABLE', error.message, '!');
  }
}

async function runAction(action) {
  try {
    render(await action());
    await refresh();
  } catch (error) {
    setAlert('danger', 'COMMAND NOT ACCEPTED', error.message, '!');
  }
}

async function startCamera() {
  try {
    const result = await api('/api/camera/start', { method: 'POST', body: JSON.stringify({ index: 0 }) });
    render(result);
    if (!result.ok) setAlert('danger', 'SENSOR ACQUISITION FAILED', result.camera?.error || 'Camera unavailable.', '!');
  } catch (error) {
    setAlert('danger', 'SENSOR ACQUISITION FAILED', error.message, '!');
  }
}

async function sendUplink(event) {
  event.preventDefault();
  const input = $('uplinkMessage');
  if (!input.value.trim()) return;
  $('uplinkSend').disabled = true;
  try {
    await api('/api/comms/messages', { method: 'POST', body: JSON.stringify({ message: input.value }) });
    input.value = '';
    renderCommunications(await api('/api/comms/messages'));
  } catch (error) {
    setAlert('danger', 'MESSAGE NOT QUEUED', error.message, '!');
  } finally {
    $('uplinkSend').disabled = false;
  }
}

$('cameraStart').addEventListener('click', startCamera);
$('cameraStop').addEventListener('click', () => runAction(() => api('/api/camera/stop', { method: 'POST' })));
$('cameraRecord').addEventListener('click', () => runAction(() => api(state?.camera?.recording ? '/api/camera/record/stop' : '/api/camera/record', { method: 'POST' })));
$('demoStart').addEventListener('click', () => runAction(() => api('/api/demo/start', { method: 'POST' })));
$('demoCorrect').addEventListener('click', () => runAction(() => api('/api/demo/next-correct', { method: 'POST' })));
$('demoWrong').addEventListener('click', () => runAction(() => api('/api/demo/wrong', { method: 'POST' })));
$('resetExperiment').addEventListener('click', () => runAction(() => api('/api/demo/reset', { method: 'POST' })));
$('uplinkForm').addEventListener('submit', sendUplink);

refresh();
setInterval(refresh, 1000);
