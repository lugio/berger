# Plans et décisions

Index des documents de conception de Berger. Les documents **visibles** ci-dessous portent des décisions et des règles encore en vigueur ;
ceux d'`archive/` sont terminés (livrés, remplacés ou abandonnés) et ne sont gardés que pour l'historique : leurs conclusions utiles sont dans
le manuel (`docs/manuel.md`) et le CHANGELOG. Les chemins `docs/plans/<nom>` des plans archivés deviennent `docs/plans/archive/<nom>`.

## Décisions et règles en vigueur

| Document | Statut | Sujet |
| --- | --- | --- |
| [2026-10-12-processus-dev-generique-spec.md](2026-10-12-processus-dev-generique-spec.md) | en vigueur | Processus de développement générique — un seul circuit pour toutes les équipes |
| [2026-10-13-hierarchie-equipe-spec.md](2026-10-13-hierarchie-equipe-spec.md) | en vigueur | Hiérarchie d'équipe générique — coordinateur → chef de projet → développeurs |
| [2026-10-13-interface-spec.md](2026-10-13-interface-spec.md) | en vigueur | Une interface web pour Berger, alignée sur Berger par construction et par les tests |
| [2026-10-15-anti-boucle-spec.md](2026-10-15-anti-boucle-spec.md) | en vigueur | Garde-fou anti-boucle, commun à tous les moteurs (spec — AUCUN code avant le go du propriétaire) |
| [2026-10-15-regle-go-spec.md](2026-10-15-regle-go-spec.md) | en vigueur | Règle de go : un go se lit, il ne se devine pas — spec |
| [2026-10-15-verbe-prod-spec.md](2026-10-15-verbe-prod-spec.md) | en vigueur | Verbe `prod` : mettre une version en production, sauvegarde vérifiée d'abord — spec |
| [2026-10-17-mcp-trous-spec.md](2026-10-17-mcp-trous-spec.md) | en vigueur | Fermer les trous MCP et connecteurs des agents strict (Claude et Codex) — étape 1 |
| [2026-10-18-berger-mcp-spec.md](2026-10-18-berger-mcp-spec.md) | en vigueur | MCP étape 2 : `berger-mcp`, serveurs déclarés par le propriétaire, enfermés dans le mur de l'agent — berger-mcp |
| [2026-10-19-argv-prive-spec.md](2026-10-19-argv-prive-spec.md) | en vigueur | L4 — Transport privé des contenus |
| [2026-10-27-modulaire-decisions.md](2026-10-27-modulaire-decisions.md) | en vigueur | Modulaire : décisions du propriétaire (27/10/2026) |
| [2026-10-27-modulaire-spec.md](2026-10-27-modulaire-spec.md) | en vigueur | Berger modulaire : un cœur mince, un socle à API explicite, des modules écartables (spec) |
| [2026-10-28-modeles-spec.md](2026-10-28-modeles-spec.md) | en vigueur | Choix des moteurs et des modèles : une table, une règle écrite, un choix tracé (spec) |
| [2026-10-28-portes-allegees-spec.md](2026-10-28-portes-allegees-spec.md) | en vigueur | Portes allégées : une demande « documentation seule » passe une porte courte (spec) |
| [2026-10-29-acces-web-envoi-spec.md](2026-10-29-acces-web-envoi-spec.md) | en vigueur | Accès web d'un agent Claude, envoi validé, recherche de traces par le courtier, registre de suivi (spec) |
| [2026-10-29-publication-github-spec.md](2026-10-29-publication-github-spec.md) | en vigueur | Publication automatique vers le dépôt en ligne après une installation réussie (spec) |
| [2026-10-29-sha-fige-decisions.md](2026-10-29-sha-fige-decisions.md) | en vigueur | SHA figé : décisions de suivi (29/10/2026) |
| [2026-10-29-sha-fige-spec.md](2026-10-29-sha-fige-spec.md) | en vigueur | SHA figé : la fusion validée est celle du commit présenté, les portes distantes testent ce commit (spec) |
| [2026-10-29-web-integre-spec.md](2026-10-29-web-integre-spec.md) | en vigueur | Outils web intégrés du moteur refusés aux agents stricts (spec) |
| [2026-10-30-refonte-espace-spec.md](2026-10-30-refonte-espace-spec.md) | en vigueur | Refonte de l'espace Berger : ce qui attend le propriétaire, d'abord et seulement lui (spec) |
| [2026-10-31-codex-sous-agents-spec.md](2026-10-31-codex-sous-agents-spec.md) | en vigueur | Sous-agents de Codex pour les agents stricts — spec courte (31/10/2026) |
| [2026-11-02-ci-tableau-spec.md](2026-11-02-ci-tableau-spec.md) | spec, go attendu | État de la CI du dépôt en ligne dans le tableau de bord (verbe `ci` de l'outil github, source `[panneaux.ci-publique]`) |

## Archive (terminé)

| Document | Statut | Sujet |
| --- | --- | --- |
| [2026-10-12-contexte-par-appel-spec.md](archive/2026-10-12-contexte-par-appel-spec.md) | livré, terminé | Contexte propre à chaque appel du courtier |
| [2026-10-12-domaines-projet-spec.md](archive/2026-10-12-domaines-projet-spec.md) | livré, terminé | Sites permis par projet — `equipes/<projet>/domaines` |
| [2026-10-12-ecrire-agent-spec.md](archive/2026-10-12-ecrire-agent-spec.md) | livré, terminé | Message à sens unique entre agents — `berger-outil ecrire <agent> --fichier .transport/requete.json` (paramètres JSON, dans l’ordre : `"<texte>"`) |
| [2026-10-12-sql-lecture-spec.md](archive/2026-10-12-sql-lecture-spec.md) | livré, terminé | Spec — type d'outil du courtier « sql_lecture » (lecture SQL Server, requêtes fixées) |
| [2026-10-12-suivi-delegations-spec.md](archive/2026-10-12-suivi-delegations-spec.md) | livré, terminé | Suivi des délégations — les promesses faites en délégation ne se perdent plus |
| [2026-10-13-chef-copie-spec.md](archive/2026-10-13-chef-copie-spec.md) | livré, terminé | Branche de finition du chef : importée de SA copie de travail |
| [2026-10-13-chef-finition-spec.md](archive/2026-10-13-chef-finition-spec.md) | livré, terminé | Branche de finition du chef de projet, et en-tête de journal avec un titre |
| [2026-10-13-finition-soldee-spec.md](archive/2026-10-13-finition-soldee-spec.md) | livré, terminé | Finition soldée et relance après application — spec courte |
| [2026-10-13-moins-validations-spec.md](archive/2026-10-13-moins-validations-spec.md) | livré, terminé | Moins de demandes de validation, sans rien affaiblir de ce qui protège d'un vrai dégât |
| [2026-10-14-besoin-berger-spec.md](archive/2026-10-14-besoin-berger-spec.md) | livré, terminé | Besoin Berger et annonce d'un changement d'outil — spec |
| [2026-10-14-skill-produit-spec.md](archive/2026-10-14-skill-produit-spec.md) | livré, terminé | La méthode du produit prime sur un homonyme du catalogue |
| [2026-10-14-tmp-par-agent-spec.md](archive/2026-10-14-tmp-par-agent-spec.md) | livré, terminé | Un dossier temporaire par agent : plus de temporaire commun entre agents stricts |
| [2026-10-14-validation-a-part-spec.md](archive/2026-10-14-validation-a-part-spec.md) | livré, terminé | Une validation longue s'exécute à part : le courtier continue de servir les autres agents |
| [2026-10-15-espace-auto-spec.md](archive/2026-10-15-espace-auto-spec.md) | livré, terminé | Espace auto : le planificateur met chaque espace ouvert en conformité (2026-10-15, sujet 2/3) |
| [2026-10-15-installer-master-spec.md](archive/2026-10-15-installer-master-spec.md) | livré, terminé | Installer le Master, pas à pas (spec courte) |
| [2026-10-15-modele-soul-spec.md](archive/2026-10-15-modele-soul-spec.md) | livré, terminé | Modèle de SOUL à la création (2026-10-15) |
| [2026-10-15-regles-espace-spec.md](archive/2026-10-15-regles-espace-spec.md) | livré, terminé | Règles d'espace : l'espace voulu d'un agent (2026-10-15, sujet 1/3) |
| [2026-10-16-alignement-spec.md](archive/2026-10-16-alignement-spec.md) | livré, terminé | Alignement après une mise en production — spec (AUCUN code avant le go inscrit) |
| [2026-10-16-courtier-textes-spec.md](archive/2026-10-16-courtier-textes-spec.md) | livré, terminé | Courtier : textes refusés au lieu d'être coupés, canal gardien → chef, redémarrage qui aboutit (spec) |
| [2026-10-16-espace-agent-spec.md](archive/2026-10-16-espace-agent-spec.md) | livré, terminé | Disposition sur mesure par agent : agents/<a>/espace.toml (2026-10-16, sujet 3/3) |
| [2026-10-18-codex-trous-spec.md](archive/2026-10-18-codex-trous-spec.md) | livré, terminé | Codex : config de projet coupée chez les agents strict (contrôle (2) du contrat) — codex-trous |
| [2026-10-18-retro-web-spec.md](archive/2026-10-18-retro-web-spec.md) | proposition réalisée par l'accès web (voir 2026-10-29-acces-web-envoi-spec.md) | Rétro : analyse web en direct par REA (voie B) — mini-spec |
| [2026-10-19-argv-prive-l4b-spec.md](archive/2026-10-19-argv-prive-l4b-spec.md) | livré, terminé | L4b — transports restants |
| [2026-10-19-web-encodages-spec.md](archive/2026-10-19-web-encodages-spec.md) | livré, terminé | Masquage des encodages de session et environnement web MCP |
| [2026-10-19-web-session-security-fixes.md](archive/2026-10-19-web-session-security-fixes.md) | livré, terminé | Décisions de sécurité — session prêtée et relais |
| [2026-10-20-codex-ouverture-spec.md](archive/2026-10-20-codex-ouverture-spec.md) | livré, terminé | Ouverture restreinte des développeurs Codex |
| [2026-10-20-herdr-stdin.md](archive/2026-10-20-herdr-stdin.md) | livré, terminé | Messages Herdr sans texte dans les arguments |
| [2026-10-21-vitrine-v1-spec.md](archive/2026-10-21-vitrine-v1-spec.md) | livré, terminé | Vitrine V1 — extraction du manuel |
| [2026-10-21-vitrine-v2-spec.md](archive/2026-10-21-vitrine-v2-spec.md) | livré, terminé | Vitrine V2 — contribution et exécution sans installation personnelle |
| [2026-10-21-vitrine-v3-spec.md](archive/2026-10-21-vitrine-v3-spec.md) | livré, terminé | Vitrine V3 — entrée bilingue du dépôt |
| [2026-10-22-coherences-vps-spec.md](archive/2026-10-22-coherences-vps-spec.md) | livré, terminé | Cohérences VPS — spécification courte |
| [2026-10-22-sans-marques-spec.md](archive/2026-10-22-sans-marques-spec.md) | livré, terminé | Berger présenté seul |
| [2026-10-23-accueil-public-spec.md](archive/2026-10-23-accueil-public-spec.md) | livré, terminé | Spec — accueil public |
| [2026-10-23-exception-url-spec.md](archive/2026-10-23-exception-url-spec.md) | livré, terminé | Spec — exception d'URL du dépôt public dans verifier-depot |
| [2026-10-23-vues-herdr-spec.md](archive/2026-10-23-vues-herdr-spec.md) | livré, terminé | Vues Herdr avant captures |
| [2026-10-24-logo-spec.md](archive/2026-10-24-logo-spec.md) | livré, terminé | Logo Berger : spécification courte |
| [2026-10-24-neutre-spec.md](archive/2026-10-24-neutre-spec.md) | livré, terminé | Noms de logiciels métier neutralisés : spécification courte |
| [2026-10-26-fusion-vm-conflits.md](archive/2026-10-26-fusion-vm-conflits.md) | livré, terminé | Fusion de la ligne de l'installation avec la ligne de développement : les conflits et leur résolution |
| [2026-10-26-fusion-vm-spec.md](archive/2026-10-26-fusion-vm-spec.md) | livré, terminé | Fusion de la ligne de l'installation avec la ligne de développement (spec) |
| [2026-10-29-portes-serialisees-spec.md](archive/2026-10-29-portes-serialisees-spec.md) | livré, terminé | Portes tests sérialisées : une seule porte `tests` à la fois sur la machine (spec) |
