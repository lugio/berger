# Berger présenté seul

## Constat et comportement

Les commentaires et le manuel citent deux projets tiers au lieu de décrire les
mécanismes de Berger. Remplacer ces références par une description de la porte
de perte mémoire, de la liste d'hôtes permis par secret, de la détection des
clés et de la délégation. Aucun comportement de ces mécanismes ne change.

Le contrôle `verifier-depot` refuse désormais aussi les deux anciennes marques,
indépendamment de la configuration locale, avec la même recherche insensible à
la casse et les mêmes limites de mots que les autres marques. Construire leurs
noms par fragments pour que le contrôle accepte son propre code et ses tests.

## Tests et limites

Un dépôt Git temporaire, un HOME temporaire et BERGER_DIR surchargé prouvent :
texte neutre accepté, chaque marque refusée en minuscules et en majuscules dans
un fichier suivi, puis acceptation après retrait. La configuration et le coffre
réels ne sont jamais lus. Ajouter la suite aux portes habituelles.

Hors périmètre : configuration d'installation, skills, présentation GitHub,
changements de droits ou de gestion des secrets. Relecture et fusion suivent le
circuit habituel. Les fichiers partagés avec l'autre développeur sont intégrés
par fusion de main, sans réécriture de l'historique.
