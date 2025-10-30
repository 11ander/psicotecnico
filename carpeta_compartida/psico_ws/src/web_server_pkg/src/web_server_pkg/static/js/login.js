(function () {
  const btn = document.getElementById('btnLogin');
  const spn = document.getElementById('spinner');
  const msg = document.getElementById('msg');

  if (!btn) return;

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    spn.classList.remove('d-none');
    msg.innerHTML = "Colócate frente a la cámara del TIAGo, mira al objetivo y mantén buena iluminación…";

    try {
      const r = await fetch("/api/login", { method: "POST" });
      const data = await r.json();
      if (data.ok) {
        msg.innerHTML = "<span class='text-success'>¡Hola, " + (data.user || '') + "!</span> Redirigiendo…";
        setTimeout(() => { window.location.href = "/"; }, 800);
      } else {
        // Mensaje de 20 min o error del backend
        msg.innerHTML = "<span class='text-danger'>" + (data.error || "No reconocido") + "</span>";
      }
    } catch (e) {
      msg.innerHTML = "<span class='text-danger'>Error de red o servidor</span>";
    } finally {
      spn.classList.add('d-none');
      btn.disabled = false;
    }
  });
})();
