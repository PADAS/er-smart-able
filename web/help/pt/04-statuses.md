# Status

O aplicativo mostra os status em inglês; aqui eles são dados como aparecem.

## Uma carga

| Status | Significado |
|---|---|
| <code>planning</code> | O plano está sendo feito. Não grava nada. |
| <code>planned</code> | O plano está pronto para ser lido e confirmado. |
| <code>queued</code> | Confirmada; a execução foi solicitada e está prestes a começar. |
| <code>running</code> | A execução está percorrendo suas etapas. A página se atualiza sozinha a cada poucos segundos. |
| <code>continuing</code> | A execução chegou ao limite de 22 horas e passou o trabalho para uma nova execução de si mesma. Consulte *Execuções longas e continuação*. |
| <code>needs_attention</code> | A execução parou em uma constatação bloqueante, ou terminou com patrulhas que falharam. Leia as constatações, corrija o site e pressione **Continue** (continuar). |
| <code>done</code> | Todas as patrulhas estão no site. |
| <code>failed</code> | O trabalho encontrou um erro do qual não conseguiu se recuperar. O erro e o registro estão na página. Depois de corrigir a causa, pressione **Plan again** (planejar de novo); o novo plano mostra o que falta e oferece Confirm. (Continue serve só para uma carga que parou por constatações ou cujo trabalho foi encerrado à força.) |

## Uma etapa

| Status | Significado |
|---|---|
| pending (pendente) | Ainda não alcançada nesta execução. |
| running (em execução) | Em andamento, com o tempo gasto até agora. |
| done (concluída) | Concluída, com quanto tempo levou e o que fez. |
| stopped (parada) | A regra de parada encerrou a execução aqui: uma constatação bloqueante depois desta etapa. |
| failed (falhou) | Um erro nesta etapa encerrou a execução. |
| interrupted (interrompida) | O trabalho foi encerrado à força antes de poder informar; a reserva dele expirou e **Continue** está disponível. |
| not reached (não alcançada) | Uma etapa posterior de uma execução que parou ou falhou antes. |

## O sinal de atividade

Abaixo da tabela de etapas, enquanto uma carga está ativa, uma linha diz há quanto tempo esta execução está rodando e há quanto tempo o trabalho informou pela última vez. O trabalho informa a cada mudança de etapa e pelo menos a cada trinta segundos durante a importação, então um tempo "last reported" que continua crescendo além de alguns minutos significa que o trabalho travou ou sumiu.
