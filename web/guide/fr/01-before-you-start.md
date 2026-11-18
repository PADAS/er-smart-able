# Avant de commencer

Ce guide s'adresse à une personne à qui l'on a demandé de transférer les données SMART d'un site vers EarthRanger. Il vous mène d'une sauvegarde SMART à une première migration terminée, à l'aide de l'application hébergée de migration SMART. Vous n'avez pas besoin de la ligne de commande.

## Ce que fait l'application

Vous lui donnez une sauvegarde ou un export de SMART. Elle lit la base de données SMART, vous montre ce qu'elle contient et écrit la zone de conservation dans un site EarthRanger : d'abord sous la forme d'un plan que vous pouvez lire, puis pour de bon lorsque vous confirmez.

## Ce qu'elle migre

- **Le modèle de données** : un type d'événement EarthRanger par catégorie SMART, avec ses champs et ses listes de choix.
- **La configuration des patrouilles** : les types de patrouille, les champs de patrouille et les choix de station.
- **Les écogardes** : un sujet EarthRanger par employé SMART qui a patrouillé ou qui est encore en poste, dans un groupe (la liste des écogardes) que vous choisissez.
- **Les patrouilles** : chaque patrouille avec ses étapes, ses membres, son tracé GPS, ses observations et ses photos.

Vous pouvez d'abord charger le modèle de données seul, ou limiter les patrouilles à une période. Voir [Charger un jeu de données](../../help/fr/03-loading.md).

## Ce qu'elle ne migre pas

- **Les données de Profils.** Si la zone de conservation utilise le module Profils (Profiles) de SMART, vous pouvez consulter ces données dans l'application, mais elles ne sont pas chargées dans EarthRanger.
- **Les équipes de patrouille et les autorisations.** L'API d'EarthRanger ne peut pas les créer. Le chargement s'arrête et indique ce qu'un administrateur EarthRanger doit créer ou accorder ; ensuite vous continuez.
- **Les icônes des types de patrouille.** Le chargement avertit qu'elles manquent, et un administrateur les choisit après coup.
- **Les comptes d'utilisateur des écogardes.** Le chargement crée les écogardes en tant que sujets. Donner à un écogarde un compte lié à ce sujet est une étape pour un administrateur, après coup.
- **Une patrouille sans date de début**, lorsque vous chargez une période.

Rien de ce que fait l'application ne supprime de données dans SMART, et supprimer un jeu de données ou un chargement dans l'application ne supprime rien dans EarthRanger.

## Quelles versions de SMART

- **SMART Desktop 7.5.x** : prise en charge et testée.
- **SMART Desktop 8.0 à 8.1.x** : devrait fonctionner, mais n'a pas encore été éprouvée avec une vraie sauvegarde. Si vous en avez une, dites à l'équipe d'ingénierie d'EarthRanger comment cela se passe.

## Où se trouve l'application, et qui peut se connecter

L'application se trouve à l'adresse [https://smart-able-977100970772.us-central1.run.app/](https://smart-able-977100970772.us-central1.run.app/).

Connectez-vous avec votre compte Google EarthRanger. Si vous voyez « Cette adresse e-mail n'est pas autorisée à utiliser smart-able », demandez à l'équipe d'ingénierie d'EarthRanger d'ajouter votre adresse.

Ce que vous téléversez vous appartient. Personne d'autre ne voit un jeu de données ou un site tant que vous ne le partagez pas.

## Combien de temps cela prend

L'extraction prend quelques minutes. Le chargement lui-même dépend de la vitesse à laquelle le site EarthRanger écrit : environ 0,8 seconde par observation, de sorte qu'une zone de conservation de 70 000 observations prend environ une journée. Il s'exécute tout seul ; vous n'avez pas besoin de garder la page ouverte.

## Suite

Réunissez les deux choses dont vous avez besoin : [Réunir vos éléments](02-get-your-inputs.md).
