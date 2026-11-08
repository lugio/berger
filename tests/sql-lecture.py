#!/usr/bin/env python3
"""Tests de l'outil « sql_lecture » (lecture SQL Server à requêtes FIXÉES) — sans serveur : une fausse connexion DB-API
et de faux modules pilotes (pymssql, pyodbc) qui notent ce qu'on leur demande. Aucun réseau, aucun coffre.
Usage : python3 tests/sql-lecture.py   (code de retour 0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, decimal, importlib.util, json, os, re, sys, tempfile, time, tomllib, types
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent / "courtier/outils/sql_lecture.py"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def erreur(f, *a):
    """Le message d'erreur levé par f(*a), ou None si f n'a rien refusé."""
    try: f(*a); return None
    except Exception as e: return f"{type(e).__name__} : {e}"


UTILISATEUR, MOT_DE_PASSE = "utilisateur-factice-du-test", "mot-de-passe-factice-du-test"
COFFRE = {"sql.utilisateur": UTILISATEUR, "sql.mot_de_passe": MOT_DE_PASSE}
LUS = []                                                                # chaque lecture du coffre


def secret(chemin):
    LUS.append(chemin); return COFFRE[chemin]


class FauxCurseur:
    def __init__(self, base): self.base, self.description = base, None

    def execute(self, sql, params=()):
        self.base.executees.append((sql, tuple(params)))
        if self.base.attente: time.sleep(self.base.attente)
        if self.base.panne: raise self.base.panne
        self.description = [(c, None, None, None, None, None, None) for c in self.base.colonnes]
        self.reste = list(self.base.lignes)

    def fetchmany(self, n):
        self.base.demandees.append(n); out, self.reste = self.reste[:n], self.reste[n:]; return out

    def fetchall(self): raise AssertionError("fetchall interdit : les lignes sont bornées")

    def close(self): pass


class FausseBase:
    """Ce que le pilote recevrait : connexions ouvertes, requêtes, rollback, commit (jamais), fermeture."""
    def __init__(self, colonnes=("n",), lignes=((1,),), attente=0, panne=None):
        self.colonnes, self.lignes, self.attente, self.panne = colonnes, list(lignes), attente, panne
        self.connexions, self.executees, self.demandees, self.journal = [], [], [], []

    def connecter(self, p):
        self.connexions.append(dict(p)); base = self

        class Connexion:
            def cursor(self): return FauxCurseur(base)
            def rollback(self): base.journal.append("rollback")
            def commit(self): base.journal.append("COMMIT")
            def close(self): base.journal.append("close")
            def cancel(self): base.journal.append("cancel")
        return Connexion()


spec = importlib.util.spec_from_file_location("outil_sql_lecture", MODULE)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

BASE_REGLAGES = {"type": "sql_lecture", "nom": "compta-test", "hote": "sql.exemple.local", "base": "COMPTA",
                 "utilisateur_cle": "sql.utilisateur", "mot_de_passe_cle": "sql.mot_de_passe", "delai": 0.5}


def outil(verbes, base=None, **reglages):
    o = mod.Outil({**BASE_REGLAGES, **reglages, "verbes": verbes}, secret, None)
    if base is not None: o.connecter = base.connecter
    return o


def conf(sql, parametres=()):
    return mod.Outil({**BASE_REGLAGES, "verbes": {"v": {"sql": sql, "parametres": list(parametres)}}}, secret, None)


DOSSIER = [{"nom": "dossier", "motif": "[A-Z][A-Z0-9]{0,9}"}]

# ── chargement : une requête qui n'est pas UN SELECT/WITH est refusée avant tout appel ──
for mauvaise in ("DELETE FROM t", "UPDATE t SET a = 1", "INSERT INTO t VALUES (1)", "SELECT 1; DROP TABLE t", "SELECT 1;",
                 "SELECT * INTO copie FROM t", "WITH c AS (SELECT 1 AS a) DELETE FROM c", "EXEC sp_who", "EXECUTE ('SELECT 1')",
                 "SELECT * FROM t -- fin", "SELECT /* note */ 1", "TRUNCATE TABLE t", "CREATE TABLE t (a int)", "DROP TABLE t",
                 "ALTER TABLE t ADD b int", "MERGE t USING u ON 1 = 1 WHEN MATCHED THEN DELETE", "SELECT 1 WAITFOR DELAY '00:00:05'",
                 "SELECT * FROM OPENROWSET('SQLNCLI', 'x', 'SELECT 1')", "SELECT * FROM OPENQUERY(lien, 'SELECT 1')",
                 "SELECT NEXT VALUE FOR compteur", "SELECT dbo.xp_cmdshell('dir')", "SELECT 1\nGO\nSELECT 2", "DECLARE @a int",
                 "SET NOCOUNT ON", "GRANT SELECT ON t TO public", "BACKUP DATABASE x TO DISK = 'y'", "DBCC CHECKDB", "USE master",
                 "BEGIN TRAN", "SELECT 'chaîne non fermée", "SELECT * FROM [t", "", "   ", "select 1 union select 2; update t set a = 1",
                 "SeLeCt 1 InTo t2", "SELECT 1\u037e DROP TABLE t", "SELECT\u00a01"):
    dire(erreur(conf, mauvaise) is not None, f"chargement : requête refusée {mauvaise!r}")
for bonne in ("SELECT 'a;b -- c /* d */ DELETE' AS texte", "SELECT [Update], [Delete] FROM [dbo].[T]", 'SELECT "Exec" FROM t',
              "WITH c AS (SELECT 1 AS a) SELECT a FROM c", "select n'Été' as x", "SELECT CAST('10:30' AS time)",
              "SELECT COUNT(*) AS n, SUM(montant) AS total FROM t GROUP BY compte", "SELECT TOP 5 * FROM t ORDER BY a OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY"):
    dire(erreur(conf, bonne) is None, f"chargement : requête de lecture acceptée {bonne!r}")
dire(erreur(conf, "SELECT a FROM t WHERE d = :dossier") is not None, "chargement : un :paramètre non déclaré est refusé")
dire(erreur(conf, "SELECT a FROM t", DOSSIER) is not None, "chargement : un paramètre déclaré mais inutilisé est refusé")
dire(erreur(conf, "SELECT a FROM t WHERE d = :dossier", [{"nom": "dossier"}]) is not None, "chargement : un paramètre sans motif est refusé")
dire(erreur(conf, "SELECT a FROM t WHERE d = :dossier", [{"nom": "dossier", "motif": "(["}]) is not None, "chargement : un motif invalide est refusé")
dire(erreur(conf, "SELECT a FROM t WHERE d = :d OR e = :d", [{"nom": "d", "motif": "x"}, {"nom": "d", "motif": "y"}]) is not None,
     "chargement : deux paramètres du même nom sont refusés")
dire(erreur(lambda: mod.Outil({**BASE_REGLAGES, "verbes": {"aide": {"sql": "SELECT 1"}}}, secret, None)) is not None
     and erreur(lambda: mod.Outil({**BASE_REGLAGES, "verbes": {"Mal nommé": {"sql": "SELECT 1"}}}, secret, None)) is not None,
     "chargement : verbe « aide » réservé, nom de verbe douteux refusé")
dire(erreur(lambda: mod.Outil({**BASE_REGLAGES, "verbes": {"v": "SELECT 1"}, "utilisateur_cle": ""}, secret, None)) is not None
     and erreur(lambda: mod.Outil({**BASE_REGLAGES, "verbes": {"v": "SELECT 1"}, "pilote": "inconnu"}, secret, None)) is not None,
     "chargement : identifiants du coffre obligatoires, pilote inconnu refusé")
dire(erreur(lambda: mod.Outil({**BASE_REGLAGES, "verbes": {"v": "SELECT 1"}, "max_lignes": 0}, secret, None)) is not None,
     "chargement : max_lignes doit être positif")
n_lus = len(LUS); o = conf("SELECT 1")
dire(set(o.verbes) == {"v"} and o.hotes() == {} and len(LUS) == n_lus, "l'outil n'a que les verbes configurés ; le coffre n'est pas lu au chargement")

# ── paramètres : motif ENTIER, valeur LIÉE, jamais collée dans le texte SQL ──
b = FausseBase(colonnes=("dossier", "lignes"), lignes=[("ABC", 3)])
o = outil({"compte": {"sql": "SELECT dossier, COUNT(*) AS lignes FROM t WHERE dossier = :dossier AND lib LIKE 'a%' GROUP BY dossier",
                      "parametres": DOSSIER, "aide": "nombre de lignes d'un dossier"}}, b)
for mauvais in ("abc", "ABC'", "ABC' OR 1=1--", "ABC;DROP", "A B", "ABCDEFGHIJK", "", "ABC\n", "ÀBC"):
    dire(erreur(o.verbes["compte"], [mauvais]) is not None, f"paramètre refusé par son motif : {mauvais!r}")
dire(erreur(o.verbes["compte"], []) is not None and erreur(o.verbes["compte"], ["ABC", "DEF"]) is not None, "il faut autant d'arguments que de paramètres")
dire(not b.connexions and not b.executees, "aucun argument refusé n'a ouvert de connexion")
r = o.verbes["compte"](["ABC"])
sql, params = b.executees[-1]
dire(params == ("ABC",) and ":dossier" not in sql and "ABC" not in sql and "= %s" in sql, "pymssql : la valeur part en paramètre lié (%s), hors du texte SQL")
dire("'a%%'" in sql, "pymssql : un % du texte SQL est doublé (sinon pris pour un marqueur)")
dire(r["colonnes"] == ["dossier", "lignes"] and r["lignes"] == [{"dossier": "ABC", "lignes": 3}] and r["nombre"] == 1 and r["tronque"] is False,
     "réponse : colonnes, lignes nommées, nombre, non tronqué")
dire(o.verbes["compte"].__doc__.startswith("compte <dossier>") and "nombre de lignes" in o.verbes["compte"].__doc__, "aide : paramètres et aide du verbe")
large = FausseBase(); ol = outil({"x": {"sql": "SELECT a FROM t WHERE b = :v", "parametres": [{"nom": "v", "motif": ".{1,80}"}]}}, large)
ol.verbes["x"](["'; DROP TABLE t --"])
dire(large.executees[-1] == ("SELECT a FROM t WHERE b = %s", ("'; DROP TABLE t --",)),
     "injection : même un motif large ne change pas la requête, la valeur reste un paramètre lié")
q = FausseBase(); oq = outil({"x": {"sql": "SELECT a FROM t WHERE b = :v AND c = ':v' AND d = :w AND e = :v",
                                   "parametres": [{"nom": "v", "motif": "[a-z]+"}, {"nom": "w", "motif": "[a-z]+"}]}}, q, pilote="pyodbc")
oq.verbes["x"](["un", "deux"])
dire(q.executees[-1] == ("SELECT a FROM t WHERE b = ? AND c = ':v' AND d = ? AND e = ?", ("un", "deux", "un")),
     "pyodbc : marqueurs « ? » dans l'ordre, un :nom dans une chaîne n'est pas un paramètre")

# ── connexion : lecture seule, nom d'application, délai, rollback et fermeture, jamais de COMMIT ──
c = b.connexions[-1]
dire(c["lecture_seule"] is True and c["application"] == "berger-compta-test" and c["delai"] == 0.5 and c["base"] == "COMPTA"
     and c["hote"] == "sql.exemple.local" and c["port"] == 1433, "connexion : lecture seule, Application Name berger-<nom>, délai, base, hôte")
dire(c["utilisateur"] == UTILISATEUR and c["mot_de_passe"] == MOT_DE_PASSE and LUS[-2:] == ["sql.utilisateur", "sql.mot_de_passe"],
     "identifiants lus au coffre à l'appel et passés au pilote seulement")
dire(b.journal == ["rollback", "close"] and "COMMIT" not in q.journal + large.journal, "après chaque appel : rollback puis fermeture, jamais de COMMIT")
dire(UTILISATEUR not in json.dumps(r) and MOT_DE_PASSE not in json.dumps(r), "aucun identifiant dans la réponse")

# ── bornes : lignes et délai ──
t = FausseBase(colonnes=("i",), lignes=[(i,) for i in range(250)])
ot = outil({"tout": "SELECT i FROM t"}, t)
r = ot.verbes["tout"]([])
dire(len(r["lignes"]) == 200 and r["tronque"] is True and "tronqué" in r["message"] and t.demandees == [201],
     "200 lignes par défaut : fetchmany(201), « tronqué » dit dans la réponse")
t5 = FausseBase(colonnes=("i",), lignes=[(i,) for i in range(5)])
r = outil({"tout": "SELECT i FROM t"}, t5, max_lignes=5).verbes["tout"]([])
dire(len(r["lignes"]) == 5 and r["tronque"] is False and "message" not in r, "exactement max_lignes : pas tronqué")
lent = FausseBase(attente=3)
t0 = time.time(); e = erreur(outil({"lent": "SELECT 1"}, lent).verbes["lent"], [])
duree = time.time() - t0
dire(e is not None and "délai" in e and duree < 2.5, f"délai dépassé : réponse en {duree:.1f} s au lieu d'attendre la base")
time.sleep(3)
dire("close" in lent.journal and "COMMIT" not in lent.journal, "délai dépassé : la connexion est annulée et fermée en arrière-plan")

# ── valeurs rendues en JSON ──
v = FausseBase(colonnes=("d", "h", "m", "b", "n"), lignes=[(datetime.date(2026, 10, 12), datetime.datetime(2026, 10, 12, 8, 30),
                                                             decimal.Decimal("12.50"), b"\x00\x01\x02", None)])
r = outil({"v": "SELECT 1"}, v).verbes["v"]([])
dire(r["lignes"][0] == {"d": "2026-10-12", "h": "2026-10-12T08:30:00", "m": 12.5, "b": "<binaire 3 octets>", "n": None} and json.dumps(r),
     "valeurs : dates ISO, décimaux en nombres, binaires masqués, JSON valide")

# ── secrets : jamais dans un message d'erreur ──
p = FausseBase(panne=RuntimeError(f"Login failed for user '{UTILISATEUR}' (password {MOT_DE_PASSE})"))
e = erreur(outil({"p": "SELECT 1"}, p).verbes["p"], [])
dire(e is not None and UTILISATEUR not in e and MOT_DE_PASSE not in e and "[masqué]" in e, f"erreur du pilote nettoyée : {e}")
dire(p.journal == ["rollback", "close"], "erreur : la connexion est quand même annulée et fermée")


class PanneConnexion(FausseBase):
    def connecter(self, p): raise ConnectionError(f"connexion refusée pour {p['utilisateur']} / {p['mot_de_passe']}")


e = erreur(outil({"p": "SELECT 1"}, PanneConnexion()).verbes["p"], [])
dire(e is not None and UTILISATEUR not in e and MOT_DE_PASSE not in e, "erreur de connexion nettoyée aussi")

# ── rien n'est gardé : pas de fichier écrit, pas de connexion conservée ──
with tempfile.TemporaryDirectory() as d:
    avant = os.getcwd(); os.chdir(d)
    try:
        g = FausseBase(); og = outil({"v": "SELECT 1"}, g); og.verbes["v"]([]); og.verbes["v"]([])
        dire(not os.listdir(d) and len(g.connexions) == 2 and g.journal.count("close") == 2,
             "aucun résultat gardé ni archivé : rien d'écrit, une connexion par appel, fermée")
    finally: os.chdir(avant)

# ── pilotes : import paresseux, paramètres demandés au vrai pilote ──
dire("pymssql" not in sys.modules and "pyodbc" not in sys.modules, "chargement de l'outil sans importer de pilote (le courtier démarre sans)")
sys.modules["pymssql"] = None                                          # pilote absent
e = erreur(outil({"v": "SELECT 1"}).verbes["v"], [])
dire(e is not None and "python3-pymssql" in e and MOT_DE_PASSE not in e, f"pilote absent : erreur claire ({e})")
vu = {}
faux = types.ModuleType("pymssql"); faux.connect = lambda **kw: (vu.update(kw), FausseBase().connecter({}))[1]
sys.modules["pymssql"] = faux
outil({"v": "SELECT 1"}, delai=7).verbes["v"]([])
dire(vu.get("read_only") is True and vu.get("appname") == "berger-compta-test" and vu.get("timeout") == 7 and vu.get("login_timeout") == 7
     and vu.get("autocommit") is False and vu.get("server") == "sql.exemple.local" and str(vu.get("port")) == "1433"
     and vu.get("database") == "COMPTA" and vu.get("tds_version") == "7.4" and vu.get("user") == UTILISATEUR,
     "pymssql : read_only (ApplicationIntent=ReadOnly), appname, timeout, autocommit désactivé, TDS 7.4")
vu = {}
fodbc = types.ModuleType("pyodbc")


def connect_odbc(chaine, **kw):
    vu.update(kw, chaine=chaine); cx = FausseBase().connecter({})
    cx.timeout = None; vu["cx"] = cx; return cx


fodbc.connect = connect_odbc; sys.modules["pyodbc"] = fodbc
COFFRE["sql.mot_de_passe"] = "mot;de}passe-factice"
outil({"v": "SELECT 1"}, delai=9, pilote="pyodbc").verbes["v"]([])
ch = vu.get("chaine", "")
dire("ApplicationIntent=ReadOnly" in ch and "APP=berger-compta-test" in ch and "DRIVER={FreeTDS}" in ch and "DATABASE={COMPTA}" in ch
     and "PWD={mot;de}}passe-factice}" in ch and vu.get("readonly") is True and vu.get("autocommit") is False and vu.get("timeout") == 9
     and vu["cx"].timeout == 9, "pyodbc : ApplicationIntent=ReadOnly, APP, mot de passe entre accolades, délais de connexion et de requête")
COFFRE["sql.mot_de_passe"] = MOT_DE_PASSE

# ── base attachée par chemin (GESTEX : « X:\\EXEMPLE\\base.db »), hôte en adresse IP + port fixe ──
CHEMIN = "X:\\EXEMPLE\\base.db"
def outil_nom_base(verbes, nom_base, **r): return mod.Outil({**BASE_REGLAGES, **r, "base": nom_base, "verbes": verbes}, secret, None)


o = outil_nom_base({"v": "SELECT 1"}, CHEMIN, hote="192.0.2.10", port=62553)
dire(o.base == CHEMIN and o.hote == "192.0.2.10" and o.port == 62553, "base par chemin et hôte IP + port fixe : acceptés")
vu = {}; sys.modules["pymssql"] = faux
o.verbes["v"]([])
dire(vu.get("database") == CHEMIN and vu.get("server") == "192.0.2.10" and str(vu.get("port")) == "62553",
     "pymssql : le chemin de la base est transmis tel quel (database=), avec l'IP et le port")
vu = {}; sys.modules["pyodbc"] = fodbc
outil_nom_base({"v": "SELECT 1"}, CHEMIN, hote="192.0.2.10", port=62553, pilote="pyodbc").verbes["v"]([])
dire("DATABASE={" + CHEMIN + "};" in vu.get("chaine", "") and "SERVER=192.0.2.10;PORT=62553;" in vu.get("chaine", ""),
     "pyodbc : le chemin passe entre accolades, comme UID et PWD, intact")
for mauvaise in ("base;UID=x", "base=x", "base\nx", "base\rx", "base\x00x", "ba{se", "ba}se", "ba[se", 'ba"se', "ba'se", "", "a" * 261):
    try: outil_nom_base({"v": "SELECT 1"}, mauvaise); refuse = False
    except ValueError: refuse = True
    dire(refuse, f"base refusée : {mauvaise[:12]!r}")
dire(outil_nom_base({"v": "SELECT 1"}, "a" * 260).base == "a" * 260, "base de 260 caractères : acceptée")

# ── l'exemple de config.exemple.toml : chargé tel quel ──
texte = (MODULE.parent.parent.parent / "config.exemple.toml").read_text()
bloc = texte[texte.index("# [outils.gestion-lecture]"):].split("\n\n")[0].splitlines()
exemple = tomllib.loads("\n".join(l[2:] for l in bloc if re.match(r"# (\[|\w[\w-]* = )", l)))["outils"]["gestion-lecture"]
ex = FausseBase(colonnes=("dossier", "lignes"), lignes=[("ABC", 1)])
oe = mod.Outil(exemple, lambda chemin: "valeur-factice", None); oe.connecter = ex.connecter
dire(set(oe.verbes) == {"etat", "etat-dossier", "version-logiciel"} and exemple.get("type") == "sql_lecture",
     "exemple gestion-lecture : chargé, verbes etat, etat-dossier et version-logiciel")
dire(exemple["base"] == CHEMIN and exemple["port"] == 62553, "exemple : base par chemin et port fixe")
oe.verbes["etat"]([]); oe.verbes["etat-dossier"](["ABC"]); oe.verbes["version-logiciel"]([])
dire(ex.executees[0][1] == () and ex.executees[1][1] == ("ABC",) and ex.connexions[0]["application"] == "berger-gestion-lecture"
     and ex.connexions[0]["lecture_seule"] and ex.connexions[0]["base"] == CHEMIN,
     "exemple : etat-dossier passe le client en paramètre lié, Application Name berger-gestion-lecture, base par chemin")
dire(erreur(oe.verbes["etat-dossier"], ["ABC' OR 1=1"]) is not None, "exemple : etat-dossier refuse un client hors motif")

print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
