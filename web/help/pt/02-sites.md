# Sites e tokens

Um site é um host do EarthRanger, por exemplo `example.pamdas.org`, e um token de API de um usuário do EarthRanger nesse site. As cargas gravam no site como esse usuário.

**Registrar um site.** Digite um nome, o host e o token. O smart-able chama `/user/me` no site com o token antes de salvar qualquer coisa, então um host errado ou um token que não vale mais é recusado na hora. A linha do site em **Sites do EarthRanger**, na página inicial, mostra os últimos caracteres do token e o usuário com o qual ele atua.

**Onde o token fica guardado.** No Google Secret Manager, em um segredo com o nome do site. Ele nunca é armazenado no banco de dados, nunca é gravado em um registro e nunca é devolvido pela API. Se o token for trocado ou revogado, pressione **Editar** no site e digite o novo: ele é conferido como o primeiro, e as cargas do site seguem com ele. O dono de um site também pode renomeá-lo ali. O endereço do site não pode ser alterado; um endereço diferente é outro site. Remover um site deixa as cargas dele legíveis, mas elas não podem ser continuadas.

**Qual usuário usar.** A importação precisa de um usuário que possa gerenciar os tipos de patrulha, os sujeitos, os grupos de sujeitos, a configuração de patrulhas e os campos universais de patrulha, e que possa criar eventos na categoria sob a qual o modelo de dados é enviado. Um superusuário é a escolha simples. A constatação *O usuário do site não tem as permissões* informa cada permissão que falta quando se usa um usuário mais restrito.

**Compartilhar um site.** Compartilhar permite que essa pessoa inicie cargas no site com o seu token. Só você pode compartilhar ou remover um site. Quem tem acesso a um conjunto de dados mas não ao site não pode carregar nele.

**A URL.** Digite o endereço do site em qualquer formato: só o host, ou o endereço copiado do navegador. O aplicativo mantém o host e descarta o resto. Portas, endereços IP e credenciais na URL são recusados.
