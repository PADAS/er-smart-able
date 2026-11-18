# Su primera migración

Tenga a mano su archivo de SMART y su token de EarthRanger; [Reúna lo necesario](02-get-your-inputs.md) explica qué son. Los pasos siguientes siguen el orden en que trabaja la aplicación, que también enumera la [Descripción general](../../help/es/01-overview.md) de la aplicación.

## 1. Iniciar sesión

Abra [la aplicación](https://smart-able-977100970772.us-central1.run.app/) e inicie sesión con su cuenta de Google de EarthRanger.

## 2. Subir el archivo de SMART

1. En la página **Conjuntos de datos**, haga clic en **Subir copia de seguridad o exportación**.
2. Dé al conjunto de datos un nombre que reconozca, como el área de conservación y la fecha, y elija su archivo `.zip`.
3. Haga clic en **Subir**. Una copia de seguridad grande tarda en enviarse; deje el cuadro de diálogo abierto hasta que se cierre.

El nuevo conjunto de datos aparece en la lista como **subiendo**, después **en cola**, después **en ejecución** y después **listo**. Eso tarda unos minutos, y la página se actualiza sola. Si termina como **falló**, abra el conjunto de datos: la pestaña **Resumen** muestra el error y el final del registro de actividad. [Estados](../../help/es/04-statuses.md) explica cada estado.

## 3. Explorar lo que se extrajo

Abra el conjunto de datos. Su pestaña **Resumen** enumera cada área de conservación del archivo, con su número de patrullas y de coordenadas (waypoints). Haga clic en **Explorar** para recorrer las patrullas, el mapa, las observaciones y el modelo de datos.

Compruebe que es el área de conservación que esperaba y que los números parecen correctos. Todavía no se ha escrito nada en EarthRanger.

## 4. Añadir un sitio

1. Abra el menú situado bajo su dirección de correo y elija **Sitios de EarthRanger**.
2. Haga clic en **Agregar un sitio**.
3. Escriba un nombre, la dirección del sitio y el token.

La aplicación comprueba el token con el sitio antes de guardarlo. Un host equivocado o un token que ya no es válido se rechaza en el momento. Consulte [Sitios y tokens](../../help/es/02-sites.md).

## 5. Planificar la carga

1. Vuelva al conjunto de datos y haga clic en **Cargar en EarthRanger** junto al área de conservación.
2. Elija el sitio. Deje las demás opciones como están, salvo que sepa que las necesita; [Cargar un conjunto de datos](../../help/es/03-loading.md) explica cada una.
3. Para una primera ejecución, ponga **Qué cargar** en **Solo el modelo de datos**. Es rápido, hace aparecer todo lo que un administrador tiene que hacer en el sitio, y después puede añadir las patrullas con una segunda carga.
4. Haga clic en **Hacer el plan**.

Un plan consulta el sitio pero no escribe nada. Cuando está listo, la página de la carga muestra lo que la ejecución crearía o actualizaría, y los hallazgos que haya.

## 6. Leer el plan y confirmar

Lea los hallazgos. Los hallazgos marcados como **bloqueante** son cosas que una persona debe hacer en el sitio de EarthRanger, como crear un equipo de patrulla; cada uno dice qué hacer. Los hallazgos marcados como **advertencia** son informativos y nunca detienen una ejecución.

Haga clic en **Confirmar y cargar**. Si hay hallazgos bloqueantes, el botón dice dónde se detendrá la ejecución. Es normal: la ejecución escribe todo lo anterior a ese punto, y confirmar es la manera de avanzar.

## 7. Si la carga se detiene

El estado pasa a **requiere atención** y los hallazgos dicen qué hace falta. Nada de lo escrito hasta entonces se deshace.

1. Haga lo que dice el hallazgo, o pídaselo al administrador del sitio. [Cuando una carga se detiene](../../help/es/05-stops.md) tiene una entrada para cada hallazgo.
2. Haga clic en **Continuar**. La ejecución empieza de nuevo, omite lo que ya existe y sigue adelante.

## 8. Cargar las patrullas

Cuando la carga del modelo de datos esté **terminada**, inicie una segunda carga de la misma área de conservación en el mismo sitio, con **Qué cargar** en **El modelo de datos y las patrullas**. Deje las fechas vacías para cargar todas las patrullas, o indíquelas para traer primero unos meses.

Una carga larga sigue ejecutándose sola. La página de la carga muestra su progreso y el tiempo que falta; puede cerrar la página y volver más tarde.

## 9. Comprobar el resultado en EarthRanger

Abra el sitio de EarthRanger y busque:

- los tipos de evento, en la categoría de eventos que nombra la página de la carga;
- los guardaparques, como sujetos en el grupo de la lista de guardaparques;
- algunas patrullas que reconozca del paso 3, con sus trayectos y reportes.

La sección **Guardaparques** de la página de la carga enumera cada guardaparque que creó la carga, para quien les dé cuentas de usuario. [Cargar un conjunto de datos](../../help/es/03-loading.md#rangers-accounts) explica cómo vincular una cuenta a un guardaparque.
