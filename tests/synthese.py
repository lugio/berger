#!/usr/bin/env python3
"""Tests des onglets « Synthèse » et « Sources » — sans modèle ni réseau : une installation JETABLE, un outil « scripts » à
faux scripts, un faux Herdr et un faux systemctl. Vérifie, côté COURTIER : un panneau déclaré lance son verbe de lecture et
range le résultat ; code de sortie ≠ 0 = échec ; un secret dans la sortie bloque le résultat ; un verbe d'écriture n'est
jamais lancé ; une cadence n'est pas doublée. Côté BERGER : la Synthèse ne garde que le rouge et le jaune (✗, ⚠, motifs
déclarés, échec, figé, validations, agent bloqué, courtier arrêté), garde « depuis » quand seuls des chiffres changent,
largeur jamais dépassée, codes de terminal d'un outil neutralisés, résultats masqués aux agents, onglets déclarés.
Usage : python3 tests/synthese.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, re, runpy, shutil, subprocess, sys, tempfile, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


net = lambda t: re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", t)
larg = lambda s: sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)
CLE = "sk-ant-" + "x" * 30                                               # forme de clé connue : jamais dans un résultat

with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"; sc = m / "scripts"; sc.mkdir(parents=True)
    _produit.copier(SRC, i, ("bin", "courtier", "commun")); _produit.admettre_moteurs(i)
    (m / "coffre.json").write_text("{}")
    (sc / "alertes.py").write_text('print("2 alerte(s)")\nprint("  firing   critical DisquePlein · srv1 · depuis 30 h")\n'
                                   'print("  ⚠ pending warning Lenteur · srv2")\nprint("  tout va bien ailleurs")\n'
                                   'print("\\x1b[2Jefface\\x9b5A")\n')
    (sc / "casse.py").write_text('import sys\nprint("demi-résultat")\nsys.exit(2)\n')
    (sc / "fuite.py").write_text(f'print("jeton : {CLE}")\n')
    (sc / "cibles.py").write_text('print("  ✗ job web · injoignable")\n' + "".join(f'print("  ✗ job n{k} · injoignable")\n' for k in range(5)))
    conf_ = (f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n'
             f'[outils.lecture]\ntype = "scripts"\ndossier = "{sc}"\nautorises = ["alertes.py", "casse.py", "fuite.py", "cibles.py"]\n'
             '[outils.essai]\ntype = "essai"\n'
             '[panneaux.alertes]\ntitre = "Alertes"\noutil = "lecture"\nverbe = "alertes.py"\ncadence = 300\nrouge = ["firing\\\\s+critical"]\njaune = ["pending"]\n'
             '[panneaux.casse]\noutil = "lecture"\nverbe = "casse.py"\n'
             '[panneaux.fuite]\noutil = "lecture"\nverbe = "fuite.py"\n'
             '[panneaux.ecrire]\noutil = "essai"\nverbe = "noter"\nargs = ["ne doit jamais être écrit"]\n'
             '[panneaux.cibles]\ntitre = "Cibles"\noutil = "lecture"\nverbe = "cibles.py"\ncadence = 60\n'
             '[panneaux.fautif]\noutil = "lecture"\nverbe = "cibles.py"\nrouge = ["(non ferme"]\n')
    (i / "config.toml").write_text(conf_)
    (t / "herdr").write_text('#!/bin/sh\necho \'{"result": {}}\'\n'); os.chmod(t / "herdr", 0o755)
    fb = m / ".local/bin"; fb.mkdir(parents=True); (fb / "systemctl").write_text('#!/bin/sh\necho "${FAUX_COURTIER:-active}"\n'); os.chmod(fb / "systemctl", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr")}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    for a, n in (("vigie", "Vigie"), ("scribe", "Scribe")): b("nouveau", a, n)

    # ── côté courtier : chaque panneau collecté une fois, dans le processus du courtier
    code = (f"import runpy,json,time;g=runpy.run_path({str(i / 'courtier/courtier')!r},run_name='essai');"
            "[g['collecter'](n,p) for n,p in g['CONFIG']['panneaux'].items()];"
            "pr={};g['panneaux_dus'](pr);avant=dict(pr);g['panneaux_dus'](pr);time.sleep(1);print(json.dumps({'une_fois':avant==pr,'n':len(pr)}))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    res = {p.stem: json.loads(p.read_text()) for p in (i / "courtier/panneaux").glob("*.json")}
    dire(r.returncode == 0 and res.get("alertes", {}).get("ok") and "  tout va bien ailleurs" in res["alertes"].get("lignes", []),
         "panneau déclaré : le courtier lance le verbe de lecture et range ses lignes")
    dire(res.get("casse", {}).get("ok") is False and "code de sortie 2" in res["casse"].get("erreur", ""), "code de sortie ≠ 0 : collecte en échec (pas un résultat vide)")
    tout = "".join(p.read_text() for p in (i / "courtier/panneaux").glob("*"))
    dire(CLE not in tout and "bloqué" in res.get("fuite", {}).get("erreur", ""), "secret dans la sortie : résultat bloqué, la clé n'est écrite nulle part")
    dire("écriture" in res.get("ecrire", {}).get("erreur", "") and not (i / "courtier/essai-ecritures.txt").exists(),
         "verbe d'écriture déclaré en panneau : refusé, rien n'est écrit")
    dire(r.returncode == 0 and json.loads(r.stdout or "{}").get("une_fois") is True, "deux tours de suite : chaque panneau lancé une seule fois (cadence)")
    dire("panneau alertes" in (i / "courtier/appels.log").read_text(), "chaque collecte est notée au journal du courtier")

    # ── côté Berger : Sources et Synthèse
    v = i / "courtier/validations"; v.mkdir(parents=True, exist_ok=True)
    (v / "3.json").write_text(json.dumps({"n": 3, "agent": "vigie", "apercu": "couper le compte de test"}))
    (i / "agents/scribe/CHECKLIST.md").write_text("# Inventaire\n- [ ] croiser\n⚠ Bloqué : accès refusé\n")
    vieux = json.loads((i / "courtier/panneaux/cibles.json").read_text())
    vieux["quand"] = (datetime.datetime.now() - datetime.timedelta(hours=2)).isoformat(timespec="seconds")
    (i / "courtier/panneaux/cibles.json").write_text(json.dumps(vieux))
    vue = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
           "print(json.dumps({'syn':g['VUES']['synthese'].vue_synthese(%d,60),'src':g['VUES']['sources'].vue_sources(%d,60),'onglets':g['ONGLETS_BERGER'],"
           "'icones':[g['ICONES_ONGLETS'].get(k) for k in ('Synthèse','Sources')],'masques':g['masques']('vigie')}))")
    lance = lambda w, **e: json.loads(subprocess.run([sys.executable, "-c", vue % (w, w)], env={**env, **e}, capture_output=True, text=True, timeout=60).stdout)
    x = lance(160); syn = [net(l) for l in x["syn"]]; src = [net(l) for l in x["src"]]; texte = "\n".join(syn)
    rouge = texte.split("ROUGE (")[1].split("JAUNE (")[0] if "ROUGE (" in texte else ""; jaune = texte.split("JAUNE (")[1] if "JAUNE (" in texte else ""
    dire("DisquePlein" in rouge and "✗ job web" not in jaune, "motif `rouge` déclaré → ROUGE")
    dire("Lenteur" in jaune and "tout va bien" not in texte and "2 alerte(s)" not in texte, "⚠ → JAUNE ; une ligne ordinaire n'entre pas dans la Synthèse")
    dire("casse : ○ collecte en échec" in rouge and "fuite : ○ collecte en échec" in rouge, "collecte en échec (code, secret bloqué) → ROUGE, nommée")
    dire("✗ job n1" in rouge and "✗ job n2" not in rouge and "Cibles : … et 3 autre(s)" in rouge, "plus de 3 lignes d'une même source : 3 montrées, le reste compté (renvoi vers Sources)")
    dire("Cibles : ○ figé" in jaune and "✗ job web" in rouge, "résultat trop vieux → JAUNE « figé » (ses lignes ✗ restent ROUGE)")
    dire("fautif : ○ collecte en échec — déclaration [panneaux.fautif] fautive" in rouge, "motif invalide dans une déclaration : échec nommé, la Synthèse ne casse pas")
    dire("n° 3 attend Proprio" in jaune and "Scribe : bloqué" in jaune, "validation en attente et agent bloqué → JAUNE")
    dire("NOUVEAU" in texte and "rien en rouge" not in texte, "alerte neuve marquée NOUVEAU")
    vu1 = json.loads((i / ".synthese-vu.json").read_text())
    (i / "courtier/panneaux/alertes.json").write_text((i / "courtier/panneaux/alertes.json").read_text().replace("30 h", "31 h"))
    lance(160); vu2 = json.loads((i / ".synthese-vu.json").read_text())
    dire(vu1 == vu2 and any("DisquePlein" in k for k in vu2), "seuls des chiffres changent (30 h → 31 h) : même alerte, « depuis » gardé")
    dire(any("○ collecte en échec" in l and "n'affiche PAS zéro" in " ".join(src) for l in src) and any("tout va bien ailleurs" in l for l in src),
         "Sources : l'échec est dit, les lignes ordinaires sont montrées")
    dire(not any("\x1b[2J" in l or "\x9b" in l for l in x["src"] + x["syn"]), "codes de terminal venus d'un outil neutralisés (effacement, CSI 8 bits)")
    e = lance(60); petit = [net(l) for l in e["syn"] + e["src"]]
    dire(all(larg(l) <= 160 for l in syn + src) and all(larg(l) <= 60 for l in petit), f"largeur jamais dépassée (max {max(map(larg, petit))}/60)")
    arret = "\n".join(net(l) for l in lance(160, FAUX_COURTIER="inactive")["syn"])
    dire("courtier ARRÊTÉ" in arret.split("JAUNE (")[0], "courtier arrêté → ROUGE")
    dire(any(re.fullmatch(r"berger/courtier/panneaux", k) for k in x["masques"]), "résultats des sources masqués aux agents (chacun passe par SES outils)")
    dire(["Synthèse", "synthese"] in x["onglets"] and ["Sources", "sources"] in x["onglets"] and x["icones"] == ["🚦", "🔎"], "onglets Synthèse et Sources déclarés, avec leur icône")

    # ── rien à signaler : une ligne verte
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    (v / "3.json").unlink(); (i / "agents/scribe/CHECKLIST.md").write_text("# Inventaire\n- [x] croiser\n")
    (i / "courtier/dernier-audit.txt").write_text("07/10 08:00 — aucune fuite (3 valeurs, 10 fichiers)\n")
    vert = [net(l) for l in lance(100)["syn"]]; src0 = [net(l) for l in lance(100)["src"]]
    dire(any("✓ rien en rouge ni en jaune" in l for l in vert) and not any("ROUGE (" in l for l in vert), "rien à signaler : une ligne verte, pas de section ROUGE")
    dire(any("aucun panneau déclaré" in l for l in src0), "aucune source déclarée : Sources le dit")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
