#!/usr/bin/env python3
"""Tests de l'affichage des panneaux — sans modèle, avec un FAUX Herdr : un écran ne déborde jamais du pane (une ligne avec un
retour à la ligne devient plusieurs lignes, chaque ligne coupée à la largeur, h - 1 lignes au plus), le panneau tourne dans un écran
séparé sans historique (la molette ne remonte plus d'anciens écrans) et rend le terminal propre quand Herdr l'arrête (SIGTERM).
Usage : python3 tests/affichage.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    (t / "herdr").write_text("#!/bin/sh\necho '{\"result\": {}}'\n"); os.chmod(t / "herdr", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr"), "COLUMNS": "40", "LINES": "8"}
    code = (f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
            "lignes=['titre', 'deux\\nlignes', 'x'*200, '🐑 icône large '*10] + [f'l{n}' for n in range(20)];"
            "sys.stdout.write(g['cadre'](lignes, 40, 8)); sys.stderr.write(repr((g['ECRAN_PANNEAU'], g['ECRAN_NORMAL'])))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    sortie = r.stdout
    dire(sortie.count("\n") == 7, f"cadre : exactement h - 1 = 7 lignes, jamais plus (obtenu {sortie.count(chr(10))})")
    vis = [ANSI.sub("", l) for l in sortie.split("\n")[:7]]
    import unicodedata
    larg = lambda s: sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)
    dire(all(larg(l) <= 40 for l in vis), f"cadre : aucune ligne plus large que le pane (max {max(map(larg, vis))})")
    dire(vis[1] == "deux" and vis[2] == "lignes", "cadre : une ligne avec un retour à la ligne devient deux lignes (pas de débordement caché)")
    dire(sortie.startswith("\x1b[H") and sortie.endswith("\x1b[J"), "cadre : réécrit en place (curseur en haut, fin effacée)")
    ecran, normal = eval(r.stderr.strip().splitlines()[-1])
    dire("\x1b[?1049h" in ecran and "\x1b[3J" in ecran, "le panneau ouvre un écran séparé et efface l'historique")
    dire("\x1b[?1049l" in normal and "\x1b[?25h" in normal, "à l'arrêt : retour à l'écran normal, curseur rendu")
    p = subprocess.Popen([sys.executable, str(i / "bin/berger"), "panneau", "catalogue"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3); p.send_signal(signal.SIGTERM)
    try: out, err = p.communicate(timeout=10)
    except subprocess.TimeoutExpired: p.kill(); out, err = p.communicate()
    out = out.decode("utf-8", "replace")
    dire(out.startswith("\x1b[?1049h") and "CATALOGUE" in out, "vrai panneau : démarre dans l'écran séparé et s'affiche")
    dire(out.rstrip().endswith("\x1b[?1049l") and p.returncode == 0, f"vrai panneau arrêté par SIGTERM (comme Herdr) : terminal rendu propre (code {p.returncode})")

    # dans un VRAI terminal (pty) : la molette, traduite en flèches par l'écran séparé, ne doit RIEN afficher ; l'écho est rendu à l'arrêt
    import pty, termios
    maitre, esclave = pty.openpty()
    p = subprocess.Popen([sys.executable, str(i / "bin/berger"), "panneau", "catalogue"], env=env, stdin=esclave, stdout=esclave, stderr=esclave)
    time.sleep(2.5); os.write(maitre, b"\x1b[B\x1b[B\x1b[A" * 5); time.sleep(3); p.send_signal(signal.SIGTERM); p.wait(timeout=10)
    os.set_blocking(maitre, False); sortie = b""
    try:
        while True: sortie += os.read(maitre, 65536)
    except (BlockingIOError, OSError): pass
    dire(b"^[[" not in sortie and b"\x1b[B\x1b[B" not in sortie, "terminal réel : les flèches de la molette ne s'affichent plus (pas d'écho ^[[A / ^[[B)")
    dire(bool(termios.tcgetattr(esclave)[3] & termios.ECHO), "terminal réel : l'écho du clavier est rendu à l'arrêt du panneau")
    os.close(maitre); os.close(esclave)

    # défilement : contenu plus long que le pane → fenêtre + pied « lignes a–b sur n », molette/flèches/pages, bornes
    code3 = (f"import runpy,sys,json,re;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
             "L=[f'ligne {n}' for n in range(1,31)];net=lambda x:re.sub(r'\\x1b\\[[0-9;?]*[A-Za-z]','',x);"
             "r=[];v,d=g['fenetre'](L,0,8);r.append([net(x) for x in v]+[d]);v,d=g['fenetre'](L,10**9,8);r.append([net(x) for x in v]+[d]);"
             "v,d=g['fenetre'](L[:5],7,8);r.append([net(x) for x in v]+[d]);"
             "r.append([g['touches'](b'\\x1b[B'*2+b'\\x1b[A',6), g['touches'](b'\\x1b[6~',6), g['touches'](b'\\x1b[H',6), g['touches'](b'\\x1b[F',6) == float('inf')]);"
             "print(json.dumps(r))")
    r = json.loads(subprocess.run([sys.executable, "-c", code3], env=env, capture_output=True, text=True, timeout=60).stdout)
    dire(r[0][:6] == [f"ligne {n}" for n in range(1, 7)] and "lignes 1–6 sur 30" in r[0][6] and r[0][7] == 0, "défilement : en haut, 6 lignes + pied « lignes 1–6 sur 30 »")
    dire(r[1][0] == "ligne 25" and "lignes 25–30 sur 30" in r[1][6] and r[1][7] == 24, "défilement : décalage trop grand → borné à la dernière page")
    dire(r[2][:-1] == [f"ligne {n}" for n in range(1, 6)] and r[2][-1] == 0, "défilement : un contenu qui tient dans le pane reste tel quel, sans pied")
    dire(r[3] == [3, 6, None, True], f"touches : molette 2 bas − 1 haut = +3 lignes, Page Bas = +1 page, Début, Fin (obtenu {r[3]})")
    # pas de molette = le réglage de Herdr (ui.mouse_scroll_lines) ; absent ou illisible → 3, comme Herdr
    xdg = t / "xdg"; (xdg / "herdr").mkdir(parents=True)
    code4 = (f"import runpy,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
             "print(g['lignes_molette'](), g['touches'](b'\\x1b[B'*2, 6, g['lignes_molette']()))")
    pas = lambda: subprocess.run([sys.executable, "-c", code4], env={**env, "XDG_CONFIG_HOME": str(xdg)}, capture_output=True, text=True, timeout=60).stdout.split()
    sans = pas(); (xdg / "herdr/config.toml").write_text("[ui]\nmouse_scroll_lines = 5\n"); cinq = pas()
    (xdg / "herdr/config.toml").write_text("[ui\ncassé"); casse = pas()
    (xdg / "herdr/config.toml").write_text("ui = 3\n"); type_ = pas()
    (xdg / "herdr/config.toml").write_text("[ui]\nmouse_scroll_lines = 0\n"); zero = pas()
    dire(sans == ["3", "6"] and cinq == ["5", "10"] and casse == type_ == zero == ["3", "6"],
         f"molette : pas lu dans la config Herdr (absent 3, réglé 5 ; illisible, mal typé, 0 → 3 comme Herdr) — {sans} {cinq} {casse} {type_} {zero}")
    code5 = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');L=[str(n) for n in range(30)];"
             "print(json.dumps([g['fenetre'](L,0,2), g['fenetre'](L,10**9,1), g['touches'](b'\\x1bOH',6), g['touches'](b'\\x1bOF',6) == float('inf')]))")
    r5 = json.loads(subprocess.run([sys.executable, "-c", code5], env=env, capture_output=True, text=True, timeout=60).stdout)
    dire(r5[0] == [["0"], 0] and r5[1] == [["0"], 0], f"pane d'une ou deux lignes : pas de pied absurde, décalage 0 — {r5[:2]}")
    dire(r5[2] is None and r5[3] is True, "Début / Fin aussi en mode curseur applicatif (\\eOH / \\eOF)")

    # de bout en bout : vrai panneau dans un terminal de 8 lignes, la molette fait avancer la fenêtre
    import fcntl, struct
    maitre, esclave = pty.openpty(); fcntl.ioctl(esclave, termios.TIOCSWINSZ, struct.pack("HHHH", 8, 60, 0, 0))
    env8 = {k: v for k, v in env.items() if k not in ("COLUMNS", "LINES")}
    p = subprocess.Popen([sys.executable, str(i / "bin/berger"), "panneau", "catalogue"], env=env8, stdin=esclave, stdout=esclave, stderr=esclave)
    def vider():
        os.set_blocking(maitre, False); x = b""
        try:
            while True: x += os.read(maitre, 65536)
        except (BlockingIOError, OSError): return x
    time.sleep(2.5); avant = ANSI.sub("", vider().decode("utf-8", "replace"))
    os.write(maitre, b"\x1b[B" * 2); time.sleep(1.5); apres = ANSI.sub("", vider().decode("utf-8", "replace"))
    p.send_signal(signal.SIGTERM); p.wait(timeout=10); os.close(maitre); os.close(esclave)
    dire("lignes 1–" in avant and "lignes 7–" in apres, "vrai panneau, terminal de 8 lignes : la molette (2 crans) avance la fenêtre de 6 lignes")

    # pane rétréci pendant l'attente, puis molette : le redessin suit la NOUVELLE taille (jamais plus de h - 1 lignes)
    maitre, esclave = pty.openpty(); fcntl.ioctl(esclave, termios.TIOCSWINSZ, struct.pack("HHHH", 20, 60, 0, 0))
    p = subprocess.Popen([sys.executable, str(i / "bin/berger"), "panneau", "catalogue"], env=env8, stdin=esclave, stdout=esclave, stderr=esclave)
    time.sleep(2.5); vider(); fcntl.ioctl(esclave, termios.TIOCSWINSZ, struct.pack("HHHH", 8, 60, 0, 0))
    os.write(maitre, b"\x1b[B"); time.sleep(0.4); apres = vider()
    p.send_signal(signal.SIGTERM); p.wait(timeout=10); os.close(maitre); os.close(esclave)
    ecrans = [e for e in apres.split(b"\x1b[H") if e.strip()]
    hauteurs = [e.count(b"\n") for e in ecrans]
    dire(bool(hauteurs) and max(hauteurs) <= 7, f"pane rétréci à 8 lignes puis molette : aucun écran de plus de 7 lignes ({hauteurs})")

sys.exit(1 if ko else 0)
