# Sitios y tokens

Un sitio es un host de EarthRanger, por ejemplo `example.pamdas.org`, y un token de API de un usuario de EarthRanger de ese sitio. Las cargas escriben en el sitio como ese usuario.

**Registrar un sitio.** Escriba un nombre, el host y el token. smart-able llama a `/user/me` del sitio con el token antes de guardar nada, de modo que un host equivocado o un token que ya no es válido se rechaza en el momento. La fila del sitio en la página **Sitios de EarthRanger** muestra los últimos caracteres del token y el usuario con el que actúa.

**Dónde se guarda el token.** En Google Secret Manager, en un secreto con el nombre del sitio. Nunca se almacena en la base de datos, nunca se escribe en un registro de actividad y nunca lo devuelve la API. Si el token se renueva o se revoca, quite el sitio y regístrelo de nuevo; las cargas que hacían referencia al sitio anterior siguen siendo legibles, pero no se pueden continuar.

**Qué usuario usar.** La importación necesita un usuario que pueda gestionar los tipos de patrullaje, los sujetos, los grupos de sujetos, la configuración de patrullas y los campos universales de patrulla, y que pueda crear eventos en la categoría bajo la que se envía el modelo de datos. Un superusuario es la opción sencilla. El hallazgo *Al usuario del sitio le faltan permisos* nombra cada permiso que falta cuando se usa un usuario más limitado.

**Compartir un sitio.** Compartir permite a esa persona iniciar cargas en el sitio con el token de usted. Solo usted puede compartir o quitar un sitio. Quien tiene acceso a un conjunto de datos pero no al sitio no puede cargar en él.

**La URL.** Escriba la dirección del sitio en cualquier forma: solo el host, o la dirección copiada del navegador. La aplicación conserva el host y descarta el resto. Se rechazan los puertos, las direcciones IP y las credenciales en la URL.
