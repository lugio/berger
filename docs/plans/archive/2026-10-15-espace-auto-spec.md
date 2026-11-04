# Espace auto : le planificateur met chaque espace ouvert en conformité (2026-10-15, sujet 2/3)

Go du propriétaire le 15/10, niveau C : des règles fixes (R1…R7, `espace_voulu(a)`, sujet 1, déjà dans `main`) disent quel
espace chaque agent devrait avoir ; ce sujet-ci les **applique** : le planificateur compare l'espace réel (Herdr) à l'espace
voulu, ajoute ce qui manque et ferme ce qui n'est plus voulu.

## Constat

`espace_voulu(a)` calcule l'espace attendu, mais rien ne l'applique : un onglet Équipe fermé par `fermer_mission` alors
qu'un développeur est encore ouvert ne revient pas ; un panneau du métier ajouté dans `[espaces.<a>]` n'apparaît qu'après
`berger refaire-espace` ; un onglet Missions resté après une mission ne part jamais.

## Comportement

`conformer_espaces(maintenant=None)` (bin/berger), appelée par `planificateur()` à chaque passage (chaque minute), après les
titres et avant la supervision. Pour chaque agent dont l'espace est **ouvert** (son `workspace` de `.herdr.json` existe dans
Herdr), au plus **une passe toutes les 5 min** (`BERGER/.espace-auto.json` : date de la dernière passe par agent),
`conformer_espace(a)` :

1. lit l'espace réel : onglets et panneaux de son workspace (`herdr tab list`, `pane list`) et les clés de `.herdr.json` ;
2. reconnaît chaque onglet réel par ce que Berger y a enregistré, sinon par son libellé (avec ou sans icône) :
   **Travail** (contient sa conversation, ou le panneau `encours`, ou s'appelle Travail / Mission), **Fiche** (`fiche`,
   ou le libellé), un onglet du rôle **R4** (`onglet-<lab>-*`, ou le libellé), **Missions/Équipe** (`missions.tab`, ou
   le libellé). Tout autre onglet est **inconnu** : jamais touché ;
3. **ajoute** ce qui manque :
   - un onglet voulu absent (Fiche, onglet du rôle, Missions/Équipe dont la condition est **vraie**), avec ses panneaux ;
   - dans un onglet connu, un panneau voulu absent (`encours`, panneaux du métier, `journal` de R2, suivi des missions,
     éléments d'un onglet du rôle) ;
   - un onglet connu dont le libellé diffère du voulu est renommé (icône, « Mission », « Équipe ») ;
   - le `journal` (R2) et le suivi des missions ne sont pas ajoutés si l'onglet a déjà un panneau non enregistré, ni
     conversation (espaces créés avant que Berger les enregistre) : pas de doublon ;
4. **ferme** ce qui n'est plus voulu :
   - l'onglet Missions/Équipe **écarté** par R7 avec une date de fin **connue** de plus de 24 h ;
   - un onglet du rôle retiré de `[espaces.<a>].onglets` (reconnu par ses clés `onglet-<lab>-*`) ;
   - dans un onglet connu, un panneau enregistré dans `.herdr.json › panneaux` sous une clé que l'espace voulu n'a plus
     (ex. `domaine-1` remplacé par `cote-1`) — jamais le dernier panneau d'un onglet, et rien n'est fermé dans un onglet Travail
     sans conversation (le journal y tient sa place) ;
5. note **chaque geste** au journal de l'agent (`espace auto : ajouté … (R3 : …)` / `fermé … (R7 : …)`) et tient
   `.herdr.json` à jour.

`espace()` enregistre désormais aussi le panneau `journal` de l'onglet « Mission » (R2), pour qu'il soit reconnu.

## Jamais (refus)

- **Une conversation d'agent** : ni ouverte, ni fermée, ni relancée (`protege`). Un onglet qui en contient une n'est
  jamais fermé ; un onglet Travail absent n'est pas recréé (il faudrait démarrer un agent : `berger espace <agent>`).
  Un onglet Missions/Équipe recréé ne porte que le suivi.
- **Un onglet inconnu**, et tout panneau qu'il contient.
- **Un onglet écarté dont la date de fin est inconnue** : gardé (fermé seulement si la fin est connue et a plus de 24 h).
- **Un agent qui attend une permission** : une de ses conversations, ou une conversation hébergée dans son espace, a le
  statut Herdr `blocked` → aucun geste dans son espace pendant cette passe.
- **Herdr illisible** (aucun onglet ou aucun panneau rendu pour un espace ouvert) : aucun geste.
- **`[espaces] auto = false`** dans config.toml : aucune passe, aucun appel à Herdr (par défaut : actif).
- Un agent sans espace ouvert (ex. un développeur en mission dans l'onglet Équipe de son chef) : rien.

## Tests

`tests/espace-auto.py` (installation jetable, **faux Herdr** à état qui journalise chaque appel, jamais le vrai ; le
démarrage, l'arrêt et la relance d'un agent remplacés par des relevés qui doivent rester vides) :
- **ajout** : onglet Fiche fermé à la main → recréé ; panneau du métier ajouté dans `[espaces.<a>].a_cote` → ajouté ;
  chef avec un développeur ouvert et Équipe fermée → Équipe recréée avec le suivi seul ;
- **fermeture** : onglet Missions sans objet depuis 30 h (fin connue) → fermé ; `domaine-1` qui n'est plus voulu → fermé ;
- **conversation intacte** : aucun `pane close`/`tab close` sur une conversation, aucun démarrage ni arrêt d'agent ;
  onglet Missions qui contient encore une conversation → gardé ;
- **date inconnue gardée** : Missions écarté sans date → gardé ; sans objet depuis 2 h → gardé (R7) ;
- **onglet inconnu intact** : un onglet « Notes » et son panneau ne reçoivent aucun appel ;
- **permission** : un agent `blocked` → aucun geste ;
- **auto = false** → aucun appel à Herdr ;
- **cadence 5 min** : deuxième passe à +2 min → rien ; à +6 min → passe ;
- chaque geste noté au journal ; une deuxième passe sur un espace conforme ne fait rien (idempotence) ;
- le planificateur appelle la mise en conformité ; Herdr illisible → aucun geste ;
- `tests/regles-espace.py` reste vert (`espace()` et `ouvrir_en_mission()`, dont des morceaux sont extraits —
  `onglet_role()`, `onglet_missions()`, `pane_racine()` —, construisent toujours exactement l'espace voulu).
