#!/usr/bin/env python3
"""L'aperçu statique (docs/apercu/interface.html) ne se connecte à rien : fetch remplacé par les données d'exemple et EventSource
neutralisé AVANT le code de la page, aucune ressource extérieure. Sans réseau, sans modèle."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, message):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + message)


html = (SRC / 'docs/apercu/interface.html').read_text()
app = (SRC / 'bin/page/app.js').read_text()
neutre = html.find('window.EventSource = undefined')
faux_fetch = html.find('window.fetch = ')
debut_app = html.find(app[:200])
dire(debut_app > 0, "le code de la page (bin/page/app.js) est embarqué tel quel")
dire(0 < neutre < debut_app, "EventSource neutralisé avant le code de la page")
dire(0 < faux_fetch < debut_app, "fetch remplacé par les données d'exemple avant le code de la page")
# Hors du code de la page lui-même, l'aperçu ne crée aucune connexion : ni flux, ni requête réelle, ni script ou ressource distants.
reste = html[:debut_app] + html[debut_app + len(app):] if debut_app > 0 else html
dire(not re.search(r'new\s+EventSource\s*\(', reste), "aucun EventSource ouvert hors du code de la page")
dire(not re.search(r'(?<![.\w])fetch\s*\(', reste), "aucun fetch appelé hors du code de la page")
dire(not re.search(r'<script[^>]+src=|<link[^>]+href=["\']?(https?:)?//|\b(?:src|href)=["\']https?://', html),
     "aucune ressource extérieure (script, feuille de style, image)")
dire('XMLHttpRequest' not in html.replace(app, '') and 'WebSocket' not in html.replace(app, ''), "ni XMLHttpRequest ni WebSocket dans l'aperçu")
# La régénération redonne le fichier validé (l'aperçu ne dérive pas de la page).
dire('EventSource' in app and 'typeof EventSource === "undefined"' in app,
     "la page sait se passer d'EventSource (condition qui rend la neutralisation sûre)")
print(f'==== {ko} échec(s)')
sys.exit(1 if ko else 0)
