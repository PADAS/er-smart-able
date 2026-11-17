# Sua primeira migração

Tenha em mãos o seu arquivo do SMART e o seu token do EarthRanger; [Reúna o que é necessário](02-get-your-inputs.md) explica o que eles são. Os passos abaixo seguem a ordem em que o aplicativo trabalha, que a [Visão geral](../../help/pt/01-overview.md) do próprio aplicativo também lista.

Por enquanto o aplicativo está em inglês. Os nomes dos botões e das páginas são dados como ele os exibe, seguidos do significado entre parênteses.

## 1. Entrar

Abra [o aplicativo](https://smart-able-977100970772.us-central1.run.app/) e entre com a sua conta Google do EarthRanger.

## 2. Enviar o arquivo do SMART

1. Na página **Datasets** (conjuntos de dados), pressione **Upload a backup or export** (enviar um backup ou uma exportação).
2. Dê ao conjunto de dados um nome que você reconheça, como a área de conservação e a data, e escolha o seu arquivo `.zip`.
3. Pressione **Upload** (enviar). Um backup grande demora para ser enviado; deixe a caixa de diálogo aberta até ela fechar.

O novo conjunto de dados aparece na lista como **uploading** (enviando), depois **queued** (na fila), depois **running** (em execução) e depois **ready** (pronto). Isso leva alguns minutos, e a página se atualiza sozinha. Se terminar como **failed** (falhou), abra o conjunto de dados: a visão geral (Overview) mostra o erro e o fim do registro. [Status](../../help/pt/04-statuses.md) explica cada status.

## 3. Explorar o que foi extraído

Abra o conjunto de dados. A visão geral (Overview) lista cada área de conservação do arquivo, com o número de patrulhas e de pontos de localização (waypoints). Pressione **Browse** (explorar) para percorrer as patrulhas, o mapa, as observações e o modelo de dados.

Confira se esta é a área de conservação que você esperava e se os números parecem certos. Nada foi gravado no EarthRanger ainda.

## 4. Adicionar um site

1. Abra o menu embaixo do seu endereço de e-mail e escolha **EarthRanger sites** (sites do EarthRanger).
2. Pressione **Add a site** (adicionar um site).
3. Digite um nome, o host e o token.

O aplicativo confere o token com o site antes de salvá-lo. Um host errado ou um token que não vale mais é recusado na hora. Consulte [Sites e tokens](../../help/pt/02-sites.md).

## 5. Planejar a carga

1. Volte ao conjunto de dados e pressione **Load into EarthRanger** (carregar no EarthRanger) ao lado da área de conservação.
2. Escolha o site. Deixe as outras opções como estão, a não ser que você saiba que precisa delas; [Carregar um conjunto de dados](../../help/pt/03-loading.md) explica cada uma.
3. Para uma primeira execução, defina **What to load** (o que carregar) como **The data model only** (só o modelo de dados). É rápido, faz aparecer tudo o que um administrador precisa fazer no site, e você pode acrescentar as patrulhas depois com uma segunda carga.
4. Pressione **Make the plan** (fazer o plano).

Um plano consulta o site mas não grava nada. Quando ele fica pronto, a página da carga mostra o que a execução criaria ou atualizaria, e as constatações que houver.

## 6. Ler o plano e confirmar

Leia as constatações. As constatações bloqueantes (**Blocking**) são coisas que uma pessoa precisa fazer no site do EarthRanger, como criar uma equipe de patrulha; cada uma diz o que fazer. Os avisos (**Warnings**) são para sua informação e nunca param uma execução.

Pressione **Confirm and load** (confirmar e carregar). Se houver constatações bloqueantes, o botão diz onde a execução vai parar. Isso é normal: a execução grava tudo o que vem antes desse ponto, e confirmar é a maneira de avançar.

## 7. Se a carga parar

O status passa a **needs attention** (precisa de atenção) e as constatações dizem o que é necessário. Nada do que já foi gravado é desfeito.

1. Faça o que a constatação diz, ou peça ao administrador do site. [Quando uma carga para](../../help/pt/05-stops.md) tem uma entrada para cada constatação.
2. Pressione **Continue** (continuar). A execução começa de novo, pula o que já existe e segue em frente.

## 8. Carregar as patrulhas

Quando a carga do modelo de dados estiver **done** (concluída), inicie uma segunda carga da mesma área de conservação no mesmo site, com **What to load** definido como **The data model and patrols** (o modelo de dados e as patrulhas). Deixe as datas vazias para carregar todas as patrulhas, ou preencha-as para trazer primeiro alguns meses.

Uma carga longa continua rodando sozinha. A página da carga mostra o progresso e o tempo restante; você pode fechar a página e voltar depois.

## 9. Conferir o resultado no EarthRanger

Abra o site do EarthRanger e procure:

- os tipos de evento, na categoria de eventos que a página da carga informa;
- os guarda-parques, como sujeitos no grupo da lista de guarda-parques;
- algumas patrulhas que você reconheça do passo 3, com suas trilhas e seus relatórios.

A seção **Rangers** (guarda-parques) da página da carga lista cada guarda-parque que a carga criou, para quem for dar contas de usuário a eles. [Carregar um conjunto de dados](../../help/pt/03-loading.md#rangers-accounts) explica como vincular uma conta a um guarda-parque.
