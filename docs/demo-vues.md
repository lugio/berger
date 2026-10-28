# Démonstration fictive des vues Herdr

Depuis un clone, avec Python 3 et Git :

```bash
python3 docs/scripts/demo-vues.py /tmp/berger-demo-vues
cat /tmp/berger-demo-vues/accueil-140.txt
cat /tmp/berger-demo-vues/colonnes-140.txt
cat /tmp/berger-demo-vues/courtier-140.txt
```

Le dossier de sortie doit être neuf. Six fichiers sont produits : Accueil, Colonnes et Courtier, chacun à 80 et 140 colonnes. Pour les captures du README, ouvrir les fichiers `*-140.txt` dans un terminal de 140 colonnes. Les fichiers sont sans codes de couleur pour être faciles à comparer. L’horloge est figée au 13 octobre 2026 à 10 h ; sous un même fuseau, deux générations sont identiques.

Tous les personnages, tâches, échanges et fusions sont inventés et en français. `HOME` et `BERGER_DIR` pointent vers un dossier temporaire ; Herdr, systemctl et les moteurs sont simulés. Le faux service Courtier est actif dans la démo ; un service réellement arrêté reste signalé « ARRÊTÉ ». La sauvegarde dispose de sa propre section. Seuls les fichiers du produit suivis par Git sont copiés : aucune configuration, aucun journal ni aucune donnée de l’installation réelle. Le dossier temporaire est retiré à la fin ; seuls les six rendus sont conservés.

## Compteurs et résolution des décisions

Accueil et Décisions comptent les mêmes gestes, distinguant propriétaire et agent. Catégories : validations, permissions du terminal, blocages, go, questions, propositions de mémoire/méthode, signalements, lectures, décisions de rapport et fusions. Une lecture compte par document ; sa décision est un geste distinct. Le Tableau agent reprend les gestes du propriétaire concernant cet agent.

Dans les quinze premières lignes d’un rapport, rattacher la décision à son objet :

```markdown
# Proposition d’archive
Décision attendue : autoriser la création de l’archive
Décision liée : validation:4
```

Ou `Décision liée : fusion:demo/navigation`. Une validation exécutée avec succès ou refusée, ou une fusion terminée, retire la décision des attentes. Un échec, un objet inconnu ou un lien mal formé laisse la décision ouverte. Hors objet, utiliser `Décision résolue : motif de la décision`. Lire le rapport ou publier un rapport plus récent ne résout pas une décision. Les anciens rapports sans lien nécessitent une mise à jour explicite de leur auteur.

Les propositions `pending/` sont comptées si leur en-tête déclare `type: memoire` ou `type: skill`. Les traces sans type, les fichiers commençant par `piege-`, `sonde-` ou `test-` (préfixe de date facultatif), et ceux marqués `test: oui` ou `sonde: oui` sont exclus.

Courtier réserve ses 200 entrées aux refus du jour avant de compléter par les appels récents. Les répétitions sont regroupées sur cette sélection ; le compteur du jour porte sur le journal complet. En mode compact étroit, Colonnes montre les livraisons en premier et réserve une ligne à chaque autre section ; le surplus de cartes est résumé par un compteur.

## Vérifications

`python3 tests/vues-herdr.py` vérifie les corrections. `python3 tests/demo-vues.py` compare deux générations indépendantes et contrôle largeurs et absence de chemins personnels.
