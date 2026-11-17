# Status

## Uma carga

| Status | Significado |
|---|---|
| <code>planning</code> planejando | O plano está sendo feito. Não grava nada. |
| <code>planned</code> planejada | O plano está pronto para ser lido e confirmado. |
| <code>queued</code> na fila | Confirmada; a execução foi solicitada e está prestes a começar. |
| <code>running</code> em execução | A execução está percorrendo suas etapas. A página se atualiza sozinha a cada poucos segundos. |
| <code>continuing</code> continuando | A execução chegou ao limite de 22 horas e passou o trabalho para uma nova execução de si mesma. Consulte *Execuções longas e continuação*. |
| <code>needs_attention</code> precisa de atenção | A execução parou em uma constatação bloqueante, ou terminou com patrulhas que falharam. Leia as constatações, corrija o site e pressione **Continuar**. |
| <code>done</code> concluída | Todas as patrulhas estão no site. |
| <code>failed</code> falhou | O trabalho encontrou um erro do qual não conseguiu se recuperar. O erro e o registro estão na página. Depois de corrigir a causa, pressione **Planejar de novo**; o novo plano mostra o que falta e oferece **Confirmar e carregar**. (**Continuar** serve só para uma carga que parou por constatações ou cujo trabalho foi encerrado à força.) |

## Uma etapa

| Status | Significado |
|---|---|
| pendente | Ainda não alcançada nesta execução. |
| em execução | Em andamento, com o tempo gasto até agora. |
| concluída | Concluída, com quanto tempo levou e o que fez. |
| parada | A regra de parada encerrou a execução aqui: uma constatação bloqueante depois desta etapa. |
| falhou | Um erro nesta etapa encerrou a execução. |
| interrompida | O trabalho foi encerrado à força antes de poder informar; o bloqueio dele expirou e **Continuar** está disponível. |
| não alcançada | Uma etapa posterior de uma execução que parou ou falhou antes. |

## O sinal de atividade

Abaixo da tabela de etapas, enquanto uma carga está ativa, uma linha diz há quanto tempo esta execução está rodando e há quanto tempo o trabalho informou pela última vez. O trabalho informa a cada mudança de etapa e pelo menos a cada trinta segundos durante a importação, então um tempo "last reported" que continua crescendo além de alguns minutos significa que o trabalho travou ou sumiu.
