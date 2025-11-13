// admin.js — Panel de administración (histórico + movilidad TIAGo + mapa nav2d)

(function () {
  // -------- Referencias DOM --------
  const historyBody    = document.getElementById('historyBody');
  const btnHistory     = document.getElementById('btnHistory');
  const btnClearHist   = document.getElementById('btnClearHistory');

  const userBadge      = document.getElementById('userBadge');

  const modeSelect     = document.getElementById('modeSelect');
  const presetGroup    = document.getElementById('presetGroup');
  const presetSelect   = document.getElementById('presetSelect');
  const coordsGroup    = document.getElementById('coordsGroup');
  const coordX         = document.getElementById('coordX');
  const coordY         = document.getElementById('coordY');
  const coordOz        = document.getElementById('coordOz');
  const coordOw        = document.getElementById('coordOw');
  const btnSendMove    = document.getElementById('btnSendMove');
  const moveStatus     = document.getElementById('moveStatus');

  const nav2dContainer = document.getElementById('nav2dViewer');

  // -------- Utilidades --------
  async function loadUser() {
    try {
      const r = await fetch('/whoami');
      if (!r.ok) return;
      const j = await r.json();
      const u = j.user || '';
      if (userBadge) userBadge.textContent = u ? `Usuario: ${u}` : '';
    } catch (_) {}
  }

  // -------- Histórico --------
  async function loadHistory() {
    if (!historyBody) return;
    historyBody.innerHTML = `
      <tr><td colspan="4" class="text-muted text-center">Cargando…</td></tr>
    `;
    try {
      const r = await fetch('/admin/history');
      if (!r.ok) {
        historyBody.innerHTML = `
          <tr><td colspan="4" class="text-danger text-center">Error cargando histórico.</td></tr>
        `;
        return;
      }
      const j = await r.json();
      if (!j.ok) {
        historyBody.innerHTML = `
          <tr><td colspan="4" class="text-danger text-center">Error: ${j.error || 'desconocido'}</td></tr>
        `;
        return;
      }

      const filas = j.filas || [];
      if (!filas.length) {
        historyBody.innerHTML = `
          <tr><td colspan="4" class="text-muted text-center">No hay sesiones registradas.</td></tr>
        `;
        return;
      }

      historyBody.innerHTML = '';
      filas.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${row.fecha || ''}</td>
          <td>${row.hora || ''}</td>
          <td>${row.paciente || ''}</td>
          <td>${row.pruebas || ''}</td>
        `;
        historyBody.appendChild(tr);
      });
    } catch (e) {
      historyBody.innerHTML = `
        <tr><td colspan="4" class="text-danger text-center">Error de red al cargar histórico.</td></tr>
      `;
    }
  }

  async function clearHistory() {
    if (!confirm('¿Seguro que quieres borrar el histórico y el CSV asociado?')) return;
    try {
      const r = await fetch('/history/clear', { method: 'POST' });
      const j = await r.json();
      if (!r.ok || !j.ok) {
        alert('Error borrando histórico: ' + (j.error || 'desconocido'));
        return;
      }
      await loadHistory();
    } catch (e) {
      alert('Error de red al borrar histórico.');
    }
  }

  // -------- Movilidad TIAGo --------
  function updateModeUI() {
    const mode = modeSelect ? modeSelect.value : 'preset';
    if (mode === 'coords') {
      coordsGroup && coordsGroup.classList.remove('d-none');
      presetGroup && presetGroup.classList.add('d-none');
    } else {
      presetGroup && presetGroup.classList.remove('d-none');
      coordsGroup && coordsGroup.classList.add('d-none');
    }
    if (moveStatus) moveStatus.textContent = '';
  }

  async function sendMove() {
    const mode = modeSelect ? modeSelect.value : 'preset';
    let payload = { mode };

    if (mode === 'preset') {
      const val = presetSelect ? presetSelect.value : '';
      if (!val) {
        alert('Selecciona una posición preprogramada.');
        return;
      }
      payload.preset = val;
    } else {
      const x  = parseFloat(coordX.value);
      const y  = parseFloat(coordY.value);
      const oz = parseFloat(coordOz.value);
      const ow = parseFloat(coordOw.value);

      if (![x,y,oz,ow].every(v => Number.isFinite(v))) {
        alert('Rellena las cuatro coordenadas con valores numéricos válidos.');
        return;
      }
      payload.coords = [x, y, oz, ow];
    }

    if (moveStatus) moveStatus.textContent = 'Enviando movimiento…';

    try {
      const r = await fetch('/admin/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const j = await r.json();
      if (!r.ok || !j.ok) {
        alert('Error enviando movimiento: ' + (j.error || 'desconocido'));
        if (moveStatus) moveStatus.textContent = 'Error al enviar movimiento.';
        return;
      }

      if (moveStatus) moveStatus.textContent = j.message || 'Movimiento enviado.';
    } catch (e) {
      alert('Error de red al enviar movimiento.');
      if (moveStatus) moveStatus.textContent = 'Error de red.';
    }
  }

  // -------- Mapa tipo RViz (nav2djs) --------
  function initNav2D() {
    if (!nav2dContainer) return;
    if (typeof ROSLIB === 'undefined' || typeof ROS2D === 'undefined' || typeof NAV2D === 'undefined') {
      console.warn('Las librerías de Robot Web Tools no están cargadas.');
      return;
    }

    // Viewer 2D en el div
    const viewer = new ROS2D.Viewer({
      divID: 'nav2dViewer',
      width: nav2dContainer.clientWidth || 400,
      height: 300
    });

    // Conexión a rosbridge
    const ros = new ROSLIB.Ros({
      url: 'ws://127.0.0.1:9090'   // cambia la IP si accedes desde otro PC
    });

    ros.on('connection', function () {
      console.log('Conectado a rosbridge.');
    });

    ros.on('error', function (error) {
      console.error('Error en rosbridge: ', error);
    });

    ros.on('close', function () {
      console.warn('Conexión con rosbridge cerrada.');
    });

    // Cliente de mapa + robot + navegación (como RViz 2D)
    // Requiere /map, /tf y /move_base.
    const nav = new NAV2D.OccupancyGridClientNav({
      ros: ros,
      rootObject: viewer.scene,
      viewer: viewer,
      serverName: '/move_base',
      continuous: true,
      withOrientation: true
      // Por defecto usa /map como topic de mapa.
    });
  }

  // -------- Eventos --------
  if (btnHistory)    btnHistory.addEventListener('click', loadHistory);
  if (btnClearHist)  btnClearHist.addEventListener('click', clearHistory);
  if (modeSelect)    modeSelect.addEventListener('change', updateModeUI);
  if (btnSendMove)   btnSendMove.addEventListener('click', sendMove);

  // -------- Init --------
  loadUser();
  loadHistory();
  updateModeUI();
  initNav2D();

})();
