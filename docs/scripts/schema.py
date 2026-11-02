#!/usr/bin/env python3
"""Generate or check the two README diagrams. Standard library, no network."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START = '<!-- BEGIN BERGER DIAGRAM -->'
END = '<!-- END BERGER DIAGRAM -->'
DIAGRAMS = {
    'en': (
        'Agent files ----> Berger ----> official CLI',
        '                    ^              |',
        '                    |              v',
        '                  Herdr         agent work',
        '                                   |',
        '                         file mailbox (berger-outil)',
        '                                   |',
        '                              trusted broker',
        '                         (approval when required)',
        '                                   |',
        '                           configured tools',
    ),
    'fr': (
        'Fichiers agent -> Berger ----> CLI officielle',
        '                    ^              |',
        '                    |              v',
        '                  Herdr      travail de l’agent',
        '                                   |',
        '                       courrier fichier (berger-outil)',
        '                                   |',
        '                            courtier de confiance',
        '                         (validation si nécessaire)',
        '                                   |',
        '                            outils configurés',
    ),
}


def render(langue):
    return '```text\n' + '\n'.join(DIAGRAMS[langue]) + '\n```'


def update(texte, langue):
    if texte.count(START) != 1 or texte.count(END) != 1:
        raise ValueError('expected exactly one pair of diagram markers')
    avant, reste = texte.split(START)
    _, apres = reste.split(END)
    return avant + START + '\n' + render(langue) + '\n' + END + apres


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    args = parser.parse_args()
    erreurs = 0
    for langue, nom in (('en', 'README.md'), ('fr', 'README.fr.md')):
        fichier = ROOT / nom
        texte = fichier.read_text()
        attendu = update(texte, langue)
        if args.write:
            fichier.write_text(attendu)
            print(f'generated {nom}')
        elif texte != attendu:
            erreurs += 1
            print(f'ÉCHEC diagram out of date: {nom}')
        else:
            print(f'ok diagram: {nom}')
    return 1 if erreurs else 0


if __name__ == '__main__':
    raise SystemExit(main())
