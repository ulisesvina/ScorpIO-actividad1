// Pop-up de confirmación de «Cerrar sesión». Sin JavaScript, el formulario funciona igual.
(function () {
  var dialogo = document.getElementById('dialogo-cerrar-sesion');
  var formulario = document.getElementById('form-cerrar-sesion');
  var dialogoError = document.getElementById('dialogo-error-conexion');
  if (!dialogo || !formulario || !dialogo.showModal) return;

  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-abrir-cerrar-sesion]')) dialogo.showModal();
  });
  document.getElementById('cancelar-cerrar-sesion').addEventListener('click', function () { dialogo.close(); });

  function limpiarLocal() {
    try { window.sessionStorage.clear(); } catch (e) { /* sin acceso al almacenamiento */ }
  }

  formulario.addEventListener('submit', function (evento) {
    if (!window.fetch) return;
    evento.preventDefault();
    var destino = formulario.getAttribute('data-destino');
    fetch(formulario.action, {
      method: 'POST', body: new FormData(formulario), credentials: 'same-origin', redirect: 'manual'
    }).then(function (respuesta) {
      if (respuesta.type === 'opaqueredirect' || respuesta.ok) {
        limpiarLocal();
        window.location.assign(destino);
      } else {
        formulario.submit();  // respuesta inesperada: envío normal
      }
    }).catch(function () {
      // E1: sin conexión con el servidor.
      limpiarLocal();
      dialogo.close();
      dialogoError.showModal();
    });
  });

  document.getElementById('aceptar-error-conexion').addEventListener('click', function () {
    window.location.assign(formulario.getAttribute('data-destino'));
  });

  // A3: si el navegador restaura una página privada desde su caché, se vuelve a pedir al servidor.
  window.addEventListener('pageshow', function (e) { if (e.persisted) window.location.reload(); });
})();