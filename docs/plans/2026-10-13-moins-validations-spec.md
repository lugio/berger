# Moins de demandes de validation, sans rien affaiblir de ce qui protège d'un vrai dégât

Spec, 13/10/2026 (mission de master, proposition validée par le propriétaire le 13/10 au soir). Constat du 13/10 :
41 validations en un jour — fusion berger 11, relancer 9, installer 8, agent-appliquer 7, fusion d'un autre projet 3,
etiqueter 3. Un garde-fou ne sert que contre un vrai dégât : secret, écriture dans le logiciel métier, production,
pare-feu. Exigence : zéro divergence, zéro bricolage, zéro régression.

**Une seule source.** Ce qui demande validation vit dans le code et la config versionnés : les verbes `actions` / `lecture`
de `config.exemple.toml` (outils à commandes fixées) et les outils du courtier (`courtier/outils/`). Le courtier ne connaît
aucun verbe par son nom : un outil peut déclarer qu'une écriture précise se passe de validation
(`sans_validation(verbe, args)`), un projet d'équipe peut déclarer l'action qui suit sa fusion (`installer_outil`).

## 1. `relancer` un agent : plus de validation, condition « au repos » AJOUTÉE

**Constat.** `berger relancer <agent>` n'avait AUCUNE condition : il coupait l'agent (ctrl+c) même en plein travail. Seule
la validation du propriétaire protégeait. Retirer la validation sans ajouter la condition aurait été une régression.

**Comportement.** `berger relancer` refuse un agent qui n'est pas au repos — même source d'état que le reste de Berger
(`statut_herdr`, celui de `berger etat` et des relances de la supervision : `idle` « au repos » ou `done` « a fini »).
Refus clair : « <agent> travaille : rien relancé ». `--force` : réservé au propriétaire en ligne de commande (refusé si
`BERGER_AGENT` est posé, inaccessible par le courtier : `{arg}` refuse un tiret initial), tracé au journal de l'agent.
Chaque relance est notée au journal de l'agent ; par le courtier, elle reste tracée dans `courtier/appels.log`.
Dans `config.exemple.toml`, `relancer` passe de `[outils.berger-admin.actions]` à `[outils.berger-admin.lecture]`.

## 2. `etiqueter` : sans validation sur le commit d'une fusion validée

**Comportement.** `<projet>-chef etiqueter <x.y.z>` s'exécute sans validation SI : (a) les contrôles habituels passent
(SemVer, plus grande que la dernière, absente, entrée non vide du `CHANGELOG.md` de main) ; (b) le commit étiqueté (tête
de main sur la forge) est celui d'une fusion inscrite et faite (`commit_fusion` de la demande « fusionnée », écrit par
`fusionner` — qui ne s'exécute qu'après validation ; pour une ancienne demande en avance rapide : son `commit`) ;
(c) la version est la plus récente du `CHANGELOG.md` de main. L'étiquette est posée sur CE commit contrôlé (pas sur une
tête relue plus tard). Sinon : validation comme aujourd'hui. Réponse et journaux disent « sans validation : … ».

## 3. Fusion de Berger + installation : une seule validation

**Repéré par la config.** `[equipes.<p>] installer_outil = "<outil> <verbe>"` : ce projet EST l'installation ; après sa
fusion validée, l'action `<verbe>` de `<outil>` (la commande `installer` de `berger-admin`, la même que l'action manuelle)
part seule. Refusé au chargement du courtier si ce n'est pas un verbe d'ÉCRITURE d'un outil déclaré, ou si
`fusion_par` n'est pas `"proprietaire"` (un agent ne valide pas une modification de ses propres murs). Aucun nom de projet
dans le code.

**`berger installer <forge> [branche]`** (une commande, testée, appelée par l'action) — les vérifications d'avant :
1. `git pull --ff-only <forge> <branche>` (avance rapide seule) ; 2. HEAD = `<branche>` de la forge (`ls-remote`) ;
3. `bin/berger verifier-depot` (nouveau code) ; 4. `bin/berger regenerer` ; 5. redémarrage DÉTACHÉ du courtier
(`systemd-run … courtier redemarrer --controle <avant>`), qui attend que le résultat (`<n>.fait.json`) soit inscrit
(inchangé), redémarre, puis contrôle que le service reste actif.

**Retour arrière automatique.** Une vérification en échec (2, 3, 4, lancement de 5, ou courtier inactif après redémarrage)
→ `git reset --keep <avant>` (le commit d'avant), preuve HEAD = avant, `regenerer`, et redémarrage du courtier s'il avait
été redémarré. Tracé : `courtier/installations.log` (une ligne par installation : avant, après, état, détail), journal du
résultat de la validation, notification urgente au propriétaire en cas d'échec. Une avance rapide refusée ne change rien.

**Résultat.** Fusion faite et installation faite : « validé et exécuté ». Installation en échec : « validé mais ÉCHEC »,
le résultat dit « fusion faite » et le retour arrière ; la demande porte `installation`.

## 4. Inchangés (validation gardée)

`agent-appliquer`, `installer` lancée à la main, `publier`, toute fusion d'un autre projet, et tout ce qui touche secrets,
logiciel métier, production, pare-feu.

## 5. Résumé d'une fusion en avance rapide (ajout de master)

**Constat.** En avance rapide, seule `pret` est rejouée ; le résumé affichait « verify : non mesuré ; tests : non mesuré »
alors qu'elles avaient été jouées à la demande. **Comportement.** Une porte non rejouée reprend le résultat inscrit dans la
demande, avec sa date (« verify : vert, à la demande du 13/10 19:34 ») ; « non mesuré » seulement si elle n'a jamais été jouée.

## Tests

`tests/moins-validations.py` : relancer (au repos → relancé ; travaille → refusé par le courtier et en ligne de
commande ; `--force` du propriétaire → relancé et tracé ; `--force` refusé à un agent) ; config.exemple (relancer en
lecture, installer/agent-appliquer/publier en actions, `installer_outil`) ; etiqueter (fusion validée → sans validation ;
version qui n'est pas la dernière, commit qui n'est pas une fusion → validation) ; fusion → installation (une fois, après
le push ; échec → « validé mais ÉCHEC », fusion faite) ; refus au chargement ; `berger installer` (succès, verifier-depot
rouge → retour arrière prouvé, avance rapide refusée → rien changé, courtier inactif → retour arrière + redémarrage) ;
résumé de fusion en avance rapide.
