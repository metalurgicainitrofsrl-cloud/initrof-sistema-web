# QA remito con Resp. Inscripto editable

Fecha: 2026-06-19

## Necesidad del usuario

En el remito impreso, la casilla de **Resp. Inscripto** del cliente quedaba marcada aunque algunos clientes no fueran responsables inscriptos.

## Solucion aplicada

- Se agrego el campo **Cliente Resp. Inscripto** en el editor de remitos.
- Si esta marcado, el PDF imprime la casilla tildada.
- Si se destilda, el PDF imprime la misma casilla sin tilde.
- Al elegir un cliente, el sistema intenta tomar un valor inicial desde las notas del cliente:
  - Si dice monotributo, exento o consumidor final, queda destildado.
  - En los demas casos queda marcado por defecto.
- El usuario puede cambiarlo manualmente antes de guardar o imprimir el remito.

## Archivos modificados

- `initrof_app/core/database.py`
- `initrof_app/core/repository.py`
- `initrof_app/services/pdf.py`
- `initrof_web/app.py`
- `initrof_web/static/app.js`
- `scripts/qa_web_functional.py`
- Copias equivalentes dentro de `deploy_github`

## Pruebas realizadas

- Conversion de presupuesto a remito con Resp. Inscripto marcado por defecto.
- Edicion de remito destildando Resp. Inscripto.
- Confirmacion de persistencia del cambio.
- Generacion de PDF del remito luego de destildar la casilla.
