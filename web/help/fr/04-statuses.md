# Statuts

Les statuts sont affichés en anglais par l'application ; ils sont donnés ici tels quels.

## Un chargement

| Statut | Signification |
|---|---|
| <code>planning</code> | Le plan est en cours d'établissement. N'écrit rien. |
| <code>planned</code> | Le plan est prêt à être lu et confirmé. |
| <code>queued</code> | Confirmé ; l'exécution a été demandée et va démarrer. |
| <code>running</code> | L'exécution parcourt ses étapes. La page se met à jour toutes les quelques secondes. |
| <code>continuing</code> | L'exécution a atteint la limite de 22 heures et a passé le relais à une nouvelle exécution d'elle-même. Voir *Longues exécutions et reprise*. |
| <code>needs_attention</code> | L'exécution s'est arrêtée sur un constat bloquant, ou s'est terminée avec des patrouilles en échec. Lisez les constats, corrigez le site, appuyez sur **Continue** (continuer). |
| <code>done</code> | Toutes les patrouilles sont sur le site. |
| <code>failed</code> | La tâche a rencontré une erreur dont elle n'a pas pu se remettre. L'erreur et le journal sont sur la page. Après avoir corrigé la cause, appuyez sur **Plan again** (refaire le plan) ; le nouveau plan montre ce qui reste et propose Confirm. (Continue ne sert que pour un chargement arrêté sur des constats ou dont la tâche a été tuée.) |

## Une étape

| Statut | Signification |
|---|---|
| pending (en attente) | Pas encore atteinte dans cette exécution. |
| running (en cours) | En cours, avec le temps écoulé jusqu'ici. |
| done (terminée) | Terminée, avec sa durée et ce qu'elle a fait. |
| stopped (arrêtée) | La règle d'arrêt a mis fin à l'exécution ici : un constat bloquant après cette étape. |
| failed (échec) | Une erreur dans cette étape a mis fin à l'exécution. |
| interrupted (interrompue) | La tâche a été tuée avant de pouvoir rendre compte ; sa réservation a expiré et **Continue** est disponible. |
| not reached (non atteinte) | Une étape ultérieure d'une exécution qui s'est arrêtée ou a échoué plus tôt. |

## Le signal de vie

Sous le tableau des étapes, tant qu'un chargement est actif, une ligne indique depuis combien de temps cette exécution tourne et depuis combien de temps la tâche a rendu compte pour la dernière fois. La tâche rend compte à chaque changement d'étape et au moins toutes les trente secondes pendant l'import ; un temps « last reported » qui continue de croître au-delà de quelques minutes signifie donc que la tâche est bloquée ou a disparu.
