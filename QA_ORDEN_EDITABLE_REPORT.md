# QA orden de trabajo editable

Fecha: 2026-06-17

## Problema detectado

La orden de trabajo se podia guardar desde el backend, pero en la web no quedaba suficientemente claro el flujo de edicion. Al refrescar o guardar, el formulario podia volver vacio y el usuario podia interpretar que la orden no era editable.

## Correccion aplicada

- Se agrego el boton **Editar seleccionada** en la pantalla de Ordenes.
- Al seleccionar una orden, el formulario queda cargado con sus datos para poder modificar responsable, fechas, estado, trabajo solicitado, materiales y observaciones.
- Despues de guardar una edicion, la orden seleccionada queda activa y visible.
- El numero de OT queda de solo lectura en la web y el backend conserva el numero original para evitar cambios accidentales.
- Se agrego validacion para no guardar una orden sin cliente, sin fecha de inicio o sin trabajo solicitado.

## Archivos modificados

- `initrof_web/static/app.js`
- `initrof_web/static/styles.css`
- `initrof_web/templates/index.html`
- `initrof_app/core/repository.py`
- `scripts/qa_web_functional.py`
- Copias equivalentes dentro de `deploy_github`

## Pruebas realizadas

- Alta de orden manual.
- Generacion de orden desde presupuesto.
- Edicion de orden generada desde presupuesto.
- Confirmacion de que la edicion actualiza la misma orden y no crea otra.
- Confirmacion de que el numero de OT no se pisa durante la edicion.
- Recuperacion de la orden editada desde la API.
