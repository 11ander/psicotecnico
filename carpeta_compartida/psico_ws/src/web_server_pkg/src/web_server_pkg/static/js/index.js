// index.js: lógica del panel que habla con /start, /status, /history

(function () {
  const availableList = document.getElementById('availableList');
  const selectedList  = document.getElementById('selectedList');
  const btnStart      = document.getElementById('btnStart');
  const btnClear      = document.getElementById('btnClear');
  const runState      = document.getElementById('runState');
  const logList       = document.getElementById('logList');
  const progressBar   = document.getElementById('progressBar');
  const runHint       = document.getElementById('runHint');

  const patientName   = document.getElementById('patientName');
  const patientId     = document.getElementById('patientId');

  const statusArea    = document.getElementById('statusArea');
  const btnHistory    = document.getElementById('btnHistory');
  const btnClearHist  = document.getElementById('btnClearHistory');
  const historyBody   = document.getElementById('historyBody');
  const userBadge     = document.getElementById('userBadge');

  // Si el backend mete el nombre en sesión, puedes mostrarlo así (opcional)
  // userBadge.textContent = "Sesión activa";

  // Lista de pruebas disponibles (ajústala si quieres cargarla del backend)
  const AVAILABLE = [
    { key: "memoria",  label: "Memoria"  },
    { key: "reflejos", label: "Reflejos" }
  ];

  // Pinta la lista de disponibles
  function renderAvailable() {
    availableList.innerHTML = '';
    AVAILABLE.forEach(t => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      li.dataset.key = t.key;
      li.innerHTML = `<span>${t.label}</span><span class="badge bg-secondary">Añadir</span>`;
      availableList.appendChild(li);
    });
  }

  // Inicializa drag & drop
  function initDnD() {
    Sortable.create(availableList, {
      group: { name: 'tests', pull: 'clone', put: false },
      animation: 150,
      sort: false
    });
    Sortable.create(selectedList, {
      group: { name: 'tests', pull: true, put: true },
      animation: 150
    });

    // click para pasar de disponibles a seleccionados
    availableList.addEventListener('click', (e) => {
      const li = e.target.closest('li.list-group-item');
      if (!li) return;
      const clone = li.cloneNode(true);
      selectedList.appendChild(clone);
    });
  }

  function setProgress(pct) {
    progressBar.style.width = pct + '%';
    progressBar.textContent = pct + '%';
  }

  function addLog(text, isError = false) {
    const li = document.createElement('li');
    li.className = 'list-group-item';
    li.innerHTML = isError ? `<span class="text-danger">${text}</span>` : text;
    logList.appendChild(li);
    li.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  function getSelectedOrder() {
    return [...selectedList.querySelectorAll('li')].map(li => li.getAttribute('data-key'));
  }

  // ---- START ----
  async function startSequence() {
    const order = getSelectedOrder();
    if (!order.length) {
      alert('Selecciona al menos una prueba.');
      return;
    }

    const patient = {
      nombre: (patientName?.value || '').trim(),
      id: (patientId?.value || '').trim()
    };

    // Reset UI
    runState.classList.remove('d-none');
    logList.innerHTML = '';
    setProgress(0);
    runHint.textContent = '';
    statusArea.textContent = '';

    // Llama al backend
    const r = await fetch('/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order, patient })
    });
    const data = await r.json();
    if (!data.ok) {
      addLog('No se pudo iniciar la secuencia.', true);
      return;
    }

    // Empieza el polling de estado
    pollStatus(order);
  }

  // ---- STATUS POLLING ----
  async function pollStatus(order) {
    const total = order.length;
    const doneSet = new Set();

    const timer = setInterval(async () => {
      try {
        const r = await fetch('/status');
        const { estado, registro } = await r.json();

        // pinta status “raw”
        statusArea.textContent = JSON.stringify(estado, null, 2);

        // pista/hint
        const current = estado.current || estado.pruebas_completadas?.slice(-1)[0] || '';
        runHint.textContent = current ? `Ejecutando: ${current}` : '';

        // progreso
        const done = estado.pruebas_completadas?.length || 0;
        const pct = Math.round((done / total) * 100);
        setProgress(pct);

        // log (solo nuevas líneas)
        if (Array.isArray(registro)) {
          registro.slice(-5).forEach(line => {
            // opcional: podrías controlar duplicados si quieres
          });
        }

        // “logs” por pruebas completadas (evita duplicar)
        (estado.pruebas_completadas || []).forEach(k => {
          if (!doneSet.has(k)) {
            doneSet.add(k);
            addLog(`✔ Finalizada: ${k}`);
          }
        });

        if (!estado.ejecutando) {
          addLog('🏁 Secuencia completada.');
          clearInterval(timer);
          // refresca histórico
          loadHistory();
        }
      } catch (e) {
        addLog('Error consultando estado: ' + e.message, true);
        clearInterval(timer);
      }
    }, 1000);
  }

  // ---- HISTORY ----
  async function loadHistory() {
    const r = await fetch('/history');
    const data = await r.json();
    if (!Array.isArray(data.filas)) {
      historyBody.innerHTML = `<tr><td colspan="4" class="text-muted">Sin datos</td></tr>`;
      return;
    }
    historyBody.innerHTML = '';
    data.filas.forEach(row => {
      const pruebas = (row.pruebas || []).map(p => `${p.prueba} (${p.puntuacion})`).join(', ');
      const paciente = row.paciente?.nombre || '-';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${row.fecha}</td><td>${row.hora}</td><td>${paciente}</td><td>${pruebas}</td>`;
      historyBody.appendChild(tr);
    });
  }

  async function clearHistory() {
    if (!confirm('¿Seguro que quieres limpiar todo el histórico?')) return;
    const r = await fetch('/history/clear', { method: 'POST' });
    const data = await r.json();
    if (data.ok) loadHistory();
  }

  // ---- Eventos UI ----
  if (btnStart)  btnStart.addEventListener('click', startSequence);
  if (btnClear)  btnClear.addEventListener('click', () => { selectedList.innerHTML = ''; setProgress(0); logList.innerHTML = ''; runState.classList.add('d-none'); });
  if (btnHistory) btnHistory.addEventListener('click', loadHistory);
  if (btnClearHist) btnClearHist.addEventListener('click', clearHistory);

  // ---- Init ----
  renderAvailable();
  initDnD();
  loadHistory();
})();
