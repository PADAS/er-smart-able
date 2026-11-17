# Visão geral

O smart-able recebe um backup ou uma exportação de uma área de conservação do SMART, extrai os dados para que você possa explorá-los aqui e os carrega em um site do EarthRanger. Os passos, em ordem:

1. **Enviar** (Upload) um zip de backup do sistema SMART, uma pasta de instalação do SMART Desktop compactada ou uma exportação de Área de Conservação. O conjunto de dados pertence a você; depois, compartilhe-o com colegas pela página dele.
2. **Extrair** (Extract) roda como um trabalho em segundo plano por alguns minutos. Ele lê o banco de dados, grava um site navegável para cada área de conservação e publica um pacote de migração para cada uma. A lista de conjuntos de dados se atualiza sozinha enquanto o trabalho roda.
3. **Explorar** os dados extraídos pela página do conjunto de dados (**Browse** na aba Overview): patrulhas, pontos de localização (waypoints), observações, o modelo de dados e as peculiaridades que a extração encontrou.
4. **Registrar um site**: um host do EarthRanger e um token de API. O token é conferido antes de ser salvo. Consulte *Sites e tokens*.
5. **Carregar** (Load) uma área de conservação em um site pela página do conjunto de dados, na aba Overview ou Loads. Uma carga produz primeiro um plano de tudo o que gravaria; você confirma o plano, e a execução o grava. Onde o site precisa de algo que só uma pessoa pode fazer, a execução para e diz o quê. Consulte *Carregar um conjunto de dados* e *Quando uma carga para*.

Tudo o que você envia, extrai e carrega é compartilhado apenas com as pessoas com quem você compartilha. Excluir um conjunto de dados exclui os dados extraídos, os pacotes e os registros de carga dele; nunca remove nada do EarthRanger.
