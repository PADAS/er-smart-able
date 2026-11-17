# Vue d'ensemble

smart-able prend une sauvegarde ou un export de zone de conservation SMART, l'extrait pour que vous puissiez le parcourir ici, et le charge dans un site EarthRanger. Les étapes, dans l'ordre :

1. **Téléverser** (Upload) un zip de sauvegarde du système SMART, un dossier d'installation de SMART Desktop compressé, ou un export de zone de conservation. Le jeu de données vous appartient ; partagez-le ensuite avec vos collègues depuis sa page.
2. **Extraire** (Extract) : une tâche de fond de quelques minutes. Elle lit la base de données, écrit un site consultable pour chaque zone de conservation et publie un lot de migration pour chacune. La liste des jeux de données se met à jour d'elle-même pendant que la tâche s'exécute.
3. **Parcourir** les données extraites depuis la page du jeu de données (**Browse** dans l'onglet Overview) : patrouilles, waypoints, observations, modèle de données, et les particularités que l'extraction a relevées.
4. **Enregistrer un site** : un hôte EarthRanger et un jeton d'API. Le jeton est vérifié avant d'être enregistré. Voir *Sites et jetons*.
5. **Charger** (Load) une zone de conservation dans un site depuis la page du jeu de données, dans son onglet Overview ou Loads. Un chargement produit d'abord un plan de tout ce qu'il écrirait ; vous confirmez le plan, et l'exécution l'écrit. Là où le site a besoin de quelque chose que seule une personne peut faire, l'exécution s'arrête et vous dit quoi. Voir *Charger un jeu de données* et *Quand un chargement s'arrête*.

Tout ce que vous téléversez, extrayez et chargez n'est partagé qu'avec les personnes avec qui vous le partagez. Supprimer un jeu de données supprime ses données extraites, ses lots et ses enregistrements de chargement ; cela ne retire jamais rien d'EarthRanger.
