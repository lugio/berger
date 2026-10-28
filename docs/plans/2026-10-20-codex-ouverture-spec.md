# Ouverture restreinte des développeurs Codex

Correctif 1b, spec révisée après les revues n° 31 et 32. Périmètre : développeurs Codex stricts seulement ; profil, droits, gardes, transport socket et chemin Claude conservés.

## Preuve du dialogue réel

Capture fournie par le propriétaire via le chef de projet le 21 octobre 2026 : Codex 0.163.0 lancé avec le CODEX_HOME de l'installation, `codex -C <dossier> -p <agent>`, profil strict généré par Berger, tmux détaché. Lignes utiles non vides, sans logo ; seul le chemin privé est remplacé par un nom neutre. Fixture : `tests/fixtures/codex-confiance-0.163.0.txt`, texte fourni reproduit tel quel :

```text
  Folder access
  /dossier/agent-essai
  Config, hooks, and exec policies from untrusted folders stay disabled. Trusted project folders can still contribute settings. Skills still load, and tools
  follow your permission settings. Opening will not change saved trust.
› 1. Open restricted
  2. Quit
  enter continue · esc quit
```

Le titre est **Folder access**. Les hypothèses antérieures « Trust this folder? » et « Trust and continue » étaient fausses pour ce lancement strict : elles ne constituent plus une preuve ni une condition acceptée.

## Comportement

Attendre l'agent nommé et son panneau. Reconnaître ensemble, dans cet ordre et une seule fois chacun : une ligne Folder access, la ligne sélectionnée `› 1. Open restricted`, une ligne `2. Quit`, puis `enter continue · esc quit`. Seules ces deux options numérotées sont admises. Une bannière avant le dialogue est permise : aucun ancrage au début absolu de l'écran. Un titre de hooks, une option isolée, une ligne manquante, un choix Quit sélectionné ou un dialogue ambigu ne reçoivent aucune touche.

Sur ce dialogue réel seulement, envoyer **Entrée**, qui valide le mode restreint déjà sélectionné. Ne jamais choisir Quit ni modifier la confiance enregistrée. Attendre ensuite l'invite au repos, puis envoyer l'invitation de mission par `agent.prompt` sur socket, sans contenu de mission en argv.

`working` confirme la réception. Au repos, un écho n'est une preuve que s'il apparaît **au-dessus de la dernière ligne d'invite** `›`/`❯`, dans l'historique soumis. La ligne d'invite elle-même, le compositeur et toutes ses lignes suivantes sont exclus de la comparaison. Sans frontière de saisie visible, aucun écho n'est présumé soumis. Les blancs sont normalisés pour comparer l'écran uniquement ; le message envoyé reste intact.

Avant le réessai unique et pendant l'attente du second tour, relire ces témoins : working ou un écho soumis terminent en succès sans exiger un retour au repos ni renvoyer le message. Sinon, deux tentatives au plus, puis erreur claire au chef sans succès annoncé ; MISSION.md est conservé pour diagnostic.

**Doublon résiduel accepté** : si le premier envoi est effectivement reçu mais ne produit aucun témoin visible (ni working observé ni écho soumis), le réessai peut dupliquer le message. Le choix est de conserver ce réessai borné pour limiter les missions perdues, sans promettre une livraison transactionnelle exactement une fois.

## Délais et preuves

Constantes de production : ouverture 60 s, réception 15 s, scrutation 0,5 s, deux tentatives maximum. Horloge monotone ; aucun délai de phase n'est réinitialisé dans sa boucle. Les appels Herdr restent bornés (CLI 20 s/appel, socket 10 s/opération) ; un appel déjà en cours peut dépasser l'échéance de phase.

Tests en mémoire rouges puis verts : texte non soumis dans la saisie et texte sans frontière d'invite ne sont pas des reçus ; un écho soumis au-dessus de l'invite et working sont reconnus. La fixture réelle est acceptée avec ou sans bannière, chaque omission d'une des quatre lignes est refusée, les hooks restent refusés. La vraie CLI mission reste couverte avec Herdr et lancement doublés : sélection Entrée seulement, réception tardive, pertes, réessai borné, faux succès de saisie refusé, argv sans texte privé et profil inchangé. L'horloge des scénarios avance par sleep simulé et leurs écrans par lectures ; la vitesse réelle des processus ne consomme pas leurs délais.

## Rejouer la capture réelle

`tests/sonde-codex-confiance.py` est une sonde manuelle pour le propriétaire **hors du bac à sable**, pas une porte ni un test automatique du moteur. Elle utilise le profil strict existant généré de l'installation et les arguments/environnement de Berger, sans régénérer ni modifier la confiance, sans envoyer de message ni de touche. Elle lance un serveur tmux privé détaché, capture l'écran, ferme sa session même en erreur, neutralise les chemins et écrit exclusivement un fichier 600 dans `.preuves/` de la copie. Elle n'affiche que le chemin de sortie et le nombre de lignes ; elle ne remplace pas une capture impossible par un écran fabriqué.

```bash
python3 tests/sonde-codex-confiance.py --installation /chemin/installation --agent agent-strict
```

Dans le bac de développement, tmux a réellement été refusé (`Operation not permitted`) avant tout lancement de Codex : aucune capture locale n'est revendiquée. La preuve réelle de cette révision est la capture fournie par le propriétaire. Les tests de transport de la sonde utilisent un double tmux et ne sont pas présentés comme une exécution réelle du moteur.

Sauvegardes de développement vérifiées avant modification, hors dépôt ; retour arrière par revert du commit de correction dans le circuit habituel de tests et fusion validée. Aucune installation effectuée par le développeur.
