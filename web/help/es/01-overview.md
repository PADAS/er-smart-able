# Descripción general

smart-able toma una copia de seguridad o una exportación de un área de conservación de SMART, la extrae para que pueda explorarla aquí y la carga en un sitio de EarthRanger. Los pasos, en orden:

1. **Subir** un zip de copia de seguridad del sistema SMART, una carpeta de instalación de SMART Desktop comprimida o una exportación de Área de Conservación. El conjunto de datos le pertenece; después puede compartirlo con sus colegas desde su página.
2. **Extraer** es un trabajo en segundo plano que dura unos minutos. Lee la base de datos, escribe un sitio explorable para cada área de conservación y publica un paquete de migración para cada una. La lista de conjuntos de datos se actualiza sola mientras el trabajo se ejecuta.
3. **Explorar** los datos extraídos desde la página del conjunto de datos (**Explorar** en su **Resumen**, o las vistas bajo **Datos** en la barra lateral): patrullas, coordenadas (waypoints), observaciones, el modelo de datos y las peculiaridades que encontró la extracción.
4. **Registrar un sitio**: un host de EarthRanger y un token de API. El token se comprueba antes de guardarlo. Consulte *Sitios y tokens*.
5. **Cargar** un área de conservación en un sitio desde la página del conjunto de datos, en su **Resumen**, o bajo **Cargas** en la barra lateral. Una carga produce primero un plan de todo lo que escribiría; usted confirma el plan y la ejecución lo escribe. Donde el sitio necesita algo que solo una persona puede hacer, la ejecución se detiene y le dice qué. Consulte *Cargar un conjunto de datos* y *Cuando una carga se detiene*.

Todo lo que usted sube, extrae y carga se comparte solo con las personas con quienes usted lo comparte. El equipo de soporte de EarthRanger también puede ver los conjuntos de datos y los sitios, para ayudar con una migración; no puede modificarlos ni cargar datos. Eliminar un conjunto de datos elimina sus datos extraídos, sus paquetes y sus registros de carga; nunca quita nada de EarthRanger.

La copia de seguridad subida se conserva durante un tiempo limitado (30 días en la aplicación alojada) y después se elimina automáticamente. La página del conjunto de datos muestra la fecha, y el propietario del conjunto de datos puede eliminar la copia de seguridad antes. Los datos extraídos no se ven afectados: se conservan hasta que se elimina el conjunto de datos. Para extraer de nuevo cuando la copia de seguridad ya no esté, súbala otra vez.

## De SMART: una copia de seguridad o una exportación {#upload-file}

Necesita un solo archivo, no los tres. La aplicación acepta cualquiera de estos, como un único archivo `.zip`:

- **Una exportación de Área de Conservación.** Contiene una sola área de conservación. SMART la llama `SMART_<area identifier>_<date>.bak.zip` (identificador del área y fecha).
- **Una copia de seguridad del sistema SMART.** SMART la llama `SMART_<date>.bak.zip`. Contiene todas las áreas de conservación de esa copia de SMART; más adelante usted elige cuál cargar.
- **Una carpeta de SMART Desktop comprimida.** Comprima en zip toda la carpeta desde la que se ejecuta SMART Desktop, con SMART Desktop cerrado. Use esta opción cuando no pueda ejecutar SMART para hacer una exportación o una copia de seguridad.

Suba el `.zip` tal como está. No lo descomprima, y no suba un archivo de su interior.
