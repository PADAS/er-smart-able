# Visão geral

O smart-able recebe um backup ou uma exportação de uma área de conservação do SMART, extrai os dados para que você possa explorá-los aqui e os carrega em um site do EarthRanger. Os passos, em ordem:

1. **Enviar** um zip de backup do sistema SMART, uma pasta de instalação do SMART Desktop compactada ou uma exportação de Área de Conservação. O conjunto de dados pertence a você; depois, compartilhe-o com colegas pela página dele.
2. **Extrair** roda como um trabalho em segundo plano por alguns minutos. Ele lê o banco de dados, grava um site navegável para cada área de conservação e publica um pacote de migração para cada uma. A lista de conjuntos de dados se atualiza sozinha enquanto o trabalho roda.
3. **Explorar** os dados extraídos pela página do conjunto de dados (**Explorar** na **Visão geral**, ou as vistas em **Dados** na barra lateral): patrulhas, pontos de localização (waypoints), observações, o modelo de dados e as peculiaridades que a extração encontrou.
4. **Registrar um site**: um host do EarthRanger e um token de API. O token é conferido antes de ser salvo. Consulte *Sites e tokens*.
5. **Carregar** uma área de conservação em um site pela página do conjunto de dados, na **Visão geral**, ou em **Cargas** na barra lateral. Uma carga produz primeiro um plano de tudo o que gravaria; você confirma o plano, e a execução o grava. Onde o site precisa de algo que só uma pessoa pode fazer, a execução para e diz o quê. Consulte *Carregar um conjunto de dados* e *Quando uma carga para*.

Tudo o que você envia, extrai e carrega é compartilhado apenas com as pessoas com quem você compartilha. A equipe de suporte do EarthRanger também pode ver os conjuntos de dados e os sites, para ajudar em uma migração; ela não pode alterá-los nem carregar dados. Excluir um conjunto de dados exclui os dados extraídos, os pacotes e os registros de carga dele; nunca remove nada do EarthRanger.

O backup enviado fica guardado por um tempo limitado (30 dias no aplicativo hospedado) e depois é excluído automaticamente. A página do conjunto de dados mostra a data, e o dono do conjunto de dados pode excluir o backup antes. Os dados extraídos não são afetados: eles ficam até o conjunto de dados ser excluído. Para extrair de novo depois que o backup não existir mais, envie-o novamente pela aba **Backup** do conjunto de dados. Ali você também pode enviar um backup mais recente do mesmo banco de dados do SMART: ele substitui o que está guardado, e o conjunto de dados é extraído de novo a partir dele. As cargas listadas no conjunto de dados ficam.

## Do SMART: um backup ou uma exportação {#upload-file}

Você precisa de um arquivo só, não dos três. O aplicativo aceita qualquer um destes, como um único arquivo `.zip`:

- **Uma exportação de Área de Conservação.** Ela contém uma única área de conservação. O SMART a nomeia `SMART_<area identifier>_<date>.bak.zip` (identificador da área e data).
- **Um backup do sistema SMART.** O SMART o nomeia `SMART_<date>.bak.zip`. Ele contém todas as áreas de conservação daquela cópia do SMART; mais tarde você escolhe qual carregar.
- **Uma pasta do SMART Desktop compactada.** Compacte em zip a pasta inteira a partir da qual o SMART Desktop é executado, com o SMART Desktop fechado. Use esta opção quando não puder executar o SMART para fazer uma exportação ou um backup.

Envie o `.zip` como ele está. Não o descompacte, e não envie um arquivo de dentro dele.
