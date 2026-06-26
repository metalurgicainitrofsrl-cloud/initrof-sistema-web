# QA eliminar remitos de prueba

Fecha: 2026-06-26

## Necesidad

Habia remitos de prueba anteriores al nuevo rango fiscal autorizado, por ejemplo `R-000001` a `R-000186`, visibles en el panel de ultimos remitos.

## Solucion aplicada

- Se agrego una accion para eliminar un documento seleccionado.
- Para remitos, la eliminacion individual bloquea los remitos del rango autorizado `201-300`; para esos casos corresponde anular si fuera necesario.
- Se agrego un boton en **Remitos**: **Eliminar remitos de prueba**.
- Ese boton elimina solamente remitos con numero menor o igual a `200`.
- No toca remitos del nuevo CAI, desde `R-000201` en adelante.

## Archivos modificados

- `initrof_web/app.py`
- `initrof_web/web_repository.py`
- `initrof_web/static/app.js`
- `initrof_web/templates/index.html`
- `scripts/qa_web_functional.py`
- Copias equivalentes dentro de `deploy_github`

## Pruebas realizadas

- Intento de eliminar remito autorizado `R-000201`: bloqueado correctamente.
- Creacion de remito de prueba anterior al rango autorizado.
- Limpieza automatica de remitos anteriores al `201`.
- QA funcional completo.
