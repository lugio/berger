#!/usr/bin/env python3
"""Contrat de l'entrée bilingue, schéma généré et assets autonomes, sans réseau."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import hashlib
import importlib.util
from pathlib import Path
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + texte)


def charger(nom, fichier):
    spec = importlib.util.spec_from_file_location(nom, fichier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


liens = charger('liens_vitrine', SRC / 'tests/vitrine.py')
fichiers = ('README.md', 'README.fr.md', 'docs/scripts/schema.py')
for f in fichiers:
    dire((SRC / f).is_file(), f'présent : {f}')
if any(not (SRC / f).is_file() for f in fichiers):
    sys.exit(1)
schema = charger('schema_vitrine', SRC / 'docs/scripts/schema.py')
sections = {
    'en': ['Quick start', 'Features', 'Herdr views', 'Safety and limits', 'How it works',
           'Documentation', 'Removal', 'Contributing', 'License'],
    'fr': ['Démarrage rapide', 'Fonctionnalités', 'Vues Herdr', 'Sécurité et limites', 'Fonctionnement',
           'Documentation', 'Retrait', 'Contribuer', 'Licence'],
}
for langue, fichier in (('en', 'README.md'), ('fr', 'README.fr.md')):
    p = SRC / fichier
    texte = p.read_text()
    titres = re.findall(r'^## (.+)$', texte, re.M)
    dire(titres == sections[langue], f'sections attendues, dans le même ordre : {fichier}')
    dire(150 <= len(texte.splitlines()) <= 220, f'{fichier} : 150–220 lignes ({len(texte.splitlines())})')
    dire(not liens.liens_invalides(p), f'liens Markdown locaux valides : {fichier}')
    sources = re.findall(r'<img[^>]+src="([^"]+)"', texte)
    dire(len(sources) == 5 and all((SRC / s).is_file() for s in sources),
         f'logo et quatre badges locaux présents : {fichier}')
    captures = re.findall(r'!\[[^]]+\]\((docs/captures/[^)]+)\)', texte)
    dire(captures == [f'docs/captures/{n}.png' for n in ('accueil', 'colonnes', 'courtier')]
         and all((SRC / c).read_bytes()[:8] == b'\x89PNG\r\n\x1a\n' for c in captures if (SRC / c).is_file())
         and all((SRC / c).is_file() for c in captures), f'trois captures locales des vues Herdr : {fichier}')
    dire('docs/demo-vues.md' in texte, f'démonstration fictive liée : {fichier}')
    dire(not re.search(r'^#+ .*screenshots', texte, re.M | re.I)
         and not re.search(r'\b(?:TODO|TBD|FIXME)\b|<ce dépôt>', texte),
         f'aucune section Screenshots ni placeholder : {fichier}')
    dire('docs/manuel.md' in texte and 'SECURITY.md' in texte and 'LICENSE' in texte,
         f'manuel, politique sécurité et licence liés : {fichier}')
    attendu = schema.render(langue)
    dire(attendu == schema.render(langue), f'génération déterministe : {langue}')
    dire(schema.update(texte, langue) == texte, f'schéma à jour : {fichier}')
    corrompu = texte.replace(attendu, 'schéma altéré', 1)
    dire(schema.update(corrompu, langue) == texte, f'témoin : schéma altéré détecté et régénéré ({langue})')
dire('Your agents. Your methods. Your choice of engine.' in (SRC / 'README.md').read_text(),
     'accroche anglaise exacte')
r = subprocess.run([sys.executable, str(SRC / 'docs/scripts/schema.py'), '--check'],
                   capture_output=True, text=True)
dire(r.returncode == 0, 'script de schéma --check vert')
for f in ('badges/mit.svg', 'badges/python.svg', 'badges/linux.svg', 'badges/herdr.svg'):
    p = SRC / 'docs/assets' / f
    dire(p.is_file(), f'asset présent : {f}')
    if not p.is_file():
        continue
    root = ET.parse(p).getroot()
    elements = [e.tag.rsplit('}', 1)[-1] for e in root.iter()]
    dire(not set(elements) & {'script', 'image', 'foreignObject'}
         and all('href' not in k for e in root.iter() for k in e.attrib)
         and not re.search(r'url\((?!#)', p.read_text()), f'SVG autonome : {f}')
logo = (SRC / 'docs/assets/berger.png').read_bytes()
blocs, i = [], 8
while logo[:8] == b'\x89PNG\r\n\x1a\n' and i + 8 <= len(logo):
    n = struct.unpack('>I', logo[i:i + 4])[0]
    blocs.append(logo[i + 4:i + 8])
    i += 12 + n
dire(len(logo) == 197975 and hashlib.sha256(logo).hexdigest() ==
     'f0e103eb8f7563fb456b894c887475c16ec3795ba25d34c15085d03e082dec24',
     'logo choisi par le propriétaire : taille et SHA-256 exacts')
dire(blocs[:1] == [b'IHDR'] and struct.unpack('>II', logo[16:24]) == (512, 512)
     and set(blocs) <= {b'IHDR', b'PLTE', b'IDAT', b'IEND'} and blocs[-1:] == [b'IEND'],
     'logo PNG 512x512 sans métadonnées')
dire(not list((SRC / 'docs/assets').glob('berger*.svg')), 'aucun ancien logo SVG')
for nom in ('README.md', 'README.fr.md'):
    texte = (SRC / nom).read_text()
    dire(texte.count('src="docs/assets/berger.png" alt="Berger" width="96" height="96"') == 1
         and '<picture' not in texte and 'prefers-color-scheme' not in texte,
         f'même logo sans variante de thème : {nom}')
badges = list((SRC / 'docs/assets/badges').glob('*.svg'))
dire(len(badges) == 4 and not any('secur' in p.name for p in badges), 'quatre badges statiques, aucun badge de sécurité')
dire('3.11+' in (SRC / 'docs/assets/badges/python.svg').read_text(), 'badge Python minimal documenté : 3.11+')
dire('tomllib' in (SRC / 'bin/berger').read_text(), 'minimum Python 3.11 cohérent avec tomllib du produit')
# Vérifier les verbes cités sans importer le CLI (qui exige une config locale).
# (les verbes sont déclarés par le registre des commandes de bin/commandes/ depuis le lot 3 : l'ancien aiguillage de main() n'existe plus)
sys.path.insert(0, str(SRC / 'tests'))
import _produit
verbes = _produit.verbes_declares(SRC)
for nom in ('README.md', 'README.fr.md'):
    texte = (SRC / nom).read_text()
    cites = set(re.findall(r'^berger ([a-z-]+)', texte, re.M))
    dire({'nouveau', 'espace'} <= cites and cites <= verbes, f'commandes Berger citées présentes dans le registre des commandes : {nom}')
    dire(all((SRC / 'systemd' / f).is_file() for f in ('berger.timer', 'berger-courtier.service', 'berger-herdr.service')),
         f'unités du démarrage rapide présentes : {nom}')
try:
    schema.update('sans marqueurs', 'en')
except ValueError:
    dire(True, 'absence de délimiteurs du schéma refusée')
else:
    dire(False, 'absence de délimiteurs du schéma refusée')
print(f'==== {ko} échec(s)')
sys.exit(1 if ko else 0)
