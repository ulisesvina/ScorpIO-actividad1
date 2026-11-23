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

---

# Anotaciones — Caso de uso 2: Iniciar sesión

## Especificación de requerimientos (Iniciar sesión)
24. **Flujo alternativo A1 truncado:** el texto termina en «...y pide q». Completar. Implementado: se informa «Ambos campos son obligatorios.» y se marca cada campo vacío.
25. **Precondición «pantalla principal con el botón iniciar sesión»:** no existe esa pantalla; el inicio de sesión es una página propia (`/cuentas/iniciar-sesion/`). Actualizar la precondición y el prototipo.
26. **Mensaje A2:** «Correo o contraseña incorrectos.» (con punto final). Se conserva el correo escrito y nunca se vuelve a mostrar la contraseña.
27. **Formato de correo inválido (no definido):** se muestra «Ingresa un correo electrónico válido.», que no revela si la cuenta existe.
28. **A3 (cuenta pendiente):** no se crea sesión y se muestra «Confirma tu correo» con «Reenviar correo». La especificación no dice si se envía un enlace nuevo automáticamente: **no se envía**, solo se ofrece.
29. **Cuenta verificada pero desactivada** (por ejemplo, dada de baja): no está contemplada. Se trata como credenciales incorrectas.
30. **E1:** mensaje «Ocurrió un problema al iniciar sesión. Intenta más tarde.»
31. **Pantalla de inicio por rol:** el Cliente ve Buscar espacios, Mis reservas, Mi perfil; la Empresa suma Mis espacios y Publicar espacio. Todas aparecen como «Próximamente» hasta que existan esos casos de uso. El Administrador ve el inicio genérico con un enlace a `/admin/`.
32. **Parámetro `next`:** si se llegó al inicio de sesión desde una página protegida, se regresa a ella tras entrar, solo si pertenece al mismo sitio.
33. **Sin «Recordarme» ni límite de intentos fallidos** (no están en los documentos).

## Diseño detallado (diagramas)
34. **Clases duplicadas en el diagrama:** `IniciarSesionController` y `AutenticacionController`, e `IniciarSesionService` y `AutenticacionService`, hacen lo mismo. Se consolidan en una vista (`views_sesion.iniciar_sesion`) y un servicio (`servicios/autenticacion.py`).
35. **`Sesion`, `SesionBD` y `crearSesion`:** la sesión la gestiona Django (`login()` con sesión en base de datos, que además renueva la clave de sesión). No hay modelo `Sesion` propio ni token manual.
36. **`verificarEstadoCuenta`** se integra en `verificar_credenciales`, que devuelve OK, PENDIENTE o CREDENCIALES_INVALIDAS. No se usa `authenticate()` de Django porque descarta las cuentas inactivas sin distinguir el motivo.
37. **`reenviarVerificacion`** reutiliza el reenvío del caso de uso 1.
38. **`DatosInicioSesion`** → `FormularioInicioSesion` (`forms_sesion.py`). **`PantallaInicioIH`** → `inicio.html`, con sus accesos aún sin pantalla destino.
39. Falta el diagrama de secuencia del caso «cuenta pendiente» (A3).

## Coordinación con Cerrar sesión
40. **Duración de la sesión:** se deja el valor por defecto de Django (2 semanas, absoluta). El flujo A1 de Cerrar sesión habla de expiración **por inactividad**; implementarlo requiere definir un tiempo y activar `SESSION_SAVE_EVERY_REQUEST`. Acordarlo con quien implemente ese caso.
41. El botón «Cerrar sesión» de la pantalla de inicio es solo una etiqueta «Próximamente».
42. Al integrar «Publicar espacio», enlazar «Mis espacios» y «Publicar espacio» en `inicio.html`.

## Riesgos y limitaciones
43. No hay límite de intentos fallidos de inicio de sesión (fuerza bruta). Recomendable antes de cualquier despliegue.


---

# Anotaciones — Caso de uso 4: Publicar espacio (Belén)

Igual que en Registrar usuario, aquí anoto lo que quedó diferente a lo que dicen los documentos
para que lo actualicemos después. Me basé sobre todo en el diagrama de clases de Publicar espacio
y en el diagrama de secuencia, y cuando les faltaba algo lo tomé del diagrama general.

## Especificación de requerimientos
1. En las pantallas puse "Empresa" en lugar de "Proveedor", porque en el Plan quedamos en usar "empresa". También hay que cambiarlo en el paso 6 del flujo normal.
2. Los mensajes son los mismos de la especificación. Ojo: para E3 hay dos versiones, el flujo dice "Ocurrió un problema al guardar las imágenes. Intente nuevamente" y el caso de prueba E-3 dice "No fue posible guardar las fotografías. Intenta cargarlas nuevamente". Usé el del flujo, hay que dejar uno solo.
3. Formatos de foto: solo JPEG y PNG, porque no estaba definido. Además se revisa que el archivo de verdad sea una imagen y no solo que tenga la extensión.
4. Los horarios son semanales (día de la semana con hora de inicio y fin) y valen del 1 de noviembre al 31 de diciembre de 2026, como lo acordamos.
5. Conflicto con Google Calendar (A5 y A9): si un día de ese horario ya tiene un evento, todo el horario de ese día de la semana se marca como "Ocupado en Google Calendar". Las fechas que ya pasaron no se toman en cuenta.
6. Los horarios ocupados sí se guardan, pero con disponible = False, para que no aparezcan como disponibles (así lo pide la poscondición).
7. Cuando sale "Datos guardados y calendario sincronizado" los datos se guardan en la sesión, no en la base de datos. Todo se guarda hasta que se presiona "Publicar", igual que en el diagrama de secuencia.
8. Si después de sincronizar se cambia el precio o algún horario, hay que volver a sincronizar antes de poder continuar.
9. Agregué dos cosas que no vienen en el prototipo: quitar una foto que ya se subió y eliminar una fila de horario. Sin eso no había forma de corregir los casos A2 y A4.
10. La precondición dice que la empresa ya tiene vinculado Google Calendar, pero ningún caso de uso explica cómo. Hice la pantalla "Vincular Google Calendar": la empresa comparte su calendario con la cuenta de servicio de Reserva-Hub (permiso "Ver solo disponibilidad") y escribe el ID de su calendario.
11. En "Espacio publicado" no puse el botón "Ver espacio" porque ese caso de uso todavía no está. Tampoco puse el menú lateral (Inicio, Reservas, Perfil) porque esas pantallas aún no existen.
12. En los prototipos de las páginas 43 y 44 están cambiados los títulos de "Después de sincronizar" y "Revisar y publicar". La imagen de "Falla al guardar las fotografías" está vacía.

## Diseño detallado (diagramas)
13. Algunas pantallas tienen nombres distintos entre diagramas (FormularioEspacio / FormularioEspacioIH, PantallaPrecioYHorarios / PantallaPrecioYDisponibilidadIH, MisEspaciosIH / PantallaMisEspaciosIH / PantallaEspacioH). Todas quedaron como plantillas. PublicarEspacioServicio y PublicarEspacioService son la misma clase, está en servicios/publicar_espacio.py.
14. EspacioRepository, EspacioBD y ConexionBD no son clases propias, las cubre el ORM de Django (igual que hizo Emiliano). El espacio, la tarifa, los horarios y las fotos se guardan en una sola transacción, así que si falla la base de datos (E2) no queda nada guardado a medias.
15. SincronizadoIH, que sale en el diagrama de navegación, no es una pantalla aparte. Es solo el estado de la pantalla de precio cuando ya se sincronizó, como se ve en los prototipos.
16. Del diagrama general tomé: idEmpresa de Espacio (quedó como "empresa"), formato y esValida() de Fotografia, esValida() de Tarifa, esValido() y seSuperponeCon() de HorarioDisponible, y descartarTemporales() de AlmacenDeImagenes.
17. En Tarifa usé "periodo" (diagrama de Publicar espacio) y no "modalidad" (diagrama general). En pantalla dice "Modalidad de tarifa": por hora, por día o por semana.
18. Agregué el campo id_calendario a Empresa en la app cuentas (migración 0002). Emiliano lo había dejado pendiente para cuando se hiciera lo de Google Calendar. El idCalendario que aparece en Espacio en el diagrama general no lo usé.
19. GoogleCalendarService tiene revisarHorarios() y consultarEventos(idCal, rango). Se conecta con una cuenta de servicio y solo consulta si los horarios están libres u ocupados, no lee los eventos. En el diagrama de secuencia Google Calendar no aparece; ahí revisarHorarios está en PublicarEspacioService, que en el código le pasa la consulta a este servicio.
20. Fotos: el diagrama de secuencia las guarda hasta publicar, pero el flujo E3 y su prototipo piden avisar antes. Lo que hice: en el paso 1 se revisan y se guardan en una carpeta temporal, y al publicar se copian a la carpeta final. Las temporales se borran hasta que el espacio ya quedó registrado.
21. Hay métodos en la secuencia que no estaban en el diagrama de clases: guardarDatosYSincronizar(), capturarDatos(datos, empresa) de Espacio y mostrarAviso(). capturar_datos quedó en el modelo y los otros dos dentro de la vista.
22. Falta agregar al diagrama la pantalla "Vincular Google Calendar" y su formulario.

## Plan del proyecto
23. Dependencias nuevas: Pillow 11.3.0 (para revisar las imágenes), google-api-python-client 2.190.0 y google-auth 2.45.0 (para Google Calendar).
24. Las fotos se guardan en la carpeta media/ del proyecto porque no tenemos hosting.
25. En el Plan dice que la sincronización con Google Calendar es bidireccional. En Publicar espacio solo se lee la disponibilidad; crear eventos le tocaría a Reservar espacio.

## Pendientes y riesgos
26. La llave de la cuenta de servicio se configura con la variable GOOGLE_CALENDAR_CREDENCIALES. No hay que subirla nunca al repositorio.
27. Si alguien empieza a publicar y deja el formulario sin presionar "Cancelar", sus fotos temporales se quedan en media/espacios/temporales/. Por ahora no se borran solas.
28. No hay límite de tamaño ni de cantidad de fotos.
