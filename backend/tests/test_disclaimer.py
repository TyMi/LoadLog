"""Schutz vor versehentlichem Entfernen: Der Haftungsausschluss muss in allen Fassungen vorhanden sein.

Geprüft werden stabile Kernaussagen, nicht der genaue Wortlaut. Ob die Formulierung zur Änderung passt, bleibt eine Prüfung von Hand.
"""

import re
from pathlib import Path

import pytest

from loadlog import i18n

ROOT = Path(__file__).resolve().parents[2]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))  # HTML-Tags und Umbrüche glätten


DE_CORE = ("keine Laborierungsentwicklung", "keine Ladedaten", "Wiederladen ist gefährlich", "allein verantwortlich", "wie besehen",
           "Produkthaftungsgesetz", "Leben, Körper oder Gesundheit")
EN_CORE = ("not a tool for developing loads", "no load recommendations", "Reloading is dangerous", "solely responsible", "as is",
           "product liability", "life, body or health")


def test_readme_has_scope_and_disclaimer_in_german_and_english():
    readme = squash(text("README.md"))
    de, en = readme.split("## English", 1)
    for phrase in DE_CORE:
        assert phrase in de, f"README (Deutsch): {phrase!r} fehlt"
    for phrase in EN_CORE:
        assert phrase in en, f"README (English): {phrase!r} fehlt"
    assert "fiktiv" in de and "nicht nachgeladen" in de  # Beispieldaten sind fiktiv und dürfen nicht nachgebaut werden
    assert "fictional" in en and "not be loaded" in en
    assert "LICENSE" in readme


def test_german_law_precedence_over_the_mit_clause_is_stated_everywhere():
    readme = squash(text("README.md"))
    de, en = readme.split("## English", 1)
    assert "deutsches Recht" in de and "anstelle des Gewährleistungs- und Haftungsausschlusses" in de
    assert "German law" in en and "instead of the warranty and liability disclaimer" in en
    assert "deutsches Recht" in squash(text("docs/manual/de/index.html"))
    assert "German law" in squash(text("docs/manual/en/index.html"))


@pytest.mark.parametrize("lang,core", [("de", DE_CORE), ("en", EN_CORE)])
def test_manual_has_a_disclaimer_section_and_links_to_it(lang, core):
    html = text(f"docs/manual/{lang}/index.html")
    section = re.search(r'<section id="disclaimer">(.*?)</section>', html, re.S)
    assert section, f"Handbuch {lang}: Abschnitt disclaimer fehlt"
    body = squash(section.group(1))
    for phrase in core:
        assert phrase in body, f"Handbuch {lang}: {phrase!r} fehlt"
    assert 'href="#disclaimer"' in html  # Hinweis in der Einleitung und Eintrag im Inhaltsverzeichnis
    sample = ("frei erfunden", "nicht nachgeladen") if lang == "de" else ("entirely fictional", "not be loaded")
    assert all(p in body for p in sample), f"Handbuch {lang}: Hinweis auf fiktive Beispieldaten fehlt"


def test_app_info_and_reports_carry_the_short_notice_in_both_languages():
    ts = text("frontend/src/i18n.ts")
    de = re.search(r'disclaimerShort: "([^"]+)"', ts).group(1)
    en = re.findall(r'disclaimerShort: "([^"]+)"', ts)[1]
    assert "keine Laborierungsentwicklung" in de and "Verantwortung" in de and "Gewähr" in de
    assert "not a tool for developing loads" in en and "responsible" in en and "warranty" in en
    assert "disclaimerLink" in ts
    for lang, needles in (("de", ("keine Ladeempfehlung", "Wiederlader")), ("en", ("not a load recommendation", "reloader"))):
        for needle in needles:
            assert needle in i18n.TEXTS[lang]["disclaimer"]


def test_license_files_are_present():
    assert "WITHOUT WARRANTY OF ANY KIND" in text("LICENSE") and "MIT License" in text("LICENSE")
    assert "LGPL" in text("THIRD_PARTY_NOTICES.md")
