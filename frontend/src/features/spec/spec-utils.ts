/**
 * Pure helpers for the subject review / spec editor: rendering of signatures, rules and calls,
 * factories for new spec items (always provenance "user") and immutable spec updates.
 * Values (args, expected returns, rule results) stay Python literal SOURCE strings.
 */
import type {
  BehaviorRule,
  Construct,
  Constraints,
  ExerciseSpec,
  FileRequirement,
  FunctionSignature,
  FunctionSpec,
  FunctionTest,
  InteractionStep,
  Origin,
  Param,
  PracticalSpec,
  ScriptSpec,
  ScriptTest,
  ValidationErrorItem,
} from '@/lib/types'

export const USER_NOTE = 'Edited in the spec editor'

export const CONSTRUCTS: Construct[] = [
  'for',
  'while',
  'loop',
  'comprehension',
  'lambda',
  'recursion',
  'try',
  'global',
  'class',
  'import',
  'with',
  'yield',
  'fstring',
  'walrus',
  'match',
]

/** "abs()" → "abs" (builtin / module names typed in chip inputs). */
export function normalizeName(raw: string): string {
  return raw.trim().replace(/\(\)$/, '').replace(/[`'"]/g, '')
}

/** Number of spec items extracted by AI and not found verbatim in the subject. */
export function countAiExtracted(spec: PracticalSpec): number {
  let n = 0
  const visit = (o: Origin | null | undefined) => {
    if (o?.provenance === 'ai_extracted') n += 1
  }
  for (const ex of spec.exercises) {
    visit(ex.origin)
    for (const fn of ex.functions) {
      visit(fn.origin)
      fn.rules.forEach((r) => visit(r.origin))
      fn.tests.forEach((t) => visit(t.origin))
    }
    ex.script?.tests.forEach((t) => visit(t.origin))
  }
  spec.structure.files.forEach((f) => visit(f.origin))
  return n
}

export interface TreeNode {
  name: string
  path: string
  file: FileRequirement | null
  children: TreeNode[]
}

/** Builds a directory tree out of the flat POSIX paths of the structure spec (folders first). */
export function buildTree(files: FileRequirement[]): TreeNode[] {
  const root: TreeNode = { name: '', path: '', file: null, children: [] }
  const sorted = [...files].sort((a, b) => a.path.localeCompare(b.path))
  for (const file of sorted) {
    const parts = file.path.replace(/\/+$/, '').split('/').filter(Boolean)
    let node = root
    parts.forEach((part, i) => {
      const path = parts.slice(0, i + 1).join('/')
      let child = node.children.find((c) => c.name === part)
      if (!child) {
        child = { name: part, path, file: null, children: [] }
        node.children.push(child)
      }
      if (i === parts.length - 1) child.file = file
      node = child
    })
  }
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => Number(b.children.length > 0) - Number(a.children.length > 0) || a.name.localeCompare(b.name))
    nodes.forEach((n) => sortNodes(n.children))
  }
  sortNodes(root.children)
  return root.children
}

// ---- rendering -------------------------------------------------------------------------------

export function formatParam(p: Param): string {
  let out = p.name
  if (p.annotation) out += `: ${p.annotation}`
  if (p.default !== null && p.default !== '') out += p.annotation ? ` = ${p.default}` : `=${p.default}`
  return out
}

/** `def is_safe(speed: int, limit: int) -> bool` */
export function formatSignature(sig: FunctionSignature): string {
  const ret = sig.return_annotation ? ` -> ${sig.return_annotation}` : ''
  return `def ${sig.name || '?'}(${sig.params.map(formatParam).join(', ')})${ret}`
}

export interface RuleText {
  condition: string
  outcome: string
  otherwise: boolean
}

/** "speed <= limit" → "True"; `when=null` reads "otherwise". */
export function formatRule(rule: BehaviorRule): RuleText {
  const outcome = rule.returns ?? (rule.raises ? `raises ${rule.raises}` : '—')
  return { condition: rule.when ?? 'otherwise', outcome, otherwise: rule.when === null }
}

/** `is_safe(90, 110)` */
export function formatCall(test: Pick<FunctionTest, 'function' | 'args' | 'kwargs'>): string {
  const kwargs = Object.entries(test.kwargs ?? {}).map(([k, v]) => `${k}=${v}`)
  return `${test.function}(${[...test.args, ...kwargs].join(', ')})`
}

/** What a test expects, as shown in tables. */
export function formatExpected(test: FunctionTest): string {
  if (test.expected_return !== null) return test.expected_return
  if (test.expected_exception) return `raises ${test.expected_exception}`
  if (test.expected_stdout !== null) return `prints ${JSON.stringify(test.expected_stdout)}`
  if (test.expected_type) return `any ${test.expected_type}`
  return '—'
}

/** Index where the trailing run of spaces starts (text.length when there is none). */
export function trailingSpaceStart(text: string): number {
  let i = text.length
  while (i > 0 && text[i - 1] === ' ') i -= 1
  return i
}

export function parserLabel(parser: string): string {
  const p = parser.toLowerCase()
  if (p.includes('ai') && p.includes('heuristic')) return 'Heuristic + AI'
  if (p.includes('ai') || p.includes('claude')) return 'AI'
  if (p.includes('heuristic')) return 'Heuristic'
  if (p.includes('user') || p.includes('manual')) return 'Manual'
  return parser || 'Unknown'
}

export function isAiParser(parser: string): boolean {
  const p = parser.toLowerCase()
  return p.includes('ai') || p.includes('claude')
}

// ---- origins & factories ----------------------------------------------------------------------

export function userOrigin(previous?: Origin | null): Origin {
  return { provenance: 'user', confidence: 1, source: previous?.source ?? null, note: USER_NOTE }
}

export function emptyConstraints(): Constraints {
  return {
    allowed_builtins: null,
    forbidden_builtins: [],
    allowed_imports: null,
    forbidden_imports: [],
    forbidden_methods: [],
    forbidden_constructs: [],
    required_constructs: [],
    origin: userOrigin(),
  }
}

export function newRule(): BehaviorRule {
  return { when: '', returns: '', raises: null, description: null, origin: userOrigin() }
}

export function newParam(): Param {
  return { name: '', annotation: null, default: null }
}

export function newFunctionTest(fn: FunctionSpec, takenIds: Set<string>): FunctionTest {
  const name = fn.signature.name || 'function'
  return {
    id: uniqueId(`${name}#user`, takenIds, 1),
    function: name,
    args: fn.signature.params.map(() => ''),
    kwargs: {},
    expected_return: '',
    expected_type: null,
    expected_stdout: null,
    expected_exception: null,
    compare: 'auto',
    timeout_s: 5,
    origin: userOrigin(),
  }
}

export function newFunction(name = ''): FunctionSpec {
  return {
    signature: { name, params: [], return_annotation: null },
    description: null,
    rules: [],
    reference: null,
    must_return: true,
    may_print: false,
    tests: [],
    origin: userOrigin(),
  }
}

export function newScript(): ScriptSpec {
  return { prompts: [], required_outputs: [], tests: [], origin: userOrigin() }
}

export function newScriptTest(exerciseId: string, takenIds: Set<string>): ScriptTest {
  return {
    id: uniqueId(`${exerciseId}#session`, takenIds, 1),
    title: null,
    argv: [],
    stdin: '',
    steps: [],
    expected_stdout: null,
    expected_exit_code: 0,
    match: 'exact',
    timeout_s: 5,
    origin: userOrigin(),
  }
}

export function newExercise(takenIds: Set<string>): ExerciseSpec {
  const id = uniqueId('exercise', takenIds, 1)
  return {
    id,
    title: 'New exercise',
    kind: 'functions',
    required: true,
    bonus: false,
    file_path: `${id}.py`,
    description: null,
    functions: [newFunction()],
    script: null,
    constraints: null,
    import_side_effects_allowed: false,
    origin: userOrigin(),
  }
}

/** `base`, then `base<n>` (n from `start`) until it is not taken. With start=1: "x#user1", "x#user2"... */
export function uniqueId(base: string, taken: Set<string>, start?: number): string {
  if (start === undefined && !taken.has(base)) return base
  let n = start ?? 2
  while (taken.has(`${base}${n}`)) n += 1
  return `${base}${n}`
}

/** Every function and script test id of the spec (ids are unique spec-wide). */
export function collectTestIds(spec: PracticalSpec, skipExerciseIndex?: number): Set<string> {
  const ids = new Set<string>()
  spec.exercises.forEach((ex, i) => {
    if (i === skipExerciseIndex) return
    for (const fn of ex.functions) for (const t of fn.tests) ids.add(t.id)
    for (const t of ex.script?.tests ?? []) ids.add(t.id)
  })
  return ids
}

export function exerciseTestIds(ex: ExerciseSpec): string[] {
  return [...ex.functions.flatMap((fn) => fn.tests.map((t) => t.id)), ...(ex.script?.tests ?? []).map((t) => t.id)]
}

// ---- immutable spec updates -------------------------------------------------------------------

export function cloneSpec<T>(value: T): T {
  return structuredClone(value)
}

export function replaceExercise(spec: PracticalSpec, index: number, exercise: ExerciseSpec): PracticalSpec {
  return { ...spec, exercises: spec.exercises.map((ex, i) => (i === index ? exercise : ex)) }
}

export function appendExercise(spec: PracticalSpec, exercise: ExerciseSpec): PracticalSpec {
  return { ...spec, exercises: [...spec.exercises, exercise] }
}

export function removeExercise(spec: PracticalSpec, index: number): PracticalSpec {
  return { ...spec, exercises: spec.exercises.filter((_, i) => i !== index) }
}

/**
 * Normalizes an exercise draft before saving: bonus ⇒ not required (backend rule), names trimmed,
 * empty optional strings become null. Prompts and session texts are never trimmed (spaces matter).
 */
export function normalizeExercise(ex: ExerciseSpec): ExerciseSpec {
  const out = cloneSpec(ex)
  if (out.bonus) out.required = false
  out.title = out.title.trim()
  out.file_path = out.file_path.trim()
  for (const fn of out.functions) {
    fn.signature.name = fn.signature.name.trim()
    fn.signature.return_annotation = blankToNull(fn.signature.return_annotation)
    for (const p of fn.signature.params) {
      p.name = p.name.trim()
      p.annotation = blankToNull(p.annotation)
      p.default = blankToNull(p.default)
    }
    fn.reference = blankToNull(fn.reference)
    for (const rule of fn.rules) {
      rule.when = blankToNull(rule.when)
      rule.returns = blankToNull(rule.returns)
      rule.raises = blankToNull(rule.raises)
    }
    for (const t of fn.tests) {
      t.function = t.function.trim() || fn.signature.name
      t.args = t.args.map((a) => a.trim())
      t.expected_return = blankToNull(t.expected_return)
    }
  }
  return out
}

/** JSON of `value` without the listed keys (used to detect edited items, origins excluded). */
function contentKey(value: object, omit: string[]): string {
  return JSON.stringify(value, (key, v: unknown) => (omit.includes(key) ? undefined : v))
}

/**
 * Marks every item that differs from `original` (or is new) with provenance "user", so that the
 * report can tell reviewed / hand-written requirements apart. Script sessions whose steps changed
 * get stdin and expected stdout recomputed from the steps.
 */
export function markEdited(original: ExerciseSpec | null, draft: ExerciseSpec): ExerciseSpec {
  const out = cloneSpec(draft)
  const changed = (a: object | null | undefined, b: object, omit: string[]) => !a || contentKey(a, omit) !== contentKey(b, omit)
  const exerciseOmit = ['origin', 'functions', 'script', 'constraints']
  if (changed(original, out, exerciseOmit)) out.origin = userOrigin(out.origin)

  out.functions.forEach((fn, fi) => {
    const before = original?.functions[fi]
    if (changed(before, fn, ['origin', 'rules', 'tests'])) fn.origin = userOrigin(fn.origin)
    fn.rules.forEach((rule, ri) => {
      if (changed(before?.rules[ri], rule, ['origin'])) rule.origin = userOrigin(rule.origin)
    })
    fn.tests.forEach((test) => {
      const prev = before?.tests.find((t) => t.id === test.id)
      if (changed(prev, test, ['origin'])) test.origin = userOrigin(test.origin)
    })
  })

  if (out.script) {
    const before = original?.script
    if (changed(before, out.script, ['origin', 'tests'])) out.script.origin = userOrigin(out.script.origin)
    for (const test of out.script.tests) {
      const prev = before?.tests.find((t) => t.id === test.id)
      if (!changed(prev, test, ['origin'])) continue
      test.origin = userOrigin(test.origin)
      if (test.steps && (!prev || contentKey(prev.steps ?? [], []) !== contentKey(test.steps, []))) {
        const io = stepsToIo(test.steps)
        test.stdin = io.stdin
        test.expected_stdout = io.stdout
      }
    }
  }

  if (out.constraints && changed(original?.constraints, out.constraints, ['origin']))
    out.constraints.origin = userOrigin(out.constraints.origin)
  return out
}

/** Mirror of the backend `steps_to_io`: inputs are typed lines (newline added), outputs are verbatim. */
export function stepsToIo(steps: InteractionStep[]): { stdin: string; stdout: string } {
  let stdin = ''
  let stdout = ''
  for (const step of steps) {
    if (step.kind === 'input') stdin += `${step.text}\n`
    else stdout += step.text
  }
  return { stdin, stdout }
}

function blankToNull(value: string | null): string | null {
  if (value === null) return null
  return value.trim() === '' ? null : value
}

// ---- validation -------------------------------------------------------------------------------

export interface DraftIssue {
  path: string
  message: string
}

const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/

/** Minimal client-side checks (non-empty literals, identifiers, unique ids). The server validates the rest. */
export function validateExerciseDraft(ex: ExerciseSpec, otherExerciseIds: Set<string>, otherTestIds: Set<string>): DraftIssue[] {
  const issues: DraftIssue[] = []
  if (!ex.id.trim()) issues.push({ path: 'id', message: 'Exercise id is required.' })
  else if (otherExerciseIds.has(ex.id)) issues.push({ path: 'id', message: `Exercise id "${ex.id}" is already used.` })
  if (!ex.title.trim()) issues.push({ path: 'title', message: 'Title is required.' })
  if (!ex.file_path.trim()) issues.push({ path: 'file_path', message: 'File path is required.' })
  else if (ex.file_path.includes('\\')) issues.push({ path: 'file_path', message: "Use '/' separators in the file path." })
  else if (ex.file_path.startsWith('/') || ex.file_path.split('/').includes('..'))
    issues.push({ path: 'file_path', message: 'The file path must be relative to the repository root.' })

  const seenTests = new Set<string>()
  const checkTestId = (id: string, path: string) => {
    if (!id.trim()) issues.push({ path, message: 'Test id is required.' })
    else if (seenTests.has(id) || otherTestIds.has(id)) issues.push({ path, message: `Test id "${id}" is already used.` })
    seenTests.add(id)
  }

  ex.functions.forEach((fn, fi) => {
    const base = `functions[${fi}]`
    const name = fn.signature.name.trim()
    if (!IDENTIFIER.test(name)) issues.push({ path: `${base}.name`, message: 'Function name must be a Python identifier.' })
    const params = new Set<string>()
    fn.signature.params.forEach((p, pi) => {
      const pname = p.name.trim()
      if (!IDENTIFIER.test(pname))
        issues.push({ path: `${base}.params[${pi}]`, message: `Parameter ${pi + 1} needs a valid name.` })
      else if (params.has(pname)) issues.push({ path: `${base}.params[${pi}]`, message: `Duplicate parameter "${pname}".` })
      params.add(pname)
    })
    fn.rules.forEach((rule, ri) => {
      if (!(rule.returns ?? '').trim() && !(rule.raises ?? '').trim())
        issues.push({ path: `${base}.rules[${ri}]`, message: `Rule ${ri + 1} needs a returned value.` })
    })
    fn.tests.forEach((t, ti) => {
      const tpath = `${base}.tests[${ti}]`
      checkTestId(t.id, `${tpath}.id`)
      t.args.forEach((arg, ai) => {
        if (!arg.trim()) issues.push({ path: `${tpath}.args[${ai}]`, message: `Test ${ti + 1}: argument ${ai + 1} is empty.` })
      })
      const hasExpectation =
        (t.expected_return ?? '').trim() !== '' || Boolean(t.expected_exception) || t.expected_stdout !== null || Boolean(t.expected_type)
      if (!hasExpectation) issues.push({ path: `${tpath}.expected_return`, message: `Test ${ti + 1}: expected value is empty.` })
    })
  })

  ex.script?.tests.forEach((t, ti) => {
    checkTestId(t.id, `script.tests[${ti}].id`)
    t.steps?.forEach((step, si) => {
      if (step.kind === 'output' && step.text === '')
        issues.push({ path: `script.tests[${ti}].steps[${si}]`, message: `Session ${ti + 1}: output step ${si + 1} is empty.` })
    })
  })
  if (ex.kind === 'functions' && ex.functions.length === 0)
    issues.push({ path: 'functions', message: 'A "functions" exercise needs at least one function.' })
  return issues
}

/** Parses the JSON editor text: JSON syntax + the minimal shape of a PracticalSpec. */
export function parseSpecJson(text: string): { spec: PracticalSpec | null; issues: DraftIssue[] } {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (error) {
    return { spec: null, issues: [{ path: 'json', message: error instanceof Error ? error.message : 'Invalid JSON' }] }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { spec: null, issues: [{ path: 'spec', message: 'The contract must be a JSON object.' }] }
  }
  const issues: DraftIssue[] = []
  const obj = value as Record<string, unknown>
  const isObject = (v: unknown) => Boolean(v) && typeof v === 'object' && !Array.isArray(v)
  if (!Array.isArray(obj.exercises)) issues.push({ path: 'exercises', message: 'Missing "exercises" array.' })
  if (!isObject(obj.metadata)) issues.push({ path: 'metadata', message: 'Missing "metadata" object.' })
  if (!isObject(obj.structure)) issues.push({ path: 'structure', message: 'Missing "structure" object.' })
  if (!isObject(obj.global_constraints)) issues.push({ path: 'global_constraints', message: 'Missing "global_constraints" object.' })
  return { spec: issues.length ? null : (value as PracticalSpec), issues }
}

/** FastAPI 422 `loc` →"exercises[0].functions[1].tests[0].args[0]". */
export function formatLoc(loc: Array<string | number>): string {
  let out = ''
  for (const part of loc) {
    if (part === 'body') continue
    if (typeof part === 'number') out += `[${part}]`
    else out += out ? `.${part}` : part
  }
  return out || 'spec'
}

export function formatValidationItems(items: ValidationErrorItem[]): DraftIssue[] {
  return items.map((item) => ({ path: formatLoc(item.loc), message: item.msg }))
}

/** "exercises[3].functions[0]" → 3 */
export function exerciseIndexFromPath(path: string): number | null {
  const match = /^exercises\[(\d+)\]/.exec(path)
  return match ? Number(match[1]) : null
}
