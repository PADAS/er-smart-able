# Antes de começar

Este guia é para quem recebeu a tarefa de transferir para o EarthRanger os dados do SMART de uma área. Ele leva você de um backup do SMART até uma primeira migração concluída, usando o aplicativo hospedado de migração do SMART. Você não precisa da linha de comando.

## O que o aplicativo faz

Você entrega a ele um backup ou uma exportação do SMART. Ele lê o banco de dados do SMART, mostra o que há nele e grava a área de conservação em um site do EarthRanger: primeiro como um plano que você pode ler, depois de verdade quando você confirma.

## O que ele migra

- **O modelo de dados**: um tipo de evento do EarthRanger para cada categoria do SMART, com seus campos e suas listas de opções.
- **A configuração de patrulhas**: os tipos de patrulha, os campos de patrulha e as opções de base.
- **Os guarda-parques**: um sujeito do EarthRanger para cada funcionário do SMART que patrulhou ou que continua empregado, em um grupo (a lista de guarda-parques) que você escolhe.
- **As patrulhas**: cada patrulha com suas pernas, seus membros, sua trilha de GPS, suas observações e suas fotos.

Você pode carregar primeiro só o modelo de dados, ou limitar as patrulhas a um intervalo de datas. Consulte [Carregar um conjunto de dados](../../help/pt/03-loading.md).

## O que ele não migra

- **Os dados de Perfis.** Se a área de conservação usa o plugin Perfis (Profiles) do SMART, você pode ver esses dados no aplicativo, mas eles não são carregados no EarthRanger.
- **As equipes de patrulha e as permissões.** A API do EarthRanger não consegue criá-las. A carga para e diz o que um administrador do EarthRanger precisa criar ou conceder; depois você continua.
- **Os ícones dos tipos de patrulha.** A carga avisa que eles estão faltando, e um administrador os escolhe depois.
- **As contas de usuário dos guarda-parques.** A carga cria os guarda-parques como sujeitos. Dar a um guarda-parque uma conta, vinculada a esse sujeito, é um passo para um administrador depois.
- **Uma patrulha sem data de início**, quando você carrega um intervalo de datas.

Nada do que o aplicativo faz remove dados do SMART, e excluir um conjunto de dados ou uma carga no aplicativo não remove nada do EarthRanger.

## Quais versões do SMART

- **SMART Desktop 7.5.x**: compatível e testada.
- **SMART Desktop 8.0 a 8.1.x**: deve funcionar, mas ainda não foi comprovada com um backup real. Se você tiver um, conte à equipe de engenharia do EarthRanger como foi.

## Onde fica o aplicativo e quem pode entrar

O aplicativo fica em [https://smart-able-977100970772.us-central1.run.app/](https://smart-able-977100970772.us-central1.run.app/).

Entre com a sua conta Google do EarthRanger. Se aparecer "Este e-mail não tem permissão para usar o smart-able", peça à equipe de engenharia do EarthRanger que adicione o seu endereço.

O que você envia pertence a você. Ninguém mais vê um conjunto de dados ou um site até que você o compartilhe.

## Quanto tempo leva

A extração leva alguns minutos. A carga em si depende da velocidade com que o site do EarthRanger grava: cerca de 0,8 segundo por observação, de modo que uma área de conservação com 70.000 observações leva cerca de um dia. Ela roda sozinha; você não precisa manter a página aberta.

## Em seguida

Reúna as duas coisas de que você precisa: [Reúna o que é necessário](02-get-your-inputs.md).
