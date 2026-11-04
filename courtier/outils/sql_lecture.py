# -*- coding: utf-8 -*-
"""Outil de type « sql_lecture » pour le courtier de Berger — LECTURE d'une base SQL Server par des requêtes FIXÉES dans la
config : l'agent ne fournit jamais de SQL, seulement les valeurs des paramètres d'un verbe.

Réglages (config.toml, section [outils.<nom>]) :
  hote, port, base   où lire (port 1433 par défaut) — « hote » peut porter une instance : srv\\instance
  utilisateur_cle, mot_de_passe_cle   chemins des identifiants dans le coffre (lus à chaque appel, jamais rendus)
  nom          nom de l'outil, pour « Application Name = berger-<nom> » (défaut sql_lecture)
  pilote       pymssql (défaut, paquet Debian python3-pymssql) ou pyodbc (python3-pyodbc + tdsodbc) ; pilote_odbc = FreeTDS
  delai        durée maximale d'une requête, en secondes (30 par défaut) ; max_lignes = lignes rendues au plus (200)
  [outils.<nom>.verbes.<verbe>]  sql = UNE requête SELECT ou WITH, où « :nom » marque un paramètre ;
               parametres = [{nom = "…", motif = "…"}, …] (chaque valeur doit suivre son motif EN ENTIER) ; aide = une ligne.

Règles : au chargement, une requête qui n'est pas un SELECT/WITH unique est refusée (« ; », commentaire, caractère non
ASCII hors des chaînes et identifiants, mot d'écriture ou d'exécution : INSERT, UPDATE, DELETE, EXEC, INTO, DDL,
OPENROWSET, WAITFOR, sp_/xp_…) — une colonne qui porte un de ces noms s'écrit entre crochets. À l'appel, les valeurs passent en paramètres LIÉS, jamais collées dans le texte.
Connexion annoncée en lecture seule (ApplicationIntent=ReadOnly), sans autocommit, annulée (rollback) et fermée après
chaque appel : jamais de COMMIT. Lignes bornées (« tronqué » dit dans la réponse), délai borné. Rien n'est gardé ni
archivé. Le pilote est importé à l'appel seulement : le courtier démarre sans lui."""
import datetime, decimal, math, re, threading, uuid

INTERDITS = set("""INSERT UPDATE DELETE MERGE EXEC EXECUTE CREATE ALTER DROP TRUNCATE GRANT REVOKE DENY INTO BACKUP RESTORE
    DBCC SHUTDOWN KILL USE DECLARE SET BEGIN COMMIT ROLLBACK SAVE OPENROWSET OPENDATASOURCE OPENQUERY OPENXML BULK WAITFOR
    RECONFIGURE GO WRITETEXT UPDATETEXT""".split())


def connecter_pymssql(p):
    try: import pymssql
    except ImportError: raise RuntimeError("pilote absent : le propriétaire installe le paquet Debian python3-pymssql "
                                           "(sudo apt install python3-pymssql)") from None
    t = max(1, math.ceil(p["delai"]))
    return pymssql.connect(server=p["hote"], port=str(p["port"]), user=p["utilisateur"], password=p["mot_de_passe"],
                           database=p["base"], appname=p["application"], read_only=p["lecture_seule"], autocommit=False,
                           login_timeout=t, timeout=t, tds_version="7.4")


def connecter_pyodbc(p):
    try: import pyodbc
    except ImportError: raise RuntimeError("pilote absent : le propriétaire installe les paquets Debian python3-pyodbc tdsodbc unixodbc") from None
    def q(v): return "{" + str(v).replace("}", "}}") + "}"                # valeur ODBC entre accolades (« ; » permis)
    t = max(1, math.ceil(p["delai"]))
    chaine = ";".join([f"DRIVER={{{p['pilote_odbc']}}}", f"SERVER={p['hote']}", f"PORT={p['port']}", f"DATABASE={q(p['base'])}",
                       f"UID={q(p['utilisateur'])}", f"PWD={q(p['mot_de_passe'])}", f"APP={p['application']}",
                       "ApplicationIntent=ReadOnly", "TDS_Version=7.4"])
    cx = pyodbc.connect(chaine, autocommit=False, readonly=p["lecture_seule"], timeout=t)
    cx.timeout = t                                                        # délai de chaque requête (timeout= : connexion)
    return cx


PILOTES = {"pymssql": (connecter_pymssql, "%s"), "pyodbc": (connecter_pyodbc, "?")}


def analyser(sql, marqueur):
    """Parcourt la requête hors des chaînes '…' et des identifiants […] / "…" : renvoie (texte pour le pilote, noms des
    paramètres dans l'ordre). Refuse ce qui n'est pas UNE requête de lecture."""
    squelette, sortie, noms, i, n = [], [], [], 0, len(sql)
    pourcent = (lambda s: s.replace("%", "%%")) if marqueur == "%s" else (lambda s: s)   # pymssql : un % seul serait un marqueur
    while i < n:
        c = sql[i]
        if c in "'[\"":
            fin = "]" if c == "[" else c; j = i + 1
            while True:
                j = sql.find(fin, j)
                if j < 0: raise ValueError(f"{c}…{fin} non fermé")
                if sql[j + 1:j + 2] == fin: j += 2; continue                # '' ]] "" : le délimiteur doublé
                break
            sortie.append(pourcent(sql[i:j + 1])); squelette.append(" '' " if c == "'" else " x "); i = j + 1
        elif sql.startswith(("--", "/*"), i): raise ValueError("commentaire refusé (-- ou /* */)")
        elif sql.startswith("::", i): sortie.append("::"); squelette.append("::"); i += 2
        elif c == ":" and (m := re.match(r"[A-Za-z_]\w*", sql[i + 1:])):
            noms.append(m.group()); sortie.append(marqueur); squelette.append(" ? "); i += 1 + len(m.group())
        else: sortie.append(pourcent(c)); squelette.append(c); i += 1
    s = "".join(squelette)
    if not s.isascii(): raise ValueError("caractère non ASCII hors d'une chaîne ou d'un identifiant (ex. « ; » grec)")
    if ";" in s: raise ValueError("« ; » refusé : une seule requête")
    if not re.match(r"\s*(SELECT|WITH)\b", s, re.I): raise ValueError("la requête doit commencer par SELECT ou WITH")
    for mot in re.findall(r"[A-Za-z_][\w$]*", s):
        if mot.upper() in INTERDITS or mot.upper().startswith(("SP_", "XP_")): raise ValueError(f"mot refusé dans une requête de lecture : {mot}")
    if re.search(r"\bNEXT\s+VALUE\s+FOR\b", s, re.I): raise ValueError("NEXT VALUE FOR refusé (une séquence qui avance est une écriture)")
    return "".join(sortie), noms


def valeur(v):
    """Une valeur de la base, rendue en JSON."""
    if v is None or isinstance(v, (str, bool, int, float)): return v
    if isinstance(v, (datetime.date, datetime.time)): return v.isoformat()
    if isinstance(v, decimal.Decimal): return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, (bytes, bytearray, memoryview)): return f"<binaire {len(v)} octets>"
    return str(v) if isinstance(v, uuid.UUID) else repr(v)[:200]


def fermer(cx, annuler=False):
    for geste in (("cancel", "close") if annuler else ("rollback", "close")):   # jamais de commit
        try: getattr(cx, geste, lambda: None)()
        except Exception: pass


class Outil:
    def __init__(self, reglages, secret, verifier_hote):                  # verifier_hote : pour HTTPS, inutile ici
        self.valeur_coffre = secret
        self.nom = str(reglages.get("nom", "sql_lecture"))
        if not re.fullmatch(r"[\w-]{1,40}", self.nom): raise ValueError(f"nom d'outil invalide : {self.nom}")
        self.hote, self.base = str(reglages.get("hote", "")), str(reglages.get("base", ""))
        self.port = int(reglages.get("port", 1433))
        if not re.fullmatch(r"[\w.-]+(\\[\w$-]+)?", self.hote): raise ValueError(f"{self.nom} : « hote » attendu (nom ou nom\\instance)")
        if not re.fullmatch(r"[\w.$:\\-]{1,260}", self.base):        # nom, ou chemin de fichier attaché (I:\DOSSIER\BASE.GI)
            raise ValueError(f"{self.nom} : « base » attendue (1 à 260 caractères : lettres, chiffres, . $ - : \\ — jamais ; = {{}} [] guillemets)")
        self.cles = (str(reglages.get("utilisateur_cle", "")), str(reglages.get("mot_de_passe_cle", "")))
        if not all(self.cles): raise ValueError(f"{self.nom} : utilisateur_cle et mot_de_passe_cle (chemins du coffre) obligatoires")
        pilote = str(reglages.get("pilote", "pymssql"))
        if pilote not in PILOTES: raise ValueError(f"{self.nom} : pilote inconnu « {pilote} » ({', '.join(PILOTES)})")
        self.connecter, self.marqueur = PILOTES[pilote]                  # connecter : remplaçable (tests : fausse base)
        self.pilote_odbc = str(reglages.get("pilote_odbc", "FreeTDS"))
        if not re.fullmatch(r"[\w .-]{1,60}", self.pilote_odbc): raise ValueError(f"{self.nom} : pilote_odbc invalide")
        self.delai, self.max_lignes = float(reglages.get("delai", 30)), int(reglages.get("max_lignes", 200))
        if self.delai <= 0 or self.max_lignes < 1: raise ValueError(f"{self.nom} : delai et max_lignes doivent être positifs")
        self.requetes, self.verbes = {}, {}
        for verbe, r in reglages.get("verbes", {}).items():
            self.requetes[verbe] = self.controler(verbe, {"sql": r} if isinstance(r, str) else dict(r))
            self.verbes[verbe] = self.fabriquer(verbe)

    def hotes(self): return {}            # les identifiants ne partent que vers le serveur SQL fixé dans la même section

    # ───────── configuration : une requête de lecture fixée, des paramètres déclarés avec leur motif ─────────
    def controler(self, verbe, r):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", verbe) or verbe == "aide": raise ValueError(f"{self.nom} : nom de verbe refusé « {verbe} »")
        try: texte, noms = analyser(str(r.get("sql", "")), self.marqueur)
        except ValueError as e: raise ValueError(f"{self.nom}.{verbe} : {e}") from None
        parametres = []
        for p in r.get("parametres", []):
            nom, motif = str(p.get("nom", "")), p.get("motif")
            if not re.fullmatch(r"[A-Za-z_]\w*", nom) or not motif: raise ValueError(f"{self.nom}.{verbe} : chaque paramètre a un nom et un motif")
            try: parametres.append((nom, re.compile(str(motif))))
            except re.error as e: raise ValueError(f"{self.nom}.{verbe} : motif invalide pour {nom} ({e})") from None
        declares = [p[0] for p in parametres]
        if len(set(declares)) != len(declares): raise ValueError(f"{self.nom}.{verbe} : paramètre déclaré deux fois")
        if set(noms) != set(declares):
            raise ValueError(f"{self.nom}.{verbe} : paramètres de la requête ({', '.join(sorted(set(noms))) or 'aucun'}) "
                             f"≠ paramètres déclarés ({', '.join(declares) or 'aucun'})")
        return {"texte": texte, "ordre": noms, "parametres": parametres, "aide": str(r.get("aide", "")).strip()}

    def fabriquer(self, verbe):
        q = self.requetes[verbe]
        def lire(args): return self.lire(verbe, args)
        lire.__doc__ = (f"{verbe}{''.join(f' <{n}>' for n, _ in q['parametres'])} : {q['aide'] or 'requête de lecture fixée'} "
                        f"(lecture SQL, {self.max_lignes} lignes au plus)")
        return lire

    # ───────── appel ─────────
    def lire(self, verbe, args):
        q = self.requetes[verbe]
        if len(args) != len(q["parametres"]):
            raise ValueError(f"{verbe} attend {len(q['parametres'])} argument(s) : {' '.join('<' + n + '>' for n, _ in q['parametres']) or 'aucun'}")
        valeurs = {}
        for (nom, motif), a in zip(q["parametres"], args):
            if not motif.fullmatch(a): raise ValueError(f"{nom} refusé : il doit suivre le motif {motif.pattern}")
            valeurs[nom] = a
        params = tuple(valeurs[n] for n in q["ordre"])
        ident = (str(self.valeur_coffre(self.cles[0])), str(self.valeur_coffre(self.cles[1])))
        etat = {}

        def travail():
            try: etat["resultat"] = self.executer(q["texte"], params, ident, etat)
            except BaseException as e: etat["erreur"] = e
        t = threading.Thread(target=travail, daemon=True); t.start(); t.join(self.delai + 1)
        if t.is_alive():                                                  # garde du courtier, en plus du délai du pilote
            if etat.get("cx") is not None: threading.Thread(target=fermer, args=(etat["cx"], True), daemon=True).start()
            raise TimeoutError(f"délai dépassé ({self.delai:g} s) : requête abandonnée")
        if "erreur" in etat:
            e = etat["erreur"]; texte = str(e) if type(e) is RuntimeError else f"{type(e).__name__} : {e}"
            for s in ident:
                if len(s) >= 3: texte = texte.replace(s, "[masqué]")       # jamais d'identifiant dans un message d'erreur
            raise RuntimeError(texte[:300]) from None
        return etat["resultat"]

    def executer(self, texte, params, ident, etat):
        cx = self.connecter({"hote": self.hote, "port": self.port, "base": self.base, "utilisateur": ident[0], "mot_de_passe": ident[1],
                             "application": f"berger-{self.nom}", "lecture_seule": True, "delai": self.delai, "pilote_odbc": self.pilote_odbc})
        etat["cx"] = cx
        try:
            cur = cx.cursor(); cur.execute(texte, params)
            colonnes = []
            for i, d in enumerate(cur.description or []):
                c = str(d[0] or f"colonne{i + 1}"); colonnes.append(c if c not in colonnes else f"{c}_{i + 1}")
            lignes = cur.fetchmany(self.max_lignes + 1) if colonnes else []
        finally: fermer(cx)
        tronque = len(lignes) > self.max_lignes
        out = {"colonnes": colonnes, "lignes": [dict(zip(colonnes, map(valeur, l))) for l in lignes[:self.max_lignes]],
               "nombre": min(len(lignes), self.max_lignes), "tronque": tronque}
        if tronque: out["message"] = f"tronqué : les {self.max_lignes} premières lignes seulement (affiner la requête ou relever max_lignes)"
        return out
