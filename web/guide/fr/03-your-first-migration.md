# Votre première migration

Ayez sous la main votre fichier SMART et votre jeton EarthRanger ; [Réunir vos éléments](02-get-your-inputs.md) explique ce qu'ils sont. Les étapes ci-dessous suivent l'ordre dans lequel l'application fonctionne, que la [Vue d'ensemble](../../help/fr/01-overview.md) de l'application énumère aussi.

## 1. Se connecter

Ouvrez [l'application](https://smart-able-977100970772.us-central1.run.app/) et connectez-vous avec votre compte Google EarthRanger.

## 2. Téléverser le fichier SMART

1. Sur la page **Jeux de données**, appuyez sur **Téléverser une sauvegarde ou un export**.
2. Donnez au jeu de données un nom que vous reconnaîtrez, par exemple la zone de conservation et la date, et choisissez votre fichier `.zip`.
3. Appuyez sur **Téléverser**. Une sauvegarde volumineuse met du temps à être envoyée ; laissez la boîte de dialogue ouverte jusqu'à ce qu'elle se ferme.

Le nouveau jeu de données apparaît dans la liste comme **téléversement**, puis **en file d'attente**, puis **en cours**, puis **prêt**. Cela prend quelques minutes, et la page se met à jour d'elle-même. S'il se termine par **échec**, ouvrez le jeu de données : l'onglet **Vue d'ensemble** montre l'erreur et la fin du journal. [Statuts](../../help/fr/04-statuses.md) explique chaque statut.

## 3. Parcourir ce qui a été extrait

Ouvrez le jeu de données. Son onglet **Vue d'ensemble** énumère chaque zone de conservation du fichier, avec le nombre de ses patrouilles et de ses waypoints. Appuyez sur **Parcourir** pour consulter les patrouilles, la carte, les observations et le modèle de données.

Vérifiez qu'il s'agit bien de la zone de conservation attendue et que les nombres semblent corrects. Rien n'a encore été écrit dans EarthRanger.

## 4. Ajouter un site

1. Sur la page d'accueil, repérez **Sites EarthRanger**, sous vos jeux de données.
2. Appuyez sur **Ajouter un site**.
3. Saisissez un nom, l'adresse du site et le jeton.

L'application vérifie le jeton auprès du site avant de l'enregistrer. Un mauvais hôte ou un jeton qui n'est plus valable est refusé immédiatement. Voir [Sites et jetons](../../help/fr/02-sites.md).

## 5. Préparer le plan du chargement

1. Revenez au jeu de données et appuyez sur **Charger dans EarthRanger** à côté de la zone de conservation.
2. Choisissez le site. Laissez les autres choix tels quels, sauf si vous savez que vous en avez besoin ; [Charger un jeu de données](../../help/fr/03-loading.md) explique chacun d'eux.
3. Pour une première exécution, réglez **Que charger** sur **Le modèle de données seulement**. C'est rapide, cela fait apparaître tout ce qu'un administrateur doit faire sur le site, et vous pourrez ajouter les patrouilles ensuite par un second chargement.
4. Appuyez sur **Établir le plan**.

Un plan interroge le site mais n'écrit rien. Lorsqu'il est prêt, la page du chargement montre ce que l'exécution créerait ou mettrait à jour, ainsi que les constats éventuels.

## 6. Lire le plan, puis confirmer

Lisez les constats. Les constats marqués **bloquant** sont des choses qu'une personne doit faire sur le site EarthRanger, comme créer une équipe de patrouille ; chacun indique quoi faire. Les constats marqués **avertissement** sont donnés pour information et n'arrêtent jamais une exécution.

Appuyez sur **Confirmer et charger**. S'il y a des constats bloquants, le bouton indique où l'exécution s'arrêtera. C'est normal : l'exécution écrit tout ce qui précède ce point, et confirmer est la façon d'avancer.

## 7. Si le chargement s'arrête

Le statut devient **intervention nécessaire** et les constats indiquent ce qu'il faut faire. Rien de ce qui a déjà été écrit n'est annulé.

1. Faites ce que dit le constat, ou demandez à l'administrateur du site de le faire. [Quand un chargement s'arrête](../../help/fr/05-stops.md) a une entrée pour chaque constat.
2. Appuyez sur **Continuer**. L'exécution reprend, ignore ce qui existe déjà et poursuit.

## 8. Charger les patrouilles

Lorsque le chargement du modèle de données est **terminé**, lancez un second chargement de la même zone de conservation dans le même site, avec **Que charger** réglé sur **Le modèle de données et les patrouilles**. Laissez les dates vides pour charger toutes les patrouilles, ou renseignez-les pour transférer d'abord quelques mois.

Un long chargement continue de s'exécuter tout seul. La page du chargement montre sa progression et le temps restant ; vous pouvez fermer la page et y revenir.

## 9. Vérifier le résultat dans EarthRanger

Ouvrez le site EarthRanger et cherchez :

- les types d'événement, dans la catégorie d'événements que nomme la page du chargement ;
- les écogardes, en tant que sujets dans le groupe de la liste des écogardes ;
- quelques patrouilles que vous reconnaissez de l'étape 3, avec leurs tracés et leurs rapports.

La section **Écogardes** de la page du chargement énumère chaque écogarde créé par le chargement, pour la personne qui leur donnera des comptes d'utilisateur. [Charger un jeu de données](../../help/fr/03-loading.md#rangers-accounts) explique comment lier un compte à un écogarde.
