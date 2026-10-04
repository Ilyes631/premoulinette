"""Deterministic, offline, beginner-friendly explanations (French + English) of check results.

Public API (see docs/ARCHITECTURE.md, ``explain/``):

* :class:`Explanation`
* :func:`explain` — why a check has its status, keyed by ``check.diagnosis`` (fallback by category)
* :func:`how_to_fix` — the deterministic ``check.fix`` (diff / commands) or step-by-step hints
* :func:`expected_behavior` — what the subject requires (rules, examples, expected session)
* :data:`DIAGNOSIS_CODES` — the shared diagnosis registry; every code has an FR + EN template
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Importing the template modules registers every diagnosis in TEMPLATES / HINTS.
from premoulinette.explain import _tpl_code, _tpl_project, _tpl_runtime  # noqa: F401
from premoulinette.explain._context import Ctx, Lang
from premoulinette.explain._expected import build_expected
from premoulinette.explain._markdown import block, code, join, numbered
from premoulinette.explain._registry import HINTS, TEMPLATES
from premoulinette.explain._tpl_generic import category_fallback, generic_steps, info_body, notes, pass_body, skipped_body
from premoulinette.results.models import CheckResult, Fix
from premoulinette.spec.models import PracticalSpec

# Shared registry (docs/ARCHITECTURE.md "Diagnosis codes"), in table order, without duplicates.
DIAGNOSIS_CODES: tuple[str, ...] = (
    # structure
    "missing_file", "misplaced_file", "wrong_case_path", "parasite_file", "missing_gitignore", "extra_file",
    "missing_bonus_file",
    # syntax
    "syntax_error", "indentation_error", "encoding_error",
    # functions (static)
    "missing_function", "wrong_function_name", "function_in_wrong_file", "wrong_param_count", "wrong_param_names",
    "wrong_annotation", "prints_instead_of_returns", "str_instead_of_bool", "nested_function",
    # tests (runtime) — str_instead_of_bool / prints_instead_of_returns are shared with the static area
    "wrong_value", "wrong_type", "number_as_str", "int_instead_of_float", "returns_none", "wrong_string",
    "exception", "timeout", "output_limit", "blocked_syscall", "unexpected_stdout",
    # output (scripts)
    "stdout_mismatch", "prompt_mismatch", "missing_prompt", "missing_output", "extra_output", "exit_code",
    "script_crash", "eof_error",
    # constraints
    "forbidden_builtin", "builtin_not_allowed", "forbidden_import", "forbidden_method", "forbidden_construct",
    "missing_required_construct", "builtin_bypass",
    # runtime (import)
    "import_side_effects", "import_crash", "import_waits_input",
    # git
    "untracked_file", "ignored_file", "dirty_tree",
    # bonus
    "bonus_not_implemented",
)

_missing = set(DIAGNOSIS_CODES) - set(TEMPLATES)
if _missing:  # pragma: no cover - guarded by tests, fails fast at import if a template is removed
    raise RuntimeError(f"explanation templates missing for: {sorted(_missing)}")


class Explanation(BaseModel):
    title: str
    markdown: str
    provider: Literal["template", "ai"]
    language: Literal["fr", "en"]
    sent_payload: dict | None = None


def _lang(lang: str) -> Lang:
    return "en" if lang == "en" else "fr"


def explain(check: CheckResult, lang: Literal["fr", "en"] = "fr") -> Explanation:
    """Why this check has its status, for a beginner, using the check's concrete evidence."""
    c = Ctx(check, _lang(lang))
    tpl = TEMPLATES.get(check.diagnosis or "")
    if check.status == "pass":
        title, body = pass_body(c)
    elif check.status == "skipped":
        title, body = skipped_body(c)
    elif tpl is not None:
        title, body = tpl.title(c), tpl.body(c)
    elif check.status == "info":
        title, body = info_body(c)
    else:
        title, body = category_fallback(c)
    return Explanation(title=title, markdown=join(body, notes(c)), provider="template", language=c.lang)


# ---------------------------------------------------------------------------------------------
# how_to_fix
# ---------------------------------------------------------------------------------------------

_FIX_INTRO: dict[str, tuple[str, str]] = {
    "str_instead_of_bool": ("Retire les guillemets : renvoie les booléens `True` / `False`, pas des chaînes.",
                            "Remove the quotes: return the booleans `True` / `False`, not strings."),
    "number_as_str": ("Retire les guillemets autour du nombre renvoyé.", "Remove the quotes around the returned number."),
    "wrong_string": ("Corrige le texte de la chaîne pour qu'il soit identique à celui du sujet.",
                     "Fix the string's text so that it is identical to the subject's."),
    "prompt_mismatch": ("Corrige le texte du prompt pour qu'il soit identique à celui du sujet (espace final compris).",
                        "Fix the prompt text so that it is identical to the subject's (trailing space included)."),
    "stdout_mismatch": ("Corrige le texte affiché sur cette ligne pour qu'il soit identique à celui du sujet.",
                        "Fix the text printed on this line so that it is identical to the subject's."),
    "wrong_function_name": ("Renomme la fonction avec le nom exact du sujet. Pense aussi à renommer les endroits où tu l'appelles.",
                            "Rename the function to the subject's exact name. Also rename the places where you call it."),
    "prints_instead_of_returns": ("Renvoie la valeur au lieu de l'afficher.", "Return the value instead of printing it."),
    "missing_gitignore": ("Crée le fichier `.gitignore` à la racine du dépôt, puis ajoute-le avec `git add .gitignore` et commit.",
                          "Create the `.gitignore` file at the repository root, then add it with `git add .gitignore` and commit."),
    "parasite_file": ("Retire ce fichier du suivi Git (ta copie locale est conservée) et ajoute son motif au `.gitignore`.",
                      "Stop tracking this file in Git (your local copy is kept) and add its pattern to `.gitignore`."),
    "misplaced_file": ("Déplace le fichier au chemin exact demandé :", "Move the file to the exact required path:"),
    "wrong_case_path": ("Renomme le fichier avec la casse exacte, en passant par un nom temporaire :",
                        "Rename the file with the exact case, going through a temporary name:"),
    "untracked_file": ("Ajoute le fichier à Git, puis fais un commit :", "Add the file to Git, then commit:"),
    "forbidden_builtin": ("Il n'y a pas de correctif automatique : remplace l'appel interdit par ta propre logique.",
                          "There is no automatic fix: replace the forbidden call with your own logic."),
}

_CONFIDENCE_NOTE: dict[str, tuple[str, str]] = {
    "medium": ("*Suggestion à vérifier : elle est probablement correcte, mais relis-la avant de l'appliquer.*",
               "*Suggestion to double-check: it is probably right, but read it before applying it.*"),
    "low": ("*Simple piste : ce n'est pas un correctif garanti.*", "*Just a lead: this is not a guaranteed fix.*"),
}


def _is_command(fix: Fix) -> bool:
    return fix.patch is None and fix.before is None and bool(fix.after) and fix.after.lstrip().startswith("git ")


def _render_fix(c: Ctx, fix: Fix) -> str:
    intro = _FIX_INTRO.get(c.check.diagnosis or "")
    summary_only = not fix.patch and not _is_command(fix) and fix.before is None
    if intro is None:
        parts = [fix.summary] if c.lang == "en" else ["Modification proposée (résumé en anglais) :", f"*{fix.summary}*"]
    else:
        parts = [c.t(*intro)]
        if summary_only and c.lang == "en" and fix.summary:
            parts.append(fix.summary)
    if fix.patch:
        parts.append(block(fix.patch, "diff"))
    elif _is_command(fix):
        parts.append(block(fix.after or "", "sh"))
    elif fix.before is not None and fix.after is not None:
        parts += [c.t("Avant :", "Before:"), block(fix.before, "python"), c.t("Après :", "After:"), block(fix.after, "python")]
    note = _CONFIDENCE_NOTE.get(fix.confidence)
    if note:
        parts.append(c.t(*note))
    if fix.patch or fix.before is not None:
        file_txt = c.t(f" dans {code(fix.file)}", f" in {code(fix.file)}") if fix.file else ""
        parts.append(c.t(
            f"Ce correctif est minimal et n'est **jamais appliqué automatiquement** : fais la modification toi-même{file_txt}, puis relance l'analyse.",
            f"This fix is minimal and is **never applied automatically**: make the change yourself{file_txt}, then run the analysis again.",
        ))
    return join(*parts)


def _steps(c: Ctx) -> list[str]:
    steps_fn = HINTS.get(c.check.diagnosis or "")
    return steps_fn(c) if steps_fn else generic_steps(c)


def how_to_fix(check: CheckResult, lang: Literal["fr", "en"] = "fr") -> Explanation:
    """The deterministic fix (diff or command) when available, else a step-by-step hint (never a full solution)."""
    c = Ctx(check, _lang(lang))
    title = c.t(f"Comment corriger : {check.title}", f"How to fix: {check.title}")
    if check.status == "pass":
        body = c.t("Rien à corriger : ce point est validé.", "Nothing to fix: this point passes.")
    elif check.status == "skipped":
        blocker = code(check.blocked_by) if check.blocked_by else c.t("le problème qui le bloque", "the problem blocking it")
        body = c.t(f"Corrige d'abord {blocker} : ce test sera ensuite exécuté normalement.",
                   f"Fix {blocker} first: this test will then run normally.")
    elif check.fix is not None:
        fix_md = _render_fix(c, check.fix)
        steps = "" if check.fix.confidence == "high" and (check.fix.patch or _is_command(check.fix)) else numbered(_steps(c))
        body = join(fix_md, c.t("**Étapes :**", "**Steps:**") if steps else "", steps)
    else:
        body = join(c.t("**Étapes :**", "**Steps:**"), numbered(_steps(c)))
    return Explanation(title=title, markdown=join(body, notes(c)), provider="template", language=c.lang)


def expected_behavior(check: CheckResult, spec: PracticalSpec, lang: Literal["fr", "en"] = "fr") -> Explanation:
    """What the subject requires for this check: rule, function rules/examples, or the expected session."""
    c = Ctx(check, _lang(lang))
    return Explanation(
        title=c.t("Ce que demande le sujet", "What the subject requires"),
        markdown=build_expected(check, spec, c),
        provider="template",
        language=c.lang,
    )
