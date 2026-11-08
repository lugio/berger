# Compatibilité Python 3.11 et suivantes

Les entrées des messages internes (`delegation-suivi`, `echange`) et du crochet d'équipe sont décodées explicitement
en UTF-8 strict, indépendamment du gestionnaire d'erreurs de l'entrée standard Python. Des octets invalides sont refusés
avant de lire les champs JSON ou d'écrire un échange ; le crochet conserve sa réponse silencieuse `suppressOutput`.
Les tests d'équivalence comparent le refus JSON trop imbriqué sans figer le libellé de limite de pile propre à CPython.
Le test de contention remonte seulement le fichier du verrou dans le `/tmp` privé, y compris pour un clone frais sous `/tmp`.
