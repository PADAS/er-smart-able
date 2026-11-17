# Carregar um conjunto de dados

Uma carga coloca uma área de conservação de um conjunto de dados em um site. Inicie-a pela página do conjunto de dados com **Load into EarthRanger** (carregar no EarthRanger), na aba Overview ou Loads, escolhendo a área de conservação, o site, o idioma dos rótulos, um modelo configurável opcional, o grupo (a lista de guarda-parques) do qual os guarda-parques são escolhidos e a categoria de eventos.

## Primeiro o plano, depois a confirmação

Toda carga começa como um **plano**: um ensaio que consulta o site mas não grava nada. Ele mostra o que a execução real criaria, atualizaria ou desativaria, as constatações em que ela pararia e as patrulhas que importaria. Leia-o e depois pressione **Confirm and load** (confirmar e carregar). Se o plano já mostra constatações bloqueantes, o botão diz onde a execução vai parar; mesmo assim a execução grava tudo o que vem antes desse ponto, então confirmar é a maneira normal de avançar.

## As quatro etapas

Uma execução percorre as etapas em ordem. Cada uma é idempotente: uma segunda execução a refaz sem prejuízo e alcança o que falta.

| Etapa | O que ela grava no EarthRanger |
|---|---|
| **Event types** (tipos de evento) | A categoria de eventos e um tipo de evento para cada categoria do SMART, com seus campos e suas listas de opções, a partir do modelo de dados (e do modelo configurável, se um foi escolhido). Os tipos existentes são atualizados, não duplicados. |
| **Patrol setup** (configuração de patrulhas) | Os tipos de patrulha, os campos universais de patrulha, os sujeitos guarda-parques (um para cada funcionário do SMART que patrulhou), a participação deles no grupo da lista de guarda-parques e as opções de base. Tudo o que a API não consegue fazer vira uma constatação: equipes, ícones, permissões. |
| **Preflight** (verificação prévia) | Não grava nada. Verifica se o site tem tudo de que as patrulhas precisam: tipos de patrulha, equipes, sujeitos, tipos de evento, campos. |
| **Patrols** (patrulhas) | As patrulhas em si, cada uma com suas pernas, seus membros, sua trilha e os eventos dos seus pontos de localização (waypoints). Um livro de registro anota cada patrulha quando ela chega, então uma execução pode ser retomada sem duplicar nada. |

## A regra de parada

Depois da configuração de patrulhas e depois da verificação prévia, a execução para se alguma constatação for **bloqueante**. O status da carga passa a `needs_attention` e as constatações dizem o que fazer. Nada do que já foi gravado é desfeito. Corrija o site e depois pressione **Continue** (continuar): a execução começa de novo pela primeira etapa, o que é rápido porque tudo já está lá, e chega às patrulhas.

Os **avisos** nunca param uma execução. Eles registram algo que vale a pena saber, como uma categoria aposentada ou um ponto de localização (waypoint) cujos eventos não podem ser agrupados.

As patrulhas que falham durante a importação não param as outras. No fim elas viram uma única constatação bloqueante que lista cada erro; **Continue** tenta de novo só essas patrulhas.

## Categoria de eventos

A categoria de eventos é o identificador do EarthRanger sob o qual o modelo de dados é enviado. O padrão é `smart-<conservation area id>`. Se um modelo de dados desta área de conservação já foi enviado ao site, por exemplo com a ferramenta de linha de comando, use o identificador que esse envio usou, para que os tipos de evento sejam atualizados em vez de criados uma segunda vez sob uma categoria nova.

## Carregar parte de um conjunto de dados

**What to load** (o que carregar), na caixa de diálogo da carga, tem duas opções.

- **The data model and patrols** (o modelo de dados e as patrulhas), o padrão. Deixe **Patrols from** e **to** (patrulhas de… até…) vazios para carregar todas as patrulhas, ou preencha um ou ambos para carregar só as patrulhas que começam nesses dias ou entre eles. As observações, as fotos e a trilha de uma patrulha vêm com ela. As datas são as da própria área de conservação, como o SMART as registrou. Uma patrulha que o SMART guardou sem data de início fica fora de qualquer intervalo. Um intervalo restringe só as patrulhas: a carga ainda configura todo o modelo de dados, então os passos que ela pede a um administrador, como criar equipes, abrangem todas as equipes da área de conservação, inclusive as que só patrulhas antigas usaram.
- **The data model only** (só o modelo de dados): os tipos de evento, os tipos de patrulha e seus campos, os guarda-parques como sujeitos e a lista de guarda-parques. É o que uma equipe precisa para começar a patrulhar e registrar no EarthRanger sem trazer o histórico. Ela ainda para em tudo o que um administrador precisa fazer antes no site, como criar equipes.

Uma carga posterior no mesmo site pode ampliar o intervalo ou acrescentar as patrulhas. O que já foi importado é pulado. A página da carga e a aba Loads do conjunto de dados informam o que cada carga gravou, por exemplo "Data model only" ou "Patrols from 2023-01-01 to 2024-12-31".

## Execuções longas e continuação

Uma execução importa primeiro cada patrulha com suas observações e suas fotos, e depois as trilhas de cada patrulha. A barra de progresso mostra a fase em que ela está, a velocidade e o tempo restante nessa fase.

Quanto tempo uma execução leva depende da velocidade com que o site do EarthRanger grava, não do smart-able. Cada observação leva cerca de 0,8 segundo, e os pontos da trilha acrescentam um pouco, então uma área de conservação com 70.000 observações leva cerca de um dia. Duas cargas em dois sites diferentes rodam lado a lado em velocidade total; duas no mesmo site só atrasariam uma à outra.

Um trabalho do Cloud Run pode rodar por no máximo 24 horas, então às 22 horas o trabalho para de pegar patrulhas novas, termina a que está em andamento, salva o livro de registro e inicia uma nova execução de si mesmo. O status da carga é `continuing` enquanto isso acontece, e a página informa a continuação que está cronometrando. Nada se perde e nada é importado duas vezes. Uma carga pode continuar até dez vezes antes de ser marcada como falha; isso é muito mais do que qualquer conjunto de dados precisa.

Se um trabalho for encerrado à força, por uma queda do serviço por exemplo, ele não consegue informar. A carga mantém o último status até a reserva dela expirar, cerca de 25 horas depois do início do trabalho, e então a página oferece **Continue**, que retoma a partir do livro de registro.

## Dar contas aos guarda-parques {#rangers-accounts}

A configuração de patrulhas cria um sujeito para cada funcionário do SMART que aparece em uma patrulha ou que continua empregado, e a importação coloca nele as patrulhas, as trilhas e os relatórios dessa pessoa. Um guarda-parque que depois use o EarthRanger Mobile precisa de uma conta de usuário **vinculada a esse sujeito**: as trilhas de um usuário vão para o sujeito vinculado a ele, e os eventos que ele relata o trazem como *reported by* (relatado por). Sem o vínculo, o primeiro login dele cria um segundo sujeito e o histórico se divide.

A seção **Rangers** (guarda-parques) da página da carga, e a aba **Rangers** do conjunto de dados (que mostra a carga mais recente que chegou à configuração de patrulhas), listam cada uma dessas pessoas, com o nome exatamente como está no site, se a pessoa continua ativa no SMART e duas contagens de patrulhas: nas patrulhas que esta carga importa (o intervalo de datas dela, se houver) e em todo o conjunto de dados. Um guarda-parque que continua empregado e não tem patrulhas mostra 0, e uma carga só do modelo de dados, que não importa patrulhas, mostra só a contagem de todo o conjunto de dados. O arquivo CSV para download tem as mesmas linhas mais uma coluna de e-mail vazia.

Uma linha marcada *employee record deleted in SMART* (registro de funcionário excluído no SMART) é um membro de patrulha cujo registro de funcionário não existe mais; o sujeito dele é nomeado por um identificador. Ninguém pode entrar como ele, então ele não precisa de conta.

Para dar uma conta a um guarda-parque, na administração do Django abra **Users › add**, digite o nome como está listado e, no campo **linked subject**, escolha o sujeito dele por esse nome. Faça isso antes de ele entrar pela primeira vez. Hoje o vínculo só pode ser feito pelo lado do usuário, e só por um administrador.

Se as contas forem criadas de outra maneira, confira se o nome e o sobrenome do usuário coincidem exatamente com o nome do sujeito e se a configuração de sujeito do provedor de fonte ER Track é "use existing": o EarthRanger então vincula o sujeito no primeiro login do guarda-parque pela coincidência do nome. Um nome que difere por uma letra recebe em vez disso um sujeito novo e vazio.

## Planejar de novo e excluir

**Plan again** (planejar de novo) roda um plano novo para uma carga planejada, parada, com falha ou concluída, por exemplo depois de corrigir o site, para ver o que falta. **Delete this load** (excluir esta carga) remove o registro que o smart-able guarda da carga, o livro de registro, o plano e o registro de atividade dela. Não remove nada do EarthRanger.

Só uma carga de uma dada área de conservação em um dado site pode estar ativa de cada vez. Iniciar outra é recusado até que a primeira termine ou pare.
