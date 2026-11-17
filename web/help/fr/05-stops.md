# Quand un chargement s'arrête

Une exécution s'arrête là où le site a besoin de quelque chose que l'API ne peut pas faire, ou là où le site n'est pas prêt pour les patrouilles. Chaque constat, sur la page du chargement, nomme ce qu'il faut faire ; les entrées ci-dessous donnent la même consigne avec plus de place. Les valeurs que le constat montre avec un bouton de copie sont exactes : EarthRanger les fait correspondre par leur nom.

Les noms de menus de l'administration d'EarthRanger sont donnés en anglais, tels qu'elle les affiche.

Après avoir corrigé le site, appuyez sur **Continuer**. L'exécution répète les premières étapes, ce qui est rapide, et poursuit.

## Configuration des patrouilles

### Créer une équipe de patrouille {#finding-team}

Les patrouilles SMART nomment une équipe ; l'API d'EarthRanger ne peut pas créer d'équipes. Dans l'administration Django, ouvrez **Patrol configuration › Teams** et ajoutez une équipe dont le champ *display* est exactement le nom d'équipe affiché. Le constat énumère les membres SMART de l'équipe, pour information ; l'import identifie l'équipe par son nom seulement. Une entrée par équipe manquante ; créez-les toutes, puis **Continuer**.

### Mettre les écogardes dans le groupe de sujets de la liste des écogardes {#finding-roster_group}

Aucun groupe n'a été indiqué pour la liste des écogardes à la création du chargement ; les sujets écogardes ont donc été créés mais pas placés dans le groupe où les écogardes sont choisis. Soit refaites le plan du chargement en nommant un groupe, ce qui permet à l'exécution de les ajouter, soit, dans l'administration Django, ouvrez **Patrol configuration › member subject groups**, choisissez ou créez le groupe, et ajoutez-y les sujets.

### Ajouter les sujets au groupe de sujets {#finding-permission_subject_group}

Le groupe de la liste des écogardes existe, mais l'utilisateur du site ne peut pas modifier l'appartenance aux groupes de sujets. Soit accordez cette autorisation à l'utilisateur et appuyez sur **Continuer**, soit ajoutez vous-même les sujets au groupe dans **Django admin › Subject groups**. Le nom du groupe est affiché avec un bouton de copie.

### Activer la fonctionnalité patrol_schemas {#finding-enable_patrol_schemas}

La fonctionnalité en préversion `patrol_schemas` est désactivée sur le site ; il n'a donc ni étapes de patrouille, ni champs de patrouille universels, ni équipes, ni listes d'écogardes dans lesquels importer. Dans l'administration Django, ouvrez **Preview features › patrol_schemas** et activez-la pour ce locataire (tenant). Adressez-vous à EarthRanger Core si la page n'est pas disponible. Puis **Continuer** ; les champs de patrouille universels sont écrits au passage suivant.

### Accorder l'autorisation : types de patrouille {#finding-permission_patrol_types}

L'utilisateur du site ne peut pas créer ni modifier les types de patrouille. Dans l'administration Django, ouvrez **Users › the user** (l'utilisateur) et ajoutez `activity | patrol type | Can add/change patrol type`. Puis **Continuer**.

### Accorder l'autorisation : champs de patrouille universels {#finding-permission_segment_schema}

L'utilisateur du site ne peut pas écrire les champs de patrouille universels (le schéma de segment). Ajoutez `activity | segment type | Can change segment type` ; aujourd'hui, cela exige un superutilisateur. Puis **Continuer**.

### Accorder l'autorisation : sujets {#finding-permission_subjects}

L'utilisateur du site ne peut pas voir, ajouter ni modifier les sujets ; les sujets écogardes n'ont donc pas pu être créés ni retrouvés. Ajoutez `observations | subject | Can view/add/change subject`. Puis **Continuer**.

### Accorder l'autorisation : configuration des patrouilles {#finding-permission_patrol_config}

L'utilisateur du site ne peut pas lire la configuration des patrouilles, par rapport à laquelle les équipes et les listes d'écogardes sont vérifiées. Ajoutez `activity | patrol | Can view patrol`. Puis **Continuer**.

### Choisir une icône pour chaque type de patrouille {#finding-patrol_type_icons}

Un avertissement, pas un arrêt. L'API ne peut pas définir l'icône d'un type de patrouille ; les nouveaux types affichent donc l'icône de patrouille par défaut d'EarthRanger jusqu'à ce que vous en choisissiez une dans **EarthRanger admin › Patrol types**.

### Nommer les stations que SMART a laissées sans nom {#finding-station_names}

Un avertissement, pas un arrêt. Certaines stations n'ont de nom dans aucune langue de SMART ; elles ont donc été créées avec un nom provisoire tel que `Unnamed station 1a2b3c4d`. Nommez-les dans SMART et refaites l'export, ou renommez le choix dans **Django admin › Choices** (champ `patrol_station`) ; une exécution ultérieure remet le nom provisoire tant que SMART n'a pas de nom.

## Vérification préalable

### Le fuseau horaire du lot a été déduit {#finding-timezone}

Un avertissement. SMART n'a pas enregistré le fuseau horaire de la zone de conservation ; l'extraction l'a donc déduit de l'emplacement des waypoints. Les heures des patrouilles et des observations sont converties avec ce fuseau. S'il est faux, définissez `SMART_ABLE_TIMEZONE` pour l'extraction et extrayez de nouveau le jeu de données ; la page des particularités explique comment les fuseaux horaires sont traités.

### Des libellés manquent dans la langue choisie {#finding-language}

Un avertissement. Certains éléments du modèle de données n'ont pas de libellé dans la langue avec laquelle le chargement a été créé ; ils se rabattent donc sur la langue par défaut du lot ou sur n'importe quelle langue qui en a un. L'onglet Data Model du jeu de données montre dans quelle mesure chaque langue est couverte ; refaites le plan du chargement avec la mieux couverte si les libellés comptent.

### Jours d'étape de patrouille sans information d'heure {#finding-time_coverage}

Un avertissement, rien à faire. Certains jours d'étape de patrouille n'ont ni tracé, ni heure de début ou de fin, ni waypoint horodaté ; leurs segments couvrent donc toute la journée. Chacun de ces segments est enregistré avec `time_source: date_only`.

### Une vérification préalable n'a pas pu s'exécuter {#finding-check_failed}

L'une des vérifications a levé une erreur avant de pouvoir rendre compte, en général un problème de connexion ou d'autorisation avec le site. Le message nomme la vérification et l'erreur. Corrigez la cause, puis **Continuer** ; la vérification préalable reprend du début.

### La fonctionnalité patrol_schemas est désactivée {#finding-feature_flag}

La même situation que *Activer la fonctionnalité patrol_schemas* ci-dessus, vue depuis la vérification préalable. Activez la fonctionnalité, puis **Continuer**.

### L'utilisateur du site n'a pas les autorisations {#finding-permissions}

Le constat énumère chaque autorisation dont l'import a besoin et que l'utilisateur n'a pas. Accordez-les dans **Django admin › Users › the user**, application `activity`. Créer des événements dans une catégorie exige l'autorisation de création de cette catégorie, en général accordée par un jeu d'autorisations. Puis **Continuer**.

### Des types de patrouille manquent ou sont inactifs {#finding-patrol_types}

La configuration des patrouilles crée les types dont les étapes de patrouille ont besoin ; lors d'une exécution, cela signifie donc normalement qu'un type a été désactivé après coup. Activez-le dans **EarthRanger admin › Patrol types**, ou appuyez sur **Continuer** pour laisser la configuration des patrouilles le recréer. Dans un plan, c'est attendu : le plan n'écrit rien, et le constat est marqué comme quelque chose que l'exécution créera.

### Des champs de patrouille universels manquent ou sont obsolètes {#finding-segment_schema}

La configuration des patrouilles écrit ces champs. Si un administrateur en a volontairement rendu un obsolète, rétablissez-le dans le générateur de formulaires de patrouille ; sinon, **Continuer**. Dans un plan, c'est attendu.

### Des options utilisées par les patrouilles manquent ou sont inactives {#finding-choices}

Un avertissement. Certaines options de liste que les patrouilles utilisent ne sont pas sur le site ou ont été désactivées ; ces champs seraient donc stockés sans entrée correspondante. La configuration des patrouilles les crée ; une option qu'un administrateur a désactivée peut être réactivée dans **Django admin › Choices**.

### Des membres de patrouille ne peuvent pas être placés sur un segment {#finding-subjects}

Les sujets écogardes de ces membres n'existent pas, ou ne sont pas dans un groupe listé sous **Patrol configuration › members**. La configuration des patrouilles les crée et, si un groupe a été nommé pour la liste des écogardes, les y ajoute. Sinon, ajoutez-les à un tel groupe dans **Django admin › Subject groups**. Dans un plan, c'est attendu.

### Des membres de patrouille sont inactifs {#finding-inactive_members}

Un avertissement, rien à faire. EarthRanger n'accepte que des membres actifs sur un segment ; l'import réactive donc ces sujets pour l'exécution et les désactive de nouveau quand elle se termine. Le registre le consigne.

### Des équipes de patrouille manquent ou sont inactives {#finding-teams}

La même situation que *Créer une équipe de patrouille* ci-dessus : chaque équipe nommée doit exister, active, avec exactement ce nom d'affichage, sous **Patrol configuration › Teams**. Une entrée par équipe, avec un bouton de copie.

### Types d'événement {#finding-event_types}

Les catégories SMART observées ont besoin d'un type d'événement actif sur le site. Le message dit quel cas s'applique :

- **No active event type** (aucun type d'événement actif) : le modèle de données n'a pas été envoyé sous la catégorie d'événements que ce chargement utilise. Dans un plan, c'est attendu et marqué comme quelque chose que l'exécution créera. Lors d'une exécution, vérifiez la catégorie d'événements : si un envoi antérieur a utilisé un autre identifiant, refaites le plan du chargement avec celui-ci.
- **Match more than one event type** (correspond à plusieurs types d'événement) : le site a plusieurs envois de modèle de données, sous des catégories différentes, avec les mêmes noms de type. Refaites le plan du chargement avec la catégorie d'événements de l'envoi sur lequel importer.
- **Map to an inactive event type** (correspond à un type d'événement inactif) : un avertissement. La catégorie est une catégorie parente de SMART ou a été désactivée ; ses événements sont importés sur le type inactif, qu'EarthRanger ne propose pas pour de nouveaux rapports. Activez le type dans **EarthRanger admin › Event types** si les écogardes doivent continuer à l'utiliser.
- **Exist only as configurable model variants** (n'existent que comme variantes du modèle configurable) : ces catégories ont un type d'événement par formulaire, et l'import ne sait pas encore à quelle variante appartient une observation. Ces patrouilles ne peuvent pas encore être importées ; il faut une table de correspondance des variantes, qui reste à faire dans er-smart-sync.

### Pas de type d'événement de regroupement {#finding-collection_type}

Un avertissement. Certains waypoints contiennent plusieurs observations, et le site n'a pas de type d'événement `incident_collection` actif pour les regrouper ; leurs événements sont donc importés sans regroupement. Ajoutez ou activez ce type dans **EarthRanger admin › Event types** pour les regrouper.

### Étapes de patrouille à la date provisoire de 1970 ou couvrant plus d'un an {#finding-leg_span}

Un avertissement, rien à faire. SMART stocke certaines dates d'étape de patrouille sous la forme d'une date provisoire ; l'import ne garde que les jours d'étape qui ont un tracé ou un waypoint. Pour corriger les dates, corrigez l'étape dans SMART et refaites l'export.

### Observations dont on ne peut dire qui les a rapportées {#finding-observers}

Un avertissement. Chaque événement importé nomme la personne qui l'a rapporté : le sujet de l'observateur SMART ou, quand cette personne n'a pas de sujet sur le site, le chef de l'étape de patrouille, sinon son premier membre. Les observations listées n'ont aucun de ceux-là ; leurs événements ne portent donc pas de rapporteur. Rien à faire, sauf si cela compte : donnez à l'observateur une fiche d'employé dans SMART et refaites l'export. Un plan n'énumère que les observations que les sujets de l'exécution elle-même ne permettent pas de résoudre.

### L'extraction a consigné des avertissements {#finding-bundle_warnings}

Un avertissement. smart-able a noté des choses au sujet des données en écrivant le lot. Elles sont listées dans le manifeste du lot et expliquées dans *SMART data quirks* (les particularités des données SMART, en anglais).

## Import

### Des patrouilles n'ont pas pu être importées {#finding-patrols_failed}

Chaque patrouille en échec est listée avec son erreur. La plupart des erreurs nomment quelque chose qui manque sur le site : une équipe, un sujet, un type d'événement. Corrigez cela, puis **Continuer** ; seules les patrouilles en échec sont réessayées. Un `500` sur un identifiant de patrouille déjà présent sur le site est EarthRanger qui refuse un doublon ; la nouvelle tentative lit la patrouille existante et poursuit.

### Le jeton du site ne fonctionne plus {#finding-site_token_rejected}

Le site a refusé le jeton ; rien n'a donc été écrit. Retirez le site, enregistrez-le de nouveau avec un jeton valable, et lancez un nouveau chargement.
