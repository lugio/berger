# Spec — type d'outil du courtier « sql_lecture » (lecture SQL Server, requêtes fixées)

Date : 2026-10-12 · Auteur : Berger · sql-lecture · Relecture sécurité demandée avant la fusion.

## But

Donner à un agent (sans réseau, sans secret) la lecture de bases SQL Server du SI (premier usage : la base GESTEX du
serveur SQL du cabinet, via un compte de lecture dédié) **sans jamais lui laisser écrire une requête**. Le courtier exécute pour lui une
requête FIXÉE par le propriétaire dans `config.toml` ; l'agent ne fournit que des valeurs de paramètres.

## Configuration (`config.toml`, `[outils.<nom>]`, `type = "sql_lecture"`)

| Réglage | Rôle | Défaut |
|---|---|---|
| `hote`, `port`, `base` | où lire (pas des secrets ; `hote` est aussi repéré par `berger verifier-depot`) | port 1433 |
| `utilisateur_cle`, `mot_de_passe_cle` | chemins des identifiants **dans le coffre** (ex. `gestion.utilisateur`, `gestion.mot_de_passe`) | — obligatoires |
| `nom` | nom de l'outil, pour `Application Name = berger-<nom>` (voir « Point ouvert ») | `sql_lecture` |
| `pilote` | `pymssql` ou `pyodbc` | `pymssql` |
| `pilote_odbc` | nom du pilote ODBC (si `pyodbc`) | `FreeTDS` |
| `delai` | durée maximale d'une requête, en secondes | 30 |
| `max_lignes` | lignes rendues au plus | 200 |
| `[outils.<nom>.verbes.<verbe>]` | `sql` = la requête ; `parametres` = liste de `{nom, motif}` ; `aide` = une ligne | — |

Dans `sql`, un paramètre s'écrit `:nom` (ex. `WHERE d.code = :dossier`). Chaque `:nom` doit être déclaré dans
`parametres` et chaque paramètre déclaré doit être utilisé.

## Règles (contrôlées au CHARGEMENT de la config : une erreur empêche le courtier de démarrer, comme les autres outils)

1. **Une seule requête de lecture** : après avoir mis de côté les chaînes `'…'` et les identifiants `[…]` / `"…"`, la
   requête doit commencer par `SELECT` ou `WITH` ; sont refusés : tout caractère non ASCII (ex. le « ; » grec U+037E), `;`, les commentaires `--` et `/* */`, et les mots
   `INSERT UPDATE DELETE MERGE EXEC EXECUTE CREATE ALTER DROP TRUNCATE GRANT REVOKE DENY INTO BACKUP RESTORE DBCC
   SHUTDOWN KILL USE DECLARE SET BEGIN COMMIT ROLLBACK SAVE OPENROWSET OPENDATASOURCE OPENQUERY OPENXML BULK WAITFOR
   RECONFIGURE GO WRITETEXT UPDATETEXT`, tout nom en `sp_…` / `xp_…`, et `NEXT VALUE FOR` (une séquence qui avance
   est une écriture). Une colonne qui porte un de ces noms s'écrit entre crochets (`[Update]`).
2. **Paramètres** : l'agent donne exactement autant d'arguments que de paramètres déclarés ; chacun doit suivre son
   `motif` **en entier** (`re.fullmatch`), sinon refus **avant toute connexion**. La valeur est passée au pilote en
   **paramètre lié** (`%s` pour pymssql, `?` pour pyodbc), jamais collée dans le texte SQL.
3. **Verbes** : noms `[a-z0-9-]`, `aide` réservé (le courtier l'ajoute). L'outil n'a QUE les verbes configurés.
4. **Connexion** : lecture seule annoncée (`read_only=True`, soit `ApplicationIntent=ReadOnly`, pour pymssql ;
   `ApplicationIntent=ReadOnly` dans la chaîne ODBC et `readonly=True` pour pyodbc), `Application Name = berger-<nom>`,
   `autocommit` désactivé, **jamais de COMMIT** : la transaction est annulée (`rollback`) puis la connexion fermée après
   chaque appel. Une connexion par appel, rien n'est gardé entre deux appels (comme le coffre).
5. **Bornes** : `fetchmany(max_lignes + 1)` ; au-delà, la réponse porte `"tronque": true` et le message « tronqué :
   les <n> premières lignes seulement ». Délai : `timeout`/`login_timeout` du pilote **et** une garde dans le courtier
   (au-delà de `delai` + 1 s : réponse « délai dépassé », la connexion est annulée/fermée en arrière-plan).
6. **Secrets** : utilisateur et mot de passe lus au coffre **à chaque appel**, passés au pilote seulement. Un message
   d'erreur du pilote est nettoyé (utilisateur et mot de passe remplacés par `[masqué]`) avant de remonter ; le filtre
   habituel du courtier (valeurs du coffre, formes de clés) reste la dernière barrière, réponse et journal.
   Le journal du courtier (`appels.log`) ne garde que agent, outil, verbe, arguments, nombre de lignes.
7. **Aucune conservation** : le courtier ne garde ni n'archive les résultats ; ils ne vont que dans la réponse à l'agent.
8. **Pas de limite aux agrégats** : les noms sont pseudonymisés par la passerelle AOS ; seule la borne de lignes s'applique.
9. **Valeurs rendues** en JSON : dates en ISO 8601, décimaux en nombres, binaires remplacés par `<binaire n octets>`.

## Pilote (à installer par le propriétaire — le courtier démarre sans : import paresseux, erreur claire à l'appel)

Recommandé, dépôts Debian 13 seulement :

    sudo apt install python3-pymssql

(paquet `python3-pymssql` 2.3.2, tire `libsybdb5` de FreeTDS ; `read_only` existe depuis pymssql 2.2.8.)
TDS fixé à 7.4 (SQL Server 2012 et plus). Remplacement possible sans toucher au code : `pilote = "pyodbc"` avec
`sudo apt install python3-pyodbc tdsodbc unixodbc` (pilote ODBC « FreeTDS »).
La connexion est une petite fonction remplaçable (`Outil.connecter`) : les tests y branchent une fausse base.

## Défense en profondeur (hors code, à faire côté SI)

- Compte de lecture dédié : rôle `db_datareader` seulement sur la base GESTEX (aucun droit d'écriture ni d'`EXECUTE`).
- Règle du pare-feu : la machine de Berger → le serveur SQL, port 1433 seulement.
- Le filtre de mots est une **barrière de configuration** (contre une erreur de copier-coller), pas la protection
  principale : la protection est que l'agent ne fournit jamais de SQL, et que le compte ne peut pas écrire.

## Tests (`tests/sql-lecture.py`, joués par `tests/suites.sh`, sans serveur)

Fausse connexion DB-API : motif refusé (sans connexion), injection refusée (valeur passée liée, texte SQL inchangé),
requêtes d'écriture refusées au chargement, troncature, délai, lecture seule et nom d'application demandés au pilote,
rollback et fermeture, aucun secret dans la réponse ni dans les messages d'erreur, pilote absent = erreur claire,
exemple `[outils.gestion-lecture]` de `config.exemple.toml` chargé tel quel.

## Point ouvert (pour master)

Le courtier ne passe le nom de l'outil qu'au type `pages_publiques` (`courtier/courtier`, ligne
`if reglages["type"] == "pages_publiques"`). Cette mission ne touche pas `courtier/courtier` : en attendant, l'exemple
déclare `nom = "gestion-lecture"`. Une ligne pour passer aussi `nom` aux outils `sql_lecture` serait plus sûre.
