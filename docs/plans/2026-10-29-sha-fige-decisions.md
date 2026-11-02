# SHA figé : décisions de suivi (29/10/2026)

Complète `docs/plans/2026-10-29-sha-fige-spec.md` (go du propriétaire n° 79), qui n'est pas modifiée : un go ne vaut que pour
la version de la spec sur laquelle il a été donné. Suivi de la demande n° 82 (installée), après les deux réserves de la relecture.

1. **Une seule attestation, du bon SHA.** La sortie d'une porte distante verte doit porter **exactement une** ligne
   `commit testé : <sha>`, avec le SHA envoyé. Plusieurs lignes d'attestation (même identiques), ou une attestation d'un autre
   SHA : porte **rouge**, et le message nomme le défaut (les lignes trouvées, ou l'autre SHA). Code : `_portes.attestation`.
   Vérifié par `tests/sha-fige.py` (point 6).
2. **Ce que vaut l'attestation.** Cette ligne est une **déclaration de l'outil**, pas une preuve infalsifiable : le courtier ne
   peut pas vérifier qu'elle dit vrai. Elle protège contre un outil qui teste **par erreur** la branche (ou un autre commit) ;
   elle ne protège **pas** contre un outil malveillant, qui pourrait l'écrire sans rien tester. La confiance reste celle donnée
   à l'outil déclaré dans `<porte>_outil` (choisi par le propriétaire dans la configuration).
3. **Commit mal formé refusé avant tout git.** `apercu_fusion` valide le commit de la demande (`sha_valide`) **avant**
   `controler` (fetch, `cat-file`…) : un nom de branche ou une option n'atteint jamais git. Vérifié par `tests/sha-fige.py` (point 6).
