"""Fallback explanations: per category (unknown diagnosis), passing checks, skipped checks, extra notes."""
from __future__ import annotations

from premoulinette.explain._context import Ctx
from premoulinette.explain._markdown import code, join, quote

# (title_fr, title_en, body_fr, body_en) for a failing/warning check without a known diagnosis
_CATEGORY_FAIL: dict[str, tuple[str, str, str, str]] = {
    "structure": ("Problème de structure", "Structure problem",
                  "Un problème de **structure** du dépôt a été détecté. Les moulinettes vérifient les chemins et les noms de fichiers **exactement** (majuscules comprises).",
                  "A repository **structure** problem was detected. Graders check paths and file names **exactly** (case included)."),
    "syntax": ("Fichier illisible", "Unreadable file",
               "Python n'arrive pas à lire ce fichier : aucune de ses fonctions ne peut être testée tant que le problème existe.",
               "Python cannot read this file: none of its functions can be tested while the problem remains."),
    "functions": ("Problème de fonction", "Function problem",
                  "La fonction ne correspond pas à ce que demande le sujet (nom, paramètres ou comportement détecté sans exécuter le code).",
                  "The function does not match what the subject requires (name, parameters or behaviour detected without running the code)."),
    "explicit_tests": ("Exemple du sujet non respecté", "Subject example not met",
                       "Ce test reprend **un exemple donné dans le sujet** : la moulinette le vérifiera très probablement.",
                       "This test is **an example given in the subject**: the grader will very likely check it."),
    "derived_tests": ("Règle du sujet non respectée", "Subject rule not met",
                      "Ce test est **déduit d'une règle du sujet** (par exemple une valeur limite) : il ne figure pas tel quel dans le sujet, mais découle directement de la règle.",
                      "This test is **derived from a subject rule** (for example a boundary value): it is not literally in the subject, but follows directly from the rule."),
    "heuristic_tests": ("Cas supplémentaire en échec", "Extra case failing",
                        "Ce cas **n'apparaît pas dans le sujet** : c'est un test supplémentaire proposé par PréMoulinette (valeur nulle, négative, grande...).",
                        "This case **is not in the subject**: it is an extra test proposed by PréMoulinette (zero, negative, large value...)."),
    "output": ("Sortie différente", "Different output",
               "La sortie du programme ne correspond pas à celle du sujet. La moulinette compare la sortie **caractère par caractère**.",
               "The program output does not match the subject. The grader compares output **character by character**."),
    "constraints": ("Contrainte du sujet non respectée", "Subject constraint not met",
                    "Ton code utilise quelque chose que le sujet interdit (fonction, import ou construction). Les moulinettes le détectent automatiquement.",
                    "Your code uses something the subject forbids (function, import or construct). Graders detect it automatically."),
    "runtime": ("Problème à l'exécution", "Runtime problem",
                "Un problème est survenu en important ou en exécutant ton fichier, en dehors d'un test précis.",
                "A problem occurred while importing or running your file, outside of a specific test."),
    "git": ("Problème Git", "Git problem",
            "Un problème Git a été détecté : la moulinette ne voit que ce qui est **commité** dans ton dépôt.",
            "A Git problem was detected: the grader only sees what is **committed** to your repository."),
}

# (body_fr, body_en) explaining why a passing check passes
_CATEGORY_PASS: dict[str, tuple[str, str]] = {
    "structure": ("Le fichier est présent **au chemin exact** demandé, avec la bonne casse : la moulinette le trouvera.",
                  "The file is present **at the exact path** required, with the right case: the grader will find it."),
    "syntax": ("Python lit ce fichier sans erreur de syntaxe : il peut être importé et testé.",
               "Python reads this file without a syntax error: it can be imported and tested."),
    "functions": ("La fonction existe avec le nom et la signature demandés par le sujet.",
                  "The function exists with the name and signature required by the subject."),
    "explicit_tests": ("Ta fonction renvoie exactement la valeur de l'exemple du sujet (même valeur **et** même type).",
                       "Your function returns exactly the value of the subject's example (same value **and** same type)."),
    "derived_tests": ("Ta fonction respecte la règle du sujet sur ce cas déduit (par exemple une valeur limite).",
                      "Your function follows the subject's rule on this derived case (for example a boundary value)."),
    "heuristic_tests": ("Ta fonction se comporte correctement sur ce cas supplémentaire (non officiel).",
                        "Your function behaves correctly on this extra (unofficial) case."),
    "output": ("La sortie est identique **caractère par caractère** à celle du sujet, prompts et retours à la ligne compris.",
               "The output is identical **character by character** to the subject's, prompts and line breaks included."),
    "constraints": ("Aucune utilisation interdite n'a été détectée pour cette contrainte.",
                    "No forbidden use was detected for this constraint."),
    "runtime": ("L'import du fichier ne produit aucun effet de bord (pas d'affichage, pas de saisie, pas de plantage).",
                "Importing the file has no side effects (no output, no input, no crash)."),
    "git": ("Git suit bien ce qui doit être rendu.", "Git tracks what must be submitted."),
}

_GENERIC_STEPS: dict[str, tuple[list[str], list[str]]] = {
    "structure": (["Compare ton arborescence avec celle du sujet, chemin par chemin.", "Corrige noms et dossiers avec `git mv`, puis commit."],
                  ["Compare your tree with the subject's, path by path.", "Fix names and folders with `git mv`, then commit."]),
    "git": (["Lance `git status` pour voir l'état du dépôt.", "`git add` les fichiers à rendre, puis commit."],
            ["Run `git status` to see the repository state.", "`git add` the files to submit, then commit."]),
}
_DEFAULT_STEPS = (
    ["Relis la partie du sujet concernée (bouton « Ce que demande le sujet »).", "Reproduis le cas toi-même dans un terminal.", "Corrige, puis relance l'analyse."],
    ["Re-read the relevant part of the subject (\"What the subject requires\").", "Reproduce the case yourself in a terminal.", "Fix it, then run the analysis again."],
)


def category_fallback(c: Ctx) -> tuple[str, str]:
    """(title, body) for a failing check whose diagnosis has no dedicated template."""
    title_fr, title_en, body_fr, body_en = _CATEGORY_FAIL.get(
        c.check.category, ("Problème détecté", "Problem detected", "Un problème a été détecté.", "A problem was detected.")
    )
    return c.t(title_fr, title_en), join(
        c.t(body_fr, body_en),
        c.t("Résultat de l'analyse :", "Analysis result:"),
        quote(c.check.message),
        c.facts(),
    )


def pass_body(c: Ctx) -> tuple[str, str]:
    body = _CATEGORY_PASS.get(c.check.category, ("Ce point est validé.", "This point is validated."))
    rule = c.t(f"Règle vérifiée : {code(c.ev.rule)}.", f"Checked rule: {code(c.ev.rule)}.") if c.ev.rule else ""
    return c.t("Pourquoi ce point est validé", "Why this passes"), join(c.t(*body), c.facts(where=False), rule)


def skipped_body(c: Ctx) -> tuple[str, str]:
    blocker = code(c.check.blocked_by) if c.check.blocked_by else c.t("un autre problème", "another problem")
    return c.t("Test non exécuté", "Test not run"), join(
        c.t(
            f"Ce point n'a **pas pu être vérifié** car {blocker} a échoué avant (fichier absent, erreur de syntaxe, "
            "fonction introuvable...). Il compte quand même comme **non réussi**.",
            f"This point **could not be checked** because {blocker} failed first (missing file, syntax error, "
            "function not found...). It still counts as **not passed**.",
        ),
        c.t("Corrige d'abord ce problème : ce test sera alors exécuté normalement.", "Fix that problem first: this test will then run normally."),
    )


def info_body(c: Ctx) -> tuple[str, str]:
    return c.t("Information", "Information"), join(
        c.t("Ce point est une simple **information** : il ne compte pas dans ton score.",
            "This point is just **information**: it does not count in your score."),
        quote(c.check.message),
    )


def generic_steps(c: Ctx) -> list[str]:
    fr, en = _GENERIC_STEPS.get(c.check.category, _DEFAULT_STEPS)
    return fr if c.lang == "fr" else en


def notes(c: Ctx) -> str:
    """Context notes appended to every explanation (bonus, unofficial test, AI-extracted requirement)."""
    check = c.check
    parts: list[str] = []
    if (check.bonus or check.status == "bonus") and check.diagnosis not in ("bonus_not_implemented", "missing_bonus_file"):
        parts.append(c.t(
            "**Bonus :** ce point concerne une partie facultative. Il **n'affecte pas ton score obligatoire** ; "
            "les bonus ne comptent en général que si toute la partie obligatoire fonctionne.",
            "**Bonus:** this point is about an optional part. It **does not affect your mandatory score**; "
            "bonus parts usually only count once every mandatory part works.",
        ))
    if check.category == "heuristic_tests" and check.status != "pass" and check.diagnosis is not None:
        parts.append(c.t(
            "**Test non officiel :** ce cas n'est pas dans le sujet. Il ne compte pas dans ton score obligatoire, "
            "mais il peut révéler un vrai bug.",
            "**Unofficial test:** this case is not in the subject. It does not count in your mandatory score, "
            "but it may reveal a real bug.",
        ))
    if check.origin.provenance == "ai_extracted":
        parts.append(c.t(
            "**À vérifier :** cette exigence a été extraite par IA et n'a pas été retrouvée mot pour mot dans le "
            "sujet. Relis le sujet avant de modifier ton code.",
            "**To double-check:** this requirement was extracted by AI and was not found word for word in the "
            "subject. Re-read the subject before changing your code.",
        ))
    return join(*parts)
