# Vitrine V1 — extraction du manuel

Mission validée par le coordinateur, go du propriétaire du 19 octobre : lot L1.

Objectif : rendre le point d’entrée court sans perdre un seul octet du manuel français.
Le README initial est copié exactement dans `docs/manuel.md`, puis remplacé à la racine par une orientation vers ce manuel.
La conservation du manuel est vérifiée par empreinte dans `tests/vitrine.py`, même dans un clone sans historique. Le sommaire est exclu du calcul ; le corps de référence est conservé. La matrice de migration initiale relève du suivi interne archivé séparément.

Refus : aucun changement dans bin/ ou courtier/, aucun réseau, capture, publication ou logo intégré sans choix du propriétaire. Les phrases historiques du manuel restent inchangées dans ce lot, y compris sa mention de licence, traitée en V2.

Plan et preuves :
1. Ajouter une suite qui échoue sans manuel, contrôle l’empreinte et les liens locaux ; éprouver aussi le refus d’un lien cassé.
2. Déplacer le manuel à l’identique et conserver son empreinte ; remplacer le README racine.
3. Adapter le test documentaire du Master et inscrire la nouvelle suite dans tests/suites.sh.
4. Prouver la liste blanche et exécuter verifier-depot dans une installation jetable sans configuration personnelle.
5. Jouer verify, tests puis pret ; transmettre le résultat à master pour contrôle des marques avant demande de fusion.

Hors périmètre : licence, modèles communautaires et CI (V2), README bilingue définitif et logo (V3). Retour arrière : commit inverse de ce lot sur la branche de travail.
