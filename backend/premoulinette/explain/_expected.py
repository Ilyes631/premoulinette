"""``expected_behavior``: what the subject requires for a check (rules, examples, expected session)."""
from __future__ import annotations

import posixpath

from premoulinette.explain._context import Ctx
from premoulinette.explain._evidence import expected_text, subject_path
from premoulinette.explain._markdown import block, bullets, code, join, quote, show_trailing, str_literal
from premoulinette.results.models import CheckResult
from premoulinette.spec.models import (
    BehaviorRule,
    ExerciseSpec,
    FunctionSpec,
    InteractionStep,
    Origin,
    PracticalSpec,
    ScriptTest,
)

INPUT_OPEN, INPUT_CLOSE = "⟨", "⟩"
_MAX_EXAMPLES = 8


# ---------------------------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------------------------


def find_exercise(check: CheckResult, spec: PracticalSpec) -> ExerciseSpec | None:
    if check.exercise_id:
        found = spec.exercise(check.exercise_id)
        if found:
            return found
    paths = {p for p in (check.file, check.location.file if check.location else None, subject_path(check)) if p}
    for ex in spec.exercises:
        if ex.file_path in paths and (not check.function or any(f.name == check.function for f in ex.functions)):
            return ex
    return None


def find_function(check: CheckResult, spec: PracticalSpec, ex: ExerciseSpec | None) -> FunctionSpec | None:
    if not check.function:
        return None
    pools = [ex.functions] if ex else []
    pools.append([f for e in spec.exercises for f in e.functions])
    for pool in pools:
        for fn in pool:
            if fn.name == check.function:
                return fn
    return None


def _test_id(check: CheckResult) -> str | None:
    if check.test_id:
        return check.test_id
    return check.id[len("test:"):] if check.id.startswith("test:") else None


def find_script_test(check: CheckResult, ex: ExerciseSpec | None) -> ScriptTest | None:
    if ex is None or ex.script is None or not ex.script.tests:
        return None
    wanted = _test_id(check)
    match = next((t for t in ex.script.tests if t.id == wanted), None)
    if match is not None:
        return match
    return ex.script.tests[0] if check.category == "output" else None


# ---------------------------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------------------------


def _origin_quote(c: Ctx, origin: Origin | None) -> str:
    if origin is None or origin.source is None or not origin.source.excerpt:
        return ""
    section = f" — *{origin.source.section}*" if origin.source.section else ""
    label = c.t("Extrait du sujet", "Subject excerpt")
    unofficial = ""
    if origin.provenance == "ai_extracted":
        unofficial = c.t(" (extrait par IA, à vérifier)", " (AI-extracted, please double-check)")
    return join(f"{label}{unofficial}{section} :" if c.lang == "fr" else f"{label}{unofficial}{section}:", quote(origin.source.excerpt))


def render_rule(c: Ctx, rule: BehaviorRule) -> str:
    if rule.raises:
        outcome = c.t(f"lève {code(rule.raises)}", f"raises {code(rule.raises)}")
    elif rule.returns is not None:
        outcome = code(rule.returns)
    else:
        outcome = c.t("(résultat non précisé)", "(result not specified)")
    head = c.t(f"si {code(rule.when)}", f"if {code(rule.when)}") if rule.when else c.t("sinon", "otherwise")
    text = f"{head} → {outcome}"
    if rule.description and rule.description.strip() not in (rule.when or ""):
        text += f" — *{rule.description.strip()}*"
    return text


def _examples(c: Ctx, fn: FunctionSpec, current: str | None) -> str:
    lines: list[str] = []
    for test in fn.tests[:_MAX_EXAMPLES]:
        marker = c.t("  # <- ce test", "  # <- this test") if test.id == current else ""
        lines.append(f">>> {test.call_repr()}{marker}")
        if test.expected_exception:
            lines.append(f"{test.expected_exception}: ...")
        elif test.expected_return is not None:
            lines.append(test.expected_return)
        if test.expected_stdout:
            lines.append(c.t("# affiche : ", "# prints: ") + str_literal(test.expected_stdout))
    return block("\n".join(lines), "python") if lines else ""


def function_section(c: Ctx, fn: FunctionSpec, ex: ExerciseSpec | None) -> str:
    current = _test_id(c.check)
    file_txt = f" ({code(ex.file_path)})" if ex else ""
    parts = [
        c.t(f"**Signature demandée**{file_txt} :", f"**Required signature**{file_txt}:"),
        block(fn.signature.render() + ":", "python"),
    ]
    if fn.description:
        parts.append(fn.description)
    if fn.rules:
        parts += [c.t("**Règles du sujet :**", "**Subject rules:**"), bullets([render_rule(c, r) for r in fn.rules])]
    if fn.reference:
        parts.append(c.t(f"**Formule du sujet :** {code(fn.reference)}", f"**Subject formula:** {code(fn.reference)}"))
    examples = _examples(c, fn, current)
    if examples:
        parts += [c.t("**Exemples du sujet :**", "**Subject examples:**"), examples]
    ev = c.ev
    in_examples = any(t.id == current for t in fn.tests)
    if ev.call and not in_examples:
        expected = c.t(f", attendu {c.typed(ev.expected_value)}", f", expected {c.typed(ev.expected_value)}") if ev.expected_value else ""
        origin = (c.t(f" (déduit de la règle {code(ev.rule)})", f" (derived from the rule {code(ev.rule)})") if ev.rule else "")
        parts.append(c.t(f"**Cas testé :** {code(ev.call)}{expected}{origin}.", f"**Tested case:** {code(ev.call)}{expected}{origin}."))
    if fn.must_return:
        parts.append(
            c.t("La fonction doit **renvoyer** son résultat avec `return`", "The function must **return** its result with `return`")
            + (c.t(", sans rien afficher.", ", without printing anything.") if not fn.may_print else ".")
        )
    parts.append(_origin_quote(c, fn.origin))
    return join(*parts)


def render_transcript(steps: list[InteractionStep]) -> str:
    """Terminal session with typed input between ⟨ ⟩ and trailing spaces shown as ␠."""
    out: list[str] = []
    pending = ""
    for step in steps:
        if step.kind == "output":
            pending += step.text
            *complete, pending = pending.split("\n")
            out.extend(show_trailing(line) for line in complete)
        else:
            out.append(show_trailing(pending) + INPUT_OPEN + step.text + INPUT_CLOSE)
            pending = ""
    if pending:
        out.append(show_trailing(pending))
    return "\n".join(out)


def _steps_of(c: Ctx, test: ScriptTest | None) -> list[InteractionStep]:
    if c.ev.expected_steps:
        steps: list[InteractionStep] = []
        for raw in c.ev.expected_steps:
            kind, text = raw.get("kind"), raw.get("text")
            if kind in ("output", "input") and isinstance(text, str):
                steps.append(InteractionStep(kind=kind, text=text))
        if steps:
            return steps
    if test is not None and test.steps:
        return list(test.steps)
    if test is not None and test.expected_stdout is not None:
        return [InteractionStep(kind="output", text=test.expected_stdout)]
    return []


def session_section(c: Ctx, ex: ExerciseSpec | None, test: ScriptTest | None) -> str:
    steps = _steps_of(c, test)
    parts: list[str] = []
    if steps:
        script = posixpath.basename(ex.file_path) if ex else (posixpath.basename(c.file) if c.file else "script.py")
        argv = " ".join(test.argv) if test and test.argv else ""
        command = f"$ python3 {script}" + (f" {argv}" if argv else "")
        transcript = render_transcript(steps)
        title = test.title if test and test.title else (test.id if test else "")
        parts += [
            c.t(f"**Session attendue**{' (' + code(title) + ')' if title else ''} :", f"**Expected session**{' (' + code(title) + ')' if title else ''}:"),
            block(command + "\n" + transcript, "text"),
            c.t("Les saisies au clavier sont entre ⟨ ⟩ (elles ne font pas partie de la sortie du programme)"
                + (" et `␠` marque un espace en fin de ligne." if "␠" in transcript else "."),
                "Typed input is shown between ⟨ ⟩ (it is not part of the program output)"
                + (" and `␠` marks a space at the end of a line." if "␠" in transcript else ".")),
        ]
    if ex and ex.script and ex.script.prompts:
        prompts = ", ".join(code(show_trailing(p)) for p in ex.script.prompts)
        parts.append(c.t(f"**Prompts attendus, dans l'ordre :** {prompts}", f"**Expected prompts, in order:** {prompts}"))
    if c.check.id.startswith("prompt:"):
        wanted = expected_text(c.check)
        if wanted is not None:
            parts.append(c.t(f"Ce prompt doit être exactement {code(show_trailing(wanted))}, à passer à `input()`.",
                             f"This prompt must be exactly {code(show_trailing(wanted))}, passed to `input()`."))
    if ex and ex.script and ex.script.required_outputs:
        parts.append(c.t("**Lignes obligatoires :** ", "**Required lines:** ") + ", ".join(code(o) for o in ex.script.required_outputs))
    if parts:
        parts.append(c.t("La sortie doit correspondre **exactement** (espaces, ponctuation, majuscules, retours à la ligne).",
                         "The output must match **exactly** (spaces, punctuation, capitals, line breaks)."))
    if test is not None:
        parts.append(_origin_quote(c, test.origin))
    return join(*parts)


def structure_section(c: Ctx, spec: PracticalSpec) -> str:
    path = subject_path(c.check)
    parts: list[str] = []
    requirement = next((f for f in spec.expected_files() if f.path == path), None)
    if requirement is not None:
        status = (c.t("bonus (facultatif)", "bonus (optional)") if requirement.bonus
                  else c.t("obligatoire", "required") if requirement.required else c.t("facultatif", "optional"))
        parts.append(c.t(f"Le sujet demande le fichier {code(requirement.path)} : **{status}**.",
                         f"The subject requires the file {code(requirement.path)}: **{status}**."))
        if requirement.description:
            parts.append(requirement.description)
        parts.append(_origin_quote(c, requirement.origin))
    if c.check.diagnosis in ("parasite_file", "missing_gitignore") or c.check.id == "structure:gitignore":
        patterns = ", ".join(code(p) for p in spec.structure.forbidden_patterns)
        severity = (c.t("Le sujet les **interdit explicitement**.", "The subject **explicitly forbids** them.")
                    if spec.structure.forbidden_patterns_are_errors
                    else c.t("Ils sont signalés par prudence.", "They are reported as a precaution."))
        parts.append(c.t(f"Fichiers à ne pas rendre : {patterns}. {severity}", f"Files not to submit: {patterns}. {severity}"))
        if spec.structure.require_gitignore:
            parts.append(c.t("Le dépôt doit contenir un fichier `.gitignore` à la racine.", "The repository must contain a `.gitignore` file at its root."))
    if not parts and path:
        parts.append(c.t(f"Le chemin concerné est {code(path)} : la moulinette le cherche exactement à cet endroit.",
                         f"The path concerned is {code(path)}: the grader looks for it exactly there."))
    return join(*parts)


def constraints_section(c: Ctx, spec: PracticalSpec, ex: ExerciseSpec | None) -> str:
    cons = spec.effective_constraints(ex) if ex else spec.global_constraints
    items: list[str] = []
    if cons.allowed_builtins is not None:
        items.append(c.t("fonctions intégrées autorisées : ", "allowed builtins: ") + (", ".join(code(b) for b in cons.allowed_builtins) or c.t("aucune", "none")))
    if cons.forbidden_builtins:
        items.append(c.t("fonctions intégrées interdites : ", "forbidden builtins: ") + ", ".join(code(b) for b in cons.forbidden_builtins))
    if cons.allowed_imports is not None:
        items.append(c.t("imports autorisés : ", "allowed imports: ") + (", ".join(code(m) for m in cons.allowed_imports) or c.t("**aucun**", "**none**")))
    if cons.forbidden_imports:
        items.append(c.t("imports interdits : ", "forbidden imports: ") + ", ".join(code(m) for m in cons.forbidden_imports))
    if cons.forbidden_methods:
        items.append(c.t("méthodes interdites : ", "forbidden methods: ") + ", ".join(code("." + m + "()") for m in cons.forbidden_methods))
    if cons.forbidden_constructs:
        items.append(c.t("constructions interdites : ", "forbidden constructs: ") + ", ".join(code(x) for x in cons.forbidden_constructs))
    if cons.required_constructs:
        items.append(c.t("constructions obligatoires : ", "required constructs: ") + ", ".join(code(x) for x in cons.required_constructs))
    if not items:
        return ""
    return join(c.t("**Contraintes du sujet :**", "**Subject constraints:**"), bullets(items), _origin_quote(c, cons.origin))


def git_section(c: Ctx) -> str:
    return c.t(
        "Le sujet attend que tes fichiers soient **commités** dans ton dépôt Git : la moulinette récupère le contenu "
        "du dépôt, pas ton dossier local. Les fichiers non suivis ou ignorés ne sont pas rendus.",
        "The subject expects your files to be **committed** to your Git repository: the grader takes the "
        "repository content, not your local folder. Untracked or ignored files are not submitted.",
    )


def build_expected(check: CheckResult, spec: PracticalSpec, c: Ctx) -> str:
    ex = find_exercise(check, spec)
    parts: list[str] = []
    if c.ev.rule and not check.function:
        parts.append(c.t(f"**Règle appliquée :** {code(c.ev.rule)}", f"**Applied rule:** {code(c.ev.rule)}"))
    fn = find_function(check, spec, ex)
    if fn is not None:
        parts.append(function_section(c, fn, ex))
    if check.category == "output" or check.id.startswith("prompt:") or (ex is not None and ex.kind == "script" and fn is None):
        parts.append(session_section(c, ex, find_script_test(check, ex)))
    if check.category == "structure":
        parts.append(structure_section(c, spec))
    if check.category == "constraints":
        parts.append(constraints_section(c, spec, ex))
    if check.category == "git":
        parts.append(git_section(c))
    body = join(*parts)
    if body:
        return body
    if ex is not None:
        return join(
            c.t(f"**{ex.title}** — fichier {code(ex.file_path)}", f"**{ex.title}** — file {code(ex.file_path)}"),
            ex.description or "",
            _origin_quote(c, ex.origin),
        )
    return c.t("Le sujet ne donne pas de règle plus précise pour ce point.", "The subject gives no more precise rule for this point.")
