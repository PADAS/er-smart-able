# Cargar un conjunto de datos

Una carga pone un área de conservación de un conjunto de datos en un sitio. Iníciela desde la página del conjunto de datos con **Load into EarthRanger** (cargar en EarthRanger), en la pestaña Overview o Loads, eligiendo el área de conservación, el sitio, el idioma de las etiquetas, un modelo configurable opcional, el grupo (la lista de guardaparques) del que se eligen los guardaparques y la categoría de eventos.

## Primero el plan, después confirmar

Toda carga empieza como un **plan**: un ensayo que consulta el sitio pero no escribe nada. Muestra lo que la ejecución real crearía, actualizaría o desactivaría, los hallazgos en los que se detendría y las patrullas que importaría. Léalo y después haga clic en **Confirm and load** (confirmar y cargar). Si el plan ya muestra hallazgos bloqueantes, el botón dice dónde se detendrá la ejecución; aun así la ejecución escribe todo lo anterior a ese punto, de modo que confirmar es la manera normal de avanzar.

## Las cuatro etapas

Una ejecución recorre las etapas en orden. Cada una es idempotente: una segunda ejecución la repite sin daño y llega a lo que falte.

| Etapa | Qué escribe en EarthRanger |
|---|---|
| **Event types** (tipos de evento) | La categoría de eventos y un tipo de evento por cada categoría de SMART, con sus campos y sus listas de opciones, a partir del modelo de datos (y del modelo configurable, si se eligió uno). Los tipos existentes se actualizan, no se duplican. |
| **Patrol setup** (configuración de patrullas) | Los tipos de patrullaje, los campos universales de patrulla, los sujetos guardaparques (uno por cada empleado de SMART que patrulló), su pertenencia al grupo de la lista de guardaparques y las opciones de estación. Todo lo que la API no puede hacer se convierte en un hallazgo: equipos, iconos, permisos. |
| **Preflight** (comprobación previa) | No escribe nada. Comprueba que el sitio tiene todo lo que las patrullas necesitan: tipos de patrullaje, equipos, sujetos, tipos de evento, campos. |
| **Patrols** (patrullas) | Las patrullas en sí, cada una con sus tramos, sus miembros, su trayecto y los eventos de sus coordenadas (waypoints). Un libro de registro anota cada patrulla cuando llega, de modo que una ejecución puede reanudarse sin duplicar nada. |

## La regla de detención

Después de la configuración de patrullas y después de la comprobación previa, la ejecución se detiene si algún hallazgo es **bloqueante**. El estado de la carga pasa a `needs_attention` y los hallazgos dicen qué hacer. Nada de lo escrito hasta entonces se deshace. Corrija el sitio y después haga clic en **Continue** (continuar): la ejecución empieza de nuevo desde la primera etapa, lo cual es rápido porque todo está ya ahí, y llega a las patrullas.

Las **advertencias** nunca detienen una ejecución. Dejan constancia de algo que conviene saber, como una categoría desactivada o una coordenada (waypoint) cuyos eventos no se pueden agrupar.

Las patrullas que fallan durante la importación no detienen a las demás. Al final se convierten en un único hallazgo bloqueante que enumera cada error; **Continue** reintenta solo esas patrullas.

## Categoría de eventos

La categoría de eventos es el identificador de EarthRanger bajo el que se envía el modelo de datos. El valor predeterminado es `smart-<conservation area id>`. Si ya se envió al sitio un modelo de datos de esta área de conservación, por ejemplo con la herramienta de línea de comandos, use el identificador que usó ese envío, para que los tipos de evento se actualicen en lugar de crearse por segunda vez bajo una categoría nueva.

## Cargar parte de un conjunto de datos

**What to load** (qué cargar), en el cuadro de diálogo de la carga, tiene dos opciones.

- **The data model and patrols** (el modelo de datos y las patrullas), la opción predeterminada. Deje **Patrols from** y **to** (patrullas desde… hasta…) vacíos para cargar todas las patrullas, o indique uno o ambos para cargar solo las patrullas que empiezan en esos días o entre ellos. Las observaciones, las fotos y el trayecto de una patrulla vienen con ella. Las fechas son las propias del área de conservación, tal como SMART las registró. Una patrulla que SMART guardó sin fecha de inicio queda fuera de cualquier intervalo. Un intervalo solo limita las patrullas: la carga sigue configurando todo el modelo de datos, de modo que los pasos que pide a un administrador, como crear equipos, abarcan todos los equipos del área de conservación, incluidos los que solo usaron patrullas antiguas.
- **The data model only** (solo el modelo de datos): los tipos de evento, los tipos de patrullaje y sus campos, los guardaparques como sujetos y la lista de guardaparques. Es lo que un equipo necesita para empezar a patrullar y registrar en EarthRanger sin traer su historial. Aun así se detiene en lo que un administrador debe hacer antes en el sitio, como crear equipos.

Una carga posterior en el mismo sitio puede ampliar el intervalo o añadir las patrullas. Lo que ya está importado se omite. La página de la carga y la pestaña Loads del conjunto de datos nombran lo que escribió cada carga, por ejemplo «Data model only» o «Patrols from 2023-01-01 to 2024-12-31».

## Ejecuciones largas y continuación

Una ejecución importa primero cada patrulla con sus observaciones y sus fotos, y después los trayectos de cada patrulla. La barra de progreso muestra la fase en la que está, la velocidad y el tiempo que falta en esa fase.

Lo que tarda una ejecución depende de la rapidez con que escribe el sitio de EarthRanger, no de smart-able. Cada observación tarda unos 0,8 segundos, y los puntos del trayecto añaden un poco, de modo que un área de conservación con 70 000 observaciones tarda alrededor de un día. Dos cargas en dos sitios distintos se ejecutan una junto a otra a toda velocidad; dos en el mismo sitio solo se frenarían entre sí.

Un trabajo de Cloud Run puede ejecutarse como máximo 24 horas, así que, al cabo de 22 horas de ejecución, el trabajo deja de tomar patrullas nuevas, termina la que está en curso, guarda su libro de registro e inicia una nueva ejecución de sí mismo. El estado de la carga es `continuing` mientras eso ocurre, y la página nombra la continuación que está cronometrando. No se pierde nada y nada se importa dos veces. Una carga puede continuar hasta diez veces antes de marcarse como fallida; es mucho más de lo que necesita cualquier conjunto de datos.

Si un trabajo es interrumpido de golpe, por una caída del servicio por ejemplo, no puede informar. La carga conserva su último estado hasta que caduca su reserva, unas 25 horas después de que empezó el trabajo, y entonces la página ofrece **Continue**, que reanuda a partir del libro de registro.

## Dar cuentas a los guardaparques {#rangers-accounts}

La configuración de patrullas crea un sujeto por cada empleado de SMART que aparece en una patrulla o que sigue empleado, y la importación pone en él sus patrullas, sus trayectos y sus reportes. Un guardaparque que después use EarthRanger Mobile necesita una cuenta de usuario **vinculada a ese sujeto**: los trayectos de un usuario van a su sujeto vinculado, y los eventos que reporta lo llevan como *reported by* (reportado por). Sin el vínculo, su primer inicio de sesión crea un segundo sujeto y el historial se divide.

La sección **Rangers** (guardaparques) de la página de la carga, y la pestaña **Rangers** del conjunto de datos (que muestra la carga más reciente que llegó a la configuración de patrullas), enumeran a cada una de esas personas, con el nombre exactamente como está en el sitio, si la persona sigue activa en SMART y dos recuentos de patrullas: en las patrullas que importa esta carga (su intervalo de fechas, si se indicó uno) y en todo el conjunto de datos. Un guardaparque que sigue empleado y no tiene patrullas muestra 0, y una carga de solo el modelo de datos, que no importa patrullas, muestra solo el recuento de todo el conjunto de datos. El archivo CSV descargable tiene las mismas filas más una columna de correo vacía.

Una fila marcada *employee record deleted in SMART* (registro de empleado eliminado en SMART) es un miembro de patrulla cuyo registro de empleado ya no existe; su sujeto se nombra con un identificador. Nadie puede iniciar sesión como él, así que no necesita cuenta.

Para dar una cuenta a un guardaparque, en la administración de Django abra **Users › add**, escriba el nombre tal como aparece en la lista y, en el campo **linked subject**, elija su sujeto por ese nombre. Hágalo antes de que inicie sesión. Hoy el vínculo solo puede hacerse desde el lado del usuario, y solo lo puede hacer un administrador.

Si las cuentas se crean de otra manera, asegúrese de que el nombre y el apellido del usuario coinciden exactamente con el nombre del sujeto y de que el ajuste de sujeto del proveedor de fuente ER Track es «use existing»: EarthRanger vincula entonces el sujeto en el primer inicio de sesión del guardaparque haciendo coincidir el nombre. Un nombre que difiere en una letra recibe en su lugar un sujeto nuevo y vacío.

## Planificar de nuevo y eliminar

**Plan again** (planificar de nuevo) ejecuta un plan nuevo para una carga planificada, detenida, fallida o terminada, por ejemplo después de corregir el sitio, para ver lo que falta. **Delete this load** (eliminar esta carga) quita el registro que smart-able guarda de la carga, su libro de registro, su plan y su registro de actividad. No quita nada de EarthRanger.

Solo puede estar activa a la vez una carga de un área de conservación dada en un sitio dado. Iniciar otra se rechaza hasta que la primera termine o se detenga.
