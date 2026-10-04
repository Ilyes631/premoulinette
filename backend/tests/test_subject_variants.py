"""Markdown and plain-text subjects (French wording) parsed by the same generic heuristics."""
from __future__ import annotations

import pytest

from premoulinette.subject.extract import SubjectExtractionError, detect_media_type, extract_document
from premoulinette.subject.heuristic import parse_heuristic
from premoulinette.subject.pipeline import parse_subject

MD = """\
# TP 2 — Station météo

**Cours :** Programmation S1

## Rendu

Votre dépôt doit respecter l'arborescence suivante :

```
.gitignore
Meteo/
├── conversions.py
├── alerte.py
├── bonus/
│   └── record.py
└── accueil.py
```

Les fichiers de `bonus/` sont facultatifs. Votre dépôt doit contenir un fichier `.gitignore`.

Ne poussez pas de dossiers `__pycache__` ni de fichiers `.pyc` : ils sont pénalisés.

## Consignes

Fonctions autorisées : `print()`, `input()`, `len()`, `int()`, `str()`

Fonctions interdites : `max()`, `min()`, `sum()`

Aucun import n'est autorisé.

## Exercice 1 — Conversion

Fichier : `Meteo/conversions.py`

```python
def to_fahrenheit(celsius: float) -> float:
```

La fonction renvoie `celsius * 9 / 5 + 32`.

```python
to_fahrenheit(0) -> 32.0
to_fahrenheit(100) == 212.0
to_fahrenheit(-40)  # -40.0
```

## Exercice 2 — Alerte

Fichier : `alerte.py`

```python
def niveau_alerte(vent: int) -> str:
```

- `vent < 50` -> `"vert"`
- `50 <= vent < 90` -> `"orange"`
- sinon -> `"rouge"`

```python
niveau_alerte(10) -> 'vert'
niveau_alerte(60) -> 'orange'
niveau_alerte(120) == 'rouge'
```

## Exercice 3 — Accueil

Fichier : `Meteo/accueil.py`

Le programme demande le nom avec l'invite `"Votre nom : "` puis la ville avec `"Ville ? "`.

```
$ python3 accueil.py
Votre nom : Alice
Ville ? Paris
Bonjour Alice de Paris !
```

## Bonus

### Bonus 1 — Record

Fichier : `Meteo/bonus/record.py`

```python
def record(a: int, b: int) -> int:
```

```python
record(3, 7) -> 7
```
"""

TXT = """\
TP 3 - Bibliotheque

Consignes generales

Fonctions autorisees : print(), input(), len()
Fonctions interdites : sorted(), sum()
Aucun import n'est autorise.

Exercice 1 - Emprunt

Fichier : Biblio/emprunt.py

    def peut_emprunter(livres: int, limite: int) -> bool:

Renvoie True si livres < limite, sinon False.

    peut_emprunter(2, 5) -> True
    peut_emprunter(5, 5) == False

Exercice 2 - Amende

Fichier : Biblio/amende.py

    def amende(jours: int) -> float:

La fonction renvoie `jours * 0.5`.

    amende(4) -> 2.0
    amende(0) == 0.0

Exercice 3 - Caisse

Fichier : Biblio/caisse.py

Le programme demande le titre avec "Titre : " puis la duree avec "Duree (jours) : ".

    $ python3 caisse.py
    Titre : Dune
    Duree (jours) : 3
    Livre Dune emprunte pour 3 jours.
    $ python3 caisse.py
    Titre : Ubik
    Duree (jours) : 0
    Duree invalide.

Bonus 1 - Total

Fichier : Biblio/bonus/total.py

    def total(a: int, b: int) -> int:

    total(1, 2) -> 3
"""


def _fn(spec, name):
    return next(f for e in spec.exercises for f in e.functions if f.name == name)


# ---------------------------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def md_spec():
    doc = extract_document(MD.encode("utf-8"), "tp2.md")
    assert doc.media_type == "markdown"
    return parse_heuristic(doc).spec


def test_md_exercises_and_bonus(md_spec):
    assert md_spec.metadata.title == "TP 2 — Station météo"
    assert md_spec.metadata.course == "Programmation S1"
    assert [(e.id, e.kind, e.bonus) for e in md_spec.exercises] == [
        ("conversions", "functions", False), ("alerte", "functions", False),
        ("accueil", "script", False), ("record", "functions", True),
    ]
    # "Fichier : alerte.py" is resolved against the tree
    assert md_spec.exercise("alerte").file_path == "Meteo/alerte.py"


def test_md_structure(md_spec):
    files = {f.path: f for f in md_spec.structure.files}
    assert set(files) == {".gitignore", "Meteo/conversions.py", "Meteo/alerte.py", "Meteo/bonus/record.py",
                          "Meteo/accueil.py"}
    assert files["Meteo/bonus/record.py"].bonus and not files["Meteo/bonus/record.py"].required
    assert files["Meteo/alerte.py"].required
    assert md_spec.structure.require_gitignore is True
    assert md_spec.structure.forbidden_patterns_are_errors is True


def test_md_constraints(md_spec):
    c = md_spec.global_constraints
    assert c.allowed_builtins == ["print", "input", "len", "int", "str"]
    assert c.forbidden_builtins == ["max", "min", "sum"]
    assert c.allowed_imports == []


def test_md_examples_all_syntaxes(md_spec):
    f = _fn(md_spec, "to_fahrenheit")
    assert f.reference == "celsius * 9 / 5 + 32"
    assert [(t.id, t.args, t.expected_return) for t in f.tests] == [
        ("to_fahrenheit#ex1", ["0"], "32.0"), ("to_fahrenheit#ex2", ["100"], "212.0"),
        ("to_fahrenheit#ex3", ["-40"], "-40.0"),
    ]
    a = _fn(md_spec, "niveau_alerte")
    assert [(r.when, r.returns) for r in a.rules] == [
        ("vent < 50", '"vert"'), ("50 <= vent < 90", '"orange"'), (None, '"rouge"'),
    ]
    assert [t.expected_return for t in a.tests] == ["'vert'", "'orange'", "'rouge'"]
    assert [(t.args, t.expected_return) for t in _fn(md_spec, "record").tests] == [(["3", "7"], "7")]


def test_md_script(md_spec):
    s = md_spec.exercise("accueil").script
    assert s.prompts == ["Votre nom : ", "Ville ? "]
    (t,) = s.tests
    assert t.id == "accueil#session1"
    assert t.stdin == "Alice\nParis\n"
    assert t.expected_stdout == "Votre nom : Ville ? Bonjour Alice de Paris !\n"
    assert t.origin.confidence == 0.7     # inputs recovered from the quoted prompts


# ---------------------------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def txt_spec():
    doc = extract_document(TXT.encode("utf-8"), "tp3.txt")
    assert doc.media_type == "text"
    return parse_heuristic(doc).spec


def test_txt_exercises(txt_spec):
    assert txt_spec.metadata.title == "TP 3 - Bibliotheque"
    assert [(e.id, e.kind, e.bonus, e.file_path) for e in txt_spec.exercises] == [
        ("emprunt", "functions", False, "Biblio/emprunt.py"),
        ("amende", "functions", False, "Biblio/amende.py"),
        ("caisse", "script", False, "Biblio/caisse.py"),
        ("total", "functions", True, "Biblio/bonus/total.py"),
    ]


def test_txt_constraints_on_consecutive_lines(txt_spec):
    c = txt_spec.global_constraints
    assert c.allowed_builtins == ["print", "input", "len"]
    assert c.forbidden_builtins == ["sorted", "sum"]
    assert c.allowed_imports == []


def test_txt_rules_reference_and_examples(txt_spec):
    f = _fn(txt_spec, "peut_emprunter")
    assert [(r.when, r.returns) for r in f.rules] == [("livres < limite", "True"), (None, "False")]
    assert [(t.args, t.expected_return) for t in f.tests] == [(["2", "5"], "True"), (["5", "5"], "False")]
    a = _fn(txt_spec, "amende")
    assert a.reference == "jours * 0.5"
    assert [(t.args, t.expected_return) for t in a.tests] == [(["4"], "2.0"), (["0"], "0.0")]


def test_txt_indented_sessions_are_dedented(txt_spec):
    s = txt_spec.exercise("caisse").script
    assert s.prompts == ["Titre : ", "Duree (jours) : "]
    assert [(t.id, t.stdin, t.expected_stdout) for t in s.tests] == [
        ("caisse#session1", "Dune\n3\n", "Titre : Duree (jours) : Livre Dune emprunte pour 3 jours.\n"),
        ("caisse#session2", "Ubik\n0\n", "Titre : Duree (jours) : Duree invalide.\n"),
    ]


# ---------------------------------------------------------------------------------------------
# Misc extraction
# ---------------------------------------------------------------------------------------------


def test_media_type_detection():
    assert detect_media_type(b"%PDF-1.4 ...", "x.txt") == "pdf"
    assert detect_media_type(b"# t", "s.MD") == "markdown"
    assert detect_media_type(b"<!DOCTYPE html><html></html>", "subject") == "html"
    assert detect_media_type(b"hello", "notes.txt") == "text"


def test_cp1252_subject_is_decoded_with_warning():
    doc = extract_document("TP\n\nFonctions interdites : abs() (évitez-les)\n".encode("cp1252"), "s.txt")
    assert any("Windows-1252" in w for w in doc.warnings)
    assert "évitez" in doc.text


def test_corrupt_pdf_is_a_value_error():
    with pytest.raises(ValueError):
        extract_document(b"%PDF-1.4 not really a pdf", "s.pdf")
    assert issubclass(SubjectExtractionError, ValueError)


def test_empty_subject_warns():
    doc, result = parse_subject(b"", "empty.txt")
    assert doc.blocks == []
    assert any("No exercise" in w for w in result.warnings)


def test_html_exercise_without_file_is_ignored_and_bonus_heading_detected():
    html = """<html><head><title>T</title></head><body><h1>T</h1>
    <h2>Exercise 1 - Add</h2><p>File: <code>add.py</code></p>
    <pre><code>def add(a: int, b: int) -&gt; int:</code></pre>
    <pre><code>&gt;&gt;&gt; add(1, 2)
3</code></pre>
    <h2>Notes</h2><p>Nothing here.</p>
    <h2>Optional</h2><h3>Mul</h3><p>File: <code>mul.py</code></p>
    <pre><code>def mul(a: int, b: int) -&gt; int:</code></pre>
    </body></html>"""
    spec = parse_heuristic(extract_document(html.encode(), "s.html")).spec
    assert [(e.id, e.bonus) for e in spec.exercises] == [("add", False), ("mul", True)]
    assert spec.exercises[0].functions[0].tests[0].expected_return == "3"
