#!/usr/bin/env python3
"""Rendus publics fictifs. Usage : python3 docs/scripts/demo-vues.py /tmp/berger-demo-vues"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / 'tests'))
import _jeu_vues as J


def generer():
    """HOME/BERGER_DIR jetables, faux moteurs, faux Herdr et horloge fixe."""
    with tempfile.TemporaryDirectory(prefix='berger-demo-') as t:
        i, env = J.construire(t, courtier_actif=True)
        J.ecrire(i / 'agents/vigie/CHECKLIST.md', '# Inventaire des archives\n- [x] Lister les archives\n- [ ] Comparer les rétentions ← en cours\n')
        J.ecrire(i / 'agents/demo-ecran/CHECKLIST.md', '# Écran du carnet\n- [x] Dessiner\n- [ ] Vérifier les contrastes ← en cours\n')
        f = i / 'agents/demo-ecran/agent.conf'
        f.write_text(f.read_text().replace('nom = Demo ecran', 'nom = Atelier'))
        for k, sujet in enumerate(('navigation', 'recherche', 'filtres', 'archives', 'couleurs')):
            J.ecrire(i / f'equipes/demo/demandes/{sujet}.json', json.dumps({'sujet': sujet, 'etat': 'fusionnée', 'agent': 'demo-ecran'}), 500 + k * 100)
        J.ecrire(i / 'courtier/appels.log', ''.join([
            '2026-10-13 08:40:00\tscribe\tarchives\tsupprimer\tancienne note\tREFUSÉ\taction absente des droits attribués\n',
            '2026-10-13 09:20:00\tvigie\tarchives\tlister\t\taccepté\tquatre archives disponibles\n',
            *[f'2026-10-13 09:{m}:00\tvigie\tequipe\tdemandes\t\taccepté\tdeux demandes à relire\n' for m in ('30', '35', '40', '45')],
            '2026-10-13 09:50:00\tscribe\tcarnet\tlire\tréunion du matin\taccepté\tcompte rendu disponible\n',
        ]))
        env.pop('BERGER_HERDR_SOCKET', None)
        rendus = J.executer(i, env, "out = {}\nfor w in (80, 140):\n    for n in ('accueil', 'colonnes', 'courtier'):\n        out[f'{n}-{w}'] = g['VUES'][n].rendre(w, 40)\nprint(json.dumps(out, ensure_ascii=False))")
        return {n: '\n'.join(re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', l).replace(str(i), '<installation>').replace(str(i.parent), '<maison>') for l in ls) + '\n' for n, ls in rendus.items()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sortie', type=Path, help='dossier neuf pour les six rendus texte')
    a = p.parse_args()
    if a.sortie.exists(): p.error('le dossier de sortie doit être neuf (aucun écrasement)')
    rendus = generer()
    a.sortie.mkdir(parents=True)
    for n, t in rendus.items(): (a.sortie / f'{n}.txt').write_text(t, encoding='utf-8')
    print('Six rendus fictifs créés dans ' + str(a.sortie))


if __name__ == '__main__': main()
