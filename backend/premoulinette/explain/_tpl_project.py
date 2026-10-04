"""Templates for repository-level diagnoses: structure, git and bonus."""
from __future__ import annotations

import posixpath

from premoulinette.explain._context import Ctx
from premoulinette.explain._evidence import detail, expected_and_found_paths, subject_path
from premoulinette.explain._markdown import block, bullets, code, join
from premoulinette.explain._registry import hint, template
from premoulinette.explain._shell import GITIGNORE_LINES, gitignore_pattern, sh_path


_EXACT_PATH = (
    "Les moulinettes cherchent chaque fichier à son **chemin exact**, majuscules et minuscules comprises : "
    "un nom comme `Kelvin.py` au lieu de `kelvin.py`, ou un dossier mal orthographié, ne sera pas trouvé.",
    "Graders look for each file at its **exact path**, including upper/lower case: a name such as "
    "`Kelvin.py` instead of `kelvin.py`, or a misspelled folder, will not be found.",
)
_BONUS_OK = (
    "**Pas d'inquiétude :** les bonus sont facultatifs et **n'affectent pas ton score obligatoire**. "
    "Ils ne comptent en général que si toute la partie obligatoire fonctionne.",
    "**Don't worry:** bonus parts are optional and **do not affect your mandatory score**. "
    "They usually only count once every mandatory part works.",
)


def _path(c: Ctx) -> str:
    return subject_path(c.check) or c.file or "?"


# ---------------------------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------------------------


@template("missing_file", "Fichier manquant", "Missing file")
def _missing_file(c: Ctx) -> str:
    path = _path(c)
    consequence = (
        c.t(
            "Tant qu'il manque, aucun test de ce fichier ne peut être lancé : ils comptent tous comme non réussis.",
            "As long as it is missing, none of its tests can run: they all count as not passed.",
        )
        if c.check.mandatory
        else ""
    )
    return join(
        c.t(f"Le fichier {code(path)} est introuvable dans ton dépôt.", f"The file {code(path)} cannot be found in your repository."),
        c.t("Crée-le exactement à ce chemin, depuis la racine du dépôt :", "Create it at exactly this path, from the repository root:"),
        block(path),
        c.t(*_EXACT_PATH),
        consequence,
    )


@hint("missing_file")
def _missing_file_steps(c: Ctx) -> list[str]:
    path = _path(c)
    return [
        c.t(f"Crée le fichier {code(path)} (chemin relatif à la racine du dépôt).", f"Create the file {code(path)} (path relative to the repository root)."),
        c.t("Vérifie l'orthographe **et la casse** de chaque dossier du chemin.", "Check the spelling **and the case** of every folder in the path."),
        c.t(f"Ajoute-le à Git : {code('git add ' + sh_path(path))}, puis fais un commit.", f"Add it to Git: {code('git add ' + sh_path(path))}, then commit."),
        c.t("Relance l'analyse.", "Run the analysis again."),
    ]


@template("misplaced_file", "Fichier mal placé", "Misplaced file")
def _misplaced_file(c: Ctx) -> str:
    expected, found = expected_and_found_paths(c.check)
    if not (expected and found):
        return join(
            c.t("Ce fichier existe, mais **pas à l'endroit demandé** par le sujet.", "This file exists, but **not where the subject expects it**."),
            c.t(*_EXACT_PATH),
        )
    return join(
        c.t(
            f"Le fichier existe, mais **pas au bon endroit** : il est dans {code(found)} alors que le sujet l'attend dans {code(expected)}.",
            f"The file exists, but **in the wrong place**: it is at {code(found)} while the subject expects {code(expected)}.",
        ),
        c.t("Déplace-le à l'emplacement exact demandé :", "Move it to the exact expected location:"),
        block(f"git mv {sh_path(found)} {sh_path(expected)}", "sh"),
        c.t(
            "La moulinette ne cherche qu'au chemin exact : un fichier mal placé est considéré comme **absent**, même si son code est juste. "
            "PréMoulinette a quand même testé le fichier trouvé pour t'aider, la vraie moulinette ne le fera pas.",
            "The grader only looks at the exact path: a misplaced file counts as **missing**, even if its code is right. "
            "PréMoulinette still tested the file it found to help you; the real grader will not.",
        ),
    )


@template("wrong_case_path", "Majuscules/minuscules incorrectes", "Wrong upper/lower case")
def _wrong_case_path(c: Ctx) -> str:
    expected, found = expected_and_found_paths(c.check)
    names = (
        c.t(f" : {code(found)} au lieu de {code(expected)}", f": {code(found)} instead of {code(expected)}")
        if expected and found
        else ""
    )
    commands = ""
    if expected and found:
        tmp = found + ".tmp"
        commands = block(f"git mv {sh_path(found)} {sh_path(tmp)}\ngit mv {sh_path(tmp)} {sh_path(expected)}", "sh")
    return join(
        c.t(
            f"Le chemin ne diffère que par des **majuscules/minuscules**{names}.",
            f"The path only differs by **upper/lower case**{names}.",
        ),
        c.t(
            "Sur Windows et macOS, cette différence passe souvent inaperçue, mais la moulinette tourne sous Linux, "
            "où `Kelvin.py` et `kelvin.py` sont **deux fichiers différents** : ton fichier ne serait pas trouvé.",
            "On Windows and macOS this difference often goes unnoticed, but the grader runs on Linux, where "
            "`Kelvin.py` and `kelvin.py` are **two different files**: your file would not be found.",
        ),
        c.t(
            "Renomme-le en passant par un nom temporaire (sinon Git peut ignorer un changement de casse seul) :",
            "Rename it through a temporary name (otherwise Git may ignore a case-only change):",
        )
        if commands
        else "",
        commands,
    )


@hint("misplaced_file", "wrong_case_path")
def _move_steps(c: Ctx) -> list[str]:
    expected, found = expected_and_found_paths(c.check)
    target = code(expected) if expected else c.t("l'emplacement demandé", "the expected location")
    return [
        c.t(f"Déplace / renomme le fichier vers {target} avec `git mv` (Git garde ainsi l'historique).",
            f"Move / rename the file to {target} with `git mv` (Git keeps its history)."),
        c.t("S'il n'est pas encore suivi par Git, déplace-le normalement puis fais `git add`.",
            "If it is not tracked by Git yet, move it normally, then `git add` it."),
        c.t("Vérifie qu'aucun autre fichier ne dépend de l'ancien chemin, puis commit.",
            "Check that nothing else depends on the old path, then commit."),
    ]


@template("parasite_file", "Fichier parasite", "Unwanted file")
def _parasite_file(c: Ctx) -> str:
    path = _path(c)
    penalized = (
        c.t("Le sujet **pénalise explicitement** ce genre de fichier.", "The subject **explicitly penalizes** this kind of file.")
        if c.check.status == "fail"
        else c.t("Ce n'est pas bloquant ici, mais beaucoup de moulinettes le pénalisent.", "It is not blocking here, but many graders penalize it.")
    )
    pattern = gitignore_pattern(path)
    return join(
        c.t(f"Le fichier {code(path)} ne devrait pas faire partie de ton rendu.", f"The file {code(path)} should not be part of your submission."),
        c.t(
            "Ce sont des fichiers générés automatiquement (`__pycache__/`, `*.pyc`) ou propres à ton système / éditeur "
            "(`.DS_Store`, `.idea/`, fichiers `~` de sauvegarde) : ils n'ont rien à faire dans un dépôt.",
            "These files are generated automatically (`__pycache__/`, `*.pyc`) or belong to your system / editor "
            "(`.DS_Store`, `.idea/`, `~` backup files): they do not belong in a repository.",
        ),
        penalized,
        c.t("Retire-le du suivi Git **sans le supprimer de ton disque**, puis empêche qu'il revienne :",
            "Stop tracking it **without deleting it from your disk**, then prevent it from coming back:"),
        block(f"git rm -r --cached {sh_path(path)}", "sh"),
        c.t(f"puis ajoute cette ligne à ton `.gitignore` : {code(pattern)}", f"then add this line to your `.gitignore`: {code(pattern)}"),
    )


@hint("parasite_file")
def _parasite_steps(c: Ctx) -> list[str]:
    path = _path(c)
    return [
        c.t(f"Retire-le de Git : {code('git rm -r --cached ' + sh_path(path))} (ton fichier local est conservé).",
            f"Remove it from Git: {code('git rm -r --cached ' + sh_path(path))} (your local file is kept)."),
        c.t(f"Ajoute {code(gitignore_pattern(path))} dans ton `.gitignore`.", f"Add {code(gitignore_pattern(path))} to your `.gitignore`."),
        c.t("Fais un commit, puis relance l'analyse.", "Commit, then run the analysis again."),
    ]


@template("missing_gitignore", "Fichier .gitignore manquant", "Missing .gitignore")
def _missing_gitignore(c: Ctx) -> str:
    return join(
        c.t(
            "Le sujet exige un fichier `.gitignore` à la **racine** de ton dépôt, et il est absent.",
            "The subject requires a `.gitignore` file at the **root** of your repository, and it is missing.",
        ),
        c.t(
            "Ce fichier liste ce que Git doit ignorer (fichiers générés, fichiers système). "
            "Un bon point de départ pour un projet Python :",
            "This file lists what Git must ignore (generated files, system files). "
            "A good starting point for a Python project:",
        ),
        block("\n".join(GITIGNORE_LINES)),
        c.t("Attention au nom : il commence par un point et n'a pas d'extension (`.gitignore`, pas `gitignore.txt`).",
            "Mind the name: it starts with a dot and has no extension (`.gitignore`, not `gitignore.txt`)."),
    )


@hint("missing_gitignore")
def _gitignore_steps(c: Ctx) -> list[str]:
    return [
        c.t("Crée un fichier nommé exactement `.gitignore` à la racine du dépôt.", "Create a file named exactly `.gitignore` at the repository root."),
        c.t(f"Mets-y au moins : {', '.join(code(x) for x in GITIGNORE_LINES)} (une ligne chacun).",
            f"Put at least: {', '.join(code(x) for x in GITIGNORE_LINES)} in it (one per line)."),
        c.t("`git add .gitignore`, puis commit.", "`git add .gitignore`, then commit."),
    ]


@template("extra_file", "Fichier non demandé", "Unexpected file")
def _extra_file(c: Ctx) -> str:
    path = _path(c)
    return join(
        c.t(f"Le fichier {code(path)} n'est pas demandé par le sujet.", f"The file {code(path)} is not requested by the subject."),
        c.t(
            "Ce n'est pas forcément une erreur (fichier d'aide, tests personnels), mais vérifie qu'il ne s'agit pas "
            "d'un fichier **mal nommé ou mal placé** : la moulinette, elle, ne le regardera pas.",
            "It is not necessarily a mistake (helper file, personal tests), but check that it is not a **misnamed "
            "or misplaced** file: the grader will not look at it.",
        ),
    )


@hint("extra_file")
def _extra_steps(c: Ctx) -> list[str]:
    return [
        c.t("Compare son nom et son dossier avec l'arborescence demandée par le sujet.", "Compare its name and folder with the tree required by the subject."),
        c.t("Si c'était le fichier d'un exercice, renomme-le / déplace-le avec `git mv`.", "If it was meant for an exercise, rename / move it with `git mv`."),
        c.t("Sinon, tu peux le garder (ou le retirer s'il ne sert à rien).", "Otherwise you can keep it (or remove it if it is useless)."),
    ]


@template("missing_bonus_file", "Fichier bonus absent", "Bonus file missing")
def _missing_bonus_file(c: Ctx) -> str:
    path = _path(c)
    return join(
        c.t(f"Le fichier bonus {code(path)} n'existe pas (encore).", f"The bonus file {code(path)} does not exist (yet)."),
        c.t(*_BONUS_OK),
        c.t(f"Si tu veux tenter le bonus, crée-le exactement à ce chemin : {code(path)}.",
            f"If you want to try the bonus, create it at exactly this path: {code(path)}."),
    )


# ---------------------------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------------------------


@template("untracked_file", "Fichier non suivi par Git", "File not tracked by Git")
def _untracked_file(c: Ctx) -> str:
    path = _path(c)
    name = posixpath.basename(path)
    return join(
        c.t(
            f"Le fichier {code(path)} existe sur ton disque, mais **Git ne le suit pas** : il ne fera pas partie de ton "
            "rendu et la moulinette ne le verra jamais.",
            f"The file {code(path)} exists on your disk, but **Git does not track it**: it will not be part of your "
            "submission and the grader will never see it.",
        ),
        c.t("Ajoute-le puis enregistre-le dans un commit :", "Add it, then record it in a commit:"),
        block(f'git add {sh_path(path)}\ngit commit -m "Add {name}"', "sh"),
    )


@hint("untracked_file")
def _untracked_steps(c: Ctx) -> list[str]:
    path = _path(c)
    return [
        code("git add " + sh_path(path)),
        c.t("`git commit -m \"...\"` avec un message clair.", "`git commit -m \"...\"` with a clear message."),
        c.t("Vérifie avec `git status` que le fichier n'apparaît plus comme non suivi.", "Check with `git status` that the file is no longer listed as untracked."),
    ]


@template("ignored_file", "Fichier ignoré par .gitignore", "File ignored by .gitignore")
def _ignored_file(c: Ctx) -> str:
    path = _path(c)
    rule = detail(c.check, "pattern", "rule", "ignore_rule")
    rule_txt = c.t(f" (règle en cause : {code(str(rule))})", f" (matching rule: {code(str(rule))})") if rule else ""
    return join(
        c.t(
            f"Le fichier {code(path)} est **ignoré par ton `.gitignore`**{rule_txt} : Git refuse de l'ajouter, "
            "il ne sera donc **pas rendu**.",
            f"The file {code(path)} is **ignored by your `.gitignore`**{rule_txt}: Git refuses to add it, so it "
            "will **not be submitted**.",
        ),
        c.t("Trouve la ligne du `.gitignore` qui le bloque :", "Find the `.gitignore` line that blocks it:"),
        block(f"git check-ignore -v {sh_path(path)}", "sh"),
        c.t(
            "Puis corrige ou supprime ce motif (par exemple `*.py` ou un dossier entier ignoré par erreur), "
            "et ajoute le fichier avec `git add`.",
            "Then fix or remove that pattern (for example `*.py` or a whole folder ignored by mistake), "
            "and add the file with `git add`.",
        ),
    )


@hint("ignored_file")
def _ignored_steps(c: Ctx) -> list[str]:
    path = _path(c)
    return [
        c.t(f"Lance {code('git check-ignore -v ' + sh_path(path))} pour voir la règle responsable.",
            f"Run {code('git check-ignore -v ' + sh_path(path))} to see the responsible rule."),
        c.t("Corrige cette ligne dans `.gitignore` (sans retirer les motifs utiles comme `__pycache__/`).",
            "Fix that line in `.gitignore` (keep useful patterns such as `__pycache__/`)."),
        c.t(f"{code('git add ' + sh_path(path))} puis commit.", f"{code('git add ' + sh_path(path))} then commit."),
    ]


@template("dirty_tree", "Modifications non commitées", "Uncommitted changes")
def _dirty_tree(c: Ctx) -> str:
    modified = detail(c.check, "modified", "files", "paths")
    listing = bullets([code(str(p)) for p in modified[:10]]) if isinstance(modified, list) else ""
    return join(
        c.t(
            "Tu as des modifications **non commitées**. La moulinette récupère le contenu de tes **commits**, "
            "pas ton dossier local : ces changements ne seraient pas pris en compte.",
            "You have **uncommitted changes**. The grader takes the content of your **commits**, not your local "
            "folder: these changes would not be taken into account.",
        ),
        listing,
        c.t("Vérifie avec `git status`, puis enregistre ce que tu veux garder :", "Check with `git status`, then record what you want to keep:"),
        block('git status\ngit add <fichier>\ngit commit -m "..."' if c.lang == "fr" else 'git status\ngit add <file>\ngit commit -m "..."', "sh"),
    )


@hint("dirty_tree")
def _dirty_steps(c: Ctx) -> list[str]:
    return [
        c.t("`git status` pour voir les fichiers modifiés.", "`git status` to see the modified files."),
        c.t("`git add` les fichiers à rendre (pas les fichiers parasites).", "`git add` the files to submit (not unwanted files)."),
        c.t("`git commit -m \"...\"`, puis relance l'analyse.", "`git commit -m \"...\"`, then run the analysis again."),
    ]


# ---------------------------------------------------------------------------------------------
# Bonus
# ---------------------------------------------------------------------------------------------


@template("bonus_not_implemented", "Bonus non réalisé", "Bonus not implemented")
def _bonus_not_implemented(c: Ctx) -> str:
    return join(
        c.t("Cet exercice bonus n'est pas (encore) réalisé.", "This bonus exercise is not implemented (yet)."),
        c.t(*_BONUS_OK),
        c.t("Concentre-toi d'abord sur les exercices obligatoires ; reviens au bonus ensuite si tu as le temps.",
            "Focus on the mandatory exercises first; come back to the bonus later if you have time."),
    )


@hint("bonus_not_implemented", "missing_bonus_file")
def _bonus_steps(c: Ctx) -> list[str]:
    return [
        c.t("Termine et vérifie d'abord tous les exercices obligatoires.", "First finish and check every mandatory exercise."),
        c.t("Crée ensuite le fichier bonus au chemin exact demandé et implémente-le pas à pas.",
            "Then create the bonus file at the exact required path and implement it step by step."),
        c.t("Relance l'analyse : le bonus est évalué séparément du score obligatoire.",
            "Run the analysis again: the bonus is scored separately from the mandatory score."),
    ]
