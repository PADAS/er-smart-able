# Quando uma carga para

Uma execução para onde o site precisa de algo que a API não consegue fazer, ou onde o site não está pronto para as patrulhas. Cada constatação na página da carga diz o que fazer; as entradas daqui dão a mesma instrução com mais espaço. Os valores que a constatação mostra com um botão de copiar são exatos: o EarthRanger os compara pelo nome.

Os nomes dos menus da administração do EarthRanger são dados em inglês, como ela os exibe.

Depois de corrigir o site, pressione **Continue** (continuar). A execução repete as primeiras etapas, o que é rápido, e segue em frente.

## Configuração de patrulhas (Patrol setup)

### Criar uma equipe de patrulha {#finding-team}

As patrulhas do SMART citam uma equipe; a API do EarthRanger não consegue criar equipes. Na administração do Django, abra **Patrol configuration › Teams** e adicione uma equipe cujo campo *display* seja exatamente o nome de equipe mostrado. A constatação lista os membros da equipe no SMART, para sua referência; a importação identifica a equipe só pelo nome. Há uma entrada para cada equipe que falta; crie todas e depois Continue.

### Colocar os guarda-parques no grupo de sujeitos da lista de guarda-parques {#finding-roster_group}

Nenhum grupo foi informado para a lista de guarda-parques quando a carga foi criada, então os sujeitos guarda-parques foram criados mas não colocados no grupo do qual os guarda-parques são escolhidos. Planeje a carga de novo informando um grupo, o que permite à execução adicioná-los, ou, na administração do Django, abra **Patrol configuration › member subject groups**, escolha ou crie o grupo e adicione os sujeitos.

### Adicionar os sujeitos ao grupo de sujeitos {#finding-permission_subject_group}

O grupo da lista de guarda-parques existe, mas o usuário do site não pode alterar a participação em grupos de sujeitos. Conceda essa permissão ao usuário e faça Continue, ou adicione você mesmo os sujeitos ao grupo em **Django admin › Subject groups**. O nome do grupo é mostrado com um botão de copiar.

### Ativar o recurso patrol_schemas {#finding-enable_patrol_schemas}

O site está com o recurso em prévia `patrol_schemas` desativado, então não tem pernas de patrulha, campos universais de patrulha, equipes nem listas para onde importar. Na administração do Django, abra **Preview features › patrol_schemas** e ative-o para este locatário (tenant). Consulte o EarthRanger Core se a página não estiver disponível. Depois Continue; os campos universais de patrulha são gravados na passagem seguinte.

### Conceder permissão: tipos de patrulha {#finding-permission_patrol_types}

O usuário do site não pode criar nem alterar tipos de patrulha. Na administração do Django, abra **Users › the user** (o usuário) e adicione `activity | patrol type | Can add/change patrol type`. Depois Continue.

### Conceder permissão: campos universais de patrulha {#finding-permission_segment_schema}

O usuário do site não pode gravar os campos universais de patrulha (o esquema de segmento). Adicione `activity | segment type | Can change segment type`; hoje isso exige um superusuário. Depois Continue.

### Conceder permissão: sujeitos {#finding-permission_subjects}

O usuário do site não pode ver, adicionar nem alterar sujeitos, então os sujeitos guarda-parques não puderam ser criados nem encontrados. Adicione `observations | subject | Can view/add/change subject`. Depois Continue.

### Conceder permissão: configuração de patrulhas {#finding-permission_patrol_config}

O usuário do site não pode ler a configuração de patrulhas, com a qual as equipes e as listas são conferidas. Adicione `activity | patrol | Can view patrol`. Depois Continue.

### Escolher um ícone para cada tipo de patrulha {#finding-patrol_type_icons}

Um aviso, não uma parada. A API não consegue definir o ícone de um tipo de patrulha, então os tipos novos mostram o ícone de patrulha padrão do EarthRanger até você escolher um em **EarthRanger admin › Patrol types**.

### Dar nome às bases que o SMART deixou sem nome {#finding-station_names}

Um aviso, não uma parada. Algumas bases não têm nome em nenhum idioma do SMART, então foram criadas com um nome provisório como `Unnamed station 1a2b3c4d`. Dê nome a elas no SMART e exporte de novo, ou renomeie a opção em **Django admin › Choices** (campo `patrol_station`); uma execução posterior coloca o nome provisório de volta até que o SMART tenha um nome.

## Verificação prévia (Preflight)

### O fuso horário do pacote foi deduzido {#finding-timezone}

Um aviso. O SMART não registrou o fuso horário da área de conservação, então a extração o deduziu de onde estão os pontos de localização (waypoints). Os horários das patrulhas e das observações são convertidos com esse fuso. Se estiver errado, defina `SMART_ABLE_TIMEZONE` para a extração e extraia o conjunto de dados de novo; a página de peculiaridades explica como os fusos horários são tratados.

### Faltam rótulos no idioma escolhido {#finding-language}

Um aviso. Alguns elementos do modelo de dados não têm rótulo no idioma com o qual a carga foi criada, então recorrem ao idioma padrão do pacote ou a qualquer idioma que tenha um. A aba Data Model do conjunto de dados mostra o quanto cada idioma está coberto; planeje a carga de novo com o mais bem coberto se os rótulos importarem.

### Dias de perna sem informação de horário {#finding-time_coverage}

Um aviso, nada a fazer. Alguns dias de perna não têm trilha, nem horário de início ou de fim, nem ponto de localização (waypoint) com horário, então os segmentos deles cobrem o dia inteiro. Cada um desses segmentos é registrado com `time_source: date_only`.

### Uma verificação prévia não pôde rodar {#finding-check_failed}

Uma das verificações gerou um erro antes de poder informar, normalmente um problema de conexão ou de permissão com o site. A mensagem informa a verificação e o erro. Corrija a causa e depois Continue; a verificação prévia roda de novo desde o início.

### O recurso patrol_schemas está desativado {#finding-feature_flag}

A mesma situação de *Ativar o recurso patrol_schemas* acima, vista pela verificação prévia. Ative o recurso e depois Continue.

### O usuário do site não tem as permissões {#finding-permissions}

A constatação lista cada permissão de que a importação precisa e que o usuário não tem. Conceda-as em **Django admin › Users › the user**, aplicativo `activity`. Criar eventos em uma categoria exige a permissão de criação dessa categoria, normalmente concedida por um conjunto de permissões. Depois Continue.

### Faltam tipos de patrulha ou eles estão inativos {#finding-patrol_types}

A configuração de patrulhas cria os tipos de que as pernas precisam, então em uma execução isso normalmente significa que um tipo foi desativado depois. Ative-o em **EarthRanger admin › Patrol types**, ou faça Continue para deixar a configuração de patrulhas recriá-lo. Em um plano isso é esperado: o plano não grava nada, e a constatação é marcada como algo que a execução vai criar.

### Faltam campos universais de patrulha ou eles estão obsoletos {#finding-segment_schema}

A configuração de patrulhas grava esses campos. Se um administrador tornou um deles obsoleto de propósito, restaure-o no construtor de formulários de patrulha; caso contrário, Continue. Em um plano isso é esperado.

### Faltam opções que as patrulhas usam ou elas estão inativas {#finding-choices}

Um aviso. Algumas opções de lista que as patrulhas usam não estão no site ou foram desativadas, então esses campos seriam guardados sem uma entrada correspondente. A configuração de patrulhas as cria; uma opção que um administrador desativou pode ser reativada em **Django admin › Choices**.

### Há membros de patrulha que não podem ser colocados em um segmento {#finding-subjects}

Os sujeitos guarda-parques desses membros não existem, ou não estão em um grupo listado em **Patrol configuration › members**. A configuração de patrulhas os cria e, se um grupo foi informado para a lista de guarda-parques, os adiciona a ele. Caso contrário, adicione-os a um grupo assim em **Django admin › Subject groups**. Em um plano isso é esperado.

### Há membros de patrulha aposentados {#finding-inactive_members}

Um aviso, nada a fazer. O EarthRanger só aceita membros ativos em um segmento, então a importação reativa esses sujeitos para a execução e os aposenta de novo quando ela termina. O livro de registro anota isso.

### Faltam equipes de patrulha ou elas estão inativas {#finding-teams}

A mesma situação de *Criar uma equipe de patrulha* acima: cada equipe citada precisa existir, ativa, com exatamente esse nome de exibição, em **Patrol configuration › Teams**. Há uma entrada por equipe, com um botão de copiar.

### Tipos de evento {#finding-event_types}

As categorias do SMART observadas precisam de um tipo de evento ativo no site. A mensagem diz qual caso se aplica:

- **No active event type** (nenhum tipo de evento ativo): o modelo de dados não foi enviado sob a categoria de eventos que esta carga usa. Em um plano isso é esperado e é marcado como algo que a execução vai criar. Em uma execução, confira a categoria de eventos: se um envio anterior usou outro identificador, planeje a carga de novo com ele.
- **Match more than one event type** (corresponde a mais de um tipo de evento): o site tem vários envios de modelo de dados, sob categorias diferentes, com os mesmos nomes de tipo. Planeje a carga de novo com a categoria de eventos do envio contra o qual importar.
- **Map to an inactive event type** (corresponde a um tipo de evento inativo): um aviso. A categoria é uma categoria-mãe do SMART ou foi aposentada; os eventos dela são importados contra o tipo inativo, que o EarthRanger não oferece para relatórios novos. Ative o tipo em **EarthRanger admin › Event types** se os guarda-parques devem continuar a usá-lo.
- **Exist only as configurable model variants** (existem só como variantes do modelo configurável): essas categorias têm um tipo de evento por formulário, e a importação ainda não sabe a qual variante uma observação pertence. Essas patrulhas ainda não podem ser importadas; é preciso um mapeamento de variantes, que está pendente no er-smart-sync.

### Não há tipo de evento de agrupamento {#finding-collection_type}

Um aviso. Alguns pontos de localização (waypoints) contêm várias observações, e o site não tem um tipo de evento `incident_collection` ativo sob o qual agrupá-las, então os eventos delas são importados sem agrupamento. Adicione ou ative esse tipo em **EarthRanger admin › Event types** para agrupá-los.

### Pernas na data provisória de 1970 ou que abrangem mais de um ano {#finding-leg_span}

Um aviso, nada a fazer. O SMART guarda algumas datas de perna como uma data provisória; a importação mantém só os dias de perna que têm uma trilha ou um ponto de localização (waypoint). Para corrigir as datas, corrija a perna no SMART e exporte de novo.

### Observações das quais não se pode dizer quem as relatou {#finding-observers}

Um aviso. Cada evento importado informa quem o relatou: o sujeito do observador do SMART ou, quando essa pessoa não tem sujeito no site, o líder da perna, ou então o primeiro membro dela. As observações listadas não têm nenhum deles, então os eventos delas não trazem quem relatou. Nada a fazer, a não ser que isso importe: dê ao observador um registro de funcionário no SMART e exporte de novo. Um plano lista só as observações que os sujeitos da própria execução não permitem resolver.

### A extração registrou avisos {#finding-bundle_warnings}

Um aviso. O smart-able anotou coisas sobre os dados quando gravou o pacote. Elas estão listadas no manifesto do pacote e explicadas em *SMART data quirks* (as peculiaridades dos dados do SMART, em inglês).

## Importação

### Houve patrulhas que não puderam ser importadas {#finding-patrols_failed}

Cada patrulha que falhou é listada com o erro dela. A maioria dos erros informa algo que falta no site: uma equipe, um sujeito, um tipo de evento. Corrija isso e depois Continue; só as patrulhas que falharam são tentadas de novo. Um `500` em um identificador de patrulha que já está no site é o EarthRanger recusando uma duplicata; a nova tentativa lê a patrulha existente e segue em frente.

### O token do site não funciona mais {#finding-site_token_rejected}

O site recusou o token, então nada foi gravado. Remova o site, registre-o de novo com um token que funcione e inicie uma carga nova.
