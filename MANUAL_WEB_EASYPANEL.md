# Publicacion web INITROF en Easypanel

## Objetivo

Publicar el sistema en `https://sistema.initrof.com.ar` para que varias computadoras accedan a la misma informacion, con numeracion consecutiva centralizada para presupuestos, remitos y ordenes.

## Configuracion en Easypanel

1. Entrar a `https://panel.initrof.com.ar`.
2. Abrir el proyecto `initrof`.
3. Crear un servicio de tipo aplicacion desde repositorio o Docker.
4. Usar el `Dockerfile` incluido en este proyecto.
5. Configurar puerto interno `8000`.
6. Crear un volumen persistente:
   - Ruta del contenedor: `/app/data`
   - Nombre sugerido: `initrof-data`
7. Variables de entorno recomendadas:
   - `INITROF_DATA_DIR=/app/data`
   - `INITROF_SECRET_KEY=` usar una clave larga y privada
   - `INITROF_ADMIN_PASSWORD=` clave inicial del usuario `admin`
8. En Dominios, crear:
   - Host: `sistema.initrof.com.ar`
   - Servicio: la aplicacion INITROF
   - Puerto: `8000`
   - HTTPS activado

## Primer ingreso

- Usuario: `admin`
- Clave inicial: la configurada en `INITROF_ADMIN_PASSWORD`. Si no se configura, sera `admin123`.

Cambiar la clave inmediatamente desde `Configuracion`.

## Remitos en hoja blanca

Los remitos generan un PDF A4 completo, con encabezado, datos fiscales, datos del cliente, tabla de detalle, firma, codigo de barras y pie CAI. Se imprimen directamente sobre una hoja A4 blanca, sin talonario ni formulario preimpreso.

## Backups

La base queda en el volumen persistente `/app/data/initrof.sqlite`. El backup premium de DonWeb protege el servidor, pero igualmente conviene descargar copias periodicas del volumen o de ese archivo.
