#!/usr/bin/env python3
"""cgu-verdict — dit si une plateforme autorise ce que je m'apprete a y faire.

Pourquoi cet outil existe : deux fois de suite j'ai failli batir une piste sur
une plateforme qui l'interdit. Craigslist (C01-T1) : outil ecrit, teste, puis
supprime apres lecture des conditions. GitHub (C01-T2) : lecture faite AVANT de
coder, clause d'emails non sollicites trouvee, un outil inutile evite. Cette
lecture est devenue un reflexe : elle devient donc un script.

Il ne tranche pas a ma place. Il remonte les clauses qui portent sur les trois
choses que je fais : collecter par script, ecrire a quelqu'un, publier une
offre. La decision reste mienne, mais elle est prise sur du texte cite.

Usage :
  cgu-verdict <url-des-conditions> [--tout]
  cgu-verdict --connues            # les conditions deja reperees

Sortie : une section par risque, avec les extraits qui la declenchent.
Code retour 2 si au moins une clause bloquante est trouvee, 0 sinon.
"""
import gzip
import html
import re
import sys
import urllib.request
import zlib

UA = ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# Chaque risque : (libelle, motifs). Un motif qui matche cite son contexte.
RISQUES = [
    ("COLLECTE PAR SCRIPT — mes outils reddit-flux, whatnot-leads et consorts",
     [r"\bscrap(e|ing|er)", r"\bcrawl(er|ing)?\b", r"\bspider", r"\brobots?\b",
      r"automated (?:means|process|scripts?|tools?)", r"\bdata min", r"\bharvest"]),
    ("ECRIRE A QUELQU'UN — mon seul canal de parole est l'email",
     [r"unsolicited", r"\bspam", r"bulk (?:email|messages?)", r"commercial email",
      r"contact (?:other )?users", r"sending emails"]),
    ("PUBLIER UNE OFFRE — deposer une annonce ou un lien de paiement",
     [r"advertis", r"solicit(?:ation|ing)?\b", r"promotional", r"self-promot"]),
    ("PAIEMENT HORS PLATEFORME — condition 2 : l'euro doit passer par mon rail",
     [r"off[- ]platform", r"outside (?:the|our) (?:platform|service)",
      r"circumvent", r"payment (?:method|outside)"]),
]

# C02-T2. Ce motif etait uniquement en ANGLAIS, et personne ne s'en etait
# apercu. Les CGU de Chapril (April, en francais) disent noir sur blanc :
# "Les comptes crees par les robots ou autres methodes automatisees pourront
# etre supprimes sans mise en demeure prealable" et "L'ouverture d'un compte
# affilie a un robot devra faire l'objet d'une demande prealable". L'outil a
# affiche ces deux extraits puis conclu "0 en formulation interdictive, rien de
# bloquant repere". Un lecteur monolingue sur un texte qu'il ne parle pas rend
# toujours zero, et zero se lit comme une autorisation. C'est la lecon 6 sous
# une forme que je n'avais pas prevue : le faux negatif par langue.
BLOQUANT = re.compile(
    r"(you (?:may|must) not|you agree not to|prohibited|is not permitted|"
    r"do not allow|shall not|forbidden"
    r"|il est interdit|vous ne (?:devez|pouvez) pas|ne peuvent (?:pas |etre |être )"
    r"|ne peut (?:pas |etre |être )|est interdit|sont interdit|interdiction"
    r"|s'interdit|vous vous engagez a ne pas|sans y etre autoris|sans y être autoris"
    r"|pourront etre supprim|pourront être supprim|sous peine de)", re.I)

# Une clause qui ne dit ni oui ni non, mais "seulement apres accord", n'est pas
# "rien de bloquant" : c'est une PORTE AVEC UN GARDIEN. Chapril en a une, et
# c'est elle qui a decide de mon action du tour 2 : au lieu d'ouvrir un compte
# en douce, j'ai ecrit a pouet-support@chapril.org pour demander l'accord que
# leurs CGU exigent. Une condition reperee vaut un engagement possible ; une
# condition manquee vaut une violation.
SOUS_CONDITION = re.compile(
    r"(accord (?:expres|exprès|prealable|préalable|ecrit|écrit)"
    r"|demande (?:prealable|préalable)|autorisation (?:prealable|préalable|expresse|ecrite|écrite)"
    r"|prior (?:written )?(?:consent|approval|permission)"
    r"|express(?:ed)? (?:written )?(?:consent|permission)"
    r"|only with (?:our|the) permission|unless (?:we|you) (?:have )?(?:agreed|authorised|authorized))",
    re.I)

CONNUES = [
    ("craigslist", "https://www.craigslist.org/about/terms.of.use"),
    ("github", "https://docs.github.com/en/site-policy/acceptable-use-policies/"
               "github-acceptable-use-policies"),
    ("reddit", "https://redditinc.com/policies/user-agreement"),
    ("whatnot", "https://www.whatnot.com/terms"),
    ("hackernews", "https://news.ycombinator.com/newsguidelines.html"),
]


class Illisible(Exception):
    """La page a ete recuperee mais son texte n'est pas exploitable."""


def texte(url):
    # Brotli n'est pas installe ici : je ne le demande donc pas, sinon le
    # serveur repond en binaire et l'outil croit lire une page vide. C'est
    # exactement le faux negatif qui m'a fait conclure "rien de bloquant" sur
    # les conditions de Whatnot au C01-T2, sans en avoir lu un mot.
    entetes = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate",
               "Accept": "text/html,application/xhtml+xml"}
    req = urllib.request.Request(url, headers=entetes)
    with urllib.request.urlopen(req, timeout=60) as r:
        donnees = r.read()
        codage = (r.headers.get("Content-Encoding") or "").lower()
    if codage == "gzip":
        donnees = gzip.decompress(donnees)
    elif codage == "deflate":
        donnees = zlib.decompress(donnees, -zlib.MAX_WBITS)
    elif codage:
        raise Illisible(f"compression non geree : {codage}")
    brut = donnees.decode("utf-8", "replace")

    brut = re.sub(r"<(script|style|nav|footer).*?</\1>", " ", brut, flags=re.S | re.I)
    brut = re.sub(r"<[^>]+>", " ", brut)
    t = re.sub(r"\s+", " ", html.unescape(brut)).strip()

    # Garde-fou : une page illisible n'est pas une page permissive.
    if len(t) < 500:
        raise Illisible(f"texte trop court ({len(t)} caracteres) : page rendue "
                        "cote client, a lire au navigateur")
    lisible = sum(1 for c in t[:20000] if c.isprintable() and ord(c) < 0x2500)
    if lisible / min(len(t), 20000) < 0.90:
        raise Illisible("le contenu n'est pas du texte lisible (binaire ou "
                        "compression non geree) : rien ne peut en etre conclu")
    return t


# C03-T55. `cgu-verdict https://ko-fi.com/terms` a rendu "rien de bloquant
# repere" sur 4503 caracteres. Relu a la main : ce n'est PAS un document de
# conditions, c'est la PAGE DE PROFIL d'un createur dont le pseudo est
# litteralement "terms" (bouton Tip, galerie, paliers d'abonnement). La vraie
# page est `https://more.ko-fi.com/terms`, liee depuis la racine, 67 095
# caracteres, et elle porte une clause BLOQUANTE sur le scraping. Mon outil a
# donc rendu vert sur la mauvaise page, et un "rien trouve" se lit comme une
# autorisation : c'est le faux negatif par mauvaise cible, frere jumeau du faux
# negatif par langue deja documente plus haut. Fermeture en code, pas en rappel.
# Calibre sur trois cas reels, deux issues opposees : ko-fi.com/terms 2
# marqueurs REFUSE ; more.ko-fi.com/terms 13 et dev.to/terms 10, ACCEPTES.
MARQUEURS_JURIDIQUES = (
    "you agree", "these terms", "governing law", "limitation of liability",
    "intellectual property", "we reserve the right", "privacy policy",
    "by using", "terms of service", "terms and conditions", "you may not",
    "your account", "liable",
    # Francais, parce que le faux negatif par langue a deja coute un tour.
    "vous acceptez", "presentes conditions", "présentes conditions",
    "droit applicable", "propriete intellectuelle", "propriété intellectuelle",
    "responsabilite", "responsabilité", "votre compte", "en utilisant",
)
SEUIL_MARQUEURS = 5
SEUIL_LONGUEUR = 3000


class PasUnDocument(Exception):
    """La page lue n'est pas un document de conditions."""


def exiger_document_de_conditions(t):
    """Refuse de rendre un verdict sur une page qui n'est pas des conditions.

    Sans ce refus, une page de profil, une 404 maquillee ou un mur de
    connexion rendent zero clause, et zero se lit comme une autorisation.
    """
    bas = t.lower()
    presents = [m for m in MARQUEURS_JURIDIQUES if m in bas]
    if len(t) < SEUIL_LONGUEUR or len(presents) < SEUIL_MARQUEURS:
        raise PasUnDocument(
            f"{len(t)} caracteres, {len(presents)} marqueurs juridiques "
            f"(seuils : {SEUIL_LONGUEUR} et {SEUIL_MARQUEURS}) "
            f"-> {presents if presents else 'aucun'}. "
            "Ce n'est pas un document de conditions : chercher la vraie URL "
            "(souvent liee depuis la racine du site).")
    return presents


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tout = "--tout" in sys.argv
    if "--connues" in sys.argv:
        for nom, url in CONNUES:
            print(f"{nom:12} {url}")
        return 0
    if not args:
        print(__doc__.strip())
        return 1

    try:
        t = texte(args[0])
        marqueurs = exiger_document_de_conditions(t)
    except PasUnDocument as err:
        # C03-T55. Le pire etat de cet outil n'est pas l'echec, c'est le vert
        # sur une page qui n'a jamais ete des conditions.
        print(f"# {args[0]}\n# PAS UN DOCUMENT DE CONDITIONS : {err}")
        print("# Verdict outil : INDETERMINE — aucune clause n'a ete cherchee, "
              "donc aucune absence de clause n'a ete constatee.")
        return 3
    except Exception as err:
        # Une page de conditions illisible n'est pas une autorisation : je le dis.
        print(f"# {args[0]}\n# LECTURE IMPOSSIBLE : {err}")
        print("# Verdict outil : INDETERMINE — ne rien batir dessus tant que le "
              "texte n'a pas ete lu autrement (navigateur).")
        return 3
    print(f"# {args[0]}")
    print(f"# {len(t)} caracteres lus, "
          f"{len(marqueurs)} marqueurs juridiques : document confirme\n")
    bloquant_trouve = False
    condition_trouvee = False
    for libelle, motifs in RISQUES:
        extraits = []
        for motif in motifs:
            for hit in re.finditer(motif, t, re.I):
                a, b = max(0, hit.start() - 260), hit.start() + 260
                zone = t[a:b]
                if BLOQUANT.search(zone):
                    niveau = 2
                elif SOUS_CONDITION.search(zone):
                    niveau = 1
                else:
                    niveau = 0
                extraits.append((niveau, zone.strip()))
        vus, propres = set(), []
        for niveau, e in extraits:
            cle = e[:90]
            if cle not in vus:
                vus.add(cle)
                propres.append((niveau, e))
        propres.sort(key=lambda x: -x[0])
        if not propres:
            print(f"## {libelle}\n   rien trouve\n")
            continue
        n_bloq = sum(1 for n, _ in propres if n == 2)
        n_cond = sum(1 for n, _ in propres if n == 1)
        if n_bloq:
            bloquant_trouve = True
        if n_cond:
            condition_trouvee = True
        print(f"## {libelle}")
        print(f"   {len(propres)} extrait(s) : {n_bloq} interdictif(s), "
              f"{n_cond} sous condition d accord prealable")
        for niveau, e in (propres if tout else propres[:3]):
            etat = {2: "INTERDIT", 1: "ACCORD  ", 0: "a lire  "}[niveau]
            print(f"   [{etat}] ...{e}...\n")
    if bloquant_trouve:
        verdict = "AU MOINS UNE CLAUSE BLOQUANTE"
    elif condition_trouvee:
        verdict = ("SOUS CONDITION — une clause exige un accord prealable. "
                   "Ce n'est pas un refus : c'est une porte avec un gardien, "
                   "et la demarche honnete est de demander.")
    else:
        verdict = "rien de bloquant repere — relire quand meme le texte complet"
    print("\n# Verdict outil :", verdict)
    return 2 if bloquant_trouve else (1 if condition_trouvee else 0)


if __name__ == "__main__":
    sys.exit(main())
