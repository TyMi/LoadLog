import re
from pathlib import Path

import pytest

MANUAL = Path(__file__).resolve().parents[2] / "docs" / "manual"


def read(lang):
    return (MANUAL / lang / "index.html").read_text(encoding="utf-8")


def test_manual_languages_have_same_structure():
    de, en = read("de"), read("en")
    ids = lambda html: re.findall(r'<section id="([^"]+)"', html)  # noqa: E731
    imgs = lambda html: re.findall(r'<img src="([^"]+)"', html)  # noqa: E731
    assert ids(de) == ids(en) and len(ids(de)) >= 10
    assert [i.replace("/de/", "/en/") for i in imgs(de)] == imgs(en)  # je Sprache eigene Screenshots, gleiche Reihenfolge


@pytest.mark.parametrize("lang", ["de", "en"])
def test_manual_internal_links_and_images_resolve(lang):
    html = read(lang)
    anchors = set(re.findall(r'id="([^"]+)"', html))
    for a in re.findall(r'href="#([^"]+)"', html):
        assert a in anchors, a
    for src in re.findall(r'<img src="([^"]+)"', html):
        assert (MANUAL / lang / src).resolve().is_file(), src
    for alt in re.findall(r'<img [^>]*alt="([^"]*)"', html):
        assert alt.strip()
    assert (MANUAL / "style.css").is_file()


def test_manual_images_exist_in_both_languages_and_nothing_is_unused():
    used = {Path(m).as_posix() for lang in ("de", "en") for m in re.findall(r'<img src="\.\./img/([^"]+)"', read(lang))}
    on_disk = {p.relative_to(MANUAL / "img").as_posix() for p in (MANUAL / "img").rglob("*.png")}
    assert used == on_disk


def test_manual_names_the_current_version():
    from loadlog.api import MANUAL_VERSION

    assert f"LoadLog {MANUAL_VERSION}.x" in read("de") and f"LoadLog {MANUAL_VERSION}.x" in read("en")
    assert f"Version {MANUAL_VERSION}" in (MANUAL / "index.html").read_text(encoding="utf-8")
