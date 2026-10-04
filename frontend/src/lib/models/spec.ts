/**
 * Mirror of backend/premoulinette/spec/models.py (PracticalSpec — the TP contract).
 * Field names are the exact JSON (snake_case) names. Fields with a Pydantic default are
 * always present in API responses, so they are typed as required here.
 * Values (args, expected returns) are Python literal SOURCE strings: "True" vs "'True'".
 */

export const SCHEMA_VERSION = 1

export type Provenance = 'explicit' | 'derived' | 'heuristic' | 'ai_extracted' | 'user'

export interface SourceRef {
  excerpt: string | null
  section: string | null
  line: number | null
}

export interface Origin {
  provenance: Provenance
  confidence: number
  source: SourceRef | null
  note: string | null
}

export type Construct =
  | 'for'
  | 'while'
  | 'loop'
  | 'comprehension'
  | 'lambda'
  | 'recursion'
  | 'try'
  | 'global'
  | 'class'
  | 'import'
  | 'with'
  | 'yield'
  | 'fstring'
  | 'walrus'
  | 'match'

export interface Constraints {
  allowed_builtins: string[] | null
  forbidden_builtins: string[]
  allowed_imports: string[] | null
  forbidden_imports: string[]
  forbidden_methods: string[]
  forbidden_constructs: Construct[]
  required_constructs: Construct[]
  origin: Origin
}

export interface Param {
  name: string
  annotation: string | null
  default: string | null
}

export interface FunctionSignature {
  name: string
  params: Param[]
  return_annotation: string | null
}

export interface BehaviorRule {
  when: string | null
  returns: string | null
  raises: string | null
  description: string | null
  origin: Origin
}

export type CompareMode = 'auto' | 'exact' | 'float_tolerance'

export interface FunctionTest {
  id: string
  function: string
  args: string[]
  kwargs: Record<string, string>
  expected_return: string | null
  expected_type: string | null
  expected_stdout: string | null
  expected_exception: string | null
  compare: CompareMode
  timeout_s: number
  origin: Origin
}

export interface FunctionSpec {
  signature: FunctionSignature
  description: string | null
  rules: BehaviorRule[]
  reference: string | null
  must_return: boolean
  may_print: boolean
  tests: FunctionTest[]
  origin: Origin
}

export interface InteractionStep {
  kind: 'output' | 'input'
  text: string
}

export interface ScriptTest {
  id: string
  title: string | null
  argv: string[]
  stdin: string
  steps: InteractionStep[] | null
  expected_stdout: string | null
  expected_exit_code: number | null
  match: 'exact' | 'contains'
  timeout_s: number
  origin: Origin
}

export interface ScriptSpec {
  prompts: string[]
  required_outputs: string[]
  tests: ScriptTest[]
  origin: Origin
}

export type ExerciseKind = 'functions' | 'script' | 'file'

export interface ExerciseSpec {
  id: string
  title: string
  kind: ExerciseKind
  required: boolean
  bonus: boolean
  file_path: string
  description: string | null
  functions: FunctionSpec[]
  script: ScriptSpec | null
  constraints: Constraints | null
  import_side_effects_allowed: boolean
  origin: Origin
}

export interface FileRequirement {
  path: string
  kind: 'file' | 'directory'
  required: boolean
  bonus: boolean
  description: string | null
  origin: Origin
}

export interface StructureSpec {
  files: FileRequirement[]
  forbidden_patterns: string[]
  forbidden_patterns_are_errors: boolean
  allow_extra_files: boolean
  require_gitignore: boolean
  origin: Origin
}

export interface SpecMetadata {
  title: string
  course: string | null
  school: string | null
  deadline: string | null
  source_name: string | null
  source_sha256: string | null
  parser: string
  /** ISO 8601 datetime */
  parsed_at: string
  reviewed_by_user: boolean
}

export interface PracticalSpec {
  schema_version: number
  metadata: SpecMetadata
  language: string
  language_version: string | null
  structure: StructureSpec
  global_constraints: Constraints
  exercises: ExerciseSpec[]
  notes: string[]
}

export interface SpecStats {
  language: string
  required_files: number
  functions: number
  known_tests: number
  script_tests: number
  constraints: number
  exercises: number
  mandatory_exercises: number
  bonus_exercises: number
}
