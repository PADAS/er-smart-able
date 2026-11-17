# Sua primeira migração

Tenha em mãos o seu arquivo do SMART e o seu token do EarthRanger; [Reúna o que é necessário](02-get-your-inputs.md) explica o que eles são. Os passos abaixo seguem a ordem em que o aplicativo trabalha, que a [Visão geral](../../help/pt/01-overview.md) do próprio aplicativo também lista.

## 1. Entrar

Abra [o aplicativo](https://smart-able-977100970772.us-central1.run.app/) e entre com a sua conta Google do EarthRanger.

## 2. Enviar o arquivo do SMART

1. Na página **Conjuntos de dados**, pressione **Enviar um backup ou uma exportação**.
2. Dê ao conjunto de dados um nome que você reconheça, como a área de conservação e a data, e escolha o seu arquivo `.zip`.
3. Pressione **Enviar**. Um backup grande demora para ser enviado; deixe a caixa de diálogo aberta até ela fechar.

O novo conjunto de dados aparece na lista como **enviando**, depois **na fila**, depois **em execução** e depois **pronto**. Isso leva alguns minutos, e a página se atualiza sozinha. Se terminar como **falhou**, abra o conjunto de dados: a aba **Visão geral** mostra o erro e o fim do registro. [Status](../../help/pt/04-statuses.md) explica cada status.

## 3. Explorar o que foi extraído

Abra o conjunto de dados. A aba **Visão geral** lista cada área de conservação do arquivo, com o número de patrulhas e de pontos de localização (waypoints). Pressione **Explorar** para percorrer as patrulhas, o mapa, as observações e o modelo de dados.

Confira se esta é a área de conservação que você esperava e se os números parecem certos. Nada foi gravado no EarthRanger ainda.

## 4. Adicionar um site

1. Abra o menu embaixo do seu endereço de e-mail e escolha **Sites do EarthRanger**.
2. Pressione **Adicionar um site**.
3. Digite um nome, o host e o token.

O aplicativo confere o token com o site antes de salvá-lo. Um host errado ou um token que não vale mais é recusado na hora. Consulte [Sites e tokens](../../help/pt/02-sites.md).

## 5. Planejar a carga

1. Volte ao conjunto de dados e pressione **Carregar no EarthRanger** ao lado da área de conservação.
2. Escolha o site. Deixe as outras opções como estão, a não ser que você saiba que precisa delas; [Carregar um conjunto de dados](../../help/pt/03-loading.md) explica cada uma.
3. Para uma primeira execução, defina **O que carregar** como **Só o modelo de dados**. É rápido, faz aparecer tudo o que um administrador precisa fazer no site, e você pode acrescentar as patrulhas depois com uma segunda carga.
4. Pressione **Fazer o plano**.

Um plano consulta o site mas não grava nada. Quando ele fica pronto, a página da carga mostra o que a execução criaria ou atualizaria, e as constatações que houver.

## 6. Ler o plano e confirmar

Leia as constatações. As constatações marcadas como **bloqueante** são coisas que uma pessoa precisa fazer no site do EarthRanger, como criar uma equipe de patrulha; cada uma diz o que fazer. As constatações marcadas como **aviso** são para sua informação e nunca param uma execução.

Pressione **Confirmar e carregar**. Se houver constatações bloqueantes, o botão diz onde a execução vai parar. Isso é normal: a execução grava tudo o que vem antes desse ponto, e confirmar é a maneira de avançar.

## 7. Se a carga parar

O status passa a **precisa de atenção** e as constatações dizem o que é necessário. Nada do que já foi gravado é desfeito.

1. Faça o que a constatação diz, ou peça ao administrador do site. [Quando uma carga para](../../help/pt/05-stops.md) tem uma entrada para cada constatação.
2. Pressione **Continuar**. A execução começa de novo, pula o que já existe e segue em frente.

## 8. Carregar as patrulhas

Quando a carga do modelo de dados estiver **concluída**, inicie uma segunda carga da mesma área de conservação no mesmo site, com **O que carregar** definido como **O modelo de dados e as patrulhas**. Deixe as datas vazias para carregar todas as patrulhas, ou preencha-as para trazer primeiro alguns meses.

Uma carga longa continua rodando sozinha. A página da carga mostra o progresso e o tempo restante; você pode fechar a página e voltar depois.

## 9. Conferir o resultado no EarthRanger

Abra o site do EarthRanger e procure:

- os tipos de evento, na categoria de eventos que a página da carga informa;
- os guarda-parques, como sujeitos no grupo da lista de guarda-parques;
- algumas patrulhas que você reconheça do passo 3, com suas trilhas e seus relatórios.

A seção **Guarda-parques** da página da carga lista cada guarda-parque que a carga criou, para quem for dar contas de usuário a eles. [Carregar um conjunto de dados](../../help/pt/03-loading.md#rangers-accounts) explica como vincular uma conta a um guarda-parque.
