# Berger

<img src="docs/assets/berger.png" alt="Berger" width="96" height="96">

**Vos agents. Vos méthodes. Votre choix de moteur.**

<img src="docs/assets/badges/mit.svg" alt="Licence MIT" width="66" height="28">
<img src="docs/assets/badges/python.svg" alt="Python 3.11 ou plus récent" width="142" height="28">
<img src="docs/assets/badges/linux.svg" alt="Linux" width="80" height="28">
<img src="docs/assets/badges/herdr.svg" alt="Herdr" width="80" height="28">

[English](README.md) · [Manuel de référence](docs/manuel.md)

Berger donne aux agents une identité de travail, une mémoire, des checklists
et des tâches planifiées, dans des fichiers texte qui vous appartiennent.
Il lance les CLI officielles **Codex** et **Claude Code**, sur leurs abonnements.
Herdr fournit les espaces de travail, les panneaux et les vues de suivi.

Vous gardez vos méthodes lorsque vous changez de moteur.
Les moteurs pris en charge sont Codex et Claude Code ; le projet ne fournit pas
d’adaptateur pour n’importe quel fournisseur.
Berger n’appelle pas directement une API de fournisseur de modèle.

## Démarrage rapide

Partez d’une installation neuve dans `~/berger`, sans écraser de données ou de
liens existants. Berger n’inclut pas d’installeur de dépendances. Le
[manuel](docs/manuel.md#installation-résumé) détaille les étapes système.

### Prérequis

- Linux, Git, Bash, Python **3.11+** (`tomllib`), [Herdr](https://herdr.dev) **0.9+**.
- Codex **0.160+** et/ou Claude Code installés et connectés à votre abonnement.
- **bubblewrap**, **GnuPG** et **systemd utilisateur** fonctionnels.
- Herdr disponible dans `~/.local/bin/herdr`, comme le supposent les unités fournies.

Vérifiez le bac : `bwrap --ro-bind / / --dev /dev --unshare-net true`.
Sur Ubuntu 24.04+, un administrateur peut devoir installer le profil AppArmor
bubblewrap du [manuel](docs/manuel.md#installation-résumé). Un agent strict
refuse de démarrer sans son bac à sable.

### Préparer la copie du dépôt

Clonez le dépôt, puis placez-vous à sa racine :

```bash
git clone https://github.com/lugio/berger.git ~/berger
cd ~/berger
cp config.exemple.toml config.toml
cp commun/modeles/USER.md commun/USER.md
mkdir -p ~/.local/bin ~/.config/systemd/user
ln -s "$PWD/bin/berger" ~/.local/bin/berger
ln -s "$PWD/courtier/berger-outil" ~/.local/bin/berger-outil
export PATH="$HOME/.local/bin:$PATH"
```

Avant de continuer, **adaptez `config.toml`** : renseignez `proprietaire`, puis
vérifiez `coffre`, `masques`, `masques_si_presents` et `masque_fichier` pour votre
machine. L’exemple copié permet un premier agent sans outil extérieur ; les
déclarations d’outils sont commentées et aucun garde personnalisé n’est fourni.
Gardez le coffre protégé et la configuration locale hors de Git.
Complétez `commun/USER.md` pour décrire pour qui travaillent les agents.

### Créer un agent et démarrer les services

```bash
berger nouveau assistant "Assistant"
```

Résultat attendu : `agent créé :` suivi du chemin absolu de `agents/assistant`.
Précisez le rôle, les capacités et les limites dans `agents/assistant/SOUL.md`.
Réglez `heures = aucune` dans `agents/assistant/agent.conf` pour un agent à la demande.
Le moteur par défaut est Codex. Pour Claude Code, réglez `moteur` et `panneaux`
sur `claude` et utilisez sa CLI connectée au lieu de la connexion Codex ci-dessous.
Régénérez ensuite les réglages ; la connexion Codex est interactive :

```bash
berger regenerer
CODEX_HOME="$HOME/berger/.codex" codex login
cp systemd/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now berger.timer berger-courtier.service berger-herdr.service
berger espace assistant
berger espace ensemble
berger etat
```

Résultat attendu : un espace Assistant avec sa conversation et un espace Berger
avec l’état de l’agent. Demandez-lui son rôle : sa réponse doit refléter `SOUL.md`.
Vérifiez les demandes d’approbation des hooks du moteur. Le premier lancement
d’une version joue son contrat d’admission (jusqu’à 20 minutes) ; un refus peut
faire basculer vers un autre moteur admis, ou bloquer si aucun ne l’est. Voir
[quels tests lancer](docs/manuel.md#tests--quand-lancer-quoi) et la
[sécurité](docs/manuel.md#sécurité-identique-pour-chaque-agent-et-chaque-moteur).
Configuration, connexion, approbation et admission sont des étapes incompressibles.

## Fonctionnalités

| Capacité | Rôle | Guide |
| --- | --- | --- |
| Méthodes portables | Identité, consignes et fichiers de travail restent sur disque | [Principes](docs/manuel.md#principes) |
| Choix du moteur | Codex ou Claude Code par leurs CLI officielles | [Commandes](docs/manuel.md#commandes) |
| Mémoire et suivi | Journaux, tâches, checklists et propositions de mémoire longue | [Vues Herdr](docs/manuel.md#dans-herdr) |
| Disposition par agent | `espace.toml`, propositions validées et application automatique sans relancer la conversation | [Disposition Herdr](docs/manuel.md#dans-herdr) |
| Travail planifié | Réveils et tâches pilotés par la minuterie utilisateur | [Exploitation](docs/manuel.md#exploitation) |
| Outils par le courtier | Verbes déclarés et validations humaines configurées | [Courtier](docs/manuel.md#courtier) |
| Missions et équipes | Travail borné, relecture avant fusion | [Équipes de développement](docs/manuel.md#équipe-de-développement-gros-projets) |
| Livrables partagés | Bibliothèques d’agents et de projets, accès délimités | [Bibliothèque](docs/manuel.md#bibliothèque--dossiers-de-travail-des-agents) |
| Vues web optionnelles | Consultation en lecture seule des mêmes données de suivi | [Interface web](docs/manuel.md#interface-web-lecture-seule) |
| Sauvegardes configurées | Archives chiffrées des données d’installation | [Sauvegardes](docs/manuel.md#sauvegarde-des-données) |

## Vues Herdr

L'interface est en français ; les données ci-dessous sont fictives. Pour les
reproduire : [démonstration des vues](docs/demo-vues.md).

![Accueil](docs/captures/accueil.png)
*Accueil : ce qui attend une décision.*

![Tableau en colonnes](docs/captures/colonnes.png)
*Tableau en colonnes : agents, validations, fusions.*

![Courtier de secrets](docs/captures/courtier.png)
*Courtier de secrets : droits, écritures à valider, appels.*

## Sécurité et limites

L’hôte, le courtier et les adaptateurs d’outils configurés sont de confiance.
Les agents stricts utilisent des permissions et réglages de bac à sable générés.
Un agent configuré avec `mur = ouvert` ne doit pas être considéré isolé.

Chaque version d’un moteur doit réussir son contrat d’admission avant usage strict.
Une suite sans modèle réussie **ne vaut pas** admission d’un moteur.
Les tests prouvent un comportement mesuré, sans garantie universelle de sécurité.
Les hooks, temporaires, relais MCP et restrictions de l’hôte ont des limites documentées.

Les identifiants vont dans le coffre configuré, hors des fichiers lisibles par l’agent.
Le filtrage du courtier et les validations déclarées contribuent au contrôle d’accès ;
relisez les permissions et l’implémentation des outils de votre installation.
Les agents peuvent écrire dans leurs zones de travail autorisées.
La mémoire longue fait l’objet de propositions à relire, sans consolidation silencieuse.

Consultez [SECURITY.md](SECURITY.md) pour signaler une faille en privé.
Ne joignez ni vrais identifiants ni données personnelles d’agent aux issues ou PR.

## Fonctionnement

Herdr héberge les espaces ; Berger prépare l’agent et son profil moteur.
Les demandes d’outils passent par le courrier fichier vers le courtier de confiance.
Il contrôle le verbe déclaré, attend la validation requise et appelle l’adaptateur
configuré. Les résultats reviennent par le courtier à l’agent demandeur.
Une vue, une commande ou un moteur est un fichier déposé (API du noyau, `bin/noyau/api.py`) ; un module cassé est écarté et nommé par `berger etat`.

<!-- BEGIN BERGER DIAGRAM -->
```text
Fichiers agent -> Berger ----> CLI officielle
                    ^              |
                    |              v
                  Herdr      travail de l’agent
                                   |
                       courrier fichier (berger-outil)
                                   |
                            courtier de confiance
                         (validation si nécessaire)
                                   |
                            outils configurés
```
<!-- END BERGER DIAGRAM -->

Ce schéma est généré par `python3 docs/scripts/schema.py --write`. L’option `--check` détecte une dérive sans modifier les fichiers.
Il présente le chemin central des outils ; le manuel couvre les flux web et MCP optionnels.

## Documentation

| Document | Usage |
| --- | --- |
| [Manuel de référence](docs/manuel.md) | Installation complète, commandes et exploitation |
| [Exemple de configuration](config.exemple.toml) | Réglages d’installation et déclaration des outils |
| [Installation du Master](docs/manuel.md#installer-le-master-pas-à-pas) | Configurer l’agent coordinateur |
| [Contribution](CONTRIBUTING.md) | Spec, tests, portes et relecture indépendante |
| [Politique de sécurité](SECURITY.md) | Signalement privé et périmètre |
| [Code de conduite](CODE_OF_CONDUCT.md) | Règles de participation et modération |
| [Journal des changements](CHANGELOG.md) | Historique des versions documentées |
| [Feuille de route](docs/ROADMAP.md) | Travaux prévus et état du chantier modulaire |

Le manuel complet reste en français ; les deux entrées renvoient à cette même référence.

## Retrait

Sauvegardez données d’agents, configuration, bibliothèques et identifiants avant retrait.
Chiffrez toute sauvegarde contenant des secrets.
Terminez ou arrêtez le travail des agents avant d’arrêter les services.
Listez les unités activées avec `systemctl --user list-unit-files 'berger*'`.
Arrêtez les services centraux et le planificateur du démarrage rapide :

```bash
systemctl --user disable --now berger.timer berger-courtier.service berger-herdr.service
```

Désactivez aussi `berger-tests.timer` et `berger-interface.service` s’ils sont activés.
Retirez le lien du plugin local `berger.reprise` selon l’aide de votre version de Herdr
(`herdr plugin --help`) pour qu’un démarrage de Herdr ne reprenne plus les agents Berger.
Retirez seulement les unités utilisateur et liens de commandes ajoutés pour Berger,
puis rechargez les unités avec `systemctl --user daemon-reload`.
Supprimez la copie et les données privées après vérification des sauvegardes.
Le retrait est manuel ; Berger ne fournit pas de commande universelle de désinstallation.

## Contribuer

Lisez [CONTRIBUTING.md](CONTRIBUTING.md) et rédigez une petite spec pour un changement notable.
Un correctif comprend un échec reproduit, sa cause racine et un test de régression.
Jouez `verify`, `tests` et `pret` ; le guide de contribution donne les commandes exactes.
La CI préparée utilise un clone local neuf avec un dossier personnel isolé.
Elle ne remplace pas les contrats d’admission sur moteurs réels.

## Licence

Berger est distribué sous la [licence MIT](LICENSE).
La version documentée actuelle est la [0.2.0](CHANGELOG.md) ; les précédentes y figurent aussi.
Les abonnements moteurs, Herdr et outils externes ont leurs conditions et licences propres.
