# L4 — Transport privé des contenus

Cause racine : les fonctions transmettent des contenus métier en paramètres positionnels aux CLI ; les descendants les exposent dans cmdline.

Critère global : aucun contenu ni chemin privé dans les argv, aux frontières directes et imbriquées. Aucun repli vers les anciens arguments.

Premier correctif indépendant : `demander` transmet la consigne par stdin aux deux moteurs (Codex `exec … -`, Claude `--print`, entrée texte). La délégation utilise `berger demander <agent> --stdin`. Le CLI refuse la consigne positionnelle et borne stdin à un Mio. Tests : capturer argv et stdin, vérifier transmission intégrale, bascule et refus du chemin ancien.

Points restant à mesurer avant admission globale : Herdr (fichier relatif et acquittement de lecture), instructions système du mur ouvert, notifications, autres commandes et wrappers, chemins d'installation. Aucun résultat partiel ne vaut admission du lot.

## Première livraison L4a (séparation demandée par le chef)

Inclut demander et sa délégation imbriquée, stdin borné et refus de l'ancienne syntaxe, notifications génériques et leur transport imbriqué JSON sur stdin, documentation et wrappers correspondants. Le fichier de sortie Codex est créé exclusivement en 600 dans un dossier temporaire 700 ; nettoyage normal, échec, SIGINT et SIGTERM en CLI. SIGKILL ne permet aucun nettoyage Python.

Les aides locales ont été consultées : `codex exec --help` documente `-` et stdin ; `claude --help` documente `--print` et `--input-format text`. Les tests utilisent des moteurs factices et capturent leur `/proc/self/cmdline` ; cela ne remplace pas l'admission des vrais moteurs.

Herdr reste inchangé. `tests/sonde-herdr-lecture.py` est un script manuel à faire lancer par le propriétaire sur un agent réel au repos, avec `BERGER_DIR` défini, depuis la copie contrôlée : `python3 tests/sonde-herdr-lecture.py <agent> codex` puis la même commande avec `claude`. Il crée un dossier 700 et un message 600 de nom neutre, demande la lecture par chemin relatif, attend une empreinte correcte et la suppression du message par l'agent, puis nettoie le dossier. Il ne montre aucune valeur et ne prétend pas admettre le transport de production. Nettoyage également après refus, délai ou interruption. Il faut jouer ce script pour chaque moteur ; pas de succès réel déduit de son test factice.

L4b doit encore traiter parler et messages, missions et équipes, interfaces du courtier, autres wrappers, instructions système du mur ouvert et chemins privés. L'audit a aussi repéré les corps JSON transmis à curl par certains connecteurs : hors admission du premier correctif.
