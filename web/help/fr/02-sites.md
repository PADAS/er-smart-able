# Sites et jetons

Un site est un hôte EarthRanger, par exemple `example.pamdas.org`, et un jeton d'API d'un utilisateur EarthRanger de ce site. Les chargements écrivent dans le site en tant que cet utilisateur.

**Enregistrer un site.** Saisissez un nom, l'hôte et le jeton. smart-able appelle `/user/me` sur le site avec le jeton avant d'enregistrer quoi que ce soit ; un mauvais hôte ou un jeton qui n'est plus valable est donc refusé immédiatement. La ligne du site, sur la page EarthRanger sites, montre les derniers caractères du jeton et l'utilisateur sous lequel il agit.

**Où le jeton est conservé.** Dans Google Secret Manager, sous un secret nommé d'après le site. Il n'est jamais stocké dans la base de données, jamais écrit dans un journal, et jamais renvoyé par l'API. Si le jeton est renouvelé ou révoqué, retirez le site et enregistrez-le de nouveau ; les chargements qui faisaient référence à l'ancien site restent lisibles mais ne peuvent pas être poursuivis.

**Quel utilisateur employer.** L'import a besoin d'un utilisateur qui peut gérer les types de patrouille, les sujets, les groupes de sujets, la configuration des patrouilles et les champs de patrouille universels, et qui peut créer des événements dans la catégorie sous laquelle le modèle de données est envoyé. Un superutilisateur est le choix le plus simple. Le constat *L'utilisateur du site n'a pas les autorisations* nomme chaque autorisation manquante lorsqu'un utilisateur plus restreint est employé.

**Partager un site.** Le partage permet à cette personne de lancer des chargements dans le site avec votre jeton. Vous seul pouvez partager ou retirer un site. Une personne qui a accès à un jeu de données mais pas au site ne peut pas y charger.

**L'URL.** Donnez l'hôte seul, sans `https://` ni chemin. Les ports, les adresses IP et les identifiants dans l'URL sont refusés.
