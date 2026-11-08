# Mise à jour d'un moteur sans casser Berger : admission automatique d'une version équivalente — spec courte (02/11/2026)

Règle de go : cas 1, une règle d'admission des agents stricts (droits). Demande du propriétaire du 02/11, qui pose la question :
« notre système est modulaire, pourquoi il casse si maj d'un moteur ? ».

## Constat

Le 01/11, `mise` a mis à jour les moteurs du portable sans prévenir :
- **Claude 2.1.316 : NON ADMIS**, pour la seule raison qu'il n'avait pas de liste fermée. Il n'avait aucun outil nouveau.
- **Codex 0.166.0 : NON ADMIS**, sur une vraie évasion (13) : un sous-agent lit le dossier d'un autre agent.

Le refus de Codex 0.166.0 est juste. Le refus de Claude 2.1.316 est un faux blocage. Il a fallu une demande de fusion
(n° 127 hier, une autre aujourd'hui) pour recopier une liste identique.

## Comportement

1. **Admission par équivalence, dans le contrat (`tests/contrat-moteur.py`).** Une version sans liste fermée est ADMISE
   automatiquement si toutes les conditions suivantes sont réunies :
   - toutes les autres conditions du contrat sont vertes ;
   - la seule ligne rouge du contrat est (12) « pas de liste fermée » ;
   - pour Codex, (13) est verte ;
   - jugée avec la **liste de référence**, c'est-à-dire la liste fermée de la version la plus récente du dépôt, (12) serait
     entièrement verte :
     - aucun outil inconnu ;
     - aucun outil web ;
     - le témoin positif montre bien les outils web quand le refus de Berger est levé (le même calcul qu'avec une liste
       exacte) ;
     - mêmes `types`, `web` et `si_13`.
   - La ligne (12) devient alors verte : « ✓ (12) liste fermée : admis par équivalence avec <moteur> <version de
     référence> (sha256 <8>), contrat du <date> ».
2. **Où vit la décision : seulement dans le verdict de l'installation.**
   - Le verdict est `tests/contrats/<moteur>-<version>.txt`, qui est hors dépôt et déjà écrit par le contrat.
   - **Aucune liste n'est écrite.** Le dépôt ne garde que des listes relues. Le verdict nomme la liste de référence et son
     empreinte.
   - `verdict_moteur` accepte ce verdict seulement si la liste de référence existe encore dans le dépôt avec la même
     empreinte. Sinon, le verdict est « à rejouer ».
   - Une équivalence ne sert jamais de référence à une autre : la référence est toujours une liste relue du dépôt.
3. **Traçabilité.** Chaque admission par équivalence émet une alerte JAUNE (« <moteur> <v> admis par équivalence avec
   <ref> : liste à ajouter au dépôt »). Le gardien (Master) livre ensuite la copie de la liste par une demande de fusion
   ordinaire, comme la n° 127. L'alerte disparaît quand la liste exacte existe.
4. **Ce qui ne change pas.**
   - Un outil nouveau, un outil web, une évasion (13) ou un témoin incomplet donnent NON ADMIS et une alerte ROUGE ;
     c'est le propriétaire qui tranche, comme aujourd'hui.
   - Aucune admission par équivalence sans contrat complet joué sur CETTE version, chez l'utilisateur.
5. **Plus de mise à jour silencieuse.**
   - Doc (manuel « À la mise à jour d'un moteur » et `docs/install.md`) : figer les versions des moteurs dans `mise` (ou npm,
     avec la mise à jour automatique coupée), et jouer le contrat avant de lancer un agent strict.
   - Alerte JAUNE quand la version installée d'un moteur n'a pas encore de verdict, c'est-à-dire avant que le contrat soit
     joué. Elle est calculée en local, sans réseau.
   - Hors périmètre : une alerte « nouvelle version disponible », qui demanderait un appel au registre npm (règle de go,
     cas 5). Elle viendra plus tard, sur demande.

## Refus

- Pas d'équivalence avec une liste mal formée, ni avec une liste d'un autre moteur.
- Pas d'équivalence si une seule autre condition est rouge ou non mesurable.
- Pas d'équivalence à partir d'un verdict ancien : seul le contrat joué sur cette version compte.

## Tests (sans moteur ni réseau)

1. Version sans liste et outils inclus dans la liste de référence : ADMIS, (12) « admis par équivalence », alerte jaune.
2. Un outil nouveau, un outil web, ou un témoin positif incomplet : NON ADMIS, outils nommés.
3. Codex avec (13) rouge : NON ADMIS, même si les outils sont identiques.
4. Liste de référence modifiée ou retirée après le verdict : « à rejouer ».
5. Liste exacte ajoutée au dépôt : l'alerte jaune disparaît, et le verdict reste valable.
6. Version installée sans verdict : alerte jaune « contrat à jouer ».

Doc : manuel, `docs/install.md`, CHANGELOG [Unreleased].
