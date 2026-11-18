# Descripción general

smart-able toma una copia de seguridad o una exportación de un área de conservación de SMART, la extrae para que pueda explorarla aquí y la carga en un sitio de EarthRanger. Los pasos, en orden:

1. **Subir** un zip de copia de seguridad del sistema SMART, una carpeta de instalación de SMART Desktop comprimida o una exportación de Área de Conservación. El conjunto de datos le pertenece; después puede compartirlo con sus colegas desde su página.
2. **Extraer** es un trabajo en segundo plano que dura unos minutos. Lee la base de datos, escribe un sitio explorable para cada área de conservación y publica un paquete de migración para cada una. La lista de conjuntos de datos se actualiza sola mientras el trabajo se ejecuta.
3. **Explorar** los datos extraídos desde la página del conjunto de datos (**Explorar** en la pestaña **Resumen**): patrullas, coordenadas (waypoints), observaciones, el modelo de datos y las peculiaridades que encontró la extracción.
4. **Registrar un sitio**: un host de EarthRanger y un token de API. El token se comprueba antes de guardarlo. Consulte *Sitios y tokens*.
5. **Cargar** un área de conservación en un sitio desde la página del conjunto de datos, en su pestaña **Resumen** o **Cargas**. Una carga produce primero un plan de todo lo que escribiría; usted confirma el plan y la ejecución lo escribe. Donde el sitio necesita algo que solo una persona puede hacer, la ejecución se detiene y le dice qué. Consulte *Cargar un conjunto de datos* y *Cuando una carga se detiene*.

Todo lo que usted sube, extrae y carga se comparte solo con las personas con quienes usted lo comparte. Eliminar un conjunto de datos elimina sus datos extraídos, sus paquetes y sus registros de carga; nunca quita nada de EarthRanger.

La copia de seguridad subida se conserva durante un tiempo limitado (30 días en la aplicación alojada) y después se elimina automáticamente. La página del conjunto de datos muestra la fecha, y el propietario del conjunto de datos puede eliminar la copia de seguridad antes. Los datos extraídos no se ven afectados: se conservan hasta que se elimina el conjunto de datos. Para extraer de nuevo cuando la copia de seguridad ya no esté, súbala otra vez.
