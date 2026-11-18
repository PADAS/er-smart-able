# Sites et jetons

Un site est un hôte EarthRanger, par exemple `example.pamdas.org`, et un jeton d'API d'un utilisateur EarthRanger de ce site. Les chargements écrivent dans le site en tant que cet utilisateur.

**Enregistrer un site.** Saisissez un nom, l'hôte et le jeton. smart-able appelle `/user/me` sur le site avec le jeton avant d'enregistrer quoi que ce soit ; un mauvais hôte ou un jeton qui n'est plus valable est donc refusé immédiatement. La ligne du site, sous **Sites EarthRanger** sur la page d'accueil, montre les derniers caractères du jeton et l'utilisateur sous lequel il agit.

**Où le jeton est conservé.** Dans Google Secret Manager, sous un secret nommé d'après le site. Il n'est jamais stocké dans la base de données, jamais écrit dans un journal, et jamais renvoyé par l'API. Si le jeton est renouvelé ou révoqué, appuyez sur **Modifier** sur le site et saisissez le nouveau : il est vérifié comme le premier, et les chargements du site se poursuivent avec lui. Le propriétaire d'un site peut aussi le renommer à cet endroit. L'adresse du site ne peut pas être modifiée ; une autre adresse est un autre site. Retirer un site laisse ses chargements lisibles, mais ils ne peuvent plus être poursuivis.

**Quel utilisateur employer.** L'import a besoin d'un utilisateur qui peut gérer les types de patrouille, les sujets, les groupes de sujets, la configuration des patrouilles et les champs de patrouille universels, et qui peut créer des événements dans la catégorie sous laquelle le modèle de données est envoyé. Un superutilisateur est le choix le plus simple. Le constat *L'utilisateur du site n'a pas les autorisations* nomme chaque autorisation manquante lorsqu'un utilisateur plus restreint est employé.

**Partager un site.** Le partage permet à cette personne de lancer des chargements dans le site avec votre jeton. Vous seul pouvez partager ou retirer un site. Une personne qui a accès à un jeu de données mais pas au site ne peut pas y charger.

**L'URL.** Saisissez l'adresse du site sous n'importe quelle forme : l'hôte seul, ou l'adresse copiée depuis le navigateur. L'application garde l'hôte et ignore le reste. Les ports, les adresses IP et les identifiants dans l'URL sont refusés.
