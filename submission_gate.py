#!/usr/bin/env python3
"""conditions -- DERIVER l URL des conditions depuis la racine, puis trancher.

Pourquoi cet outil existe, campagne 03 tour 61.

Trois fautes de la meme famille, trois tours d affilee, toutes du genre
"j ai devine une URL au lieu de la lire" :

  T55 : `cgu-verdict https://ko-fi.com/terms` rend vert sur 4503 caracteres.
        Ce n etait pas un document de conditions, c etait la page de PROFIL
        d un createur dont le pseudo est litteralement "terms". La vraie page,
        `more.ko-fi.com/terms`, liee depuis la racine, porte une clause
        BLOQUANTE. cgu-verdict a ferme ce trou en exigeant des marqueurs
        juridiques, mais il ne sait toujours pas TROUVER la bonne page.
  T60 : j ai devine la cible du POST de correction libhunt a partir de l id
        -> 404. Lue dans le formulaire -> 200.
  T60 : l URL /terms de libhunt, elle, je l avais DERIVEE du lien de la
        racine, et c est le seul des trois gestes qui a marche du premier coup.

Donc la derivation devient un script, pas un rappel (lecon 12 : une lecon
dans mon prompt n empeche pas sa faute, seul un refus en code l arrete).

Ce qu il fait, dans cet ordre :

  1. robots.txt de l hote, lu AVANT tout le reste. Un `Disallow: /` ferme la
     porte et rien ne la rouvre (T33 : reddit.com).
  2. la racine, dont il EXTRAIT les ancres de nature juridique. Aucune URL
     n est fabriquee : si la racine ne lie rien, le verdict est INDETERMINE.
  3. chaque candidate, passee au meme garde-fou que cgu-verdict (marqueurs
     juridiques, longueur), puis aux motifs de risque.

REFUS EN CODE :
  1. aucune ancre juridique dans la racine          -> INDETERMINE
  2. aucune candidate ne passe les marqueurs        -> INDETERMINE
  3. robots.txt interdit le chemin vise             -> INTERDIT
  4. une clause bloquante sur l automatisation      -> INTERDIT
Un hote qui ne rend pas PERMIS ne se lit pas. INDETERMINE n est pas PERMIS.

Usage :
  conditions <hote> [chemin_vise]     le verdict, JSON
  conditions lot <liste> <sortie>     un hote (et son chemin) par ligne
  conditions canari                   trois cas REELS, issues OPPOSEES
"""
import html
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ICI = os.path.dirname(os.path.abspath(__file__))
_voisin = os.path.join(ICI, "cgu-verdict")
if not os.path.exists(_voisin):
    _voisin = os.path.join(ICI, "cgu_verdict.py")
_spec = importlib.util.spec_from_loader(
    "cguv", importlib.machinery.SourceFileLoader("cguv", _voisin))
cguv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cguv)

UA = cguv.UA

# Une ancre est juridique par son TEXTE ou par son HREF. Les deux sont
# mesures : un site qui ecrit "Legal" sans le mot terms dans l URL existe.
MOTS_ANCRE = re.compile(
    r"terms|conditions|legal|tos\b|policy|policies|guidelines|"
    r"mentions|cgu|cgv|aup|acceptable use", re.I)
RANG = [
    (re.compile(r"terms[-_ /]?(of[-_ /]?(service|use))?|conditions|cgu|tos\b|aup|acceptable", re.I), 0),
    (re.compile(r"legal|mentions", re.I), 1),
    (re.compile(r"guidelines|policy|policies", re.I), 2),
]


def _rang(txt, href):
    s = (txt or "") + " " + (href or "")
    for motif, r in RANG:
        if motif.search(s):
            return r
    return 3


def _corps(url, accept="text/html,application/xhtml+xml"):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Accept": accept})
    with urllib.request.urlopen(req, timeout=60) as r:
        brut = r.read()
        codage = (r.headers.get("Content-Encoding") or "").lower()
        final = r.geturl()
    if codage == "gzip":
        import gzip as _g
        brut = _g.decompress(brut)
    elif codage == "deflate":
        import zlib as _z
        brut = _z.decompress(brut, -_z.MAX_WBITS)
    return brut.decode("utf-8", "replace"), final


def ancres(hote):
    """Les URL de conditions LIEES par la racine. Aucune n est fabriquee."""
    page, final = _corps("https://%s/" % hote)
    vues, sortie = set(), []
    for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href, txt = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        txt = re.sub(r"\s+", " ", html.unescape(txt)).strip()
        if not MOTS_ANCRE.search(txt + " " + href):
            continue
        url = urllib.parse.urljoin(final, html.unescape(href))
        if not url.startswith("http") or url in vues:
            continue
        vues.add(url)
        sortie.append({"url": url, "ancre": txt, "rang": _rang(txt, href)})
    sortie.sort(key=lambda a: (a["rang"], len(a["url"])))
    return sortie


def robots(hote, chemin):
    """Refus 3. Un robots.txt qui ferme le chemin ferme la porte."""
    rp = urllib.robotparser.RobotFileParser()
    try:
        corps, _ = _corps("https://%s/robots.txt" % hote, accept="text/plain")
    except Exception as e:
        return {"lu": False, "raison": str(e)[:120],
                "autorise": None, "autorise_etoile": None}
    rp.parse(corps.splitlines())
    cible = urllib.parse.urljoin("https://%s/" % hote, chemin or "/")
    return {"lu": True, "octets": len(corps),
            "autorise": rp.can_fetch(UA, cible),
            "autorise_etoile": rp.can_fetch("*", cible)}


# C03-T61, et c est la faute que cet outil a commise au tour meme ou il est ne.
# Premiere sortie sur `uneed.best` : verdict PERMIS. Relecture a la main des
# 13 092 caracteres : section "6. Prohibited Activities", "You agree not to
# engage in any of the following prohibited activities", puis une LISTE ou
# figure mot pour mot "Engaging in any automated use of the system, such as
# using scripts" et "Using bots, scripts, or automated tools". La phrase qui
# interdit est a 585 caracteres du motif, ma fenetre en faisait 180, donc zero
# clause trouvee, et zero se lit comme une autorisation. C est le faux negatif
# par DISTANCE, troisieme de la famille apres celui par langue (C02-T2) et
# celui par mauvaise cible (C03-T55).
#
# Une liste d interdits n est pas de la prose : le verbe gouverne vingt items
# et ne se repete pas. Donc on cherche la phrase gouvernante EN ARRIERE, loin,
# et on assume l asymetrie : un faux positif coute une porte, un faux negatif
# coute la campagne.
PORTEE_ARRIERE = 2500
PORTEE_AVANT = 300


def portee_interdictive(t, debut, fin):
    """La phrase interdictive la plus proche qui GOUVERNE ce motif, ou None."""
    gauche = max(0, debut - PORTEE_ARRIERE)
    avant = t[gauche:debut]
    dernier = None
    for m in cguv.BLOQUANT.finditer(avant):
        dernier = m
    if dernier is not None:
        return {"phrase": dernier.group(0),
                "distance": len(avant) - dernier.end()}
    apres = t[fin:fin + PORTEE_AVANT]
    m = cguv.BLOQUANT.search(apres)
    if m:
        return {"phrase": m.group(0), "distance": -m.start()}
    return None


def juger(hote, chemin=None, limite=6):
    out = {"hote": hote, "chemin_vise": chemin or "/", "verdict": "INDETERMINE",
           "robots": None, "ancres_vues": 0, "candidates": [], "clauses": []}
    out["robots"] = robots(hote, chemin)
    if out["robots"]["lu"] and out["robots"]["autorise_etoile"] is False:
        out["verdict"] = "INTERDIT"
        out["refus_3"] = "robots.txt ferme %s" % (chemin or "/")
        return out
    try:
        liens = ancres(hote)
    except Exception as e:
        out["refus_1"] = "racine illisible : %s" % str(e)[:160]
        return out
    out["ancres_vues"] = len(liens)
    if not liens:
        out["refus_1"] = "la racine ne lie aucune page de nature juridique"
        return out

    retenue = None
    for a in liens[:limite]:
        fiche = {"url": a["url"], "ancre": a["ancre"]}
        # C03-T61, seconde faute du meme tour : je verifiais robots.txt sur le
        # chemin de SOUMISSION, puis j allais chercher la racine et les pages
        # de conditions sans le redemander. Un robots.txt qui ferme /legal et
        # ouvre /submit existe. On redemande, par URL.
        rc = robots(urllib.parse.urlparse(a["url"]).netloc,
                    urllib.parse.urlparse(a["url"]).path or "/")
        fiche["robots"] = rc.get("autorise_etoile")
        if rc["lu"] and rc["autorise_etoile"] is False:
            fiche["etat"] = "ROBOTS_FERME"
            out["candidates"].append(fiche)
            continue
        try:
            t = cguv.texte(a["url"])
        except Exception as e:
            fiche["etat"] = "ILLISIBLE : %s" % str(e)[:120]
            out["candidates"].append(fiche)
            continue
        try:
            marqueurs = cguv.exiger_document_de_conditions(t)
        except cguv.PasUnDocument as e:
            fiche["etat"] = "PAS_UN_DOCUMENT"
            fiche["detail"] = str(e)[:160]
            out["candidates"].append(fiche)
            continue
        fiche["etat"] = "DOCUMENT"
        fiche["caracteres"] = len(t)
        fiche["marqueurs"] = len(marqueurs)
        out["candidates"].append(fiche)
        if retenue is None:
            retenue = (a["url"], t)

    if retenue is None:
        out["refus_2"] = ("aucune des %d candidates n est un document de "
                          "conditions" % len(out["candidates"]))
        return out

    url, t = retenue
    out["document"] = url
    out["caracteres"] = len(t)
    bloquantes = []
    for libelle, motifs in cguv.RISQUES:
        for motif in motifs:
            trouve = False
            for m in re.finditer(motif, t, re.I):
                porte = portee_interdictive(t, m.start(), m.end())
                if porte is None:
                    continue
                bloquantes.append({
                    "risque": libelle.split(" \u2014 ")[0], "motif": motif,
                    "gouverne_par": porte["phrase"], "distance": porte["distance"],
                    "extrait": t[max(0, m.start() - 120): m.end() + 220].strip()})
                trouve = True
                break
            if trouve:
                break
    out["clauses"] = bloquantes
    auto = [c for c in bloquantes if c["risque"].startswith("COLLECTE")]
    out["verdict"] = "INTERDIT" if auto else "PERMIS"
    if auto:
        out["refus_4"] = auto[0]["extrait"][:300]
    return out


def canari():
    """Deux cas REELS, issues OPPOSEES (lecon 7). Un detecteur qui ne rend
    qu une valeur est indistinguable d un detecteur casse (lecon 8)."""
    cas = [
        ("reddit.com", "/", "INTERDIT",
         "T33 : le robots.txt de reddit dit Disallow: / . Elle reste fermee."),
        ("libhunt.com", "/repo/submit", "PERMIS",
         "T60 : CGU lues en entier a la main, rien contre l automatisation."),
        ("uneed.best", "/submit-a-tool", "INTERDIT",
         "T61 : le cas qui a pris cet outil en faute. robots.txt ouvert, CGU "
         "lisibles, et section 6 qui interdit 'any automated use of the "
         "system'. La phrase gouvernante est a 585 caracteres du motif : une "
         "fenetre de 180 rendait PERMIS."),
    ]
    vus, ok, det = set(), True, []
    for hote, chemin, attendu, pourquoi in cas:
        try:
            v = juger(hote, chemin)["verdict"]
        except Exception as e:
            v = "EXCEPTION:%s" % str(e)[:80]
        vus.add(v)
        bon = v == attendu
        ok = ok and bon
        det.append({"hote": hote, "attendu": attendu, "rendu": v,
                    "passe": bon, "pourquoi": pourquoi})
    if len(vus) < 2:
        ok = False
        det.append({"note": "une seule valeur rendue sur deux cas opposes : "
                            "detecteur indistinguable d un detecteur casse"})
    return {"canari": "PASSE" if ok else "ECHOUE", "cas": det}


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 1
    if a[0] == "lot":
        # Le cimetiere se relit, il ne se devine pas (lecon 9). Une liste
        # d hotes, un verdict chacun, et le JSON complet sur la sortie.
        hotes = [l.strip().split() for l in open(a[1]) if l.strip()]
        res = []
        for i, ligne in enumerate(hotes):
            hote = ligne[0]
            chemin = ligne[1] if len(ligne) > 1 else None
            try:
                v = juger(hote, chemin)
            except Exception as e:
                v = {"hote": hote, "chemin_vise": chemin, "verdict": "EXCEPTION",
                     "refus_1": str(e)[:200]}
            res.append(v)
            print("%2d/%d %-26s %-12s %s" % (
                i + 1, len(hotes), hote, v["verdict"],
                v.get("document") or v.get("refus_1") or v.get("refus_2")
                or v.get("refus_3") or ""), file=sys.stderr)
            time.sleep(1.0)
        json.dump(res, open(a[2], "w"), indent=1, ensure_ascii=False)
        return 0
    if a[0] == "canari":
        r = canari()
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return 0 if r["canari"] == "PASSE" else 3
    r = juger(a[0], a[1] if len(a) > 1 else None)
    print(json.dumps(r, indent=1, ensure_ascii=False))
    return 0 if r["verdict"] == "PERMIS" else 2


if __name__ == "__main__":
    sys.exit(main())
