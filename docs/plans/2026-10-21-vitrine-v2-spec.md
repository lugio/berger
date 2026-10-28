# Vitrine V2 — contribution et exécution sans installation personnelle

Lot L6 autorisé dans la mission de refonte. Une seule demande de fusion à la fois ; les préparatifs locaux de ce lot ne sont pas poussés pendant l’attente de V1.

Comportement : fichiers communautaires en anglais, modèles GitHub, CI qui exécute les portes de syntaxe et de tests dans un clone local frais, sous HOME jetable, sans configuration, coffre, moteurs ou Herdr réels. La CI est préparée mais jamais exécutée depuis cette mission.

Préparation indépendante : CONTRIBUTING.md, modèles de PR et d’issues, CI, test documentaire et script de preuve de clone frais. Le script refuse une copie sale, clone le commit exact via le système de fichiers, vide l’environnement, pose des sentinelles interdisant les vrais moteurs et Herdr, joue tests/syntaxe.sh puis tests/suites.sh et conserve les codes de retour.

Décisions du propriétaire relayées par le chef : licence MIT au titulaire demandé, signalement et modération par Private vulnerability reporting de GitHub, aucune adresse email, version initiale 0.1.0 au format Keep a Changelog 1.1.0. LICENSE, SECURITY.md, CODE_OF_CONDUCT.md et CHANGELOG.md matérialisent ces décisions. Aucun réglage GitHub n’est créé ni modifié.

Le copyright est conservé exactement comme demandé. Si verifier-depot refuse le nom du titulaire comme marque de l’installation, le refus est remonté au chef et bloque la fusion ; aucune exception ni contournement ne fait partie de ce lot. La phrase de licence obsolète du manuel est remplacée par le lien MIT, avec conservation prouvée du reste du texte.

Tests : nouvelle suite communautaire rouge avant création des fichiers ; puis contrôles de structure, liens, liste blanche, absence de secrets et de permissions d’écriture dans la CI ; preuve réelle du clone frais sur le commit complet. Portes verify/tests/pret et contrôle des marques avant demander-fusion.

Refus : aucun bin/ ni courtier/, pas de publication, pas de capture, pas de réseau depuis cette mission, pas de deuxième demande tant que V1 n’est pas traitée.

## Régression trouvée par le clone frais

Cause racine : tests/notifier.py posait un faux Herdr dans son HOME mais héritait de BERGER_HERDR ; la sentinelle absolue du clone prenait donc priorité sur ce double. Reproduction ciblée : BERGER_HERDR=/bin/false BERGER_NOTIFY_SEND=/bin/true python3 tests/notifier.py, cinq échecs avant correction. Le test désigne désormais son propre double et neutralise explicitement les notifications de bureau. Aucune modification du code du produit.
