# Spec — accueil public

## Objectif
Permettre à une personne découvrant Berger de suivre une installation documentée jusqu’à son premier agent, et de consulter des décisions techniques sans suivi interne ni références propres à une installation.

## Success metrics
- [ ] README anglais et français : URL de clone exacte vérifiée, configuration minimale, création du premier agent, lancement et résultat attendu ; commandes confirmées dans le produit, prérequis et interventions manuelles explicites.
- [ ] `docs/install.md` fournit une installation courte en anglais, liée depuis le README anglais ; `docs/manuel.md` possède un sommaire avec ancres valides.
- [ ] `docs/plans/` conserve les décisions utiles avec exemples neutres ; les fichiers de suivi interne sont retirés du dépôt après inventaire, leur copie complète étant conservée par le coordinateur selon la mission.
- [ ] `CONTRIBUTING.md` précise brièvement les langues des contributions ; les liens locaux restent valides et le contrôle de conservation du manuel est adapté sans perdre son contenu de référence.
- [ ] Portes `verify`, `tests`, `pret` réussies ; contrôle des marques demandé au coordinateur avant une unique demande de fusion listant chaque fichier retiré ou modifié et les limites restantes.

## Hors scope
- `bin/`, `courtier/`, `verifier_depot` et tous les tests sauf les adaptations documentaires de `tests/vitrine.py` autorisées par la mission ; liste blanche Git seulement si nécessaire aux documents.
- Manuel anglais complet, captures, publication, fusion, installation et production.
- Modification des permissions, de l’authentification ou des services ; exécution de l’installation sur l’hôte et appels supplémentaires à des services externes.

## Risques
- Installation dépendante de prérequis système et de connexions interactives : distinguer commandes copiables et interventions incompressibles, sans prétendre avoir validé un moteur réel.
- Perte d’une décision ou lien cassé lors du tri : classer les plans, conserver les décisions et inventorier chaque retrait ; vérifier les références avant livraison.
- Empreinte du manuel liée à une matrice interne : remplacer la référence de migration par un contrôle documentaire conservant la preuve utile, dans le seul test autorisé.
- Budget maximal de trois heures : limiter le travail à ce lot, réserver du temps aux portes ; livrer les éléments vérifiés et nommer explicitement les manques à l’échéance.

## Plan d’attaque (≤ 5 étapes)
1. Examiner les commandes et unités existantes, l’exemple de configuration et les contrôles documentaires ; remettre cette spec au coordinateur.
2. Compléter les deux démarrages rapides, l’installation anglaise, le sommaire et la règle de langue.
3. Trier les plans, neutraliser les références locales et établir l’inventaire exact des changements.
4. Adapter le contrôle documentaire autorisé, vérifier commandes et liens puis jouer les trois portes.
5. Demander le contrôle des marques au coordinateur, puis préparer une seule demande de fusion avec résultats et écarts.
