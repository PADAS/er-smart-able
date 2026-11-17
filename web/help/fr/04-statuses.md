# Statuts

## Un chargement

| Statut | Signification |
|---|---|
| <code>planning</code> planification | Le plan est en cours d'établissement. N'écrit rien. |
| <code>planned</code> planifié | Le plan est prêt à être lu et confirmé. |
| <code>queued</code> en file d'attente | Confirmé ; l'exécution a été demandée et va démarrer. |
| <code>running</code> en cours | L'exécution parcourt ses étapes. La page se met à jour à intervalles de quelques secondes. |
| <code>continuing</code> en reprise | L'exécution a atteint la limite de 22 heures et a passé le relais à une nouvelle exécution d'elle-même. Voir *Longues exécutions et reprise*. |
| <code>needs_attention</code> intervention nécessaire | L'exécution s'est arrêtée sur un constat bloquant, ou s'est terminée avec des patrouilles en échec. Lisez les constats, corrigez le site, appuyez sur **Continuer**. |
| <code>done</code> terminé | Toutes les patrouilles sont sur le site. |
| <code>failed</code> échec | La tâche a rencontré une erreur dont elle n'a pas pu se remettre. L'erreur et le journal sont sur la page. Après avoir corrigé la cause, appuyez sur **Refaire le plan** ; le nouveau plan montre ce qui reste et propose **Confirmer et charger**. (**Continuer** ne sert que pour un chargement arrêté sur des constats ou dont la tâche a été tuée.) |

## Une étape

| Statut | Signification |
|---|---|
| en attente | Pas encore atteinte dans cette exécution. |
| en cours | En cours, avec le temps écoulé jusqu'ici. |
| terminé | Terminée, avec sa durée et ce qu'elle a fait. |
| arrêté | La règle d'arrêt a mis fin à l'exécution ici : un constat bloquant après cette étape. |
| échec | Une erreur dans cette étape a mis fin à l'exécution. |
| interrompu | La tâche a été tuée avant de pouvoir rendre compte ; sa réservation a expiré et **Continuer** est disponible. |
| non atteint | Une étape ultérieure d'une exécution qui s'est arrêtée ou a échoué plus tôt. |

## Le signal de vie

Sous le tableau des étapes, tant qu'un chargement est actif, une ligne indique depuis combien de temps cette exécution tourne et depuis combien de temps la tâche a rendu compte pour la dernière fois. La tâche rend compte à chaque changement d'étape et au moins toutes les trente secondes pendant l'import ; un temps « last reported » qui continue de croître au-delà de quelques minutes signifie donc que la tâche est bloquée ou a disparu.
