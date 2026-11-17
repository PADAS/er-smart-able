# Estados

La aplicación muestra los estados en inglés; aquí se dan tal como aparecen.

## Una carga

| Estado | Significado |
|---|---|
| <code>planning</code> | Se está haciendo el plan. No escribe nada. |
| <code>planned</code> | El plan está listo para leerlo y confirmarlo. |
| <code>queued</code> | Confirmada; se ha pedido la ejecución y está a punto de empezar. |
| <code>running</code> | La ejecución está recorriendo sus etapas. La página se actualiza sola cada pocos segundos. |
| <code>continuing</code> | La ejecución llegó al límite de 22 horas y pasó el relevo a una nueva ejecución de sí misma. Consulte *Ejecuciones largas y continuación*. |
| <code>needs_attention</code> | La ejecución se detuvo en un hallazgo bloqueante, o terminó con patrullas que fallaron. Lea los hallazgos, corrija el sitio y haga clic en **Continue** (continuar). |
| <code>done</code> | Todas las patrullas están en el sitio. |
| <code>failed</code> | El trabajo encontró un error del que no pudo recuperarse. El error y el registro de actividad están en la página. Después de corregir la causa, haga clic en **Plan again** (planificar de nuevo); el nuevo plan muestra lo que falta y ofrece Confirm. (Continue es solo para una carga que se detuvo por hallazgos o cuyo trabajo fue interrumpido.) |

## Una etapa

| Estado | Significado |
|---|---|
| pending (pendiente) | Todavía no se ha alcanzado en esta ejecución. |
| running (en ejecución) | En curso, con el tiempo que lleva hasta ahora. |
| done (terminada) | Terminada, con lo que tardó y lo que hizo. |
| stopped (detenida) | La regla de detención terminó la ejecución aquí: un hallazgo bloqueante después de esta etapa. |
| failed (fallida) | Un error en esta etapa terminó la ejecución. |
| interrupted (interrumpida) | El trabajo fue interrumpido antes de poder informar; su reserva ha caducado y **Continue** está disponible. |
| not reached (no alcanzada) | Una etapa posterior de una ejecución que se detuvo o falló antes. |

## La señal de actividad

Debajo de la tabla de etapas, mientras una carga está activa, una línea dice cuánto tiempo lleva esta ejecución y cuánto hace que el trabajo informó por última vez. El trabajo informa en cada cambio de etapa y al menos cada treinta segundos durante la importación, de modo que un tiempo «last reported» que sigue creciendo más allá de unos minutos significa que el trabajo está atascado o ha desaparecido.
