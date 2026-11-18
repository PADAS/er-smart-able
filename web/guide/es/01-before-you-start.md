# Antes de empezar

Esta guía es para quien ha recibido el encargo de trasladar los datos de SMART de un sitio a EarthRanger. Le lleva desde una copia de seguridad de SMART hasta una primera migración terminada, con la aplicación alojada de migración de SMART. No necesita la línea de comandos.

## Qué hace la aplicación

Usted le entrega una copia de seguridad o una exportación de SMART. La aplicación lee la base de datos de SMART, le muestra lo que contiene y escribe el área de conservación en un sitio de EarthRanger: primero como un plan que puede leer, y después de verdad cuando usted confirma.

## Qué migra

- **El modelo de datos**: un tipo de evento de EarthRanger por cada categoría de SMART, con sus campos y sus listas de opciones.
- **La configuración de patrullas**: los tipos de patrullaje, los campos de patrulla y las opciones de estación.
- **Los guardaparques**: un sujeto de EarthRanger por cada empleado de SMART que patrulló o que sigue empleado, en un grupo (la lista de guardaparques) que usted elige.
- **Las patrullas**: cada patrulla con sus tramos, sus miembros, su trayecto GPS, sus observaciones y sus fotos.

Puede cargar primero el modelo de datos solo, o limitar las patrullas a un intervalo de fechas. Consulte [Cargar un conjunto de datos](../../help/es/03-loading.md).

## Qué no migra

- **Los datos de Perfiles.** Si el área de conservación usa el complemento Perfiles (Profiles) de SMART, puede ver esos datos en la aplicación, pero no se cargan en EarthRanger.
- **Los equipos de patrulla y los permisos.** La API de EarthRanger no puede crearlos. La carga se detiene y dice lo que un administrador de EarthRanger debe crear o conceder; después usted continúa.
- **Los iconos de los tipos de patrullaje.** La carga advierte que faltan, y un administrador los elige después.
- **Las cuentas de usuario de los guardaparques.** La carga crea los guardaparques como sujetos. Dar a un guardaparque una cuenta, vinculada a ese sujeto, es un paso para un administrador después.
- **Una patrulla sin fecha de inicio**, cuando carga un intervalo de fechas.

Nada de lo que hace la aplicación elimina datos de SMART, y eliminar un conjunto de datos o una carga en la aplicación no elimina nada de EarthRanger.

## Qué versiones de SMART

- **SMART Desktop 7.5.x**: compatible y probada.
- **SMART Desktop 8.0 a 8.1.x**: se espera que funcione, pero aún no se ha comprobado con una copia de seguridad real. Si tiene una, cuente al equipo de ingeniería de EarthRanger cómo le va.

## Dónde está la aplicación y quién puede iniciar sesión

La aplicación está en [https://smart-able-977100970772.us-central1.run.app/](https://smart-able-977100970772.us-central1.run.app/).

Inicie sesión con su cuenta de Google de EarthRanger. Si ve «Este correo electrónico no tiene permiso para usar smart-able», pida al equipo de ingeniería de EarthRanger que añada su dirección.

Lo que usted sube le pertenece. Nadie más ve un conjunto de datos o un sitio hasta que usted lo comparte.

## Cuánto tarda

La extracción tarda unos minutos. La carga en sí depende de la rapidez con que escribe el sitio de EarthRanger: unos 0,8 segundos por observación, de modo que un área de conservación con 70 000 observaciones tarda alrededor de un día. Se ejecuta sola; no necesita mantener la página abierta.

## Siguiente

Reúna las dos cosas que necesita: [Reúna lo necesario](02-get-your-inputs.md).
