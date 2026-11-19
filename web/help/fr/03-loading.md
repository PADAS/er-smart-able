# Charger un jeu de données

Un chargement place une zone de conservation d'un jeu de données dans un site. Lancez-le depuis la page du jeu de données avec **Charger dans EarthRanger**, dans l'onglet **Vue d'ensemble** ou **Chargements**, en choisissant la zone de conservation, le site, la langue des libellés, un modèle configurable facultatif, le groupe (la liste des écogardes) dans lequel les écogardes sont choisis, et la catégorie d'événements.

## Un plan, puis la confirmation

Chaque chargement commence par un **plan** : un essai à blanc qui interroge le site mais n'écrit rien. Il montre ce que la vraie exécution créerait, mettrait à jour ou désactiverait, les constats sur lesquels elle s'arrêterait, et les patrouilles qu'elle importerait. Lisez-le, puis appuyez sur **Confirmer et charger**. Si le plan montre déjà des constats bloquants, le bouton indique où l'exécution s'arrêtera ; l'exécution écrit tout de même tout ce qui précède ce point, de sorte que confirmer est la façon normale d'avancer.

## Les quatre étapes

Une exécution parcourt les étapes dans l'ordre. Chacune est idempotente : une seconde exécution la refait sans dommage et atteint ce qui reste.

| Étape | Ce qu'elle écrit dans EarthRanger |
|---|---|
| **Types d'événement** | La catégorie d'événements et un type d'événement par catégorie SMART, avec leurs champs et leurs listes de choix, à partir du modèle de données (et du modèle configurable, s'il en a été choisi un). Les types existants sont mis à jour, pas dupliqués. |
| **Configuration des patrouilles** | Les types de patrouille, les champs de patrouille universels, les sujets écogardes (un par employé SMART qui a patrouillé), leur appartenance au groupe de la liste des écogardes, et les choix de station. Tout ce que l'API ne peut pas faire devient un constat : équipes, icônes, autorisations. |
| **Vérification préalable** | N'écrit rien. Vérifie que le site a tout ce dont les patrouilles ont besoin : types de patrouille, équipes, sujets, types d'événement, champs. |
| **Patrouilles** | Les patrouilles elles-mêmes, chacune avec ses étapes de patrouille, ses membres, son tracé et les événements issus de ses waypoints. Un registre consigne chaque patrouille au moment où elle arrive, de sorte qu'une exécution peut être reprise sans rien dupliquer. |

## La règle d'arrêt

Après la configuration des patrouilles et après la vérification préalable, l'exécution s'arrête si un constat est **bloquant**. Le statut du chargement devient `needs_attention` et les constats disent quoi faire. Rien de ce qui a déjà été écrit n'est annulé. Corrigez le site, puis appuyez sur **Continuer** : l'exécution repart de la première étape, ce qui est rapide puisque tout est déjà là, et atteint les patrouilles.

Les **avertissements** n'arrêtent jamais une exécution. Ils consignent quelque chose qu'il est utile de savoir, comme une catégorie désactivée ou un waypoint dont les événements ne peuvent pas être regroupés.

Les patrouilles qui échouent pendant l'import n'arrêtent pas les autres. À la fin, elles deviennent un seul constat bloquant qui énumère chaque erreur ; **Continuer** ne réessaie que ces patrouilles.

## Catégorie d'événements

La catégorie d'événements est la catégorie EarthRanger où vont les types d'événement que ce chargement crée. Par défaut, c'est `smart-<conservation area id>`, ou `smart-<event type set name>` pour un chargement avec un modèle configurable. Quand le site a déjà les types d'événement de ce chargement, ils restent dans leur catégorie et les nouveaux les y rejoignent, quoi qu'on saisisse ici. La page du chargement nomme cette catégorie une fois le plan établi.

## Plusieurs zones de conservation sur un même site

Les zones de conservation qui utilisent le même modèle de données partagent ses types d'événement sur un site ; une seule requête les couvre donc toutes.

- **Sans modèle configurable**, chaque chargement sur le site écrit le même ensemble de types d'événement et de listes d'options.
- **Avec un modèle configurable**, les chargements qui ont le même nom d'**ensemble de types d'événement** partagent un seul ensemble. Ce nom est celui du modèle configurable, sauf si vous le changez. Donnez-lui un autre nom pour garder les types d'événement d'un modèle à part de ceux d'un autre modèle du même nom. Donnez un même nom à deux modèles pour les réunir.

Un chargement ne fait qu'ajouter à un ensemble. Il crée les types d'événement et les options de liste qui manquent au site et met à jour les champs de ceux qu'il a. Il ne désactive jamais une option ni un type d'événement, et ne déplace jamais un type d'événement vers une autre catégorie. Une option ou un type d'événement retiré de SMART reste donc actif sur le site jusqu'à ce qu'un administrateur le désactive.

Si le modèle de cette zone de conservation diffère de ce que le site a déjà sous le même nom, le plan le signale par un avertissement qui liste les types d'événement que le chargement modifierait.

Une zone de conservation chargée avant le partage des types d'événement garde ses propres types d'événement sur ce site. La page du chargement le dit, et le nom de l'ensemble ne s'applique pas.

## Charger une partie d'un jeu de données

**Que charger**, dans la boîte de dialogue du chargement, propose deux choix.

- **Le modèle de données et les patrouilles**, le choix par défaut. Laissez **Patrouilles du** et **au** vides pour charger toutes les patrouilles, ou renseignez l'un ou les deux pour ne charger que les patrouilles qui commencent ces jours-là ou entre eux. Les observations, les photos et le tracé d'une patrouille viennent avec elle. Les dates sont celles de la zone de conservation, telles que SMART les a enregistrées. Une patrouille que SMART a stockée sans date de début est exclue de toute période. Une période ne restreint que les patrouilles : le chargement met tout de même en place tout le modèle de données, de sorte que les actions qu'il demande à un administrateur, comme la création d'équipes, couvrent toutes les équipes de la zone de conservation, y compris celles que seules d'anciennes patrouilles ont utilisées.
- **Le modèle de données seulement** : les types d'événement, les types de patrouille et leurs champs, les écogardes en tant que sujets, et la liste des écogardes. C'est ce dont une équipe a besoin pour commencer à patrouiller et à enregistrer dans EarthRanger sans transférer son historique. Ce chargement s'arrête tout de même sur ce qu'un administrateur doit d'abord faire sur le site, comme créer des équipes.

Un chargement ultérieur dans le même site peut élargir la période ou ajouter les patrouilles. Tout ce qui est déjà importé est ignoré. La page du chargement et l'onglet **Chargements** du jeu de données nomment ce que chaque chargement a écrit, par exemple « Modèle de données seulement » ou « Patrouilles du 2023-01-01 au 2024-12-31 ».

## Longues exécutions et reprise

Une exécution importe d'abord chaque patrouille avec ses observations et ses photos, puis les tracés de chaque patrouille. La barre de progression montre la phase en cours, la vitesse, et le temps restant dans cette phase.

La durée d'une exécution dépend de la vitesse à laquelle le site EarthRanger écrit, pas de smart-able. Chaque observation prend environ 0,8 seconde, et les points de tracé en ajoutent un peu ; une zone de conservation de 70 000 observations prend donc environ une journée. Deux chargements dans deux sites différents s'exécutent côte à côte à pleine vitesse ; deux chargements dans le même site ne feraient que se ralentir.

Une tâche Cloud Run peut s'exécuter 24 heures au plus ; au bout de 22 heures d'exécution, la tâche cesse donc de prendre de nouvelles patrouilles, termine celle qui est en cours, enregistre son registre et lance une nouvelle exécution d'elle-même. Le statut du chargement est `continuing` pendant ce temps, et la page nomme la reprise qu'elle chronomètre. Rien n'est perdu et rien n'est importé deux fois. Un chargement peut reprendre jusqu'à dix fois avant d'être marqué en échec ; c'est bien plus que ce dont un jeu de données a besoin.

Si une tâche est tuée net, par une panne par exemple, elle ne peut pas rendre compte. Le chargement garde son dernier statut jusqu'à l'expiration de sa réservation, environ 25 heures après le démarrage de la tâche ; la page propose alors **Continuer**, qui reprend à partir du registre.

## Donner des comptes aux écogardes {#rangers-accounts}

La configuration des patrouilles crée un sujet par employé SMART qui figure dans une patrouille ou qui est encore en poste, et l'import y place ses patrouilles, ses tracés et ses rapports. Un écogarde qui utilise ensuite EarthRanger Mobile a besoin d'un compte d'utilisateur **lié à ce sujet** : les tracés d'un utilisateur vont à son sujet lié, et les événements qu'il rapporte le portent comme *reported by* (rapporté par). Sans ce lien, sa première connexion crée un second sujet et l'historique se scinde.

La section **Écogardes** de la page du chargement, et l'onglet **Écogardes** du jeu de données (qui montre le chargement le plus récent ayant atteint la configuration des patrouilles), énumèrent chacune de ces personnes, avec le nom exactement tel qu'il est sur le site, l'indication que la personne est encore active ou non dans SMART, et deux nombres de patrouilles : dans les patrouilles que ce chargement importe (sa période, s'il y en a une) et dans tout le jeu de données. Un écogarde encore en poste et sans patrouille affiche 0, et un chargement du modèle de données seulement, qui n'importe aucune patrouille, n'affiche que le nombre pour tout le jeu de données. Le fichier CSV téléchargeable a les mêmes lignes, plus une colonne e-mail vide.

Une ligne marquée *fiche d'employé supprimée dans SMART* est un membre de patrouille dont la fiche d'employé n'existe plus ; son sujet est nommé par un identifiant. Personne ne peut se connecter sous ce nom, il n'a donc pas besoin de compte.

Pour donner un compte à un écogarde, dans l'administration Django, ouvrez **Users › add**, saisissez le nom tel qu'il est listé et, dans le champ **linked subject**, choisissez son sujet par ce nom. Faites-le avant qu'il ne se connecte. Aujourd'hui, le lien ne peut être fait que du côté de l'utilisateur, et seulement par un administrateur.

Si les comptes sont créés autrement, assurez-vous que le prénom et le nom de l'utilisateur correspondent exactement au nom du sujet et que le réglage du sujet du fournisseur de source ER Track est « use existing » : EarthRanger lie alors le sujet à la première connexion de l'écogarde en faisant correspondre le nom. Un nom qui diffère d'une lettre reçoit à la place un nouveau sujet, vide.

## Refaire le plan et supprimer

**Refaire le plan** lance un nouveau plan pour un chargement planifié, arrêté, en échec ou terminé, par exemple après avoir corrigé le site, pour voir ce qui reste. **Supprimer ce chargement** retire l'enregistrement que smart-able garde du chargement, son registre, son plan et son journal. Cela ne retire rien d'EarthRanger.

Un seul chargement d'une zone de conservation donnée dans un site donné peut être actif à la fois. En lancer un autre est refusé jusqu'à ce que le premier se termine ou s'arrête.
