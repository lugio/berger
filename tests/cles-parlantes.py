#!/usr/bin/env python3
"""Tests des clés « parlantes » du coffre (08/10/2026) — le filtre ne retient une valeur que si le NOM de sa clé dit que c'est
un secret. « jeton » (français) en manquait : une valeur rangée sous `jeton` passait le filtre du courtier et l'audit des
secrets. Vérifie, avec le VRAI courtier (module) dans une installation JETABLE, que jeton, mot_de_passe, motdepasse, mdp, secret
sont retenus, qu'une adresse ne l'est pas, que `berger secrets audit` trouve une valeur « jeton » laissée en clair, et que les
trois copies de la liste (courtier, audit, verifier-depot) restent identiques. Les valeurs d'essai sont construites à
l'exécution et jamais affichées. Usage : python3 tests/cles-parlantes.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    v = {k: f"ESSAI-{k.upper()}-" + str(987654) for k in ("jeton", "mot_de_passe", "motdepasse", "mdp", "secret")}
    coffre = {"svc": dict(v), "web": {"url": "https://exemple.invalid/chemin"}}
    (m / "coffre-essai.json").write_text(json.dumps(coffre))
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    d = i / "agents/a"; (d / "memory").mkdir(parents=True)
    (d / "agent.conf").write_text("nom = a\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n")
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))
    loader = importlib.machinery.SourceFileLoader("courtier_cles", str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader("courtier_cles", loader); C = importlib.util.module_from_spec(spec); loader.exec_module(C)
    retenues = C.valeurs_du_coffre()
    for k, val in v.items():
        dire(val in retenues and C.contient_secret(f"texte {val} texte"), f"courtier : une valeur rangée sous « {k} » est retenue par le filtre")
    dire("https://exemple.invalid/chemin" not in retenues, "courtier : une adresse n'est pas prise pour un secret")

    # 18/10 (REA, tools/list de 3 Mo) : le filtre d'une grosse réponse MCP reste rapide, et le coffre relu seulement s'il change
    lu = []; charger = C.json.load; C.json.load = lambda f: lu.append(1) or charger(f)
    try:
        for _ in range(50): C.contient_secret("rien de secret ici")
    finally: C.json.load = charger
    dire(not lu, f"courtier : coffre inchangé, jamais relu ({len(lu)} lecture(s) pour 50 filtrages)")
    neuf = "ESSAI-NEUF-" + "424242"; coffre["svc"]["token"] = neuf
    (m / "coffre-essai.json").write_text(json.dumps(coffre)); os.utime(m / "coffre-essai.json", ns=(1, 1))
    dire(C.contient_secret(f"x {neuf} x"), "courtier : coffre modifié, nouvelle valeur filtrée aussitôt (relu)")
    outils = [{"name": f"outil_{n}", "description": "décrit " * 200, "inputSchema": {"type": "object", "properties":
               {f"p{k}": {"type": "string", "description": f"paramètre {k} " * 60} for k in range(12)}}} for n in range(207)]
    gros = (json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": outils}}) + "\n").encode()
    recu = []; R = C._mcp.Relais("a", "rea", recu.append, lambda b: None, C.contient_secret, lambda *x: None, lambda *x: None, max_reponse=16 << 20)
    R.du_client(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).encode())
    t0 = __import__("time").monotonic(); R.du_serveur(gros); duree = __import__("time").monotonic() - t0
    dire(len(gros) > 2_500_000 and recu == [gros] and duree < 1.5, f"relais MCP : tools/list de {len(gros) // 1024} Ko filtré et transmis en {duree:.2f} s (< 1,5 s)")
    n = []; R2 = C._mcp.Relais("a", "rea", lambda b: None, lambda b: None, lambda x: n.append(1) or C.contient_secret(x), lambda *x: None, lambda *x: None, max_reponse=16 << 20)
    R2.du_client(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).encode()); R2.du_serveur(gros)
    dire(len(n) <= 2, f"relais MCP : filtre appelé {len(n)} fois pour la réponse entière (2 au plus : brut + chaînes jointes)")
    piege = (json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"tools": outils[:5] + [{"name": "x", "description": v["jeton"]}]}}) + "\n").encode()
    R.du_client(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}).encode()); R.du_serveur(piege)
    dire(len(recu) == 2 and C._mcp.BLOQUEE.encode() in recu[1] and v["jeton"].encode() not in recu[1], "relais MCP : une valeur du coffre dans une grosse réponse reste bloquée")

    (d / "memory/2026-10-08.md").write_text("- note : " + v["jeton"] + "\n")          # une valeur « jeton » laissée en clair
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "secrets", "audit"], capture_output=True, text=True, timeout=120,
                       env={**os.environ})
    sortie = r.stdout + r.stderr
    dire(r.returncode != 0 and "svc.jeton" in sortie, "secrets audit : la valeur « jeton » en clair est trouvée (nommée par sa clé)")
    dire(not any(val in sortie for val in v.values()), "secrets audit : aucune valeur affichée")

copies = [re.search(r'parlant = re\.compile\((r"[^"]+")\)', s).group(1) for s in
          [(SRC / "courtier/courtier").read_text()] + (SRC / "bin/berger").read_text().split("def verifier_depot", 1)]
dire(len(set(copies)) == 1 and "jeton" in copies[0], "les trois listes de clés parlantes (courtier, audit, verifier-depot) sont identiques")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
