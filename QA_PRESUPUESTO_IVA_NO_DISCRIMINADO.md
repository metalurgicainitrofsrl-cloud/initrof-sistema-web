# QA presupuesto con IVA no discriminado

Fecha: 2026-06-18

## Necesidad del usuario

Para presupuestos especiales, por ejemplo Municipalidad, el precio debe incluir el IVA internamente pero el presupuesto no debe mostrar el IVA discriminado.

## Solucion aplicada

- Se agrego una opcion por presupuesto: **Mostrar IVA 21% discriminado**.
- La opcion queda marcada por defecto para mantener el comportamiento existente.
- Si se desmarca:
  - El sistema toma los precios de los items como precios finales.
  - No suma el 21% aparte.
  - El PDF del presupuesto no muestra la linea **IVA 21%**.
  - El total general queda igual a la suma de los items.
- Al convertir ese presupuesto a remito, se conserva el mismo criterio de total.

## Archivos modificados

- `initrof_app/core/database.py`
- `initrof_app/core/repository.py`
- `initrof_app/services/pdf.py`
- `initrof_web/app.py`
- `initrof_web/static/app.js`
- `initrof_web/static/styles.css`
- `scripts/qa_web_functional.py`
- Copias equivalentes dentro de `deploy_github`

## Pruebas realizadas

- Presupuesto normal: IVA visible por defecto y total con 21%.
- Presupuesto municipal: IVA oculto, total sin sumar IVA aparte.
- PDF de presupuesto normal.
- PDF de presupuesto municipal.
- Conversion de presupuesto a remito manteniendo el criterio de total.
