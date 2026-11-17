# Anotaciones para actualizar la documentación — Caso de uso 1: Registrar Usuario

Lo implementado sigue los **diagramas de clases**; esta lista recoge todo lo que difiere de la
Especificación de requerimientos, del Diseño detallado o del Plan, para homologarlos después.

## Especificación de requerimientos (Registrar Usuario)
1. **Empresa solo con RFC.** Se eliminan nombre comercial y giro de negocio (descripción, flujo paso 2, casos de prueba).
2. **Teléfono eliminado** del registro (la clase `Usuario` del diagrama no lo tiene).
3. **Flujos alternativos A1–A6 no están definidos** en el documento (solo E1 y E2) aunque los casos de prueba los citan. Quedaron así en la implementación:
   - A1 contraseñas distintas / correo inválido · A2 campo obligatorio vacío · A3 correo de cuenta activa · A4 correo de cuenta pendiente · A5 contraseña que no cumple la política (nuevo) · A6 enlace vencido.
   - Añadir además: enlace ya utilizado, enlace inválido, y RFC vacío/inválido.
4. **Vigencia del enlace: 24 horas** (configurable). No estaba definida.
5. **Textos de error distintos a los de los casos de prueba** (CP2, CP3): «Las contraseñas no coinciden.» y «Ingresa un correo electrónico válido.». Los campos se marcan con «* obligatorio». Actualizar los resultados esperados.
6. **CP6 (correo pendiente): comportamiento ampliado.** No se crea otra cuenta y se envía un enlace nuevo, pero además los datos y la contraseña del último envío **reemplazan** a los anteriores. Evita que alguien reserve el correo ajeno con una contraseña conocida.
7. **Reenvío de correo** (no descrito como flujo): se hace desde «Confirma tu correo», desde la pantalla de enlace vencido y desde `/cuentas/reenviar-correo/`. La respuesta es igual exista o no la cuenta. Enlaces anteriores quedan invalidados al reenviar.
8. **Pantalla destino tras activar:** se muestra «Correo verificado. Ya puedes iniciar sesión.» en la propia pantalla de confirmación, con botón a una pantalla de inicio de sesión **provisional** hasta implementar ese caso de uso.
9. **Política de contraseña:** se usan los 4 validadores de Django (mínimo 8, no solo numérica, no común, no parecida al nombre/correo). La especificación solo menciona los dos primeros.
10. **Nueva regla de formato del RFC** (no estaba en los documentos): 3 letras (persona moral) o 4 (persona física) + 6 dígitos + 3 caracteres alfanuméricos; se guarda en mayúsculas y sin espacios. **Pendiente de aprobación.** El RFC **no** se obliga a ser único; confirmar si debe serlo.
11. El registro público solo crea Cliente o Empresa; el rol Admin no es seleccionable.

## Diseño detallado (diagramas de clases y secuencia)
12. **`TokenVerificacion` y `EnlaceVerificacion` se fusionan** en `EnlaceVerificacion`. Solo se guarda el hash SHA-256 del token; `usado: boolean` pasa a `usado_en: fecha`.
13. **`Usuario`:** `idUsuario: int` → `id` autogenerado; `contraseña` se guarda con hash de Django; `cuentaActiva` → `is_active` + `correo_verificado_en`; `esEmpresa` → `es_empresa`. Se añaden `is_staff`, `is_superuser`, `fecha_registro`.
14. **`Empresa` no hereda de `Usuario`** (el diagrama muestra herencia): se implementa como relación 1 a 1 (`usuario.empresa`). `Empresa.nombre` es `Usuario.nombre`; `idEmpresa` es el `id` propio; **`idCalendario` se pospone** a la integración con Google Calendar.
15. **`UsuarioBD`, `ConexionBD`, `EnlaceBD`:** los cubre el ORM de Django; no hay clases propias. Además `ServicioCorreo` aparece dos veces en el diagrama.
16. **Capa controlador:** `UsuarioController` → funciones en `views.py`; `RegistrarUsuarioService` → `servicios/registro.py` y `servicios/verificacion.py`; `DatosRegistroUsuario` → `FormularioRegistro`; `correoDisponible` y `esEmpresaValida` → `clean_correo` y la validación del RFC en el formulario.
17. **Vistas:** `RegistrarUsuarioIH`, `MensajeIH` y `PantallaPrincipalIH` son plantillas. Faltan en el diagrama las pantallas «Confirma tu correo», «Correo verificado», «Enlace inválido/vencido/usado» y «Reenviar correo».
18. Falta el **diagrama de secuencia** de reenvío y del caso «correo pendiente».

## Plan del proyecto
19. `LANGUAGE_CODE='es-mx'` y zona horaria `America/Mexico_City` (por la restricción de idioma).
20. Longitudes máximas impuestas por la base de datos (no por negocio): nombre 150, correo 254, RFC 13.

## Riesgos y limitaciones técnicas
21. El servidor de desarrollo imprime en su log la URL de activación (incluye el token). Es de un solo uso y vence; no aplica en producción con un servidor real.
22. `SECRET_KEY` sigue estando escrita en `settings.py` (ya estaba así). Moverla a variable de entorno antes de cualquier despliegue.
23. No hay límite de frecuencia para reenvíos de correo.
