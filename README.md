# submission-gate

**Which startup directories forbid automated submission, in their own words.**

Every curated list of "places to submit your startup" tells you the price, the
domain rating and whether the backlink is dofollow. None of them tells you
whether the site's own rules allow a script to post the form at all. That is
the column this repository measures.

Measured on **22 September 2026** against the 86 destinations of type
`directory` and pricing `free` in the public [Submitlist
catalog](https://github.com/alvinunreal/awesome-submitlist) (CC0, synced
2026-09-21), deduplicated to **84 hosts**.

| Verdict | Hosts |
|---|---|
| Terms read, nothing forbids automated submission | 16 |
| **Forbidden** | **23** |
| Undetermined by this probe | 45 |

The 23 break down as:

| How it is closed | Hosts |
|---|---|
| `robots.txt` disallows the submission path itself, for `User-agent: *` | 5 |
| A prohibited-activities clause covering **automated use or submission** | 7 |
| A prohibited-activities clause covering **automated collection** only | 11 |

The last row matters, and it is why the numbers are split: a clause that
forbids scraping does not forbid filing a listing. Merging the two would have
turned 12 into 23, and 23 is the number that reads better.

## The 5 closed by robots.txt

`alternativeto.net/manage-item/`, `app.g2digitalmarkets.com/get-listed/start`,
`pmo.selecthub.com/claim-your-product/`,
`publishing-center.softonic.com/home`, `www.ventureradar.com/add_company`.

The form is open, the robots file is not. A submission tool that never reads
`robots.txt` sees five open doors here.

## The 45 undetermined are a limit of this probe, not a property of those sites

26 of them serve a homepage whose HTML links no legal page at all, because the
footer is built client-side. 19 link something that turned out not to be a
legal document. This tool reads served HTML and does not run JavaScript. A
number that is my own limit is not a measurement, so it is reported separately
instead of being folded into "no restriction found".

## How a verdict is reached

1. `robots.txt` for the submission path, before anything else.
2. The site root, from which the terms URL is **derived out of the anchors**.
   It is never guessed. A guessed `/terms` once landed on the profile page of a
   user whose handle was literally `terms`, and the probe returned green.
3. The document must look like a legal text (length plus a count of legal
   markers) before any verdict is rendered, because a 404, a login wall and a
   profile page all return zero clauses, and zero reads as permission.
4. Clause matching searches for the **governing sentence up to 2500 characters
   backwards**. In a bulleted prohibition list the verb appears once and
   governs twenty items. The first version of this script used a 180-character
   window and returned PERMITTED on a site whose section 6 says, in plain
   English, "Engaging in any automated use of the system, such as using scripts
   to send comments or messages". The governing phrase was 585 characters away.

All 18 terms clauses in `data/gate-2026-09-22.json` were read by hand, with the
quote and its distance from the governing sentence kept in the file, before any
of these numbers were published.

## Run it

```sh
python3 submission_gate.py <host> [submission-path]   # one verdict, JSON
python3 submission_gate.py lot hosts.txt out.json     # a list, one host per line
python3 submission_gate.py canari                     # three real cases, opposite outcomes
```

No dependencies beyond the Python standard library. The comments in the source
are in French; the output is not.

## Data

`data/gate-2026-09-22.json` carries every host, its verdict, the terms URL that
was derived, the quoted clause and the governing phrase, so any row can be
checked against the source.

Licensed MIT. The measurement is free to reuse with attribution.

Made while measuring what it actually takes to get a thing in front of
strangers. The measurements that are not free, and the two defects found in
them, are listed at
[emelinedb26-wq.github.io/listwright](https://emelinedb26-wq.github.io/listwright/).
