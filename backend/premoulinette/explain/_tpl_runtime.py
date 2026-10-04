"""Templates for runtime diagnoses: function tests and script output (stdout, prompts, crashes)."""
from __future__ import annotations

from premoulinette.explain._context import Ctx
from premoulinette.explain._evidence import (
    changed_lines,
    detail,
    detail_str,
    expected_text,
    first_difference,
    lines_with_op,
    literal_str,
    stdout_diff,
    text_pair,
)
from premoulinette.explain._markdown import (
    block,
    bullets,
    caret_diff,
    code,
    involves_whitespace,
    join,
    show_trailing,
    show_ws,
    str_literal,
    tail_lines,
)
from premoulinette.explain._registry import hint, template
from premoulinette.results.models import DiffLine, TextDiff

EXCEPTION_HINTS: dict[str, tuple[str, str]] = {
    "ZeroDivisionError": (
        "Une **division par zéro** : un diviseur vaut `0` pour ce cas. Le sujet prévoit-il un cas particulier "
        "(par exemple quand une valeur vaut `0`) ? Traite-le avec un `if` **avant** de diviser.",
        "A **division by zero**: a divisor is `0` for this case. Does the subject define a special case (for "
        "example when a value is `0`)? Handle it with an `if` **before** dividing.",
    ),
    "TypeError": (
        "Une opération entre des **types incompatibles** (par exemple `\"3\" + 1`), ou un appel avec un mauvais "
        "nombre d'arguments. Pense à convertir ce que renvoie `input()` avec `int()` ou `float()`.",
        "An operation between **incompatible types** (for example `\"3\" + 1`), or a call with the wrong number "
        "of arguments. Remember to convert what `input()` returns with `int()` or `float()`.",
    ),
    "NameError": (
        "Un nom (variable ou fonction) est utilisé **sans avoir été défini**, ou il est mal orthographié.",
        "A name (variable or function) is used **without being defined**, or it is misspelled.",
    ),
    "UnboundLocalError": (
        "Une variable est utilisée **avant d'avoir reçu une valeur** : souvent, elle n'est définie que dans une "
        "des branches d'un `if`.",
        "A variable is used **before it gets a value**: often it is only defined in one branch of an `if`.",
    ),
    "ValueError": (
        "Une valeur du bon type mais **invalide**, typiquement `int(\"abc\")` : la chaîne ne représente pas un nombre.",
        "A value of the right type but **invalid**, typically `int(\"abc\")`: the string is not a number.",
    ),
    "IndexError": (
        "Un accès à un **indice qui n'existe pas** (par exemple `liste[len(liste)]`) : les indices vont de `0` à `len - 1`.",
        "An access to an **index that does not exist** (for example `items[len(items)]`): indices go from `0` to `len - 1`.",
    ),
    "KeyError": (
        "Une **clé absente** d'un dictionnaire a été demandée.",
        "A **missing key** was looked up in a dictionary.",
    ),
    "AttributeError": (
        "Une **méthode ou un attribut qui n'existe pas** pour ce type de valeur (par exemple `(5).upper()`).",
        "A **method or attribute that does not exist** for this type of value (for example `(5).upper()`).",
    ),
    "RecursionError": (
        "Une **récursion infinie** : la fonction s'appelle elle-même sans jamais atteindre son cas de base.",
        "An **infinite recursion**: the function calls itself without ever reaching its base case.",
    ),
    "ModuleNotFoundError": (
        "Un `import` d'un module qui n'existe pas (ou qui n'est pas autorisé dans ce TP).",
        "An `import` of a module that does not exist (or is not allowed in this assignment).",
    ),
    "ImportError": (
        "Un `import` qui échoue (module ou nom introuvable).",
        "An `import` that fails (module or name not found).",
    ),
    "EOFError": (
        "`input()` a été appelé alors qu'il n'y avait **plus rien à lire** : ton programme pose plus de questions que prévu.",
        "`input()` was called while there was **nothing left to read**: your program asks more questions than expected.",
    ),
    "PermissionError": (
        "Une opération **bloquée** (fichier, réseau ou processus) : elle n'est pas nécessaire pour ce TP.",
        "A **blocked** operation (file, network or process): it is not needed for this assignment.",
    ),
    "AssertionError": (
        "Un `assert` de ton code a échoué.",
        "An `assert` in your code failed.",
    ),
}

_KIND_TEXT: dict[str, tuple[str, str]] = {
    "typo": ("une faute de frappe", "a typo"),
    "case": ("une différence de majuscule/minuscule", "an upper/lower case difference"),
    "whitespace": ("une différence d'espaces", "a whitespace difference"),
    "trailing_whitespace": ("un espace en trop ou manquant en fin de ligne", "an extra or missing space at the end of a line"),
    "missing_newline": ("un retour à la ligne manquant", "a missing line break"),
    "extra_newline": ("un retour à la ligne en trop", "an extra line break"),
    "crlf": ("des fins de ligne Windows (`\\r\\n`)", "Windows line endings (`\\r\\n`)"),
    "missing_lines": ("des lignes manquantes", "missing lines"),
    "extra_lines": ("des lignes en trop", "extra lines"),
}

_EXACT_COMPARE = (
    "La moulinette compare **caractère par caractère** : une majuscule, un espace, une ponctuation ou un retour "
    "à la ligne suffit à faire échouer le test.",
    "The grader compares **character by character**: one capital letter, space, punctuation mark or line break "
    "is enough to fail the test.",
)


def exception_hint(c: Ctx, exc_type: str) -> str:
    texts = EXCEPTION_HINTS.get(exc_type)
    return c.t(*texts) if texts else ""


def _labels(c: Ctx) -> tuple[str, str]:
    return (c.t("attendu :", "expected:"), c.t("reçu :", "received:"))


def _invisible_note(c: Ctx, expected: str, actual: str) -> str:
    if not involves_whitespace(expected, actual):
        return ""
    return c.t(
        "Attention, la différence porte sur un caractère **invisible** (espace, tabulation ou retour à la ligne). "
        "Ici les espaces sont affichés `␠`, les tabulations `→` et les retours à la ligne `↵`.",
        "Careful, the difference is an **invisible** character (space, tab or line break). Here spaces are shown "
        "as `␠`, tabs as `→` and line breaks as `↵`.",
    )


def _kinds_text(c: Ctx, diff: TextDiff | None, hints: list[str] | None = None) -> str:
    kinds = [c.t(*_KIND_TEXT[k]) for k in (diff.kinds if diff else []) if k in _KIND_TEXT]
    details = [code(h) for h in (hints or [])]
    if not kinds and not details:
        return ""
    found = ", ".join(kinds) if kinds else ""
    extra = (" — " if found else "") + ", ".join(details) if details else ""
    return c.t(f"Type de différence : {found}{extra}.", f"Kind of difference: {found}{extra}.")


def _source_of(c: Ctx, line: DiffLine) -> str:
    src = line.source
    if src is None or not src.file:
        return ""
    if src.line:
        return c.t(f", produite par la ligne {src.line} de {code(src.file)}", f", produced by line {src.line} of {code(src.file)}")
    return c.t(f", produite par {code(src.file)}", f", produced by {code(src.file)}")


def _diff_line_text(text: str | None, eol: str) -> str:
    return (text or "") + eol


# ---------------------------------------------------------------------------------------------
# Function tests
# ---------------------------------------------------------------------------------------------


@template("wrong_value", "Mauvaise valeur renvoyée", "Wrong return value")
def _wrong_value(c: Ctx) -> str:
    parts = [
        c.t("Ta fonction renvoie une valeur du bon type, mais **pas la bonne valeur**.",
            "Your function returns a value of the right type, but **not the right value**."),
        c.facts(),
    ]
    if c.ev.rule:
        parts.append(c.t(f"La règle du sujet qui s'applique à ce cas : {code(c.ev.rule)}.",
                         f"The subject rule that applies to this case: {code(c.ev.rule)}."))
    if c.is_boundary_case():
        parts.append(c.t(
            "Ce cas est une **valeur limite** de la règle : c'est souvent une confusion entre `<` et `<=` (ou `>` et `>=`).",
            "This case is a **boundary value** of the rule: it is often a mix-up between `<` and `<=` (or `>` and `>=`).",
        ))
    exp = c.ev.expected_value
    if exp is not None and exp.type == "float":
        parts.append(c.t(
            "Pour les nombres à virgule, vérifie l'opération utilisée : `/` donne un résultat décimal, `//` une division entière.",
            "For floating-point numbers, check the operation used: `/` gives a decimal result, `//` an integer division.",
        ))
    return join(*parts)


@template("wrong_type", "Mauvais type renvoyé", "Wrong return type")
def _wrong_type(c: Ctx) -> str:
    exp, act = c.ev.expected_value, c.ev.actual_value
    if exp is None or act is None:
        intro = c.t("La valeur renvoyée n'a pas le bon **type**.", "The returned value does not have the right **type**.")
    else:
        intro = c.t(
            f"La valeur renvoyée n'a pas le bon **type** : le sujet attend {c.type_name(exp.type)}, ta fonction renvoie {c.type_name(act.type)}.",
            f"The returned value does not have the right **type**: the subject expects {c.type_name(exp.type)}, your function returns {c.type_name(act.type)}.",
        )
    return join(
        intro,
        c.facts(),
        c.t("Pour Python, `1`, `1.0`, `\"1\"` et `True` sont des valeurs de types différents : la moulinette compare aussi le type.",
            "For Python, `1`, `1.0`, `\"1\"` and `True` are values of different types: the grader also compares the type."),
    )


def _bool_word(c: Ctx) -> str:
    """"True"/"False" as returned by the student (runtime value or static source line)."""
    actual = literal_str(c.ev.actual_value)
    if actual in ("True", "False"):
        return actual
    line = c.source_line() or ""
    for word in ("True", "False"):
        if f'"{word}"' in line or f"'{word}'" in line:
            return word
    return "True"


@template("str_instead_of_bool", "Chaîne au lieu d'un booléen", "String instead of boolean")
def _str_instead_of_bool(c: Ctx) -> str:
    word = _bool_word(c)
    exp = c.ev.expected_value
    expected_word = exp.repr if exp is not None and exp.repr in ("True", "False") else word
    runtime = c.ev.actual_value is not None
    if not runtime:
        where = f" ({c.where()})" if c.where() else ""
        subject = c.t(f"La fonction {code(c.fn)}", f"The function {code(c.fn)}") if c.fn else c.t("Ta fonction", "Your function")
        intro = c.t(
            f"{subject} retourne une **chaîne de caractères** au lieu d'un **booléen**{where}.",
            f"{subject} returns a **string** instead of a **boolean**{where}.",
        )
    elif word == expected_word:
        intro = c.t(
            "Ta logique de comparaison est correcte, mais tu retournes une **chaîne de caractères** au lieu d'un **booléen**.",
            "Your comparison logic is correct, but you return a **string** instead of a **boolean**.",
        )
    else:
        intro = c.t(
            "Tu retournes une **chaîne de caractères** au lieu d'un **booléen**, et en plus la valeur n'est pas la bonne pour ce cas.",
            "You return a **string** instead of a **boolean**, and the value is also wrong for this case.",
        )
    return join(
        intro,
        bullets([
            c.t(f'`"{word}"` est un `str` (à cause des guillemets)', f'`"{word}"` is a `str` (because of the quotes)'),
            c.t(f"`{word}` est un `bool`", f"`{word}` is a `bool`"),
        ]),
        c.t(f"Le sujet demande `{expected_word}` sans guillemets.", f"The subject asks for `{expected_word}` without quotes."),
        c.facts(values=False) if runtime else "",
        c.t(
            "Piège classique : dans un `if`, toute chaîne non vide est considérée comme vraie, **même** `\"False\"`.",
            "Classic trap: in an `if`, any non-empty string counts as true, **even** `\"False\"`.",
        ),
    )


@template("number_as_str", "Nombre renvoyé sous forme de texte", "Number returned as text")
def _number_as_str(c: Ctx) -> str:
    exp, act = c.ev.expected_value, c.ev.actual_value
    shown_act = c.value(act) if act else code('"42"')
    shown_exp = c.value(exp) if exp else code("42")
    exp_type = code(exp.type) if exp else code("int")
    return join(
        c.t(
            f"Tu renvoies le nombre **sous forme de texte** : {shown_act} est une chaîne (`str`), alors que le sujet attend le nombre {shown_exp} ({exp_type}).",
            f"You return the number **as text**: {shown_act} is a string (`str`), while the subject expects the number {shown_exp} ({exp_type}).",
        ),
        bullets([
            c.t('`"42"` (avec guillemets) est du texte : `"42" + 1` provoque une erreur', '`"42"` (with quotes) is text: `"42" + 1` raises an error'),
            c.t("`42` (sans guillemets) est un nombre : `42 + 1` vaut `43`", "`42` (without quotes) is a number: `42 + 1` is `43`"),
        ]),
        c.facts(values=False),
        c.t("Cherche des guillemets, un `str(...)` ou une f-string autour de ton résultat.",
            "Look for quotes, a `str(...)` or an f-string around your result."),
    )


@template("int_instead_of_float", "Entier au lieu d'un nombre à virgule", "Integer instead of float")
def _int_instead_of_float(c: Ctx) -> str:
    exp, act = c.ev.expected_value, c.ev.actual_value
    shown_act = c.value(act) if act else code("75")
    shown_exp = c.value(exp) if exp else code("75.0")
    return join(
        c.t(f"Tu renvoies l'entier {shown_act} alors que le sujet attend le nombre à virgule {shown_exp} (`float`).",
            f"You return the integer {shown_act} while the subject expects the float {shown_exp} (`float`)."),
        c.t(
            "En Python `75 == 75.0` est vrai, mais l'affichage diffère (`75` contre `75.0`) et une moulinette stricte "
            "peut aussi comparer le type.",
            "In Python `75 == 75.0` is true, but the display differs (`75` vs `75.0`) and a strict grader may also "
            "compare the type.",
        ),
        c.t("Astuce : `/` renvoie toujours un `float` ; pour une constante, écris `0.0` plutôt que `0`.",
            "Tip: `/` always returns a `float`; for a constant, write `0.0` rather than `0`."),
        c.facts(values=False),
    )


@template("returns_none", "La fonction renvoie None", "Function returns None")
def _returns_none(c: Ctx) -> str:
    return join(
        c.t(
            "Ta fonction renvoie `None`, c'est-à-dire **rien**. En Python, une fonction qui se termine sans exécuter "
            "de `return <valeur>` renvoie automatiquement `None`.",
            "Your function returns `None`, i.e. **nothing**. In Python, a function that ends without running a "
            "`return <value>` automatically returns `None`.",
        ),
        c.facts(),
        c.t("Causes fréquentes :", "Common causes:"),
        bullets([
            c.t("un `return` oublié dans une des branches `if` / `else` (ce cas passe peut-être par celle-là)",
                "a `return` forgotten in one of the `if` / `else` branches (this case may go through that one)"),
            c.t("un `return` écrit seul, sans valeur", "a `return` written alone, without a value"),
            c.t("un `print(...)` à la place du `return`", "a `print(...)` instead of the `return`"),
        ]),
    )


@template("prints_instead_of_returns", "print au lieu de return", "print instead of return")
def _prints_instead_of_returns(c: Ctx) -> str:
    runtime = c.ev.actual_value is not None or c.ev.call is not None
    printed = c.ev.actual_stdout or detail_str(c.check, "stdout")
    if runtime:
        tail = (c.t(f", même si ta fonction a bien affiché {code(printed.strip())} : ton calcul est probablement juste",
                    f", even though your function printed {code(printed.strip())}: your computation is probably right")
                if printed and printed.strip() else "")
        consequence = c.t(
            f"La moulinette appelle ta fonction et compare la **valeur renvoyée** : elle reçoit `None`{tail}.",
            f"The grader calls your function and compares the **returned value**: it gets `None`{tail}.",
        )
    else:
        where = c.t(f" ({c.where()})", f" ({c.where()})") if c.where() else ""
        consequence = c.t(
            f"Dans {c.fn_code()}, il y a un `print(...)`{where} mais aucun `return` avec une valeur : la moulinette, "
            "qui compare la **valeur renvoyée**, recevra `None`.",
            f"In {c.fn_code()}, there is a `print(...)`{where} but no `return` with a value: the grader, which "
            "compares the **returned value**, will get `None`.",
        )
    return join(
        c.t("Ta fonction **affiche** son résultat avec `print()` au lieu de le **renvoyer** avec `return`.",
            "Your function **prints** its result with `print()` instead of **returning** it with `return`."),
        bullets([
            c.t("`print(x)` écrit `x` dans le terminal, mais la fonction renvoie ensuite `None`",
                "`print(x)` writes `x` to the terminal, but the function then returns `None`"),
            c.t("`return x` transmet `x` à celui qui a appelé la fonction", "`return x` hands `x` back to the caller"),
        ]),
        consequence,
        c.facts(values=False) if runtime else "",
    )


@template("wrong_string", "Chaîne différente", "Different string")
def _wrong_string(c: Ctx) -> str:
    pair = text_pair(c.check)
    diff = c.ev.value_diff
    hints = [h for line in (diff.lines if diff else []) for h in line.hints]
    if pair is None:
        return join(
            c.t("La chaîne renvoyée n'est pas identique à celle du sujet.", "The returned string is not identical to the subject's."),
            c.facts(),
            c.t(*_EXACT_COMPARE),
        )
    expected, actual = pair
    return join(
        c.t("La chaîne renvoyée est presque la bonne, mais elle n'est **pas identique caractère par caractère**.",
            "The returned string is almost right, but it is **not identical character by character**."),
        caret_diff(expected, actual, _labels(c)),
        _invisible_note(c, expected, actual),
        _kinds_text(c, diff, hints),
        c.t(*_EXACT_COMPARE),
        c.facts(values=False),
    )


@template("exception", "Plantage pendant le test", "Crash during the test")
def _exception(c: Ctx) -> str:
    exc = c.ev.exception
    error = code(f"{exc.type}: {exc.message}") if exc else code(c.check.message)
    call = c.t(f" pendant le test {code(c.ev.call)}", f" during the test {code(c.ev.call)}") if c.ev.call else ""
    return join(
        c.t(f"Ton code a **planté**{call}{c.at_line()} : {error}.", f"Your code **crashed**{call}{c.at_line()}: {error}."),
        exception_hint(c, exc.type) if exc else "",
        c.facts(call=False, values=True, where=False) if c.ev.expected_value else "",
        block(tail_lines(exc.traceback, 12), "text") if exc and exc.traceback else "",
    )


@template("timeout", "Temps limite dépassé", "Time limit exceeded")
def _timeout(c: Ctx) -> str:
    limit = detail(c.check, "timeout_s", "timeout")
    limit_txt = c.t(f" ({limit} s)", f" ({limit} s)") if isinstance(limit, (int, float)) else ""
    subject = code(c.ev.call) if c.ev.call else c.t("ton programme", "your program")
    return join(
        c.t(f"Le test {subject} ne s'est pas terminé dans le temps imparti{limit_txt}.",
            f"The test {subject} did not finish within the time limit{limit_txt}."),
        c.t("Causes les plus fréquentes :", "Most common causes:"),
        bullets([
            c.t("une **boucle infinie** : une boucle `while` dont la condition ne devient jamais fausse (variable jamais modifiée dans la boucle)",
                "an **infinite loop**: a `while` loop whose condition never becomes false (variable never updated in the loop)"),
            c.t("un `input()` qui attend une saisie qui n'arrive jamais", "an `input()` waiting for input that never comes"),
            c.t("une récursion qui n'atteint jamais son cas de base", "a recursion that never reaches its base case"),
        ]),
        c.stdin_facts(),
    )


@template("output_limit", "Sortie trop longue", "Output too long")
def _output_limit(c: Ctx) -> str:
    return join(
        c.t("Ton programme a écrit **beaucoup trop de texte** : la sortie a été tronquée.",
            "Your program wrote **far too much text**: the output was truncated."),
        c.t("C'est presque toujours un `print` à l'intérieur d'une boucle qui ne s'arrête pas.",
            "It is almost always a `print` inside a loop that never stops."),
        c.facts(values=False),
    )


@template("blocked_syscall", "Opération bloquée par le bac à sable", "Operation blocked by the sandbox")
def _blocked_syscall(c: Ctx) -> str:
    blocked = detail(c.check, "blocked_syscalls", "blocked", "syscalls")
    names = [str(b) for b in blocked] if isinstance(blocked, list) else ([str(blocked)] if blocked else [])
    shown = ", ".join(code(n) for n in names[:5]) if names else c.t("une opération système", "a system operation")
    return join(
        c.t(f"Ton code a tenté une opération **bloquée par le bac à sable** de PréMoulinette : {shown}{c.at_line()}.",
            f"Your code attempted an operation **blocked by PréMoulinette's sandbox**: {shown}{c.at_line()}."),
        c.t(
            "Pour protéger ton ordinateur, l'exécution des tests interdit le réseau, le lancement d'autres programmes "
            "(`os.system`, `subprocess`...) et l'écriture de fichiers hors d'un dossier temporaire. Un exercice de ce "
            "type n'en a normalement pas besoin : cherche ce qui déclenche cette opération dans ton code.",
            "To protect your computer, test execution forbids network access, starting other programs (`os.system`, "
            "`subprocess`...) and writing files outside a temporary folder. This kind of exercise normally does not "
            "need it: find what triggers this operation in your code.",
        ),
    )


@template("unexpected_stdout", "Affichage inattendu", "Unexpected output")
def _unexpected_stdout(c: Ctx) -> str:
    stdout = c.ev.actual_stdout or detail_str(c.check, "stdout")
    return join(
        c.t("Ta fonction **affiche** du texte alors que le sujet demande qu'elle ne fasse que **renvoyer** son résultat.",
            "Your function **prints** text while the subject asks it to only **return** its result."),
        block(tail_lines(stdout, 8), "text") if stdout else "",
        c.t(
            "Même si la valeur renvoyée est correcte, ce texte en trop peut faire échouer la moulinette. Retire les "
            "`print` de débogage (ou commente-les) avant de rendre.",
            "Even if the returned value is right, this extra text can make the grader fail. Remove debug `print` "
            "calls (or comment them out) before submitting.",
        ),
        c.facts(values=False),
    )


# ---------------------------------------------------------------------------------------------
# Script output
# ---------------------------------------------------------------------------------------------


@template("stdout_mismatch", "Sortie différente", "Different output")
def _stdout_mismatch(c: Ctx) -> str:
    diff = stdout_diff(c.check)
    first = first_difference(diff)
    summary = c.t(f" ({diff.summary})", f" ({diff.summary})") if diff and diff.summary else ""
    parts = [c.t(f"La sortie de ton programme ne correspond pas **exactement** à celle du sujet{summary}.",
                 f"Your program's output does not match the subject's **exactly**{summary}.")]
    if first is not None:
        number = first.expected_lineno or first.actual_lineno
        line_txt = c.t(f", ligne {number} de la sortie", f", output line {number}") if number else ""
        parts.append(c.t(f"Première différence{line_txt}{_source_of(c, first)} :", f"First difference{line_txt}{_source_of(c, first)}:"))
        if first.op == "changed":
            expected = _diff_line_text(first.expected, first.expected_eol)
            actual = _diff_line_text(first.actual, first.actual_eol)
            parts += [caret_diff(expected, actual, _labels(c)), _invisible_note(c, expected, actual), _kinds_text(c, diff, first.hints)]
        elif first.op == "missing":
            parts.append(c.t(f"la ligne {code(show_ws(first.expected or ''))} est attendue mais ton programme ne l'affiche pas.",
                             f"the line {code(show_ws(first.expected or ''))} is expected but your program does not print it."))
        else:
            parts.append(c.t(f"ton programme affiche la ligne {code(show_ws(first.actual or ''))}, qui n'est pas attendue.",
                             f"your program prints the line {code(show_ws(first.actual or ''))}, which is not expected."))
    elif c.ev.expected_stdout is not None and c.ev.actual_stdout is not None:
        parts.append(caret_diff(c.ev.expected_stdout, c.ev.actual_stdout, _labels(c)))
    parts += [c.t(*_EXACT_COMPARE), c.stdin_facts()]
    if len(changed_lines(diff)) > 1:
        parts.append(c.t(f"{len(changed_lines(diff))} lignes diffèrent au total : corrige la première puis relance l'analyse.",
                         f"{len(changed_lines(diff))} lines differ in total: fix the first one, then run the analysis again."))
    return join(*parts)


def _prompt_number(c: Ctx) -> str:
    parts = c.check.id.split(":")
    if c.check.id.startswith("prompt:") and parts[-1].isdigit():
        return parts[-1]
    return ""


@template("prompt_mismatch", "Prompt différent", "Different prompt")
def _prompt_mismatch(c: Ctx) -> str:
    pair = text_pair(c.check)
    intro = c.t("Le texte affiché par `input()` (le **prompt**) n'est pas exactement celui demandé par le sujet.",
                "The text shown by `input()` (the **prompt**) is not exactly the one required by the subject.")
    if pair is None:
        return join(intro, c.t(*_EXACT_COMPARE))
    expected, actual = pair
    trailing = expected.rstrip(" ") != expected and actual == expected.rstrip(" ")
    return join(
        intro,
        caret_diff(expected, actual, _labels(c)),
        _invisible_note(c, expected, actual),
        c.t(f"Il manque l'espace **après** {code(actual)} : écris {code('input(' + str_literal(expected) + ')')}.",
            f"The space **after** {code(actual)} is missing: write {code('input(' + str_literal(expected) + ')')}.") if trailing else "",
        c.t("Le prompt fait partie de la sortie : la moulinette le compare caractère par caractère, **espace final compris**.",
            "The prompt is part of the output: the grader compares it character by character, **trailing space included**."),
        c.t(f"Où regarder : {c.where()}.", f"Where to look: {c.where()}.") if c.where() else "",
    )


@template("missing_prompt", "Prompt manquant", "Missing prompt")
def _missing_prompt(c: Ctx) -> str:
    expected = expected_text(c.check)
    number = _prompt_number(c)
    which = c.t(f" (question n°{number})", f" (question #{number})") if number else ""
    shown = code(show_trailing(str_literal(expected)[1:-1])) if expected else c.t("demandé", "required")
    example = 'input("Pilot name: ")' if expected is None else "input(" + str_literal(expected) + ")"
    return join(
        c.t(f"Le sujet demande le prompt {shown}{which}, mais ton programme ne l'affiche pas.",
            f"The subject requires the prompt {shown}{which}, but your program does not show it."),
        c.t(f"Passe ce texte **en argument** de `input()` : {code(example)}.", f"Pass this text **as the argument** of `input()`: {code(example)}."),
        c.t(
            "À éviter : `print(\"...\")` suivi de `input()`. `print` ajoute un retour à la ligne, donc la sortie "
            "n'est plus identique à celle du sujet.",
            "Avoid `print(\"...\")` followed by `input()`. `print` adds a line break, so the output is no longer "
            "identical to the subject's.",
        ),
    )


def _diff_lines_block(lines: list[DiffLine], attr: str) -> str:
    texts = [show_trailing(getattr(line, attr) or "") for line in lines[:8]]
    more = ["…"] if len(lines) > 8 else []
    return block("\n".join(texts + more), "text") if texts else ""


@template("missing_output", "Sortie incomplète", "Missing output")
def _missing_output(c: Ctx) -> str:
    diff = stdout_diff(c.check)
    missing = lines_with_op(diff, "missing")
    stderr = c.ev.stderr
    return join(
        c.t("Ton programme s'arrête **trop tôt** : des lignes attendues n'ont pas été affichées.",
            "Your program stops **too early**: some expected lines were not printed."),
        c.t("Lignes manquantes :", "Missing lines:") if missing else "",
        _diff_lines_block(missing, "expected"),
        c.t("Causes fréquentes : une condition jamais vraie, un `print` oublié, ou un plantage (voir la sortie d'erreur).",
            "Common causes: a condition that is never true, a forgotten `print`, or a crash (see the error output)."),
        block(tail_lines(stderr, 8), "text") if stderr else "",
        c.stdin_facts(),
    )


@template("extra_output", "Sortie en trop", "Extra output")
def _extra_output(c: Ctx) -> str:
    extra = lines_with_op(stdout_diff(c.check), "extra")
    return join(
        c.t("Ton programme affiche des lignes **en trop** :", "Your program prints **extra** lines:"),
        _diff_lines_block(extra, "actual"),
        c.t("Souvent : un `print` de débogage oublié, ou un message affiché deux fois (par exemple dans une boucle).",
            "Often: a forgotten debug `print`, or a message printed twice (for example inside a loop)."),
        c.stdin_facts(),
    )


@template("exit_code", "Code de sortie inattendu", "Unexpected exit code")
def _exit_code(c: Ctx) -> str:
    expected = detail(c.check, "expected_exit_code", "expected")
    expected_code = expected if isinstance(expected, int) and not isinstance(expected, bool) else 0
    actual = c.ev.exit_code
    actual_txt = code(str(actual)) if actual is not None else c.t("non nul", "non-zero")
    return join(
        c.t(f"Ton programme s'est terminé avec le code de sortie {actual_txt} au lieu de {code(str(expected_code))}.",
            f"Your program exited with code {actual_txt} instead of {code(str(expected_code))}."),
        c.t(
            "Un code différent de `0` signale une erreur : une exception non rattrapée (le programme a planté) ou "
            "un appel à `exit(...)` / `sys.exit(...)` avec une valeur non nulle.",
            "A code other than `0` signals an error: an uncaught exception (the program crashed) or a call to "
            "`exit(...)` / `sys.exit(...)` with a non-zero value.",
        ),
        block(tail_lines(c.ev.stderr, 8), "text") if c.ev.stderr else "",
    )


@template("script_crash", "Le programme a planté", "The program crashed")
def _script_crash(c: Ctx) -> str:
    exc = c.ev.exception
    error = code(f"{exc.type}: {exc.message}") if exc else code(c.check.message)
    trace = exc.traceback if exc and exc.traceback else (c.ev.stderr or "")
    return join(
        c.t(f"Ton programme a **planté** pendant l'exécution{c.at_line()} : {error}.",
            f"Your program **crashed** while running{c.at_line()}: {error}."),
        exception_hint(c, exc.type) if exc else "",
        c.stdin_facts(),
        block(tail_lines(trace, 12), "text") if trace else "",
    )


@template("eof_error", "input() sans réponse", "input() with nothing left to read")
def _eof_error(c: Ctx) -> str:
    return join(
        c.t(
            "Ton programme a appelé `input()` **plus de fois** que le nombre de réponses prévues par l'exemple du "
            "sujet : il n'y avait plus rien à lire, d'où l'erreur `EOFError`.",
            "Your program called `input()` **more times** than the number of answers in the subject's example: "
            "there was nothing left to read, hence the `EOFError`.",
        ),
        c.stdin_facts(),
        c.t(f"L'appel en trop se trouve probablement {c.where()}." if c.where() else "",
            f"The extra call is probably at {c.where()}." if c.where() else ""),
        c.t("Vérifie le nombre et l'ordre des questions : un `input()` en trop, ou une boucle qui redemande une saisie ?",
            "Check the number and order of the questions: an extra `input()`, or a loop asking again?"),
    )


# ---------------------------------------------------------------------------------------------
# Fix hints (used when no deterministic patch is available)
# ---------------------------------------------------------------------------------------------


@hint("wrong_value", "returns_none")
def _value_steps(c: Ctx) -> list[str]:
    call = code(c.ev.call) if c.ev.call else c.t("le cas testé", "the tested case")
    return [
        c.t(f"Calcule à la main le résultat attendu pour {call}.", f"Work out by hand the expected result for {call}."),
        c.t("Suis ton code ligne par ligne avec ces valeurs : quelle branche est prise ? quel `return` est exécuté ?",
            "Trace your code line by line with these values: which branch is taken? which `return` runs?"),
        c.t(f"Compare avec la règle du sujet ({code(c.ev.rule)}) et corrige la condition ou le calcul." if c.ev.rule
            else "Compare avec la règle du sujet et corrige la condition ou le calcul.",
            f"Compare with the subject's rule ({code(c.ev.rule)}) and fix the condition or the computation." if c.ev.rule
            else "Compare with the subject's rule and fix the condition or the computation."),
    ]


@hint("wrong_type", "str_instead_of_bool", "number_as_str", "int_instead_of_float")
def _type_steps(c: Ctx) -> list[str]:
    exp = c.ev.expected_value
    want = code(exp.type) if exp else c.t("le type demandé", "the required type")
    return [
        c.t("Repère le `return` exécuté pour ce cas.", "Find the `return` executed for this case."),
        c.t(f"Fais en sorte qu'il renvoie une valeur de type {want} : pas de guillemets autour d'un booléen ou d'un nombre.",
            f"Make it return a value of type {want}: no quotes around a boolean or a number."),
        c.t("Vérifie dans un terminal avec `type(ma_fonction(...))`.", "Check in a terminal with `type(my_function(...))`."),
    ]


@hint("prints_instead_of_returns", "unexpected_stdout")
def _print_steps(c: Ctx) -> list[str]:
    return [
        c.t(f"Dans {c.fn_code()}, remplace le `print(...)` du résultat par `return ...`.",
            f"In {c.fn_code()}, replace the `print(...)` of the result with `return ...`."),
        c.t("Supprime les autres `print` de débogage à l'intérieur de la fonction.", "Remove the other debug `print` calls inside the function."),
        c.t("Si tu veux voir le résultat, affiche-le **en dehors** : `print(ma_fonction(...))` sous le *main guard*.",
            "If you want to see the result, print it **outside**: `print(my_function(...))` under the *main guard*."),
    ]


@hint("wrong_string", "stdout_mismatch", "prompt_mismatch", "missing_prompt")
def _text_steps(c: Ctx) -> list[str]:
    where = c.t(f" ({c.where()})", f" ({c.where()})") if c.where() else ""
    return [
        c.t(f"Copie le texte attendu **directement depuis le sujet** dans ta chaîne{where}.",
            f"Copy the expected text **directly from the subject** into your string{where}."),
        c.t("Vérifie les espaces (surtout en fin de prompt), la ponctuation et les majuscules.",
            "Check spaces (especially at the end of prompts), punctuation and capital letters."),
        c.t("Relance l'analyse et compare de nouveau ligne par ligne.", "Run the analysis again and compare line by line."),
    ]


@hint("missing_output", "extra_output", "exit_code", "eof_error")
def _flow_steps(c: Ctx) -> list[str]:
    return [
        c.t("Lance ton programme toi-même avec les saisies du sujet et compare la sortie à l'exemple.",
            "Run your program yourself with the subject's inputs and compare the output with the example."),
        c.t("Vérifie l'ordre des `input()` et des `print()` ainsi que les conditions qui choisissent les messages.",
            "Check the order of `input()` and `print()` calls and the conditions that choose the messages."),
        c.t("Corrige le premier écart, puis relance l'analyse.", "Fix the first difference, then run the analysis again."),
    ]


@hint("exception", "script_crash")
def _crash_steps(c: Ctx) -> list[str]:
    exc = c.ev.exception
    error = code(exc.type) if exc else c.t("l'erreur", "the error")
    return [
        c.t(f"Ouvre {c.where() or c.t('la ligne indiquée', 'the reported line')} : c'est là que {error} se produit.",
            f"Open {c.where() or 'the reported line'}: this is where {error} happens."),
        c.t("Reproduis le cas dans un terminal avec les mêmes valeurs et observe les variables (avec `print` temporaires).",
            "Reproduce the case in a terminal with the same values and inspect the variables (with temporary `print`s)."),
        c.t("Ajoute le traitement du cas particulier (division par zéro, conversion...) puis relance l'analyse.",
            "Handle the special case (division by zero, conversion...), then run the analysis again."),
    ]


@hint("timeout", "output_limit")
def _loop_steps(c: Ctx) -> list[str]:
    return [
        c.t("Repère tes boucles `while` : la condition finit-elle par devenir fausse ?", "Find your `while` loops: does the condition eventually become false?"),
        c.t("Vérifie que la variable de la condition est bien modifiée à chaque tour.", "Check that the condition's variable is updated at each iteration."),
        c.t("Vérifie que tu n'appelles pas `input()` plus que prévu.", "Check that you do not call `input()` more than expected."),
    ]


@hint("blocked_syscall")
def _blocked_steps(c: Ctx) -> list[str]:
    return [
        c.t("Cherche dans ton code `os`, `subprocess`, `socket`, `open(..., \"w\")`.", "Look for `os`, `subprocess`, `socket`, `open(..., \"w\")` in your code."),
        c.t("Supprime ce qui n'est pas demandé par le sujet.", "Remove whatever the subject does not ask for."),
    ]

