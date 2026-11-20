# Cargar un conjunto de datos

Una carga pone un área de conservación de un conjunto de datos en un sitio. Iníciela desde la página del conjunto de datos con **Cargar en EarthRanger**, en su **Resumen**, o bajo **Cargas** en la barra lateral, eligiendo el área de conservación, el sitio, el idioma de las etiquetas, un modelo configurable opcional, el grupo (la lista de guardaparques) del que se eligen los guardaparques y la categoría de eventos.

## Primero el plan, después confirmar

Toda carga empieza como un **plan**: un ensayo que consulta el sitio pero no escribe nada. Muestra lo que la ejecución real crearía, actualizaría o desactivaría, los hallazgos en los que se detendría y las patrullas que importaría. Léalo y después haga clic en **Confirmar y cargar**. Si el plan ya muestra hallazgos bloqueantes, el botón dice dónde se detendrá la ejecución; aun así la ejecución escribe todo lo anterior a ese punto, de modo que confirmar es la manera normal de avanzar.

## Las cuatro etapas

Una ejecución recorre las etapas en orden. Cada una es idempotente: una segunda ejecución la repite sin daño y llega a lo que falte.

| Etapa | Qué escribe en EarthRanger |
|---|---|
| **Tipos de evento** | La categoría de eventos y un tipo de evento por cada categoría de SMART, con sus campos y sus listas de opciones, a partir del modelo de datos (y del modelo configurable, si se eligió uno). Los tipos existentes se actualizan, no se duplican. |
| **Configuración de patrullas** | Los tipos de patrullaje, los campos universales de patrulla, los sujetos guardaparques (uno por cada empleado de SMART que patrulló), su pertenencia al grupo de la lista de guardaparques y las opciones de estación. Todo lo que la API no puede hacer se convierte en un hallazgo: equipos, iconos, permisos. |
| **Comprobación previa** | No escribe nada. Comprueba que el sitio tiene todo lo que las patrullas necesitan: tipos de patrullaje, equipos, sujetos, tipos de evento, campos. |
| **Patrullas** | Las patrullas en sí, cada una con sus tramos, sus miembros, su trayecto y los eventos de sus coordenadas (waypoints). Un libro de registro anota cada patrulla cuando llega, de modo que una ejecución puede reanudarse sin duplicar nada. |

## La regla de detención

Después de la configuración de patrullas y después de la comprobación previa, la ejecución se detiene si algún hallazgo es **bloqueante**. El estado de la carga pasa a `needs_attention` y los hallazgos dicen qué hacer. Nada de lo escrito hasta entonces se deshace. Corrija el sitio y después haga clic en **Continuar**: la ejecución empieza de nuevo desde la primera etapa, lo cual es rápido porque todo está ya ahí, y llega a las patrullas.

Las **advertencias** nunca detienen una ejecución. Dejan constancia de algo que conviene saber, como una categoría desactivada o una coordenada (waypoint) cuyos eventos no se pueden agrupar.

Las patrullas que fallan durante la importación no detienen a las demás. Al final se convierten en un único hallazgo bloqueante que enumera cada error; **Continuar** reintenta solo esas patrullas.

## Categoría de eventos

La categoría de eventos es la categoría de EarthRanger a la que van los tipos de evento que crea esta carga. El valor predeterminado es `smart-<conservation area id>`, o `smart-<event type set name>` en una carga con un modelo configurable. Cuando el sitio ya tiene los tipos de evento de esta carga, se quedan en su categoría y los nuevos se unen a ellos allí, sea cual sea el valor escrito aquí. La página de la carga nombra esa categoría una vez hecho el plan.

## Varias áreas de conservación en un mismo sitio

Las áreas de conservación que usan el mismo modelo de datos comparten sus tipos de evento en un sitio, de modo que una sola consulta las abarca todas.

- **Sin modelo configurable**, cada carga en el sitio escribe el mismo grupo de tipos de evento y de listas de opciones.
- **Con un modelo configurable**, las cargas con el mismo nombre de **grupo de tipos de evento** comparten un solo grupo. El nombre es el del modelo configurable, salvo que usted lo cambie. Dele otro nombre para mantener los tipos de evento de un modelo aparte de los de otro modelo con el mismo nombre. Dé un mismo nombre a dos modelos para reunirlos.

Una carga solo añade a un grupo. Crea los tipos de evento y las opciones de lista que le faltan al sitio. Lo que hace con los que el sitio ya tiene depende de su elección (vea « Cambios hechos en el sitio » más abajo). Nunca desactiva una opción ni un tipo de evento, y nunca mueve un tipo de evento a otra categoría. Por eso una opción o un tipo de evento quitado de SMART sigue activo en el sitio hasta que un administrador lo desactive allí.

Si el modelo de esta área de conservación difiere de lo que el sitio ya tiene bajo el mismo nombre, el plan enumera los tipos de evento que difieren, y advierte cuando la carga añadiría opciones a las listas del sitio.

Un área de conservación cargada antes de que se compartieran los tipos de evento conserva sus propios tipos de evento en ese sitio. La página de la carga lo dice, y el nombre del grupo no se aplica.

## Cambios hechos en el sitio

Después de una carga, un administrador puede cambiar en el sitio los tipos de evento migrados: añadir un campo, cambiar el nombre de un tipo de evento, reformular o reordenar opciones de lista, desactivar una. El formulario de carga pregunta qué hace una carga posterior con los **tipos de evento que ya están en el sitio**.

- **Dejarlos como están** es lo elegido, salvo que usted lo cambie. La carga no escribe nada en un tipo de evento que el sitio tiene: su nombre, sus campos y si está activo se quedan. Lo mismo vale para una opción de lista: su texto, su lugar en la lista y si está activa se quedan. La carga sigue creando los tipos de evento y las opciones que le faltan al sitio.
- **Actualizarlos desde SMART** reemplaza el nombre y los campos de cada tipo de evento que difiere de SMART. Elíjalo cuando el propio modelo de datos de SMART cambió y el sitio debe seguirlo. Un campo añadido en el sitio se elimina.

El plan enumera cada tipo de evento del sitio que difiere de SMART, con los campos que solo tiene el sitio y los que solo tiene SMART. No puede decir qué lado hizo un cambio. Lea la lista antes de ejecutar una carga que actualiza.

Cuando una carga deja los tipos de evento como están y el modelo de esta área de conservación tiene un campo que le falta al tipo de evento del sitio, el plan se lo advierte. Añada el campo en el sitio, o haga el plan de nuevo con una actualización.

Un sitio que todavía tiene tipos de evento de SMART en la forma antigua de EarthRanger (versión 1) es la excepción: elija **Actualizarlos desde SMART** para su primera carga, para que la carga los convierta. Una carga que deja los tipos de evento como están no los convierte, omite los que tienen el mismo valor, y la comprobación previa indica entonces que esos tipos de evento faltan.

La elección abarca los tipos de evento y sus listas de opciones. Los tipos de patrullaje y los campos universales de patrullaje se configuran como antes.

## Cargar parte de un conjunto de datos

**Qué cargar**, en el cuadro de diálogo de la carga, tiene dos opciones.

- **El modelo de datos y las patrullas**, la opción predeterminada. Deje **Patrullas desde** y **hasta** vacíos para cargar todas las patrullas, o indique uno o ambos para cargar solo las patrullas que empiezan en esos días o entre ellos. Las observaciones, las fotos y el trayecto de una patrulla vienen con ella. Las fechas son las propias del área de conservación, tal como SMART las registró. Una patrulla que SMART guardó sin fecha de inicio queda fuera de cualquier intervalo. Un intervalo solo limita las patrullas: la carga sigue configurando todo el modelo de datos, de modo que los pasos que pide a un administrador, como crear equipos, abarcan todos los equipos del área de conservación, incluidos los que solo usaron patrullas antiguas.
- **Solo el modelo de datos**: los tipos de evento, los tipos de patrullaje y sus campos, los guardaparques como sujetos y la lista de guardaparques. Es lo que un equipo necesita para empezar a patrullar y registrar en EarthRanger sin traer su historial. Aun así se detiene en lo que un administrador debe hacer antes en el sitio, como crear equipos.

Una carga posterior en el mismo sitio puede ampliar el intervalo o añadir las patrullas. Lo que ya está importado se omite. La página de la carga y la página **Cargas** del conjunto de datos nombran lo que escribió cada carga, por ejemplo «Solo el modelo de datos» o «Patrullas del 2023-01-01 al 2024-12-31».

## Ejecuciones largas y continuación

Una ejecución importa primero cada patrulla con sus observaciones y sus fotos, y después los trayectos de cada patrulla. La barra de progreso muestra la fase en la que está, la velocidad y el tiempo que falta en esa fase.

Lo que tarda una ejecución depende de la rapidez con que escribe el sitio de EarthRanger, no de smart-able. Cada observación tarda unos 0,8 segundos, y los puntos del trayecto añaden un poco, de modo que un área de conservación con 70 000 observaciones tarda alrededor de un día. Dos cargas en dos sitios distintos se ejecutan una junto a otra a toda velocidad; dos en el mismo sitio solo se frenarían entre sí.

Un trabajo de Cloud Run puede ejecutarse como máximo 24 horas, así que, al cabo de 22 horas de ejecución, el trabajo deja de tomar patrullas nuevas, termina la que está en curso, guarda su libro de registro e inicia una nueva ejecución de sí mismo. El estado de la carga es `continuing` mientras eso ocurre, y la página nombra la continuación que está cronometrando. No se pierde nada y nada se importa dos veces. Una carga puede continuar hasta diez veces antes de marcarse como fallida; es mucho más de lo que necesita cualquier conjunto de datos.

Si un trabajo es interrumpido de golpe, por una caída del servicio por ejemplo, no puede informar. La carga conserva su último estado hasta que caduca su reserva, unas 25 horas después de que empezó el trabajo, y entonces la página ofrece **Continuar**, que reanuda a partir del libro de registro.

## Dar cuentas a los guardaparques {#rangers-accounts}

La configuración de patrullas crea un sujeto por cada empleado de SMART que aparece en una patrulla o que sigue empleado, y la importación pone en él sus patrullas, sus trayectos y sus reportes. Un guardaparque que después use EarthRanger Mobile necesita una cuenta de usuario **vinculada a ese sujeto**: los trayectos de un usuario van a su sujeto vinculado, y los eventos que reporta lo llevan como *reported by* (reportado por). Sin el vínculo, su primer inicio de sesión crea un segundo sujeto y el historial se divide.

La sección **Guardaparques** de la página de la carga, y la página **Vincular guardaparques** del conjunto de datos (que muestra la carga más reciente que llegó a la configuración de patrullas), enumeran a cada una de esas personas, con el nombre exactamente como está en el sitio, si la persona sigue activa en SMART y dos recuentos de patrullas: en las patrullas que importa esta carga (su intervalo de fechas, si se indicó uno) y en todo el conjunto de datos. Un guardaparque que sigue empleado y no tiene patrullas muestra 0, y una carga de solo el modelo de datos, que no importa patrullas, muestra solo el recuento de todo el conjunto de datos. El archivo CSV descargable tiene las mismas filas más una columna de correo vacía.

Una fila marcada *registro de empleado eliminado en SMART* es un miembro de patrulla cuyo registro de empleado ya no existe; su sujeto se nombra con un identificador. Nadie puede iniciar sesión como él, así que no necesita cuenta.

Para dar una cuenta a un guardaparque, en la administración de Django abra **Users › add**, escriba el nombre tal como aparece en la lista y, en el campo **linked subject**, elija su sujeto por ese nombre. Hágalo antes de que inicie sesión. Hoy el vínculo solo puede hacerse desde el lado del usuario, y solo lo puede hacer un administrador.

Si las cuentas se crean de otra manera, asegúrese de que el nombre y el apellido del usuario coinciden exactamente con el nombre del sujeto y de que el ajuste de sujeto del proveedor de fuente ER Track es «use existing»: EarthRanger vincula entonces el sujeto en el primer inicio de sesión del guardaparque haciendo coincidir el nombre. Un nombre que difiere en una letra recibe en su lugar un sujeto nuevo y vacío.

## Planificar de nuevo y eliminar

**Planificar de nuevo** ejecuta un plan nuevo para una carga planificada, detenida, fallida o terminada, por ejemplo después de corregir el sitio, para ver lo que falta. **Eliminar esta carga** quita el registro que smart-able guarda de la carga, su libro de registro, su plan y su registro de actividad. No quita nada de EarthRanger.

Solo puede estar activa a la vez una carga de un área de conservación dada en un sitio dado. Iniciar otra se rechaza hasta que la primera termine o se detenga.
