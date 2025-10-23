// main.js
(function () {
  const availableList = document.getElementById('availableList');
  const selectedList  = document.getElementById('selectedList');
  const btnStart      = document.getElementById('btnStart');
  const btnClear      = document.getElementById('btnClear');
  const runState      = document.getElementById('runState');
  const logList       = document.getElementById('logList');
  const progressBar   = document.getElementById('progressBar');
  const runHint       = document.getElementById('runHint');

  if (!availableList || !selectedList) return;

  // Sortable (drag & drop)
  Sortable.create(availableList, {
    group: { name: 'tests', pull: 'clone', put: false },
    animation: 150,
    sort: false,
    onEnd: function (evt) {
      // También permitimos click para mover
    }
  });

  Sortable.create(selectedList, {
    group: { name: 'tests', pull: true, put: true },
    animation: 150,
  });

  // Click para pasar de "disponibles" a "seleccionados"
  availableList.addEventListener('click', (e) => {
    const li = e.target.closest('li.list-group-item');
    if (!li) return;
    const clone = li.cloneNode(true);
    selectedList.appendChild(clone);
  });

  // Limpiar selección
  if (btnClear) {
    btnClear.addEventListener('click', () => {
      selectedList.innerHTML = '';
      setProgress(0);
      logList.innerHTML = '';
      runState.style.display = 'none';
    });
  }

  // Empezar prueba (crea job y hace polling de estado)
  if (btnStart) {
    btnStart.addEventListener('click', async () => {
      const order = [...selectedList.querySelectorAll('li')].map(li => li.getAttribute('data-key'));
      if (!order.length) {
        alert('Selecciona al menos una prueba.');
        return;
      }

      // Reset UI
      runState.style.display = '';
      logList.innerHTML = '';
      setProgress(0);
      runHint.textContent = '';

      const createResp = await fetch('/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order })
      });
      if (!createResp.ok) {
        const err = await createResp.json().catch(() => ({}));
        alert('Error al iniciar: ' + (err.error || createResp.statusText));
        return;
      }
      const { job_id } = await createResp.json();

      // Polling
      await pollStatus(job_id, order);
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

  async function pollStatus(jobId, order) {
    const total = order.length;
    const doneSet = new Set();

    return new Promise((resolve) => {
      const timer = setInterval(async () => {
        let data;
        try {
          const r = await fetch(`/status/${jobId}`);
          if (!r.ok) throw new Error('status HTTP ' + r.status);
          data = await r.json();
        } catch (e) {
          addLog('Error consultando estado: ' + e.message, true);
          clearInterval(timer);
          resolve();
          return;
        }

        const { state, current, done, error, results } = data;

        // hint
        runHint.textContent = current ? `Ejecutando: ${current}` : '';

        // progreso
        const pct = Math.round(((done?.length || 0) / total) * 100);
        setProgress(pct);

        // nuevos completados -> log con resultados básicos
        (done || []).forEach(key => {
          if (!doneSet.has(key)) {
            doneSet.add(key);
            const entry = results?.[key];
            if (entry?.ok) {
              addLog(`✔ Finalizada: ${entry.test_display}`);
            } else {
              addLog(`✖ Error en: ${key}`, true);
            }
          }
        });

        if (state === 'error') {
          addLog(`⛔ Error en ${error?.test || ''}: ${error?.message || 'Desconocido'}`, true);
          clearInterval(timer);
          resolve();
        }

        if (state === 'done') {
          addLog('🏁 Secuencia completada.');
          clearInterval(timer);
          // Redirige al resumen
          setTimeout(() => {
            window.location.href = `/summary/${jobId}`;
          }, 600);
          resolve();
        }
      }, 1000);
    });
  }
})();
