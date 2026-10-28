#!/usr/bin/env python3
"""Régressions du lot vues : données fictives, horloge figée et faux Herdr uniquement."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json
import re
import sys
import tempfile
from pathlib import Path

import _jeu_vues as J

ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + texte)


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True)
    ag = i / 'agents/vigie'
    J.ecrire(ag / 'pending/piege-equipe-runpy.md', 'type: memoire\npourquoi: sonde technique\n---\nSonde\n')
    J.ecrire(ag / 'pending/sonde.md', 'type: test\n---\nSonde\n')
    J.ecrire(ag / 'pending/memoire-utile.md', 'type: memoire\npourquoi: durable\n---\nUne proposition utile.\n')
    for n in range(6):
        J.ecrire(i / f'equipes/demo/demandes/lot-{n}.json', json.dumps({'sujet': f'lot-{n}', 'etat': 'fusionnée', 'fusionnee': f'2026-10-13T09:{n:02d}'}), 5+n)
    J.ecrire(ag / 'a-lire/resolu.md', '# Ancienne validation\nDécision attendue : redémarrer\nDécision liée : validation:4\n')
    J.ecrire(ag / 'a-lire/fusion.md', '# Ancienne fusion\nDécision attendue : fusionner\nDécision liée : fusion:demo/lot-5\n')
    J.ecrire(ag / 'a-lire/non-resolu.md', '# Autre décision\nDécision attendue : choisir la durée\nDécision liée : validation:1\n')
    J.ecrire(ag / 'a-lire/invalide.md', '# Lien inconnu\nDécision attendue : vérifier\nDécision liée : validation:inconnue\n')
    J.ecrire(ag / 'a-lire/livraison.md', '# Livraison récente\nTout est livré.\n')
    J.ecrire(ag / 'a-lire/manuelle.md', '# Choix archivé\nDécision attendue : choisir\nDécision résolue : choix reçu\n')
    J.ecrire(i / 'courtier/validations/8.fait.json', json.dumps({'etat': 'ÉCHEC exécution'}))
    J.ecrire(ag / 'a-lire/echec.md', '# Action en échec\nDécision attendue : reprendre\nDécision liée : validation:8\n')
    J.ecrire(i / 'courtier/derniere-sauvegarde.txt', 'archive chiffrée sauvegardée ' * 8 + 'fin sauvegarde réussie')
    appels = [f'2026-10-13 09:{n:02d}:00\tvigie\tlecture\tdemandes\t\taccepté\trien\n' for n in range(12)]
    appels.insert(0, '2026-10-13 08:00:00\tscribe\tlecture\tverbe-long\t' + 'argument-très-long-'*10 + '\tREFUSÉ\taccès refusé\n')
    J.ecrire(i / 'courtier/appels.log', ''.join(appels))
    x = J.executer(i, env, """
v = g['VUES']; dec = g['decisions']()
out = {'dec': dec, 'acc': v['accueil'].donnees(), 'tab': g['tableau_donnees']('vigie')}
out['rendus'] = {str(w): {n: v[n].rendre(w, 40) for n in ('accueil', 'courtier', 'tokens', 'checklists', 'colonnes')} for w in (80, 140)}
out['vides'] = v['checklists'].rendu_texte({'dossier': '/chemin/personnel', 'listes': []}, 80, 24)
out['depassements'] = [(w, n, g['vlen'](l), g['ANSI'].sub('', l)) for w, vues in out['rendus'].items() for n, ls in vues.items() for l in ls if g['vlen'](l) > int(w)]
print(json.dumps(out, ensure_ascii=False))
""")
    net = lambda ls: '\n'.join(re.sub(r'\x1b\[[0-9;]*m', '', l) for l in ls)
    dire(not x['depassements'], f"largeurs 80/140 respectées : {x['depassements'][:4]}")
    attente = [d for d in x['dec'] if d['genre'] == 'a_decider']
    dire(not any('Ancienne' in d['detail'] for d in attente), 'résolutions liées à la validation exécutée et à la fusion')
    dire(any('Autre décision' in d['detail'] for d in attente) and any('Lien inconnu' in d['detail'] for d in attente), 'rapport récent et lien invalide ne résolvent pas une décision')
    dire(any('Action en échec' in d['detail'] for d in attente) and not any('Choix archivé' in d['detail'] for d in attente), 'échec conservé et résolution manuelle reconnue')
    dire(not any('piege' in a['texte'] or 'sonde' in a['texte'] for a in x['tab']['attend']), 'sondes et traces techniques absentes des attentes')
    dire(any(d['genre'] == 'proposition' for d in x['dec']), 'propositions mémoire visibles dans Décisions')
    dire(x['acc'].get('attentes') == x['dec'], 'Accueil partage la liste de Décisions')
    dire(len(x['tab']['attend']) == sum(d['pour'] == 'toi' and d['agent'] == 'vigie' for d in x['dec']), 'Tableau agent utilise les mêmes catégories pour son agent')
    accueil = net(x['rendus']['140']['accueil'])
    dire('fusionnés (7)' in accueil and 'lot-5' in accueil and 'lot-0' not in accueil, 'trois dernières fusions, dans leur ordre chronologique, total visible')
    dire('état inconnu' in accueil and 'état inc…' not in accueil, 'statut inconnu explicite sans ellipse')
    courtier = net(x['rendus']['80']['courtier'])
    dire('ARRÊTÉ' in courtier and 'en service' not in courtier, 'courtier réellement inactif toujours signalé arrêté')
    dire(courtier.index('ÉCRITURES À VALIDER') < courtier.index('SAUVEGARDE') < courtier.index('archive chiffrée'), 'sauvegarde dans une section indépendante')
    dire('Équipe demo' in accueil, 'nom de projet conservé dans le titre de section')
    singuliers = J.executer(i, env, """
v = g['VUES']['courtier']; d = v.donnees()
d['droits'] = 1; d['aujourdhui'] = {'appels': 1, 'refus': 1}
print(json.dumps(v.rendu_texte(d, 80, 40)))
""")
    dire('1 droit attribué' in net(singuliers) and '1 appel · 1 refusé' in net(singuliers), 'courtier : compteurs au singulier')
    dire('fin sauvegarde réussie' in ' '.join(courtier.split()), 'résultat final de sauvegarde conservé après un message long')
    dire('×12' in courtier and courtier.index('accès refusé') < courtier.index('×12'), 'répétitions groupées et refus du jour en priorité')
    dire('/chemin/personnel' not in net(x['vides']) and '- [ ]' in net(x['vides']), 'état vide neutre avec exemple court')
    largeurs = J.executer(i, env, """
d = {'dossier': 'listes', 'listes': [{'titre': 'Un titre de checklist très long ' * 8, 'faites': 0, 'total': 1, 'termine': False, 'restantes': [{'section': None, 'libelle': 'Préparer le rapport'}]}]}
print(json.dumps([g['vlen'](l) for l in g['VUES']['checklists'].rendu_texte(d, 80, 40)]))
""")
    dire(max(largeurs) <= 80, 'titre de checklist long borné à 80 colonnes')
    # Toutes les livraisons restent visibles même avec une hauteur réduite.
    lignes = J.executer(i, env, "print(json.dumps(g['VUES']['colonnes'].rendre(80, 24)))")
    dire(len(lignes) <= 24 and 'LIVRÉ' in net(lignes) and 'lot-5' in net(lignes), 'livraisons accessibles dans le premier écran étroit')
    lignes = J.executer(i, env, "print(json.dumps(g['VUES']['colonnes'].rendre(140, 24)))")
    dire(len(lignes) <= 24 and 'lot-5' in net(lignes), 'livraisons accessibles dans le premier écran large')
    # Un fort volume d'activité ne doit pas effacer les refus et les livraisons.
    J.ecrire(i / 'courtier/appels.log', '2026-10-13 08:00:00\tscribe\tlecture\tinconnu\t\tREFUSÉ\trefus ancien du jour\n' +
             '2026-10-13 09:00:00\tvigie\tlecture\tdemandes\t\taccepté\trien\n' * 201)
    lignes = J.executer(i, env, "print(json.dumps(g['VUES']['courtier'].rendre(80, 40)))")
    dire('refus ancien du jour' in net(lignes), 'refus du jour préservé au-delà de 200 appels')
    lignes = J.executer(i, env, """
v = g['VUES']['colonnes']; d = v.donnees()
d['cartes'] = [{'colonne': 'cours', 'titre': f'Carte {n}', 'lignes': [], 'vif': False} for n in range(24)] + [{'colonne': 'livre', 'titre': 'Livraison importante', 'lignes': [], 'vif': False}]
print(json.dumps(v.rendu_texte(d, 80, 24)))
""")
    dire(len(lignes) <= 24 and 'Livraison importante' in net(lignes), 'budget de hauteur réservé aux livraisons même après 24 cartes')

print(f'---- {ko} échec(s)')
sys.exit(bool(ko))
