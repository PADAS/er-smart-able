# Cuando una carga se detiene

Una ejecución se detiene donde el sitio necesita algo que la API no puede hacer, o donde el sitio no está listo para las patrullas. Cada hallazgo de la página de la carga dice qué hacer; las entradas de aquí dan la misma instrucción con más espacio. Los valores que el hallazgo muestra con un botón de copiar son exactos: EarthRanger los hace coincidir por nombre.

Los nombres de los menús de la administración de EarthRanger se dan en inglés, tal como ella los muestra.

Después de corregir el sitio, haga clic en **Continuar**. La ejecución repite las primeras etapas, lo cual es rápido, y sigue adelante.

## Configuración de patrullas

### Crear un equipo de patrulla {#finding-team}

Las patrullas de SMART nombran un equipo; la API de EarthRanger no puede crear equipos. En la administración de Django, abra **Patrol configuration › Teams** y añada un equipo cuyo campo *display* sea exactamente el nombre de equipo mostrado. El hallazgo enumera los miembros de SMART del equipo, para su referencia; la importación identifica el equipo solo por su nombre. Hay una entrada por cada equipo que falta; créelos todos y después **Continuar**.

### Poner a los guardaparques en el grupo de sujetos de la lista de guardaparques {#finding-roster_group}

No se indicó un grupo para la lista de guardaparques al crear la carga, así que los sujetos guardaparques se crearon pero no se pusieron en el grupo del que se eligen los guardaparques. Planifique de nuevo la carga indicando un grupo, lo que permite a la ejecución añadirlos, o bien, en la administración de Django, abra **Patrol configuration › member subject groups**, elija o cree el grupo y añada los sujetos.

### Añadir los sujetos al grupo de sujetos {#finding-permission_subject_group}

El grupo de la lista de guardaparques existe, pero el usuario del sitio no puede cambiar la pertenencia a grupos de sujetos. Conceda ese permiso al usuario y haga clic en **Continuar**, o añada usted mismo los sujetos al grupo en **Django admin › Subject groups**. El nombre del grupo se muestra con un botón de copiar.

### Activar la función patrol_schemas {#finding-enable_patrol_schemas}

El sitio tiene desactivada la función de vista previa `patrol_schemas`, así que no tiene tramos de patrulla, campos universales de patrulla, equipos ni listas de guardaparques en los que importar. En la administración de Django, abra **Preview features › patrol_schemas** y actívela para este inquilino (tenant). Consulte a EarthRanger Core si la página no está disponible. Después **Continuar**; los campos universales de patrulla se escriben en la siguiente pasada.

### Conceder permiso: tipos de patrullaje {#finding-permission_patrol_types}

El usuario del sitio no puede crear ni cambiar tipos de patrullaje. En la administración de Django, abra **Users › the user** (el usuario) y añada `activity | patrol type | Can add/change patrol type`. Después **Continuar**.

### Conceder permiso: campos universales de patrulla {#finding-permission_segment_schema}

El usuario del sitio no puede escribir los campos universales de patrulla (el esquema de segmento). Añada `activity | segment type | Can change segment type`; hoy eso requiere un superusuario. Después **Continuar**.

### Conceder permiso: sujetos {#finding-permission_subjects}

El usuario del sitio no puede ver, añadir ni cambiar sujetos, así que los sujetos guardaparques no se pudieron crear ni encontrar. Añada `observations | subject | Can view/add/change subject`. Después **Continuar**.

### Conceder permiso: configuración de patrullas {#finding-permission_patrol_config}

El usuario del sitio no puede leer la configuración de patrullas, contra la que se comprueban los equipos y las listas de guardaparques. Añada `activity | patrol | Can view patrol`. Después **Continuar**.

### Elegir un icono para cada tipo de patrullaje {#finding-patrol_type_icons}

Una advertencia, no una detención. La API no puede establecer el icono de un tipo de patrullaje, así que los tipos nuevos muestran el icono de patrulla predeterminado de EarthRanger hasta que usted elija uno en **EarthRanger admin › Patrol types**.

### Poner nombre a las estaciones que SMART dejó sin nombre {#finding-station_names}

Una advertencia, no una detención. Algunas estaciones no tienen nombre en ningún idioma de SMART, así que se crearon con un nombre provisional como `Unnamed station 1a2b3c4d`. Póngales nombre en SMART y exporte de nuevo, o cambie el nombre de la opción en **Django admin › Choices** (campo `patrol_station`); una ejecución posterior vuelve a poner el nombre provisional hasta que SMART tenga un nombre.

## Comprobación previa

### La zona horaria del paquete se dedujo {#finding-timezone}

Una advertencia. SMART no registró la zona horaria del área de conservación, así que la extracción la dedujo de dónde están las coordenadas (waypoints). Las horas de las patrullas y de las observaciones se convierten con esa zona. Si es incorrecta, defina `SMART_ABLE_TIMEZONE` para la extracción y extraiga de nuevo el conjunto de datos; la página de peculiaridades explica cómo se tratan las zonas horarias.

### Faltan etiquetas en el idioma elegido {#finding-language}

Una advertencia. Algunos elementos del modelo de datos no tienen etiqueta en el idioma con el que se creó la carga, así que recurren al idioma predeterminado del paquete o a cualquier idioma que la tenga. La pestaña Data Model del conjunto de datos muestra lo bien cubierto que está cada idioma; planifique de nuevo la carga con el mejor cubierto si las etiquetas importan.

### Días de tramo sin información de hora {#finding-time_coverage}

Una advertencia, nada que hacer. Algunos días de tramo no tienen trayecto, ni hora de inicio o de fin, ni coordenada (waypoint) con hora, así que sus segmentos abarcan todo el día. Cada uno de esos segmentos se registra con `time_source: date_only`.

### Una comprobación previa no pudo ejecutarse {#finding-check_failed}

Una de las comprobaciones dio un error antes de poder informar, normalmente un problema de conexión o de permisos con el sitio. El mensaje nombra la comprobación y el error. Corrija la causa y después **Continuar**; la comprobación previa se ejecuta de nuevo desde el principio.

### La función patrol_schemas está desactivada {#finding-feature_flag}

La misma situación que *Activar la función patrol_schemas* más arriba, vista desde la comprobación previa. Active la función y después **Continuar**.

### Al usuario del sitio le faltan permisos {#finding-permissions}

El hallazgo enumera cada permiso que la importación necesita y que el usuario no tiene. Concédalos en **Django admin › Users › the user**, aplicación `activity`. Crear eventos en una categoría requiere el permiso de creación de esa categoría, que normalmente se concede mediante un conjunto de permisos. Después **Continuar**.

### Faltan tipos de patrullaje o están inactivos {#finding-patrol_types}

La configuración de patrullas crea los tipos que los tramos necesitan, así que en una ejecución esto normalmente significa que un tipo se desactivó después. Actívelo en **EarthRanger admin › Patrol types**, o haga clic en **Continuar** para que la configuración de patrullas lo cree de nuevo. En un plan esto es de esperar: el plan no escribe nada, y el hallazgo se marca como algo que la ejecución creará.

### Faltan campos universales de patrulla o están obsoletos {#finding-segment_schema}

La configuración de patrullas escribe estos campos. Si un administrador marcó uno como obsoleto a propósito, restáurelo en el generador de formularios de patrulla; si no, **Continuar**. En un plan esto es de esperar.

### Faltan opciones que usan las patrullas o están inactivas {#finding-choices}

Una advertencia. Algunas opciones de lista que usan las patrullas no están en el sitio o se desactivaron, así que esos campos se guardarían sin una entrada correspondiente. La configuración de patrullas las crea; una opción que un administrador desactivó puede reactivarse en **Django admin › Choices**.

### Hay miembros de patrulla que no se pueden poner en un segmento {#finding-subjects}

Los sujetos guardaparques de esos miembros no existen, o no están en un grupo incluido en **Patrol configuration › members**. La configuración de patrullas los crea y, si se indicó un grupo para la lista de guardaparques, los añade a él. Si no, añádalos a un grupo así en **Django admin › Subject groups**. En un plan esto es de esperar.

### Hay miembros de patrulla inactivos {#finding-inactive_members}

Una advertencia, nada que hacer. EarthRanger solo acepta miembros activos en un segmento, así que la importación reactiva esos sujetos para la ejecución y los desactiva de nuevo cuando termina. El libro de registro lo anota.

### Faltan equipos de patrulla o están inactivos {#finding-teams}

La misma situación que *Crear un equipo de patrulla* más arriba: cada equipo nombrado debe existir, activo, con exactamente ese nombre para mostrar, en **Patrol configuration › Teams**. Hay una entrada por equipo, con un botón de copiar.

### Tipos de evento {#finding-event_types}

Las categorías de SMART observadas necesitan un tipo de evento activo en el sitio. El mensaje dice qué caso se aplica:

- **Ningún tipo de evento activo**: el modelo de datos no se ha enviado bajo la categoría de eventos que usa esta carga. En un plan esto es de esperar y se marca como algo que la ejecución creará. En una ejecución, revise la categoría de eventos: si un envío anterior usó otro identificador, planifique de nuevo la carga con ese.
- **Coincide con más de un tipo de evento**: el sitio tiene varios envíos de modelo de datos, bajo categorías distintas, con los mismos nombres de tipo. Planifique de nuevo la carga con la categoría de eventos del envío contra el que importar.
- **Corresponde a un tipo de evento inactivo**: una advertencia. La categoría es una categoría superior de SMART o se desactivó; sus eventos se importan contra el tipo inactivo, que EarthRanger no ofrece para reportes nuevos. Active el tipo en **EarthRanger admin › Event types** si los guardaparques deben seguir usándolo.
- **Existe solo como variantes del modelo configurable**: esas categorías tienen un tipo de evento por formulario, y la importación todavía no sabe a qué variante pertenece una observación. Esas patrullas no se pueden importar aún; hace falta una correspondencia de variantes, que queda pendiente en er-smart-sync.

### No hay tipo de evento de agrupación {#finding-collection_type}

Una advertencia. Algunas coordenadas (waypoints) contienen varias observaciones, y el sitio no tiene un tipo de evento `incident_collection` activo bajo el que agruparlas, así que sus eventos se importan sin agrupar. Añada o active ese tipo en **EarthRanger admin › Event types** para agruparlos.

### Tramos en la fecha provisional de 1970 o que abarcan más de un año {#finding-leg_span}

Una advertencia, nada que hacer. SMART guarda algunas fechas de tramo como una fecha provisional; la importación conserva solo los días de tramo que tienen un trayecto o una coordenada (waypoint). Para corregir las fechas, corrija el tramo en SMART y exporte de nuevo.

### Observaciones de las que no se puede decir quién las reportó {#finding-observers}

Una advertencia. Cada evento importado nombra a quien lo reportó: el sujeto del observador de SMART o, cuando esa persona no tiene sujeto en el sitio, el líder del tramo, y si no, su primer miembro. Las observaciones enumeradas no tienen ninguno de ellos, así que sus eventos no indican quién los reportó. Nada que hacer a menos que importe: dé al observador un registro de empleado en SMART y exporte de nuevo. Un plan enumera solo las observaciones que los sujetos de la propia ejecución no permiten resolver.

### La extracción registró advertencias {#finding-bundle_warnings}

Una advertencia. smart-able anotó cosas sobre los datos cuando escribió el paquete. Están enumeradas en el manifiesto del paquete y explicadas en *SMART data quirks* (las peculiaridades de los datos de SMART, en inglés).

## Importación

### Hubo patrullas que no se pudieron importar {#finding-patrols_failed}

Cada patrulla fallida se enumera con su error. La mayoría de los errores nombran algo que falta en el sitio: un equipo, un sujeto, un tipo de evento. Corríjalo y después **Continuar**; solo se reintentan las patrullas fallidas. Un `500` en un identificador de patrulla que ya está en el sitio es EarthRanger rechazando un duplicado; el reintento lee la patrulla existente y sigue adelante.

### El token del sitio ya no funciona {#finding-site_token_rejected}

El sitio rechazó el token, así que no se escribió nada. Quite el sitio, regístrelo de nuevo con un token que funcione e inicie una carga nueva.
