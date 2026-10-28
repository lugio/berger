# -*- coding: utf-8 -*-
"""Validateur de schémas JSON en Python standard (spec docs/plans/2026-10-13-interface-spec.md, §3) — le sous-ensemble
dont les vues ont besoin, rien de plus : type (un nom ou une liste), properties, required, additionalProperties (false, ou le schéma des clés libres),
items, enum, maxItems, anyOf (une des branches), $ref (« #/$defs/X » dans le même fichier, « communs.schema.json#/$defs/X » dans bin/schemas/).
Les mots « x-… » (x-rendu, x-libelle, x-version) sont des annotations : ignorées par la validation.

valider(donnee, schema, racine) → [erreurs] (chemin : message), vide si conforme.
proprietes(schema, racine) → [(chemin, schéma de la propriété)] : chaque propriété déclarée, y compris dans les listes."""
import json
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parent.parent / "bin/schemas"
TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "null": type(None), "object": dict, "array": list}


def charger(f):
    return json.loads(Path(f).read_text())


def resoudre(s, racine):
    """Suit un $ref ; rend (schéma visé, racine du fichier visé)."""
    ref = s["$ref"]; fichier, _, chemin = ref.partition("#")
    if fichier: racine = charger(SCHEMAS / fichier)
    cible = racine
    for p in [x for x in chemin.split("/") if x]: cible = cible[p]
    return cible, racine


def bon_type(v, t):
    if t in ("integer", "number") and isinstance(v, bool): return False          # True n'est pas un nombre
    return isinstance(v, TYPES[t])


def valider(v, s, racine, chemin="$"):
    if "$ref" in s: s, racine = resoudre(s, racine)
    if "anyOf" in s:
        essais = [valider(v, x, racine, chemin) for x in s["anyOf"]]
        if not any(not e for e in essais): return [f"{chemin} : ne correspond à aucune forme permise ({' / '.join(e[0] for e in essais)})"]
    err = []
    if "type" in s:
        types = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(bon_type(v, t) for t in types): return [f"{chemin} : type {type(v).__name__}, attendu {'|'.join(types)}"]
    if "enum" in s and v not in s["enum"]: err.append(f"{chemin} : {v!r} hors de {s['enum']}")
    if isinstance(v, dict) and "properties" in s:
        for k in s.get("required", []):
            if k not in v: err.append(f"{chemin} : champ requis absent « {k} »")
        if s.get("additionalProperties") is False:
            err += [f"{chemin} : champ non déclaré « {k} »" for k in v if k not in s["properties"]]
        for k, sous in s["properties"].items():
            if k in v: err += valider(v[k], sous, racine, f"{chemin}.{k}")
    if isinstance(v, dict) and isinstance(s.get("additionalProperties"), dict):          # dictionnaire à clés libres
        libres = s["additionalProperties"]
        for k, x in v.items():
            if k not in s.get("properties", {}): err += valider(x, libres, racine, f"{chemin}.{k}")
    if isinstance(v, list):
        if "maxItems" in s and len(v) > s["maxItems"]: err.append(f"{chemin} : {len(v)} éléments, {s['maxItems']} au plus")
        if "items" in s:
            for n, x in enumerate(v): err += valider(x, s["items"], racine, f"{chemin}[{n}]")
    return err


def proprietes(s, racine, chemin="$", suivre_refs=False):
    """Chaque propriété déclarée : (chemin, schéma). Les listes ajoutent « [] » au chemin. Un $ref n'est suivi que si
    suivre_refs (les types communs sont rendus d'un bloc : leurs champs ne sont pas ceux de la vue)."""
    if "$ref" in s:
        if not suivre_refs: return []
        s, racine = resoudre(s, racine)
    out = []
    for x in s.get("anyOf", []): out += proprietes(x, racine, chemin, suivre_refs)        # forme objet d'un champ « ou null »
    for k, sous in s.get("properties", {}).items():
        out.append((f"{chemin}.{k}", sous)); out += proprietes(sous, racine, f"{chemin}.{k}", suivre_refs)
    if "items" in s: out += proprietes(s["items"], racine, f"{chemin}[]", suivre_refs)
    return out


def valeurs(v, chemin):
    """Toutes les valeurs de `v` au chemin « $.a[].b » (une par élément de liste)."""
    parts = chemin.replace("[]", ".[]").split(".")[1:]
    cour = [v]
    for p in parts:
        suite = []
        for x in cour:
            if p == "[]" and isinstance(x, list): suite += x
            elif isinstance(x, dict) and p in x: suite.append(x[p])
        cour = suite
    return cour
