# Hinweise zu Bibliotheken Dritter / Third-party notices

LoadLog selbst steht unter der [MIT-Lizenz](LICENSE). Es nutzt die folgenden Bibliotheken, die jeweils unter ihren eigenen Lizenzen stehen.
Die vollständigen Lizenztexte liegen in den installierten Paketen (`*.dist-info/licenses/`) bzw. im Quellcode der jeweiligen Projekte.

*LoadLog itself is licensed under the [MIT License](LICENSE). It uses the libraries below, each under its own license. The full license
texts are shipped in the installed packages (`*.dist-info/licenses/`) and in the respective source repositories.*

## LGPL-3.0: py_ballisticcalc

LoadLog verwendet die Bibliothek **py_ballisticcalc** (Version 3.1.1, GNU Lesser General Public License Version 3,
<https://github.com/o-murphy/py-ballisticcalc>) für die Widerstandstabellen G1 und G7 bei der Berechnung des ballistischen Koeffizienten
(`backend/src/loadlog/ballistics.py`). Die Bibliothek wird **unverändert** und als **austauschbare Python-Abhängigkeit** installiert, ihr Code
ist nicht in LoadLog kopiert. Du kannst sie durch eine andere (auch eigene, geänderte) Version ersetzen: Version in `backend/pyproject.toml` bzw.
`backend/uv.lock` anpassen und das Image neu bauen (`docker compose up -d --build`); in einer eigenen, nicht schreibgeschützten Installation
genügt `pip install -U py_ballisticcalc` oder `pip install <Fork>`. Die Lizenztexte der LGPL-3.0 und der GPL-3.0, auf die sie verweist,
liegen in `licenses/LGPL-3.0.txt` und `licenses/GPL-3.0.txt` (im Image unter `/app/licenses/`) sowie im installierten Paket
(`py_ballisticcalc-<Version>.dist-info/licenses/LICENSE`).

*LoadLog uses the library **py_ballisticcalc** (version 3.1.1, GNU Lesser General Public License v3) for the G1/G7 drag tables. It is installed
unmodified as a replaceable Python dependency; its code is not copied into LoadLog. You can replace it with another (also modified) version:
change the version in `backend/pyproject.toml` / `backend/uv.lock` and rebuild the image (`docker compose up -d --build`); in your own,
writable installation `pip install -U py_ballisticcalc` or `pip install <fork>` is enough. The texts of the LGPL-3.0 and of the GPL-3.0 it
refers to are in `licenses/LGPL-3.0.txt` and `licenses/GPL-3.0.txt` (in the image under `/app/licenses/`) and in the installed package
(`py_ballisticcalc-<version>.dist-info/licenses/LICENSE`).*

## Python (Laufzeit / runtime)

Alle Pakete der Laufzeit-Abhängigkeiten laut `backend/uv.lock` (ohne Entwicklungswerkzeuge). Die Lizenzen stammen aus den Metadaten der
installierten Pakete. *All runtime packages according to `backend/uv.lock` (without development tools). Licenses are taken from the metadata of the
installed packages.*

| Paket / Package | Version | Lizenz / License |
|---|---|---|
| fastapi | 0.162.0 | MIT |
| starlette | 1.10.0 | BSD-3-Clause |
| uvicorn | 0.54.0 | BSD-3-Clause |
| pydantic, pydantic-core | 2.14.1 / 2.50.1 | MIT |
| annotated-types, annotated-doc, typing-inspection, deprecated | 0.8.0 / 0.0.5 / 0.4.4 / 3.0.0 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| zopfli | 0.4.3 | Apache-2.0 |
| anyio, h11, wrapt | 4.15.1 / 0.16.0 / 2.5.1 | MIT / MIT / BSD-2-Clause |
| click, idna, markupsafe, pycparser | 8.5.0 / 3.20 / 3.0.4 / 3.12 | BSD-3-Clause |
| typing-extensions | 4.16.0 | PSF-2.0 |
| jinja2 | 3.1.6 | BSD-3-Clause |
| weasyprint | 70.0 | BSD-3-Clause |
| cssselect2, pydyf, tinycss2, webencodings | 0.10.1 / 0.13.0 / 1.5.1 / 0.6.1 | BSD-3-Clause |
| tinyhtml5, fonttools, brotli, brotlicffi (plattformabhängig / platform dependent) | 2.1.0 / 4.68.0 / 1.2.1 | MIT |
| cffi | 2.1.1 | MIT-0 |
| pillow | 13.0.0 | MIT-CMU (HPND) |
| py_ballisticcalc | 3.1.1 | **LGPL-3.0** (siehe oben / see above) |
| pyphen (über weasyprint / via weasyprint) | 0.18.1 | GPL-2.0+ / LGPL-2.0+ / MPL-1.1 (Dreifachlizenz; LoadLog nutzt sie unter LGPL/MPL / multi-licensed, used under LGPL/MPL) |

`pyphen` bringt Silbentrennungs-Wörterbücher mit, die eigene Lizenzen tragen (überwiegend LGPL, GPL, MPL); sie liegen im installierten Paket
unter `pyphen/dictionaries/`. *`pyphen` ships hyphenation dictionaries with their own licenses (mostly LGPL, GPL, MPL); they are in the installed
package under `pyphen/dictionaries/`.*

Die exakten Versionen stehen in `backend/uv.lock`. *The exact versions are in `backend/uv.lock`.*

## JavaScript (im ausgelieferten Bundle / in the shipped bundle)

| Paket / Package | Lizenz / License |
|---|---|
| preact | MIT (Copyright Jason Miller) |

Alle übrigen npm-Pakete (Vite, Vitest, TypeScript, jsdom u. a.) sind reine Build- und Testwerkzeuge und werden nicht ausgeliefert.
*All other npm packages (Vite, Vitest, TypeScript, jsdom, etc.) are build and test tools only and are not shipped.*

## Docker-Image / Docker image

Das Image (`Dockerfile`) enthält neben den obigen Paketen **Debian-Pakete** (u. a. Pango, HarfBuzz, GLib, FreeType, Fribidi, `fonts-dejavu-core`)
und das Python-Basis-Image mit unterschiedlichen Lizenzen (u. a. GPL, LGPL, MIT, PSF). Die Lizenztexte liegen im Image unter
`/usr/share/doc/<Paket>/copyright`; den Quellcode der Debian-Pakete erhältst du über `apt-get source <Paket>` bzw. <https://sources.debian.org>.

*The image contains, besides the packages above, **Debian packages** (e.g. Pango, HarfBuzz, GLib, FreeType, Fribidi, `fonts-dejavu-core`) and
the Python base image under various licenses (e.g. GPL, LGPL, MIT, PSF). License texts are in the image at `/usr/share/doc/<package>/copyright`;
source code for the Debian packages is available via `apt-get source <package>` or <https://sources.debian.org>.*

## Marken / Trademarks

LabRadar und Gordon's Reloading Tool sind Marken bzw. Produkte ihrer jeweiligen Inhaber. LoadLog ist ein unabhängiges, inoffizielles Projekt
ohne Verbindung zu ihnen. *LabRadar and Gordon's Reloading Tool are trademarks or products of their respective owners. LoadLog is an
independent, unofficial project not affiliated with them.*
