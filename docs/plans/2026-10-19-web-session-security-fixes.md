# Décisions de sécurité — session prêtée et relais

Les décisions suivantes encadrent le filtrage et le cycle de vie des sessions prêtées. Les régressions locales utilisent des données factices.

1. Réponse du prêt : obtenir les valeurs liées au domaine et à l'agent ; cadrer et filtrer la réponse entière avant publication dans l'enveloppe, y compris les valeurs d'en-têtes et le corps. Les formats non pris en charge sont refusés avant publication. Le tampon est borné et documenté.
2. Refuser les trois en-têtes de surcharge de méthode et le paramètre `_method` avant Cookie/amont. Appliquer la politique des chemins sensibles aux actions explicites de la query ; documenter que GET n'assure pas l'absence d'effets côté site.
3. Découpler la fermeture des proxies de la sauvegarde/suppression du coffre. Chaque accès a une échéance indépendante ; le nettoyage lent ne tient pas le verrou global. Conserver la réservation du domaine tant que sa marque de nettoyage persiste pour éviter de supprimer un nouveau prêt.
4. Garder l'aperçu complet dans la validation protégée ; transmettre l'échange par stdin et n'adresser aux backends de notification qu'un avis neutre avec référence de validation. Vérifier toute la chaîne de sous-processus avec un canari.
5. Ne retenir dans le filtre général du courtier que les valeurs de session d'au moins huit caractères ; garder le filtrage des valeurs longues après suppression. La protection des valeurs effectivement reflétées par le proxy reste distincte du refus global des réponses MCP.

Régressions : `tests/web-security-review.py`, tests de proxy et de coffre. Les essais locaux ne prouvent pas l’admission sur un moteur réel.
