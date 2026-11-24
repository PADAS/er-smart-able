# Vue d'ensemble

smart-able prend une sauvegarde ou un export de zone de conservation SMART, l'extrait pour que vous puissiez le parcourir ici, et le charge dans un site EarthRanger. Les étapes, dans l'ordre :

1. **Téléverser** un zip de sauvegarde du système SMART, un dossier d'installation de SMART Desktop compressé, ou un export de zone de conservation. Le jeu de données vous appartient ; partagez-le ensuite avec vos collègues depuis sa page.
2. **Extraire** : une tâche de fond de quelques minutes. Elle lit la base de données, écrit un site consultable pour chaque zone de conservation et publie un lot de migration pour chacune. La liste des jeux de données se met à jour d'elle-même pendant que la tâche s'exécute.
3. **Parcourir** les données extraites depuis la page du jeu de données (**Parcourir** dans sa **Vue d'ensemble**, ou les vues sous **Données** dans la barre latérale) : patrouilles, waypoints, observations, modèle de données, et les particularités que l'extraction a relevées.
4. **Enregistrer un site** : un hôte EarthRanger et un jeton d'API. Le jeton est vérifié avant d'être enregistré. Voir *Sites et jetons*.
5. **Charger** une zone de conservation dans un site depuis la page du jeu de données, dans sa **Vue d'ensemble**, ou sous **Chargements** dans la barre latérale. Un chargement produit d'abord un plan de tout ce qu'il écrirait ; vous confirmez le plan, et l'exécution l'écrit. Là où le site a besoin de quelque chose que seule une personne peut faire, l'exécution s'arrête et vous dit quoi. Voir *Charger un jeu de données* et *Quand un chargement s'arrête*.

Tout ce que vous téléversez, extrayez et chargez n'est partagé qu'avec les personnes avec qui vous le partagez. L'équipe d'assistance d'EarthRanger peut aussi consulter les jeux de données et les sites, pour aider à une migration ; elle ne peut ni les modifier ni charger de données. Supprimer un jeu de données supprime ses données extraites, ses lots et ses enregistrements de chargement ; cela ne retire jamais rien d'EarthRanger.

La sauvegarde téléversée elle-même est conservée pendant une durée limitée (30 jours sur l'application hébergée), puis supprimée automatiquement. La page du jeu de données indique la date, et le propriétaire du jeu de données peut supprimer la sauvegarde plus tôt. Les données extraites ne sont pas concernées : elles restent jusqu'à la suppression du jeu de données. Pour extraire de nouveau une fois la sauvegarde disparue, téléversez-la de nouveau depuis l'onglet **Sauvegarde** du jeu de données. Vous pouvez aussi y téléverser une sauvegarde plus récente de la même base de données SMART : elle remplace celle qui est conservée, et le jeu de données est extrait de nouveau à partir d'elle. Les chargements listés pour le jeu de données restent.

## De SMART : une sauvegarde ou un export {#upload-file}

Il vous faut un seul fichier, pas les trois. L'application accepte n'importe lequel de ceux-ci, sous la forme d'un seul fichier `.zip` :

- **Un export de zone de conservation.** Il contient une seule zone de conservation. SMART le nomme `SMART_<area identifier>_<date>.bak.zip` (identifiant de la zone, puis date).
- **Une sauvegarde du système SMART.** SMART la nomme `SMART_<date>.bak.zip`. Elle contient toutes les zones de conservation de cette copie de SMART ; vous choisirez plus tard laquelle charger.
- **Un dossier SMART Desktop compressé.** Compressez en zip tout le dossier à partir duquel SMART Desktop s'exécute, SMART Desktop étant fermé. Utilisez cette solution lorsque vous ne pouvez pas lancer SMART pour faire un export ou une sauvegarde.

Téléversez le `.zip` tel quel. Ne le décompressez pas, et ne téléversez pas un fichier qui se trouve à l'intérieur.
