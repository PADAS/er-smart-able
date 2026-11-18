# Estados

## Una carga

| Estado | Significado |
|---|---|
| <code>planning</code> planificando | Se está haciendo el plan. No escribe nada. |
| <code>planned</code> planificada | El plan está listo para leerlo y confirmarlo. |
| <code>queued</code> en cola | Confirmada; se ha pedido la ejecución y está a punto de empezar. |
| <code>running</code> en ejecución | La ejecución está recorriendo sus etapas. La página se actualiza sola cada pocos segundos. |
| <code>continuing</code> continuando | La ejecución llegó al límite de 22 horas y pasó el relevo a una nueva ejecución de sí misma. Consulte *Ejecuciones largas y continuación*. |
| <code>needs_attention</code> requiere atención | La ejecución se detuvo en un hallazgo bloqueante, o terminó con patrullas que fallaron. Lea los hallazgos, corrija el sitio y haga clic en **Continuar**. |
| <code>done</code> terminada | Todas las patrullas están en el sitio. |
| <code>failed</code> falló | El trabajo encontró un error del que no pudo recuperarse. El error y el registro de actividad están en la página. Después de corregir la causa, haga clic en **Planificar de nuevo**; el nuevo plan muestra lo que falta y ofrece **Confirmar y cargar**. (**Continuar** es solo para una carga que se detuvo por hallazgos o cuyo trabajo fue interrumpido.) |

## Una etapa

| Estado | Significado |
|---|---|
| pendiente | Todavía no se ha alcanzado en esta ejecución. |
| en ejecución | En curso, con el tiempo que lleva hasta ahora. |
| terminada | Terminada, con lo que tardó y lo que hizo. |
| detenida | La regla de detención terminó la ejecución aquí: un hallazgo bloqueante después de esta etapa. |
| falló | Un error en esta etapa terminó la ejecución. |
| interrumpida | El trabajo fue interrumpido antes de poder informar; su reserva ha caducado y **Continuar** está disponible. |
| no alcanzada | Una etapa posterior de una ejecución que se detuvo o falló antes. |

## La señal de actividad

Debajo de la tabla de etapas, mientras una carga está activa, una línea dice cuánto tiempo lleva esta ejecución y cuánto hace que el trabajo informó por última vez. El trabajo informa en cada cambio de etapa y al menos cada treinta segundos durante la importación, de modo que un tiempo «last reported» que sigue creciendo más allá de unos minutos significa que el trabajo está atascado o ha desaparecido.
