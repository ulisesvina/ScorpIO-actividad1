// Muestra u oculta el campo de Empresa y revisa la coincidencia de contraseñas.
// Las mismas reglas se validan siempre en el servidor.
(function () {
  var radios = document.querySelectorAll('input[name="tipo_cuenta"]');
  var bloque = document.getElementById('bloque-empresa');
  var rfc = document.getElementById('id_rfc');
  var p1 = document.getElementById('id_password1');
  var p2 = document.getElementById('id_password2');

  function actualizarTipo() {
    var esEmpresa = document.querySelector('input[name="tipo_cuenta"]:checked');
    esEmpresa = esEmpresa && esEmpresa.value === 'empresa';
    bloque.hidden = !esEmpresa;
    rfc.required = esEmpresa;
  }

  function revisarContrasenas() {
    p2.setCustomValidity(p2.value && p1.value !== p2.value ? 'Las contraseñas no coinciden.' : '');
  }

  for (var i = 0; i < radios.length; i++) radios[i].addEventListener('change', actualizarTipo);
  p1.addEventListener('input', revisarContrasenas);
  p2.addEventListener('input', revisarContrasenas);
  actualizarTipo();
})();
