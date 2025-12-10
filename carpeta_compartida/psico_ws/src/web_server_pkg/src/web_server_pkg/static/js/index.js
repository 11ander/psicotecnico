// index.js — Panel principal (cola de pruebas, progreso, resultados, PDF)

(function () {
  // ---------- Referencias a elementos del DOM ----------
  const queueListEl   = document.getElementById('queueList');              // UL de la cola seleccionada
  const btnStart      = document.getElementById('btnStart');
  const btnClear      = document.getElementById('btnClear');

  const runState      = document.getElementById('runState');               // Contenedor estado de ejecución
  const runBanner     = document.getElementById('runBanner');              // <div class="alert ...">
  const runLabel      = document.getElementById('runLabel');               // “Ejecutando…” / “Finalizado”
  const runHint       = document.getElementById('runHint');                // pista (prueba actual)
  const progressBar   = document.getElementById('progressBar');            // barra de progreso

  const logList       = document.getElementById('logList');                // (opcional)
  const resultsList   = document.getElementById('results');                // UL de resultados

  const btnDownload   = document.getElementById('btnDownload');            // Descargar PDF
  const userBadge     = document.getElementById('userBadge');              // Usuario logado (opcional)

  // ---------- Estado en front ----------
  let testQueue = [];        // Cola seleccionada en UI
  let runPlan   = [];        // Copia congelada al pulsar “Empezar”
  let pollingTimer = null;

  const LABELS = {
    memoria: "Memoria",
    reflejos: "Reflejos",
    audicion: "Audición",
    coordinacion: "Coordinación",
    vision: "Visión"
  };

  function labelOf(k){ return LABELS[k] || (k ? (k[0].toUpperCase()+k.slice(1)) : ''); }
  function tagClass(k){
    if (k === 'reflejos')    return 'bg-info-subtle text-info-emphasis';
    if (k === 'memoria')     return 'bg-success-subtle text-success-emphasis';
    if (k === 'audicion')    return 'bg-warning-subtle text-warning-emphasis';
    if (k === 'coordinacion')return 'bg-primary-subtle text-primary-emphasis';
    return 'bg-secondary-subtle text-secondary-emphasis';
  }

  // ---------- Cola estilo “compi” (expuesta al HTML) ----------
  window.addTest = function (key){
    if (!key) return;
    if (testQueue.includes(key)) return;
    testQueue.push(key);
    renderQueue();
    enableStartIfReady();
  };

  window.removeItem = function (index){
    if (!Number.isInteger(index)) return;
    testQueue.splice(index, 1);
    renderQueue();
    enableStartIfReady();
  };

  window.moveItem = function (index, delta){
    const i = index | 0;
    const j = i + (delta | 0);
    if (j < 0 || j >= testQueue.length) return;
    [testQueue[i], testQueue[j]] = [testQueue[j], testQueue[i]];
    renderQueue();
  };

  window.clearQueue = function (){
    testQueue = [];
    renderQueue();
    enableStartIfReady();
  };

  function renderQueue(){
    if (!queueListEl) return;
    queueListEl.innerHTML = '';
    testQueue.forEach((k, i) => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex align-items-center justify-content-between';
      li.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <span class="badge ${tagClass(k)}">${labelOf(k)}</span>
          <span class="text-muted">#${i+1}</span>
        </div>
        <div class="d-flex gap-1">
          <button class="btn btn-sm btn-outline-secondary" onclick="moveItem(${i},-1)">↑</button>
          <button class="btn btn-sm btn-outline-secondary" onclick="moveItem(${i}, 1)">↓</button>
          <button class="btn btn-sm btn-outline-danger"    onclick="removeItem(${i})">✕</button>
        </div>`;
      queueListEl.appendChild(li);
    });
  }

  function enableStartIfReady(){
    if (!btnStart) return;
    btnStart.disabled = (testQueue.length === 0);
  }

  function setProgress(pct) {
    if (!progressBar) return;
    const p = Math.max(0, Math.min(100, pct|0));
    progressBar.style.width = p + '%';
    progressBar.textContent = p + '%';
  }

  function addLog(text, isError = false) {
    if (!logList) return;
    const li = document.createElement('li');
    li.className = 'list-group-item';
    li.innerHTML = isError ? `<span class="text-danger">${text}</span>` : text;
    logList.appendChild(li);
    li.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  async function loadUser() {
    try {
      const r = await fetch('/whoami');
      if (!r.ok) return;
      const j = await r.json();
      const u = j.user || '';
      if (userBadge) userBadge.textContent = u ? `Usuario: ${u}` : '';
    } catch (e) {}
  }

  // ---------- Inicio de la secuencia ----------
  async function startSequence() {
    if (!testQueue.length) return;

    // Estado visual (reset)
    resultsList && (resultsList.innerHTML = '');
    logList && (logList.innerHTML = '');
    setProgress(0);
    runHint && (runHint.textContent = '');
    if (runLabel)  runLabel.textContent = 'Ejecutando…';
    if (runBanner) runBanner.className = 'alert alert-info d-flex align-items-center';
    runState && runState.classList.remove('d-none');
    btnDownload && btnDownload.classList.add('d-none');

    // Congelamos la planificación
    runPlan = [...testQueue];

    // Llamamos al backend
    const r = await fetch('/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order: runPlan })
    });
    const data = await r.json();
    if (!data.ok) {
      addLog('No se pudo iniciar la secuencia.', true);
      return;
    }

    // Polling
    if (pollingTimer) clearInterval(pollingTimer);
    pollingTimer = setInterval(pollTick, 800);
  }

  // ---------- Polling de estado ----------
  async function pollTick() {
    try {
      const r = await fetch('/status');
      const { estado, registro } = await r.json();

      // Logs (últimas líneas)
      if (Array.isArray(registro) && logList) {
        const last = registro.slice(-50);
        logList.innerHTML = '';
        last.forEach(line => addLog(line));
      }

      // Progreso (basado en runPlan si existe, si no, usa total_pruebas del backend)
      const done = (estado?.pruebas_completadas || []).length;
      const total = (runPlan.length || estado?.total_pruebas || 1);
      const pct = Math.round((done / total) * 100);
      setProgress(pct);

      // Pista de ejecución
      if (runHint) {
        const current = estado?.current || '';
        runHint.textContent = current ? `Ejecutando: ${labelOf(current)}` : (estado?.ejecutando ? 'Ejecutando…' : '');
      }

      // Resultados
      renderResults(estado?.resultados || []);

      // Fin
      if (!estado?.ejecutando) {
        finishedUI();
        clearInterval(pollingTimer);
        pollingTimer = null;
      }
    } catch (e) {
      addLog('Error consultando estado: ' + (e?.message || e), true);
      if (pollingTimer) clearInterval(pollingTimer);
      pollingTimer = null;
    }
  }

  function finishedUI(){
    setProgress(100);
    if (runLabel)  runLabel.textContent = 'Finalizado';
    if (runBanner) runBanner.className = 'alert alert-success d-flex align-items-center';
    runState && runState.classList.remove('d-none');
    if (btnDownload) btnDownload.classList.remove('d-none');
  }

  // ---------- Resultados (incluye entrada numérica para Audición P2) ----------
  function renderResults(resultados){
    if (!resultsList) return;

    // Guardar valores temporales de inputs Audición/Vision(creo que tambien loc coge) si estaban siendo escritos
    const prevInputs = {};
    resultsList.querySelectorAll('input[data-test-input="1"]').forEach(inp => {
      prevInputs[inp.id] = inp.value;
    });


    resultsList.innerHTML = "";

    (resultados || []).forEach((r, idx) => {
      const li = document.createElement("li");
      li.className = 'list-group-item';

      const hora = r.hora || '';
      const etiqueta = LABELS[r.prueba] || (r.prueba || '').toUpperCase();
      const nota   = (r.puntuacion === null || typeof r.puntuacion === 'undefined') ? '—' : r.puntuacion;

      let html = `<div><strong>${hora}</strong> · ${etiqueta} → <b>${nota}</b> /10</div>`;

      if (r.prueba === 'audicion') {
        const d = r.detalles || {};
        const notaP1 = (d.nota_p1 !== undefined) ? d.nota_p1 : '—';
        const notaP2 = (d.nota_p2 !== undefined) ? d.nota_p2 : '—';

        // Subnotas (sin métricas crudas)
        html += `
          <div class="mt-1 text-muted">
            Nota P1: <b>${notaP1}</b> /10 · Nota P2: <b>${notaP2}</b> /10
          </div>
        `;

        const yaRespondido = !!(r.respuesta_usuario);
        const necesita = d.requiere_input && !yaRespondido;

        if (necesita) {
          const schema = d.input_schema || {};
          const campo = (schema.campos && schema.campos[0]) ||
            {name:"p2_contados_paciente",label:"¿Cuántos pitidos escuchaste en la PRUEBA 2?", type:"number"};
          const inputId = `aud_${idx}_${campo.name}`;

          html += `
            <div class="mt-2 p-2 border rounded-3">
              <div class="fw-semibold mb-1">${schema.titulo || 'Audición – Respuesta del paciente (P2)'}</div>
              <div class="text-muted mb-2">${schema.descripcion || ''}</div>
              <div class="mb-2" style="max-width:260px;">
                <label class="form-label">${campo.label || 'Respuesta'}</label>
                <input
                  type="${campo.type || 'number'}"
                  id="${inputId}"
                  data-test-input="1" 
                  class="form-control"
                  min="${campo.min ?? 0}"
                  inputmode="numeric"
                  pattern="[0-9]*"
                />
              </div>
              <button class="btn btn-sm btn-primary" onclick="enviarRespuestaAudicion(${idx}, '${campo.name}', '${inputId}')">
                Guardar
              </button>
            </div>
          `;

          li.innerHTML = html;
          resultsList.appendChild(li);

          const inp = document.getElementById(inputId);
          if (inp) {
            if (prevInputs[inputId] !== undefined) inp.value = prevInputs[inputId];
            inp.addEventListener('keydown', (ev) => {
              if (ev.key === 'Enter') {
                enviarRespuestaAudicion(idx, campo.name, inputId);
              }
            });
          }
          return;
        } else if (yaRespondido) {
          const v = r.respuesta_usuario || {};
          if (typeof v.p2_contados_paciente !== 'undefined') {
            html += `<div class="mt-1">✅ Respuesta guardada (P2): <b>${v.p2_contados_paciente}</b></div>`;
          }
        }
      }


        if (r.prueba === 'vision') {
        const d = r.detalles || {};
        const notaF1 = (d.nota_f1 !== undefined) ? d.nota_f1 : '—';
        const notaF2 = (d.nota_f2 !== undefined) ? d.nota_f2 : '—';

        html += `
          <div class="mt-1 text-muted">
            Nota frase 1: <b>${notaF1}</b> /10 · Nota frase 2: <b>${notaF2}</b> /10
          </div>
        `;

        const yaRespondido = !!(r.respuesta_usuario);
        const necesita = d.requiere_input && !yaRespondido;

        if (necesita) {
          const schema = d.input_schema || {};
          const campos = schema.campos || [];
          const campo1 = campos[0] || {name:"vision_frase_1",label:"Frase 1", type:"text"};
          const campo2 = campos[1] || {name:"vision_frase_2",label:"Frase 2", type:"text"};

          const inputId1 = `vision_${idx}_${campo1.name}`;
          const inputId2 = `vision_${idx}_${campo2.name}`;

          html += `
            <div class="mt-2 p-2 border rounded-3">
              <div class="fw-semibold mb-1">${schema.titulo || 'Visión – Respuesta del paciente'}</div>
              <div class="text-muted mb-2">${schema.descripcion || ''}</div>

              <div class="mb-2" style="max-width:260px;">
                <label class="form-label">${campo1.label || 'Frase 1 recordada'}</label>
                <input
                  type="${campo1.type || 'text'}"
                  id="${inputId1}"
                  data-test-input="1"
                  class="form-control"
                />
              </div>

              <div class="mb-2" style="max-width:260px;">
                <label class="form-label">${campo2.label || 'Frase 2 recordada'}</label>
                <input
                  type="${campo2.type || 'text'}"
                  id="${inputId2}"
                  data-test-input="1"
                  class="form-control"
                />
              </div>

              <button class="btn btn-sm btn-primary"
                      onclick="enviarRespuestaVision(${idx}, '${campo1.name}', '${inputId1}', '${campo2.name}', '${inputId2}')">
                Guardar
              </button>
            </div>
          `;

          li.innerHTML = html;
          resultsList.appendChild(li);

          const i1 = document.getElementById(inputId1);
          const i2 = document.getElementById(inputId2);
          if (i1 && prevInputs[inputId1] !== undefined) i1.value = prevInputs[inputId1];
          if (i2 && prevInputs[inputId2] !== undefined) i2.value = prevInputs[inputId2];

          // Enter en cualquiera de los dos dispara el envío
          [i1, i2].forEach(inp => {
            if (!inp) return;
            inp.addEventListener('keydown', ev => {
              if (ev.key === 'Enter') {
                enviarRespuestaVision(idx, campo1.name, inputId1, campo2.name, inputId2);
              }
            });
          });

          return;
        } else if (yaRespondido) {
          const v = r.respuesta_usuario || {};
          const f1 = v.vision_frase_1 || '';
          const f2 = v.vision_frase_2 || '';
          html += `
            <div class="mt-1">
              ✅ Respuesta guardada:
              <div class="small"><b>Frase 1:</b> ${f1}</div>
              <div class="small"><b>Frase 2:</b> ${f2}</div>
            </div>
          `;
        }
      }




      li.innerHTML = html;
      resultsList.appendChild(li);
    });
  }

  // Exponer para el onclick del HTML
  window.enviarRespuestaAudicion = async function (index, fieldName, inputId){
    const el = document.getElementById(inputId);
    if (!el) return alert("No se encuentra el campo.");
    const raw = (el.value || '').trim();
    if (raw === '') return alert("Introduce un número, por favor.");
    const val = Number(raw);
    if (!Number.isFinite(val) || val < 0) return alert("Valor inválido.");

    await fetch("/answer", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ index, values: { [fieldName]: val } })
    });

    setTimeout(pollTick, 200);
  };


  window.enviarRespuestaVision = async function (index, fieldName1, inputId1, fieldName2, inputId2){
    const el1 = document.getElementById(inputId1);
    const el2 = document.getElementById(inputId2);
    if (!el1 || !el2) return alert("No se encuentran los campos de texto.");

    const v1 = (el1.value || '').trim();
    const v2 = (el2.value || '').trim();

    if (!v1 || !v2) {
      return alert("Rellena las dos frases, por favor.");
    }

    await fetch("/answer", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        index,
        values: {
          [fieldName1]: v1,
          [fieldName2]: v2
        }
      })
    });

    setTimeout(pollTick, 200);
  };


  // ---------- PDF ----------
  async function downloadPDF(){
    window.open('/report/pdf', '_blank');
  }

  // ---------- Carga inicial (clave para --no-test) ----------
  async function hydrateFromBackendOnLoad() {
    // 1) Carga usuario
    await loadUser();

    // 2) Pide estado 1 vez
    try {
      const r = await fetch('/status');
      if (!r.ok) return;
      const { estado } = await r.json();

      // Si ya hay resultados (seed --no-test) y no se está ejecutando, los pintamos
      const hasResults = Array.isArray(estado?.resultados) && estado.resultados.length > 0;
      if (hasResults) {
        // Pintar resultados
        renderResults(estado.resultados);

        // UI como finalizada si no está ejecutando
        if (!estado.ejecutando) {
          // Progreso al 100% basado en total_pruebas si viene del backend
          const total = estado.total_pruebas || estado.resultados.length;
          const done  = estado.pruebas_completadas ? estado.pruebas_completadas.length : total;
          const pct   = Math.round((done / (total || 1)) * 100);
          setProgress(pct >= 100 ? 100 : pct);

          if (runLabel)  runLabel.textContent = 'Finalizado';
          if (runBanner) runBanner.className = 'alert alert-success d-flex align-items-center';
          runState && runState.classList.remove('d-none');
          if (btnDownload) btnDownload.classList.remove('d-none');
        } else {
          // Si por lo que sea está ejecutando (no debería con --no-test), arrancamos polling
          if (pollingTimer) clearInterval(pollingTimer);
          pollingTimer = setInterval(pollTick, 800);
        }
      }
    } catch (_) {
      // silencioso
    }
  }

  // ---------- Eventos ----------
  if (btnStart)     btnStart.addEventListener('click', startSequence);
  if (btnClear)     btnClear.addEventListener('click', () => { clearQueue(); setProgress(0); logList && (logList.innerHTML=''); runState && runState.classList.add('d-none'); });
  if (btnDownload)  btnDownload.addEventListener('click', downloadPDF);

  // ---------- Init ----------
  renderQueue();
  enableStartIfReady();
  hydrateFromBackendOnLoad();   // <<--- IMPORTANTE para ver resultados con --no-test
})();
