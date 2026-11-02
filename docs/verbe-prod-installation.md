# Installer le verbe prod sur le serveur d'un projet — notice à copier-coller

Pour le propriétaire, pas à pas. Chaque étape : les commandes (à copier telles quelles, en remplaçant les `<…>`), ce qui
doit se passer, et comment le vérifier. **Aucune valeur secrète** n'est écrite ici ni ne doit l'être.
Spec : `docs/plans/2026-10-15-verbe-prod-spec.md`. Le script : `bin/serveur/berger-prod` (dans l'installation de Berger).

**Ce que ça donne à la fin** : le chef de projet demande `berger-outil <OUTIL> prod v1.4.0` ; vous validez
(`berger valider <n°>`) ; le serveur sauvegarde la base (chiffrée, vérifiée), installe la version, contrôle qu'elle est
servie, et revient seul en arrière si ça ne va pas. Les développeurs n'ont pas ce droit.

À remplacer partout (notez vos valeurs avant de commencer) :

| Repère | Ce que c'est | Exemple |
|---|---|---|
| `<CT>` | numéro du conteneur du serveur (hyperviseur) | 100 |
| `<NOEUD>` | le nœud de l'hyperviseur où il tourne | noeud1 |
| `<ADRESSE>` | adresse IP du serveur | 192.0.2.10 |
| `<OUTIL>` | nom de l'outil dans Berger | projet-prod |
| `<CHEF>` | l'agent chef de projet | projet-chef |
| `<APPLI>` | dossier de l'appli sur le serveur (copie git) | /srv/appli |
| `<COMPTE-APPLI>` | compte propriétaire de ce dossier | appli |
| `<COMPOSE>` | fichier compose de la production | /srv/appli/docker-compose.yml |
| `<BASE>` | service compose de la base PostgreSQL | db |
| `<SANTE>` | adresse qui répond la version servie (JSON) | http://127.0.0.1:8000/sante |
| `<MIGRATIONS>` | dossier des migrations `.sql`, dans la copie (s'il y en a) | backend/src/migrations |
| `<TABLE>` | table de la base qui garde la liste des migrations passées | schema_migrations |

Pour trouver `<BASE>` et `<SANTE>` sur le serveur : `docker compose -f <COMPOSE> ps` (la colonne SERVICE) et
`curl -s <SANTE>` doit afficher quelque chose comme `{"version": "v1.3.0", …}`. Si l'appli ne donne pas sa version :
arrêtez-vous là, c'est à ajouter d'abord dans l'appli (le contrôle de santé en dépend).
Si la copie appartient à root (`ls -ld <APPLI>`), `<COMPTE-APPLI>` ne sert pas : la ligne `git_utilisateur` est retirée.

## 0. Prérequis du serveur

Dans le serveur (`pct enter <CT>`) :
```bash
python3 --version; git --version; gpg --version | head -1; docker compose version
df -h <APPLI> /var/lib/docker
```
**Il faut** : `python3` **3.11 ou plus** (le script lit ses réglages avec `tomllib`), `git`, `gpg`, `docker compose`
(la version 2, avec un espace). Si l'un manque, le script refuse de lui-même (`aide`, `prod`, `--essai`) en le nommant
(« prérequis absents sur le serveur : gpg… ») : rien n'est fait. Pour l'ajouter (Debian) : `apt install gnupg` — c'est une
modification du serveur, qui passe par votre go comme les autres.
**Disque** : le script refuse si le disque de l'appli, des sauvegardes ou de docker est occupé à **92 % ou plus**
(réglage `disque_seuil`) : une construction d'image sur un disque presque plein casse au milieu.

---

## 1. Sur la VM Berger : la clé ssh du courtier

```bash
ssh-keygen -t ed25519 -N "" -C "berger-courtier-<OUTIL>" -f ~/.ssh/<OUTIL>
chmod 600 ~/.ssh/<OUTIL>
cat ~/.ssh/<OUTIL>.pub
```
**Effet** : une paire de clés, sans phrase de passe (le courtier s'en sert seul). La clé privée reste dans `~/.ssh`, que
les agents ne voient pas. La dernière commande affiche la clé **publique** (une ligne `ssh-ed25519 AAAA… berger-courtier-…`) :
copiez-la, elle sert à l'étape 2.4. Elle n'est pas secrète.
**Vérifier** : `ls -l ~/.ssh/<OUTIL>` montre `-rw-------`.

## 2. Sur le serveur, en root (console de l'hyperviseur, ex. `pct enter <CT>` depuis `<NOEUD>`)

### 2.1 Le compte restreint
```bash
adduser --system --group --shell /bin/sh --home /var/lib/berger-prod berger-prod
passwd -l berger-prod
```
**Effet** : un compte sans mot de passe, qui ne pourra lancer QUE le script (étape 2.4).
**Vérifier** : `id berger-prod` affiche le compte ; `passwd -S berger-prod` affiche `L` (verrouillé).

### 2.2 Le script
Le script vient de l'installation de Berger (après la fusion de ce sujet). Depuis la VM Berger, vers le nœud de l'hyperviseur :
```bash
sha256sum ~/berger/bin/serveur/berger-prod
scp ~/berger/bin/serveur/berger-prod root@<NOEUD>:/root/berger-prod
```
Puis sur le nœud `<NOEUD>`, en root :
```bash
pct push <CT> /root/berger-prod /usr/local/sbin/berger-prod --perms 0755 --user 0 --group 0
rm /root/berger-prod
```
Puis dans le serveur (`pct enter <CT>`) :
```bash
sha256sum /usr/local/sbin/berger-prod
/usr/local/sbin/berger-prod aide
```
**Effet** : le script est en place, à root, lisible et exécutable par tous, modifiable par root seul.
**Vérifier** : les deux `sha256sum` (VM et serveur) donnent la même empreinte ; `aide` affiche l'usage (`prod [--essai] vX.Y.Z …`)
et finit par `Prérequis : présents.` Sinon, il répond `"statut": "refus"` et le `motif` dit ce qui manque (étape 0).

### 2.3 Le droit de lancer le script en root, et rien d'autre
```bash
cat > /etc/sudoers.d/berger-prod <<'FIN'
berger-prod ALL=(root) NOPASSWD: /usr/local/sbin/berger-prod --config /etc/berger-prod.toml --ssh *
FIN
chmod 440 /etc/sudoers.d/berger-prod
visudo -cf /etc/sudoers.d/berger-prod
```
**Effet** : le compte `berger-prod` peut lancer ce script, avec ce fichier de réglages, et aucune autre commande.
**Vérifier** : `visudo` répond `parsed OK`. (S'il signale une erreur : `rm /etc/sudoers.d/berger-prod` et recommencez.)

### 2.4 La clé du courtier, limitée au script
Remplacez `<CLÉ PUBLIQUE DE L'ÉTAPE 1>` par la ligne copiée à l'étape 1 (tout le reste tel quel, guillemets compris) :
```bash
install -d -m 700 -o berger-prod -g berger-prod /var/lib/berger-prod/.ssh
cat > /var/lib/berger-prod/.ssh/authorized_keys <<'FIN'
restrict,command="sudo -n /usr/local/sbin/berger-prod --config /etc/berger-prod.toml --ssh \"$SSH_ORIGINAL_COMMAND\"" <CLÉ PUBLIQUE DE L'ÉTAPE 1>
FIN
chown berger-prod:berger-prod /var/lib/berger-prod/.ssh/authorized_keys
chmod 600 /var/lib/berger-prod/.ssh/authorized_keys
cat /var/lib/berger-prod/.ssh/authorized_keys
```
**Effet** : quoi que demande la clé, le serveur lance le script (`command=`) ; `restrict` interdit le reste (terminal,
tunnels, redirections). Le script ne connaît que `prod`, `prod --essai`, `compte-rendu` et `aide`, et refuse tout caractère
spécial.
**Vérifier** : la ligne affichée commence par `restrict,command="sudo -n /usr/local/sbin/berger-prod` et finit par
`berger-courtier-<OUTIL>`.

### 2.5 Le fichier de réglages
```bash
cat > /etc/berger-prod.toml <<'FIN'
depot = "<APPLI>"
git_utilisateur = "<COMPTE-APPLI>"
compose = "<COMPOSE>"
service_base = "<BASE>"
sauvegardes = "/var/backups/berger-prod"
gpg_destinataire = "sauvegardes-prod"
gpg_home = "/var/lib/berger-prod/gnupg"
sante_url = "<SANTE>"
sante_delai = 180
migrations_dossier = "<MIGRATIONS>"
migrations_table = "<TABLE>"
apres = ["docker image prune -f", "docker builder prune -f"]
FIN
chmod 600 /etc/berger-prod.toml
```
(Copie à root : retirez la ligne `git_utilisateur`. Pas de migrations : retirez les lignes `migrations_…`.)
Le modèle commenté de tous les réglages est `bin/serveur/berger-prod.exemple.toml` : colonne de la table
(`migrations_colonne`, défaut `name`), colonne « qui l'a jouée » si la table en a une (`migrations_colonne_par`, ex.
`applied_by` : elle reçoit `berger-prod vX.Y.Z`), quels fichiers comptent (`migrations_motif`), commandes de contrôle du
projet à jouer avant (`avant`), seuil de disque (`disque_seuil`), contrôles de santé supplémentaires qui comptent pour
le retour arrière (`controles_sante`).
**Un service qui réutilise l'image d'un autre** (pas d'image à lui) : le démarrage ordinaire peut le laisser sur
l'ancienne image. Le modèle montre le réglage `demarrer` qui le recrée de force, et deux `controles_sante` : il tourne
bien sur l'image qui vient d'être construite, et sa santé docker est au vert. Sinon : retour arrière automatique.
**Effet** : le script sait où est l'appli, où sauvegarder, comment contrôler la santé, quelles migrations jouer. Aucun mot
de passe : la base est sauvegardée et migrée de l'intérieur de son conteneur (`psql` y est ; l'image de l'appli n'en a pas
besoin). Chaque migration en attente est jouée seule, dans une transaction qui l'inscrit aussi dans `<TABLE>` : tout ou rien.
Un fichier qui ouvre lui-même sa transaction (une ligne `BEGIN;`) est joué tel quel, puis inscrit juste après.
Un nom de fichier avec une apostrophe ou un espace est refusé (rien n'est fait).
`apres` fait le ménage des images et du cache de construction après un succès — **jamais `docker system prune`** (il
efface aussi ce qui sert ailleurs ; le script le refuse).
**Vérifier** : `cat /etc/berger-prod.toml` ; `ls -l /etc/berger-prod.toml` montre `-rw-------  root root`.
**Migrations** : la table doit déjà lister celles passées à la main. Contrôle :
`docker compose -f <COMPOSE> exec -T <BASE> sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM <TABLE>"'`
répond un nombre proche du nombre de fichiers (`ls <APPLI>/<MIGRATIONS>/*.sql | wc -l`). Une table vide = le script refuse
(sinon il rejouerait tout).

## 3. La clé gpg qui chiffre les sauvegardes : la publique seule sur le serveur

Le serveur **chiffre** les sauvegardes et contrôle le fichier sans jamais pouvoir le relire : il n'a que la clé
**publique**. La clé **privée** reste chez vous ; elle ne sert que pour restaurer.

### 3.1 Créer la paire, chez vous (pas sur le serveur)
Dans votre terminal de la VM Berger (votre `~/.gnupg` est masqué aux agents) — ou sur votre poste avec un outil GPG :
```bash
gpg --quick-gen-key sauvegardes-prod default default never
gpg --armor --export sauvegardes-prod
```
**Effet** : gpg vous demande une **phrase de passe** : choisissez-la et rangez-la dans votre coffre (jamais dans un fichier
ni un message). La seconde commande affiche la clé **publique**, un bloc qui commence par
`-----BEGIN PGP PUBLIC KEY BLOCK-----` : copiez tout le bloc (il n'est pas secret).
**Garder la clé privée** : `gpg --armor --export-secret-keys sauvegardes-prod > ~/sauvegardes-prod-privee.asc`, rangez ce
fichier dans votre coffre (il reste protégé par la phrase de passe), puis `rm ~/sauvegardes-prod-privee.asc`.
Sans elle, aucune sauvegarde ne peut être relue.

### 3.2 Poser la clé publique sur le serveur (en root)
```bash
install -d -m 700 /var/lib/berger-prod/gnupg
cat > /root/sauvegardes-prod.pub.asc <<'FIN'
<COLLEZ ICI LE BLOC DE LA CLÉ PUBLIQUE, de -----BEGIN à -----END compris>
FIN
gpg --homedir /var/lib/berger-prod/gnupg --import /root/sauvegardes-prod.pub.asc
gpg --homedir /var/lib/berger-prod/gnupg --list-keys sauvegardes-prod
gpg --homedir /var/lib/berger-prod/gnupg --list-secret-keys
rm /root/sauvegardes-prod.pub.asc
```
**Effet** : le serveur connaît la clé publique, et elle seule.
**Vérifier** : `--list-keys` affiche une clé `uid … sauvegardes-prod` ; `--list-secret-keys` n'affiche **rien**.

## 4. Sur la VM Berger : l'outil dans config.toml, donné au chef de projet

### 4.0 Le réseau : la VM Berger doit joindre le serveur sur le port 22
Depuis la VM Berger :
```bash
timeout 5 bash -c '</dev/tcp/<ADRESSE>/22' && echo "port 22 joignable" || echo "port 22 FERMÉ"
```
**Si « FERMÉ »** : il faut une règle de pare-feu (le pare-feu du réseau, ou celui de l'hyperviseur pour le conteneur) qui autorise **la VM
Berger seule** vers **`<ADRESSE>`, TCP 22 seul**. C'est une modification du pare-feu : **votre go**, avec la sauvegarde
de la configuration faite et vérifiée avant, et la règle à retirer comme retour arrière. Rien d'autre à ouvrir : le
serveur n'a pas besoin de joindre la VM.
**Vérifier** : la commande répond `port 22 joignable`.

### 4.1 Reconnaître le serveur (une fois)
Sur la VM Berger :
```bash
ssh-keyscan -t ed25519 <ADRESSE> 2>/dev/null | tee -a ~/.ssh/known_hosts | ssh-keygen -lf -
```
Dans le serveur : `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.
**Vérifier** : les deux empreintes (`SHA256:…`) sont **identiques**. Sinon : arrêtez, retirez la ligne ajoutée à la fin de
`~/.ssh/known_hosts`, et cherchez pourquoi.

### 4.2 La section de config.toml
Sauvegarde d'abord, puis ajout à la fin :
```bash
cp ~/berger/config.toml ~/berger/config.toml.avant-<OUTIL>-$(date +%Y%m%d)
cat >> ~/berger/config.toml <<'FIN'

[outils.<OUTIL>]
type = "ssh"
hote = "<ADRESSE>"
utilisateur = "berger-prod"
cle_fichier = "~/.ssh/<OUTIL>"
[outils.<OUTIL>.lecture]
compte-rendu = "compte-rendu"
[outils.<OUTIL>.actions]
essai = "prod --essai {arg}"
prod = "prod {arg}"
FIN
```
**Effet** : un outil `<OUTIL>` à trois verbes. `compte-rendu` se lit sans validation ; `essai` et `prod` attendent **à chaque
fois** votre `berger valider <n°>`.
**Vérifier** : `tail -n 12 ~/berger/config.toml` ; et la copie existe : `ls -l ~/berger/config.toml.avant-<OUTIL>-*`.

### 4.3 Le droit, au chef de projet seul
Le plus simple : l'outil s'ajoute dans l'`agent.conf` du chef de projet (aucun changement de Berger) ; les développeurs ne
l'ont jamais (leurs outils sont calculés à leur ouverture).
```bash
cp ~/berger/agents/<CHEF>/agent.conf ~/berger/agents/<CHEF>/agent.conf.avant-<OUTIL>-$(date +%Y%m%d)
grep -q '^outils *=' ~/berger/agents/<CHEF>/agent.conf \
  && sed -i '/^outils *=/ s/$/, <OUTIL>/' ~/berger/agents/<CHEF>/agent.conf \
  || echo 'outils = <OUTIL>' >> ~/berger/agents/<CHEF>/agent.conf
grep '^outils' ~/berger/agents/<CHEF>/agent.conf
systemctl --user restart berger-courtier.service
```
**Effet** : le chef de projet a l'outil ; le courtier relit `config.toml`.
**Vérifier** : la ligne `outils = …` se termine par `<OUTIL>` ; `systemctl --user is-active berger-courtier.service` répond
`active`.

## 5. Essai à blanc

Une étiquette déjà en production, par exemple la version servie aujourd'hui (`curl -s <SANTE>` sur le serveur) : `vX.Y.Z`.
Depuis la VM Berger :
```bash
ssh -i ~/.ssh/<OUTIL> berger-prod@<ADRESSE> "prod --essai vX.Y.Z"
```
**Effet** : toutes les vérifications (étiquette de main, copie propre), une **vraie sauvegarde chiffrée et vérifiée**, la
version servie notée — puis arrêt : **rien d'autre ne change**.
**Vérifier** : la réponse JSON dit `"statut": "essai"` et donne `"sauvegarde": "/var/backups/berger-prod/base-…dump.gpg"`.
L'essai à blanc montre `"migrations_en_attente"` : la liste des migrations que la vraie mise en production jouerait, dans
l'ordre. Comparez-la à la liste attendue, donnée par le chef de projet dans sa demande. Si elle ne correspond pas,
arrêtez-vous : la table ne connaît pas des migrations déjà passées, ou en connaît une de trop.
Dans le serveur : `ls -l /var/backups/berger-prod/` (le fichier existe, `-rw-------`, pas vide) et
`tail -n 3 /var/backups/berger-prod/berger-prod.log`.
Puis par le chef de projet (dans son espace) : `berger-outil <OUTIL> essai vX.Y.Z` → une validation apparaît chez vous →
`berger valider <n°>`. Un développeur qui essaie : refusé (« pas le droit »).

Si l'essai dit `refus` : le `motif` dit pourquoi (étiquette absente, copie modifiée, sauvegarde illisible…). Rien n'a changé.

**Attention, durée** : le courtier coupe une commande ssh après 3 minutes. Une vraie mise en production peut durer plus
(construction). Le script continue quand même jusqu'au bout (retour arrière compris) ; le résultat se relit ensuite par
`berger-outil <OUTIL> compte-rendu`.

## 6. Retour arrière complet (tout retirer)

Les sauvegardes déjà faites ne sont **pas** supprimées (c'est votre décision, à part : `/var/backups/berger-prod/`).

Sur la VM Berger :
```bash
cp ~/berger/config.toml.avant-<OUTIL>-AAAAMMJJ ~/berger/config.toml
cp ~/berger/agents/<CHEF>/agent.conf.avant-<OUTIL>-AAAAMMJJ ~/berger/agents/<CHEF>/agent.conf
systemctl --user restart berger-courtier.service
ssh-keygen -R <ADRESSE>
rm ~/.ssh/<OUTIL> ~/.ssh/<OUTIL>.pub
```
(remplacez `AAAAMMJJ` par la date de la copie : `ls ~/berger/config.toml.avant-*`). **Effet** : l'outil n'existe plus, le chef
ne l'a plus, la clé est détruite. **Vérifier** : `grep -c '<OUTIL>' ~/berger/config.toml` répond `0`.

Dans le serveur, en root :
```bash
rm /var/lib/berger-prod/.ssh/authorized_keys /etc/sudoers.d/berger-prod /usr/local/sbin/berger-prod /etc/berger-prod.toml
```
**Effet** : plus aucune clé n'entre, plus aucun droit root, plus de script. **Vérifier** : depuis la VM,
`ssh -i ~/.ssh/<OUTIL> berger-prod@<ADRESSE> aide` échoue (`Permission denied`) — ou la clé est déjà détruite.
Le compte et la clé gpg restent (inoffensifs, et la clé gpg est nécessaire pour relire les sauvegardes) ; pour les retirer
aussi, plus tard et si vous n'avez plus besoin des sauvegardes : `deluser berger-prod` et `rm -r /var/lib/berger-prod`.

**Annuler une mise en production** (pas l'installation) : le compte rendu donne `retour_arriere` (la commande qui remet le
code d'avant) et, si des migrations ont été jouées, `restauration` (la commande qui remet la base de la sauvegarde — elle
**efface** les données écrites depuis : c'est vous qui la lancez, en connaissance de cause). La restauration demande votre
clé privée, le temps de la commande, dans le gpg de root du serveur :
```bash
cat > /root/cle.asc <<'FIN'
<COLLEZ ICI LE CONTENU DE sauvegardes-prod-privee.asc, tiré de votre coffre>
FIN
gpg --import /root/cle.asc && rm /root/cle.asc
<la commande « restauration » du compte rendu>          # gpg demande la phrase de passe
gpg --delete-secret-keys sauvegardes-prod
gpg --list-secret-keys
```
**Vérifier** : la dernière commande n'affiche plus rien (la clé privée a quitté le serveur).

## 7. Avant la première vraie mise en production

### 7.1 Un seul chemin de déploiement
Une fois le verbe **prouvé** (l'essai à blanc, puis une première vraie mise en production réussie et relue par
`compte-rendu`), l'ancien script de déploiement du projet est **retiré** du dépôt du projet (par une demande de fusion
du projet, comme tout changement). Deux chemins de déploiement, c'est deux façons de se tromper : la production ne
change plus que par `berger-outil <OUTIL> prod vX.Y.Z`, validé par vous.

### 7.2 La porte avant la production — à vous de trancher
Décision attendue : faut-il rejouer une porte du projet juste avant de valider une mise en production ?
- **Option A — une porte rejouée avant la validation de prod.** Le chef de projet rejoue `pret` (ou la porte « gate » du
  projet) sur le commit de l'étiquette, et joint le résultat à sa demande `prod`. Plus sûr si l'environnement a pu
  bouger depuis la fusion (dépendances, base de recette) ; une étape de plus, quelques minutes à chaque fois.
- **Option B — la porte de la fusion suffit.** L'étiquette `vX.Y.Z` est posée sur le commit d'une fusion que vous avez
  validée, après que les portes y ont été jouées : c'est déjà le même code. Plus simple ; on s'appuie sur l'essai à blanc
  et le contrôle de santé pour le reste.
Recommandation : **B** tant que l'étiquette est toujours posée sur le commit de la fusion validée (c'est la règle des
versions de Berger) ; **A** si une étiquette peut un jour être posée ailleurs.

### 7.3 Pour le chef de projet : la ligne « déployée » du CHANGELOG
Après une mise en production réussie (`"statut": "ok"` relu par `compte-rendu`), le chef de projet ajoute sous l'entrée
`## [x.y.z]` du `CHANGELOG.md` du projet la ligne `Déployée en production le AAAA-MM-JJ.` Cette ligne **fait partie de
sa finition** : elle passe par une demande de fusion comme le reste, jamais directement sur la branche principale.
