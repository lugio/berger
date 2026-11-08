# Modèle de SOUL à la création (2026-10-15)

## Constat

`berger nouveau` écrit toujours un SOUL.md générique « À compléter par <propriétaire> », même pour le Master, dont le rôle est connu.

## Comportement

`nouveau(a, nom)` utilise `commun/modeles/SOUL-<a>.md` s'il existe et si `a` est dans `[\w-]` ; `{nom}` (le nom donné, sinon `a.capitalize()`) et `{proprietaire}` y sont remplacés. Sinon, le SOUL générique d'aujourd'hui, inchangé. Le modèle `SOUL-master.md` est livré.

## Refus

Un nom d'agent hors `[\w-]` n'est jamais utilisé pour construire le chemin du modèle : il ne lit rien hors de `commun/modeles/`.

## Inchangé

`agent.conf` créé par `nouveau`, `methode()`/`lier_skills`, section README « Master ».

## Tests

`tests/modele-soul.py` (installation jetable) : `nouveau master "Master"` → SOUL = modèle, remplacements faits, plus d'accolade de gabarit ; `nouveau autre` → SOUL générique ; nom piégé (`../x`) → aucun modèle lu hors de `modeles/` ; le modèle ne contient ni nom de personne ni chemin personnel (`verifier-depot`).
