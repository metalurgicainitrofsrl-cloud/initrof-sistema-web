# QA CAI remitos 2026-06-26

## Constancia revisada

Archivo: `C:/Users/Pc/Downloads/CONSTANCIA CAI REMITOS.pdf`

Datos confirmados:

- Contribuyente: METALURGICA INITROF S. R. L.
- CUIT: 30718288149
- CAI: 52269219201935
- Vencimiento: 25/06/2027
- Tipo comprobante: REMITO R
- Punto de venta: 2
- Rango autorizado: 201 a 300
- Cantidad autorizada: 100

## Cambios aplicados

- Se actualizo la configuracion automatica de remitos para usar el CAI `52269219201935`.
- Se actualizo el vencimiento del CAI a `25/06/2027`.
- Se ajusto la secuencia de remitos para que el proximo remito no sea menor a `R-000201`.
- En el PDF el remito `R-000201` se imprime como `0002-00000201`, respetando punto de venta 2.

## Recomendaciones operativas

- Usar como remitos reales solamente los numeros del 201 al 300 con este CAI.
- No usar como reales los remitos de prueba generados con el CAI anterior.
- Al acercarse al numero 300, pedir una nueva constancia antes de emitir mas remitos.

## Pruebas realizadas

- Validacion de CAI y vencimiento en bootstrap/configuracion.
- Conversion de presupuesto a remito con numeracion `R-000201`.
- Generacion de PDF de remito.
- QA funcional completo del sistema.
