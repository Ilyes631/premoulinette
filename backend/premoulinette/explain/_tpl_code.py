"""Templates for source-level diagnoses: syntax, static function checks, constraints, import side effects."""
from __future__ import annotations

import re

from premoulinette.explain._context import Ctx
from premoulinette.explain._evidence import constraint_name, detail, detail_str, found_function_name, int_list
from premoulinette.explain._markdown import block, bullets, code, join, tail_lines
from premoulinette.explain._registry import hint, template
from premoulinette.explain._tpl_runtime import exception_hint

# ---------------------------------------------------------------------------------------------
# Syntax
# ---------------------------------------------------------------------------------------------

_SYNTAX_HINTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"expected ':'"),
     "Il manque probablement les deux-points `:` à la fin d'une ligne `if`, `elif`, `else`, `for`, `while` ou `def`.",
     "A colon `:` is probably missing at the end of an `if`, `elif`, `else`, `for`, `while` or `def` line."),
    (re.compile(r"unterminated (triple-quoted )?string|EOL while scanning"),
     "Une chaîne de caractères n'est pas fermée : il manque un guillemet.",
     "A string is not closed: a quote is missing."),
    (re.compile(r"was never closed|unexpected EOF|EOF while parsing"),
     "Une parenthèse, un crochet ou une accolade ouvert(e) n'est jamais fermé(e).",
     "An opening parenthesis, bracket or brace is never closed."),
    (re.compile(r"unmatched|closing parenthesis"),
     "Une parenthèse (ou un crochet) fermante n'a pas d'ouvrante correspondante.",
     "A closing parenthesis (or bracket) has no matching opening one."),
    (re.compile(r"forgot a comma"),
     "Il manque probablement une virgule entre deux éléments.",
     "A comma is probably missing between two items."),
    (re.compile(r"Maybe you meant '==' |cannot assign to"),
     "Tu as sans doute écrit `=` (affectation) là où il faut `==` (comparaison), par exemple dans un `if`.",
     "You probably wrote `=` (assignment) where `==` (comparison) is needed, for example in an `if`."),
    (re.compile(r"invalid character"),
     "Un caractère invalide s'est glissé dans le code (par exemple des guillemets typographiques “ ” copiés depuis un document).",
     "An invalid character slipped into the code (for example typographic quotes “ ” copied from a document)."),
    (re.compile(r"invalid decimal literal"),
     "Un nom commence par un chiffre, ou il manque un opérateur entre un nombre et un nom.",
     "A name starts with a digit, or an operator is missing between a number and a name."),
    (re.compile(r"'return' outside function"),
     "Un `return` se trouve en dehors de toute fonction (souvent un problème d'indentation).",
     "A `return` is outside of any function (often an indentation problem)."),
    (re.compile(r"Missing parentheses in call to 'print'"),
     "En Python 3, `print` est une fonction : il faut des parenthèses, `print(\"...\")`.",
     "In Python 3, `print` is a function: parentheses are required, `print(\"...\")`."),
]

_INDENT_HINTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"expected an indented block"),
     "Après une ligne qui se termine par `:` (`def`, `if`, `for`...), le bloc suivant doit être **indenté** (décalé vers la droite).",
     "After a line ending with `:` (`def`, `if`, `for`...), the next block must be **indented** (shifted to the right)."),
    (re.compile(r"unexpected indent"),
     "Une ligne est indentée alors qu'elle ne devrait pas l'être (elle n'est pas dans un bloc).",
     "A line is indented although it is not inside a block."),
    (re.compile(r"unindent does not match"),
     "Une ligne revient à un niveau d'indentation qui n'existe pas plus haut (par exemple 3 espaces au lieu de 4).",
     "A line goes back to an indentation level that does not exist above (for example 3 spaces instead of 4)."),
    (re.compile(r"inconsistent use of tabs and spaces|TabError"),
     "Le fichier mélange **tabulations** et **espaces** pour indenter : Python refuse ce mélange.",
     "The file mixes **tabs** and **spaces** for indentation: Python refuses this mix."),
]


def _syntax_info(c: Ctx) -> tuple[str, int | None, int | None, str | None]:
    """(message, line, 1-based column, offending source line)."""
    exc = c.ev.exception
    message = detail_str(c.check, "message", "error") or (exc.message if exc else None) or c.check.message
    line_value = detail(c.check, "line")
    line = line_value if isinstance(line_value, int) else c.line
    col_value = detail(c.check, "col", "offset")
    col = col_value if isinstance(col_value, int) else (c.check.location.col + 1 if c.check.location and c.check.location.col is not None else None)
    text = detail_str(c.check, "text") or c.source_line()
    return message, line, col, text


def _pointer(line: int | None, text: str | None, col: int | None) -> str:
    if not text:
        return ""
    text = text.rstrip("\r\n")
    prefix = f"{line} | " if line else "| "
    out = [prefix + text]
    if col and 1 <= col <= len(text) + 1:
        out.append(" " * (len(prefix) - 2) + "| " + " " * (col - 1) + "^")
    return block("\n".join(out), "text")


def _matching_hint(c: Ctx, message: str, table: list[tuple[re.Pattern[str], str, str]]) -> str:
    for pattern, fr, en in table:
        if pattern.search(message):
            return c.t(fr, en)
    return ""


@template("syntax_error", "Erreur de syntaxe", "Syntax error")
def _syntax_error(c: Ctx) -> str:
    message, line, col, text = _syntax_info(c)
    where = c.t(f", ligne {line}", f", line {line}") if line else ""
    return join(
        c.t(
            f"Python n'arrive pas à **lire** ton fichier {c.file_code()}{where} : il contient une erreur de syntaxe. "
            "Tant qu'elle est là, **aucune** fonction de ce fichier ne peut être testée.",
            f"Python cannot **read** your file {c.file_code()}{where}: it contains a syntax error. "
            "While it is there, **no** function of this file can be tested.",
        ),
        c.t(f"Message de Python : {code(message)}", f"Python's message: {code(message)}"),
        _pointer(line, text, col),
        _matching_hint(c, message, _SYNTAX_HINTS),
        c.t("L'erreur est parfois signalée une ligne **après** l'endroit réel : regarde aussi la ligne précédente.",
            "The error is sometimes reported one line **after** the real place: also look at the previous line."),
    )


@template("indentation_error", "Erreur d'indentation", "Indentation error")
def _indentation_error(c: Ctx) -> str:
    message, line, col, text = _syntax_info(c)
    where = c.t(f", ligne {line}", f", line {line}") if line else ""
    return join(
        c.t(
            f"Python n'arrive pas à lire {c.file_code()}{where} à cause de l'**indentation** "
            "(les espaces en début de ligne). En Python, c'est l'indentation qui indique quelles lignes "
            "appartiennent à un bloc (`def`, `if`, `for`...).",
            f"Python cannot read {c.file_code()}{where} because of the **indentation** (the spaces at the "
            "start of a line). In Python, indentation tells which lines belong to a block (`def`, `if`, `for`...).",
        ),
        c.t(f"Message de Python : {code(message)}", f"Python's message: {code(message)}"),
        _pointer(line, text, col),
        _matching_hint(c, message, _INDENT_HINTS),
        c.t("Règle simple : **4 espaces** par niveau, jamais de tabulations mélangées aux espaces.",
            "Simple rule: **4 spaces** per level, never tabs mixed with spaces."),
    )


@template("encoding_error", "Encodage du fichier", "File encoding")
def _encoding_error(c: Ctx) -> str:
    return join(
        c.t(
            f"Le fichier {c.file_code()} n'est pas enregistré en **UTF-8** : Python (et la moulinette) "
            "ne peut pas le lire correctement, souvent à cause d'un caractère accentué.",
            f"The file {c.file_code()} is not saved as **UTF-8**: Python (and the grader) cannot read it "
            "correctly, often because of an accented character.",
        ),
        c.t(
            "Ré-enregistre-le en UTF-8 depuis ton éditeur (VS Code : clique sur l'encodage en bas à droite, "
            "puis *Save with Encoding* → *UTF-8*).",
            "Save it again as UTF-8 from your editor (VS Code: click the encoding in the bottom-right corner, "
            "then *Save with Encoding* → *UTF-8*).",
        ),
    )


@hint("syntax_error", "indentation_error", "encoding_error")
def _syntax_steps(c: Ctx) -> list[str]:
    _, line, _, _ = _syntax_info(c)
    at = c.t(f"à la ligne {line}", f"at line {line}") if line else c.t("à la ligne indiquée", "at the reported line")
    return [
        c.t(f"Ouvre {c.file_code()} {at} (et la ligne juste avant).", f"Open {c.file_code()} {at} (and the line just before)."),
        c.t("Compare avec le message de Python : deux-points, parenthèses, guillemets, indentation.",
            "Compare with Python's message: colons, parentheses, quotes, indentation."),
        c.t(f"Vérifie en lançant {code('python3 ' + (c.file or 'fichier.py'))} dans un terminal : il ne doit plus y avoir de `SyntaxError`.",
            f"Check by running {code('python3 ' + (c.file or 'file.py'))} in a terminal: there must be no `SyntaxError` left."),
    ]


# ---------------------------------------------------------------------------------------------
# Functions (static)
# ---------------------------------------------------------------------------------------------


def _signature(c: Ctx, *keys: str) -> str | None:
    return detail_str(c.check, *keys)


@template("missing_function", "Fonction introuvable", "Function not found")
def _missing_function(c: Ctx) -> str:
    expected = _signature(c, "expected_signature", "signature", "expected")
    return join(
        c.t(
            f"La fonction {c.fn_code()} est introuvable dans {c.file_code()}.",
            f"The function {c.fn_code()} cannot be found in {c.file_code()}.",
        ),
        c.t(
            "La moulinette importe ton fichier puis appelle la fonction **par son nom exact** : si elle n'existe pas, "
            "tous ses tests échouent.",
            "The grader imports your file and calls the function **by its exact name**: if it does not exist, all "
            "its tests fail.",
        ),
        c.t("Signature demandée :", "Required signature:") if expected else "",
        block(expected.rstrip(":") + ":", "python") if expected else "",
        c.t(
            "Vérifie aussi qu'elle est définie **au niveau principal** du fichier (pas indentée, pas à l'intérieur "
            "d'une autre fonction ni sous `if __name__ == \"__main__\":`).",
            "Also check that it is defined at the **top level** of the file (not indented, not inside another "
            "function nor under `if __name__ == \"__main__\":`).",
        ),
    )


@template("wrong_function_name", "Nom de fonction incorrect", "Wrong function name")
def _wrong_function_name(c: Ctx) -> str:
    found = found_function_name(c.check)
    found_txt = code(found) if found else c.t("une fonction au nom proche", "a function with a similar name")
    return join(
        c.t(
            f"Tu as défini {found_txt}, mais le sujet demande {c.fn_code('la fonction', 'the function')}.",
            f"You defined {found_txt}, but the subject asks for {c.fn_code('la fonction', 'the function')}.",
        ),
        c.t(
            "Le nom doit être **identique**, caractère par caractère (majuscules et `_` compris) : la moulinette "
            "appelle la fonction par son nom et ne trouvera pas la tienne.",
            "The name must be **identical**, character by character (case and `_` included): the grader calls "
            "the function by its name and will not find yours.",
        ),
        c.t("Pense à renommer aussi les endroits où tu l'appelles.", "Remember to also rename the places where you call it."),
    )


@template("function_in_wrong_file", "Fonction dans le mauvais fichier", "Function in the wrong file")
def _function_in_wrong_file(c: Ctx) -> str:
    found_file = detail_str(c.check, "found_file", "actual_file", "found_in", "found")
    expected_file = detail_str(c.check, "expected_file") or c.check.file
    found_txt = code(found_file) if found_file else c.t("un autre fichier", "another file")
    return join(
        c.t(
            f"La fonction {c.fn_code()} existe, mais dans {found_txt} au lieu de {code(expected_file or '?')}.",
            f"The function {c.fn_code()} exists, but in {found_txt} instead of {code(expected_file or '?')}.",
        ),
        c.t(
            "Pour tester cette fonction, la moulinette n'importe **que** le fichier demandé par le sujet.",
            "To test this function, the grader **only** imports the file required by the subject.",
        ),
    )


@template("wrong_param_count", "Nombre de paramètres incorrect", "Wrong number of parameters")
def _wrong_param_count(c: Ctx) -> str:
    expected = _signature(c, "expected_signature", "expected")
    actual = _signature(c, "actual_signature", "found_signature", "actual")
    sigs = bullets([
        c.t("demandé : ", "required: ") + code(expected) if expected else "",
        c.t("trouvé : ", "found: ") + code(actual) if actual else "",
    ])
    call = c.t(f" (par exemple {code(c.ev.call)})", f" (for example {code(c.ev.call)})") if c.ev.call else ""
    subject = c.t(f"La fonction {code(c.fn)}", f"The function {code(c.fn)}") if c.fn else c.t("Ta fonction", "Your function")
    return join(
        c.t(
            f"{subject} n'a pas le **nombre de paramètres** demandé par le sujet.",
            f"{subject} does not have the **number of parameters** required by the subject.",
        ),
        sigs,
        c.t(
            f"La moulinette appelle ta fonction avec exactement les arguments du sujet{call} : avec un autre nombre "
            "de paramètres, Python lève `TypeError` avant même d'exécuter ton code.",
            f"The grader calls your function with exactly the subject's arguments{call}: with a different number of "
            "parameters, Python raises `TypeError` before even running your code.",
        ),
    )


@template("wrong_param_names", "Noms de paramètres différents", "Different parameter names")
def _wrong_param_names(c: Ctx) -> str:
    expected = _signature(c, "expected_signature", "expected")
    actual = _signature(c, "actual_signature", "found_signature", "actual")
    return join(
        c.t(f"Les noms des paramètres de {c.fn_code()} diffèrent de ceux du sujet.", f"The parameter names of {c.fn_code()} differ from the subject."),
        bullets([
            c.t("demandé : ", "required: ") + code(expected) if expected else "",
            c.t("trouvé : ", "found: ") + code(actual) if actual else "",
        ]),
        c.t(
            "Ça fonctionne tant que la moulinette passe les arguments **par position**, mais un appel avec des "
            "arguments **nommés** (`f(speed=200)`) échouerait. Reprends les noms exacts du sujet.",
            "It works as long as the grader passes arguments **by position**, but a call with **named** arguments "
            "(`f(speed=200)`) would fail. Use the exact names from the subject.",
        ),
    )


@template("wrong_annotation", "Annotation de type différente", "Different type annotation")
def _wrong_annotation(c: Ctx) -> str:
    expected = _signature(c, "expected_signature", "expected")
    return join(
        c.t(
            f"Les annotations de type de {c.fn_code()} (`: int`, `-> bool`...) ne correspondent pas à la signature du sujet.",
            f"The type annotations of {c.fn_code()} (`: int`, `-> bool`...) do not match the subject's signature.",
        ),
        c.t(
            "Elles ne changent pas l'exécution, mais elles indiquent le type attendu : recopier la signature exacte "
            "évite de se tromper de type de retour.",
            "They do not change execution, but they state the expected type: copying the exact signature avoids "
            "returning the wrong type.",
        ),
        block(expected, "python") if expected else "",
    )


@template("nested_function", "Fonction imbriquée", "Nested function")
def _nested_function(c: Ctx) -> str:
    return join(
        c.t(
            f"La fonction {c.fn_code()} est définie **à l'intérieur** d'une autre fonction (ou d'une classe).",
            f"The function {c.fn_code()} is defined **inside** another function (or a class).",
        ),
        c.t(
            "La moulinette ne peut appeler que les fonctions définies **au niveau principal** du fichier : "
            "la ligne `def` doit commencer tout à gauche, sans indentation.",
            "The grader can only call functions defined at the **top level** of the file: the `def` line must "
            "start at the very left, without indentation.",
        ),
    )


@hint("missing_function", "wrong_function_name", "function_in_wrong_file", "wrong_param_count",
      "wrong_param_names", "wrong_annotation", "nested_function")
def _function_steps(c: Ctx) -> list[str]:
    return [
        c.t("Recopie la ligne `def` **exactement** comme dans le sujet (nom, paramètres, annotations).",
            "Copy the `def` line **exactly** as in the subject (name, parameters, annotations)."),
        c.t(f"Place-la au niveau principal de {c.file_code()}, sans indentation.",
            f"Put it at the top level of {c.file_code()}, without indentation."),
        c.t("Mets à jour les éventuels appels à l'ancienne version, puis relance l'analyse.",
            "Update any calls to the old version, then run the analysis again."),
    ]


# ---------------------------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------------------------

BUILTIN_ALTERNATIVES: dict[str, tuple[str, str]] = {
    "abs": ("une **condition** : si le nombre est négatif, prends son opposé (`-x`), sinon garde-le.",
            "a **condition**: if the number is negative, take its opposite (`-x`), otherwise keep it."),
    "max": ("des **comparaisons** : garde la plus grande valeur dans une variable et compare-la aux autres avec `>`.",
            "**comparisons**: keep the largest value in a variable and compare it to the others with `>`."),
    "min": ("des **comparaisons** : garde la plus petite valeur dans une variable et compare-la aux autres avec `<`.",
            "**comparisons**: keep the smallest value in a variable and compare it to the others with `<`."),
    "sum": ("une **boucle** : une variable initialisée à `0` à laquelle tu ajoutes chaque élément.",
            "a **loop**: a variable initialised to `0` to which you add each element."),
    "round": ("l'**arithmétique entière** : `int()` tronque, `//` et `%` donnent quotient et reste ; ajoute `0.5` avant de tronquer pour arrondir un positif.",
              "**integer arithmetic**: `int()` truncates, `//` and `%` give quotient and remainder; add `0.5` before truncating to round a positive number."),
    "sorted": ("des **boucles et comparaisons** : parcours la liste et place chaque élément à sa position (tri par insertion).",
               "**loops and comparisons**: walk through the list and put each element at its place (insertion sort)."),
    "eval": ("une **conversion explicite** avec `int()` ou `float()` : `eval` exécute n'importe quel code, c'est dangereux.",
             "an **explicit conversion** with `int()` or `float()`: `eval` runs arbitrary code, which is dangerous."),
    "exec": ("écrire directement le code voulu : `exec` exécute n'importe quel texte comme du code.",
             "writing the code you need directly: `exec` runs any text as code."),
    "len": ("un **compteur** : une variable qui augmente de 1 à chaque tour de boucle.",
            "a **counter**: a variable increased by 1 at each loop iteration."),
    "pow": ("l'opérateur `**`, ou une multiplication répétée dans une boucle.",
            "the `**` operator, or a repeated multiplication in a loop."),
    "divmod": ("les opérateurs `//` (quotient) et `%` (reste).", "the `//` (quotient) and `%` (remainder) operators."),
    "any": ("une boucle avec un booléen qui passe à `True` dès qu'un élément convient.",
            "a loop with a boolean that becomes `True` as soon as one element matches."),
    "all": ("une boucle avec un booléen qui passe à `False` dès qu'un élément ne convient pas.",
            "a loop with a boolean that becomes `False` as soon as one element does not match."),
    "reversed": ("une boucle sur les indices, du dernier au premier.", "a loop over the indices, from last to first."),
    "map": ("une boucle `for` qui construit le résultat élément par élément.", "a `for` loop that builds the result element by element."),
    "filter": ("une boucle `for` avec un `if` qui ne garde que les bons éléments.", "a `for` loop with an `if` that keeps only the right elements."),
    "enumerate": ("un compteur d'indice que tu incrémentes toi-même.", "an index counter that you increment yourself."),
    "zip": ("une boucle sur les indices pour lire les deux séquences en parallèle.", "a loop over the indices to read both sequences in parallel."),
}

METHOD_ALTERNATIVES: dict[str, tuple[str, str]] = {
    "sort": ("trie toi-même avec des boucles et des comparaisons.", "sort it yourself with loops and comparisons."),
    "split": ("parcours la chaîne caractère par caractère et construis les morceaux.", "walk through the string character by character and build the pieces."),
    "join": ("construis la chaîne avec `+` dans une boucle.", "build the string with `+` in a loop."),
    "upper": ("compare/convertis les caractères toi-même (par exemple avec `ord`/`chr` si autorisés).", "compare/convert characters yourself (for example with `ord`/`chr` if allowed)."),
    "lower": ("compare/convertis les caractères toi-même (par exemple avec `ord`/`chr` si autorisés).", "compare/convert characters yourself (for example with `ord`/`chr` if allowed)."),
    "replace": ("construis une nouvelle chaîne caractère par caractère.", "build a new string character by character."),
    "reverse": ("parcours la liste à l'envers avec les indices.", "walk through the list backwards with indices."),
    "count": ("utilise un compteur dans une boucle.", "use a counter in a loop."),
    "index": ("parcours les indices avec une boucle jusqu'à trouver l'élément.", "loop over the indices until you find the element."),
    "find": ("parcours les indices avec une boucle jusqu'à trouver le texte.", "loop over the indices until you find the text."),
}

CONSTRUCT_NAMES: dict[str, tuple[str, str]] = {
    "for": ("une boucle `for`", "a `for` loop"),
    "while": ("une boucle `while`", "a `while` loop"),
    "loop": ("une boucle (`for` ou `while`)", "a loop (`for` or `while`)"),
    "comprehension": ("une compréhension (`[x for x in ...]`)", "a comprehension (`[x for x in ...]`)"),
    "lambda": ("une fonction `lambda`", "a `lambda` function"),
    "recursion": ("la récursivité (une fonction qui s'appelle elle-même)", "recursion (a function calling itself)"),
    "try": ("un bloc `try` / `except`", "a `try` / `except` block"),
    "global": ("le mot-clé `global`", "the `global` keyword"),
    "class": ("une classe (`class`)", "a class (`class`)"),
    "import": ("un `import`", "an `import`"),
    "with": ("un bloc `with`", "a `with` block"),
    "yield": ("`yield` (générateur)", "`yield` (generator)"),
    "fstring": ("une f-string (`f\"...\"`)", "an f-string (`f\"...\"`)"),
    "walrus": ("l'opérateur `:=`", "the `:=` operator"),
    "match": ("un `match` / `case`", "a `match` / `case`"),
}

_ZERO_RISK = (
    "Les moulinettes détectent ces appels automatiquement et peuvent mettre **0 à tout l'exercice**, même si le résultat est juste.",
    "Graders detect these calls automatically and may give **0 for the whole exercise**, even if the result is right.",
)


def _lines_text(c: Ctx) -> str:
    lines = int_list(detail(c.check, "lines", "line_numbers"))
    if not lines and c.line:
        lines = [c.line]
    if not lines:
        return ""
    first, others = lines[0], lines[1:]
    more = c.t(f" (et aussi ligne(s) {', '.join(map(str, others))})", f" (and also line(s) {', '.join(map(str, others))})") if others else ""
    return c.t(f" à la ligne {first}{more}", f" on line {first}{more}")


@template("forbidden_builtin", "Fonction intégrée interdite", "Forbidden builtin")
def _forbidden_builtin(c: Ctx) -> str:
    name = constraint_name(c.check) or "?"
    alternative = BUILTIN_ALTERNATIVES.get(name)
    referenced = bool(detail(c.check, "referenced_only"))
    return join(
        c.t(
            f"Le sujet interdit la fonction intégrée {code(name + '()')}, et ton code l'utilise{_lines_text(c)}.",
            f"The subject forbids the builtin {code(name + '()')}, and your code uses it{_lines_text(c)}.",
        ),
        c.t("Même une simple référence sans appel (par exemple `f = " + name + "`) est détectée.",
            "Even a mere reference without a call (for example `f = " + name + "`) is detected.") if referenced else "",
        c.t(
            "**Pourquoi c'est interdit ?** Le but de l'exercice est de t'entraîner à écrire cette logique toi-même. " + _ZERO_RISK[0],
            "**Why is it forbidden?** The point of the exercise is to practise writing this logic yourself. " + _ZERO_RISK[1],
        ),
        c.t(f"**Piste :** remplace-la par {alternative[0]}", f"**Idea:** replace it with {alternative[1]}") if alternative
        else c.t("**Piste :** écris la logique toi-même avec des conditions (`if`) et des boucles.",
                 "**Idea:** write the logic yourself with conditions (`if`) and loops."),
    )


@template("builtin_not_allowed", "Fonction intégrée non autorisée", "Builtin not allowed")
def _builtin_not_allowed(c: Ctx) -> str:
    name = constraint_name(c.check) or "?"
    allowed = detail(c.check, "allowed", "allowed_builtins")
    allowed_txt = ", ".join(code(str(a)) for a in allowed) if isinstance(allowed, list) else ""
    alternative = BUILTIN_ALTERNATIVES.get(name)
    return join(
        c.t(
            f"Le sujet n'autorise **que** certaines fonctions intégrées{' : ' + allowed_txt if allowed_txt else ''}. "
            f"{code(name + '()')} n'en fait pas partie, et ton code l'utilise{_lines_text(c)}.",
            f"The subject **only** allows some builtins{': ' + allowed_txt if allowed_txt else ''}. "
            f"{code(name + '()')} is not one of them, and your code uses it{_lines_text(c)}.",
        ),
        c.t(_ZERO_RISK[0], _ZERO_RISK[1]),
        c.t(f"**Piste :** {alternative[0]}", f"**Idea:** {alternative[1]}") if alternative else "",
    )


@template("forbidden_import", "Import interdit", "Forbidden import")
def _forbidden_import(c: Ctx) -> str:
    module = constraint_name(c.check) or "?"
    none_allowed = detail(c.check, "allowed", "allowed_imports") == [] or "no import" in c.check.message.lower()
    rule = (c.t("Le sujet n'autorise **aucun** `import`.", "The subject allows **no** `import` at all.") if none_allowed
            else c.t(f"Le sujet interdit l'import du module {code(module)}.", f"The subject forbids importing the module {code(module)}."))
    math_tip = c.t(
        "Pour `math` : `x ** 0.5` remplace `sqrt`, `//` remplace `floor` pour les positifs, et une constante remplace `pi`.",
        "For `math`: `x ** 0.5` replaces `sqrt`, `//` replaces `floor` for positive numbers, and a constant replaces `pi`.",
    ) if module == "math" else ""
    return join(
        rule + c.t(f" Ton code en contient un{_lines_text(c)}.", f" Your code has one{_lines_text(c)}."),
        c.t(
            "Tout ce dont tu as besoin peut s'écrire avec les opérations de base (`+ - * / // % **`), des conditions, "
            "des boucles et les fonctions autorisées.",
            "Everything you need can be written with basic operations (`+ - * / // % **`), conditions, loops and "
            "the allowed functions.",
        ),
        math_tip,
    )


@template("forbidden_method", "Méthode interdite", "Forbidden method")
def _forbidden_method(c: Ctx) -> str:
    method = constraint_name(c.check) or "?"
    alternative = METHOD_ALTERNATIVES.get(method)
    return join(
        c.t(f"Le sujet interdit la méthode {code('.' + method + '()')}, et ton code l'utilise{_lines_text(c)}.",
            f"The subject forbids the method {code('.' + method + '()')}, and your code uses it{_lines_text(c)}."),
        c.t(_ZERO_RISK[0], _ZERO_RISK[1]),
        c.t(f"**Piste :** {alternative[0]}", f"**Idea:** {alternative[1]}") if alternative else "",
    )


def _construct(c: Ctx) -> str:
    name = constraint_name(c.check) or "?"
    names = CONSTRUCT_NAMES.get(name)
    return c.t(*names) if names else code(name)


@template("forbidden_construct", "Construction interdite", "Forbidden construct")
def _forbidden_construct(c: Ctx) -> str:
    return join(
        c.t(f"Le sujet interdit d'utiliser {_construct(c)}, et ton code en contient{_lines_text(c)}.",
            f"The subject forbids using {_construct(c)}, and your code contains it{_lines_text(c)}."),
        c.t("Cette contrainte fait partie de l'exercice : il faut trouver une autre façon d'écrire la même logique.",
            "This constraint is part of the exercise: you must find another way to write the same logic."),
    )


@template("missing_required_construct", "Construction obligatoire absente", "Required construct missing")
def _missing_required_construct(c: Ctx) -> str:
    return join(
        c.t(f"Le sujet exige d'utiliser {_construct(c)}, et ton code n'en contient pas.",
            f"The subject requires using {_construct(c)}, and your code does not contain it."),
        c.t("Même si ton résultat est juste, la moulinette peut vérifier la façon dont tu l'obtiens.",
            "Even if your result is right, the grader may check how you obtain it."),
    )


@template("builtin_bypass", "Contournement des fonctions intégrées", "Builtin bypass")
def _builtin_bypass(c: Ctx) -> str:
    name = constraint_name(c.check)
    shown = c.t(f" ({code(name)}{_lines_text(c)})", f" ({code(name)}{_lines_text(c)})") if name else ""
    return join(
        c.t(
            f"Ton code utilise un moyen **détourné** d'accéder aux fonctions intégrées{shown} : `__builtins__`, "
            "`getattr`, `__import__`, `eval` ou `exec`.",
            f"Your code uses an **indirect** way to reach builtins{shown}: `__builtins__`, `getattr`, `__import__`, "
            "`eval` or `exec`.",
        ),
        c.t(
            "Les moulinettes détectent ces contournements et les traitent comme une triche. Écris la logique "
            "directement avec les outils autorisés.",
            "Graders detect these workarounds and treat them as cheating. Write the logic directly with the allowed tools.",
        ),
    )


@hint("forbidden_builtin", "builtin_not_allowed", "forbidden_import", "forbidden_method",
      "forbidden_construct", "missing_required_construct", "builtin_bypass")
def _constraint_steps(c: Ctx) -> list[str]:
    name = constraint_name(c.check) or "?"
    alternative = BUILTIN_ALTERNATIVES.get(name) or METHOD_ALTERNATIVES.get(name)
    steps = [
        c.t(f"Repère chaque utilisation{_lines_text(c)}.", f"Find every use{_lines_text(c)}."),
        c.t(f"Remplace-la par ta propre logique : {alternative[0]}", f"Replace it with your own logic: {alternative[1]}") if alternative
        else c.t("Réécris ce passage avec des conditions et des boucles autorisées.", "Rewrite this part with allowed conditions and loops."),
        c.t("Teste ta version sur les exemples du sujet, puis relance l'analyse.", "Test your version on the subject's examples, then run the analysis again."),
    ]
    if c.check.diagnosis == "missing_required_construct":
        steps[1] = c.t(f"Réécris la partie concernée en utilisant {_construct(c)}.", f"Rewrite the relevant part using {_construct(c)}.")
    return steps


# ---------------------------------------------------------------------------------------------
# Runtime: import
# ---------------------------------------------------------------------------------------------

_MAIN_GUARD_EXAMPLE = 'def ma_fonction(x):\n    ...\n\n\nif __name__ == "__main__":\n    print(ma_fonction(3))  # tests personnels'
_MAIN_GUARD_EXAMPLE_EN = 'def my_function(x):\n    ...\n\n\nif __name__ == "__main__":\n    print(my_function(3))  # personal tests'


def _effects(c: Ctx) -> str:
    effects = detail(c.check, "effects", "top_level_effects")
    items: list[str] = []
    if isinstance(effects, list):
        for effect in effects[:6]:
            if isinstance(effect, dict) and effect.get("line"):
                src = effect.get("src")
                items.append(c.t(f"ligne {effect['line']}", f"line {effect['line']}") + (f" : {code(str(src))}" if src else ""))
    if not items and c.line:
        src = c.source_line()
        items.append(c.t(f"ligne {c.line}", f"line {c.line}") + (f" : {code(src.strip())}" if src else ""))
    return bullets(items)


@template("import_side_effects", "Code exécuté à l'import", "Code runs at import")
def _import_side_effects(c: Ctx) -> str:
    stdout = c.ev.actual_stdout or detail_str(c.check, "import_stdout", "stdout")
    return join(
        c.t(
            f"Ton fichier {c.file_code()} exécute du code **dès qu'il est importé** :",
            f"Your file {c.file_code()} runs code **as soon as it is imported**:",
        ),
        _effects(c),
        c.t("Sortie produite à l'import :", "Output produced at import:") if stdout else "",
        block(tail_lines(stdout, 8), "text") if stdout else "",
        c.t(
            "La moulinette importe ton fichier pour appeler tes fonctions : ces lignes s'exécuteraient et "
            "pollueraient la sortie. Supprime ces tests de débogage, ou place-les sous le *main guard* :",
            "The grader imports your file to call your functions: these lines would run and pollute the output. "
            "Remove these debug tests, or put them under the *main guard*:",
        ),
        block(c.t(_MAIN_GUARD_EXAMPLE, _MAIN_GUARD_EXAMPLE_EN), "python"),
    )


@template("import_crash", "Plantage à l'import", "Crash at import")
def _import_crash(c: Ctx) -> str:
    exc = c.ev.exception
    error = code(f"{exc.type}: {exc.message}") if exc else code(c.check.message)
    return join(
        c.t(
            f"Ton fichier {c.file_code()} **plante dès l'import**{c.at_line()}, avant même que la moulinette "
            f"puisse appeler une fonction : {error}.",
            f"Your file {c.file_code()} **crashes at import**{c.at_line()}, before the grader can even call a "
            f"function: {error}.",
        ),
        exception_hint(c, exc.type) if exc else "",
        c.t("Comme le fichier ne peut pas être importé, **aucune** de ses fonctions ne peut être testée.",
            "Since the file cannot be imported, **none** of its functions can be tested."),
        block(tail_lines(exc.traceback, 12), "text") if exc and exc.traceback else "",
    )


@template("import_waits_input", "input() à l'import", "input() at import")
def _import_waits_input(c: Ctx) -> str:
    return join(
        c.t(
            f"Ton fichier {c.file_code()} appelle `input()` **au moment de l'import**{c.at_line()}.",
            f"Your file {c.file_code()} calls `input()` **at import time**{c.at_line()}.",
        ),
        c.t(
            "La moulinette importe ton fichier pour tester tes fonctions : elle resterait bloquée à attendre une "
            "saisie. Déplace ces appels dans une fonction, ou sous `if __name__ == \"__main__\":`.",
            "The grader imports your file to test your functions: it would get stuck waiting for input. Move these "
            "calls into a function, or under `if __name__ == \"__main__\":`.",
        ),
    )


@hint("import_side_effects", "import_crash", "import_waits_input")
def _import_steps(c: Ctx) -> list[str]:
    check_cmd = code('python3 -c "import ' + _module_name(c.file) + '"')
    return [
        c.t(f"Repère le code au niveau principal de {c.file_code()} (hors `def`).", f"Find the top-level code of {c.file_code()} (outside any `def`)."),
        c.t("Supprime les `print`/`input` de test, ou mets-les sous `if __name__ == \"__main__\":`.",
            "Remove test `print`/`input` calls, or put them under `if __name__ == \"__main__\":`."),
        c.t(f"Vérifie depuis le dossier du fichier : {check_cmd} ne doit rien afficher ni planter.",
            f"Check from the file's folder: {check_cmd} must print nothing and not crash."),
    ]


def _module_name(path: str | None) -> str:
    if not path:
        return "module"
    name = path.rsplit("/", 1)[-1]
    return name[:-3] if name.endswith(".py") else name
