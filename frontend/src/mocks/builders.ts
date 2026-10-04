/**
 * Factories producing complete, type-correct model objects for tests, stories and mocks.
 * Only override what matters: `makeCheck({ status: 'fail', title: '...' })`.
 */
import type {
  CheckResult,
  Constraints,
  DiffLine,
  DiffSegment,
  Evidence,
  Location,
  Origin,
  TextDiff,
} from '@/lib/types'

export function makeOrigin(overrides: Partial<Origin> = {}): Origin {
  return { provenance: 'explicit', confidence: 1, source: null, note: null, ...overrides }
}

export function explicitOrigin(excerpt: string, section: string, line: number): Origin {
  return makeOrigin({ source: { excerpt, section, line } })
}

export function makeLocation(file: string, line: number | null = null): Location {
  return { file, line, end_line: null, col: null }
}

export function makeEvidence(overrides: Partial<Evidence> = {}): Evidence {
  return {
    call: null,
    argv: null,
    stdin: null,
    expected_value: null,
    actual_value: null,
    value_diff: null,
    stdout_diff: null,
    expected_stdout: null,
    actual_stdout: null,
    stderr: null,
    exit_code: null,
    exception: null,
    timed_out: false,
    duration_ms: null,
    transcript: null,
    expected_steps: null,
    rule: null,
    code: null,
    details: {},
    ...overrides,
  }
}

export function makeCheck(overrides: Partial<CheckResult> & Pick<CheckResult, 'id' | 'title'>): CheckResult {
  return {
    category: 'explicit_tests',
    status: 'pass',
    severity: null,
    message: '',
    diagnosis: null,
    exercise_id: null,
    function: null,
    test_id: null,
    file: null,
    location: null,
    origin: makeOrigin(),
    mandatory: true,
    bonus: false,
    blocked_by: null,
    evidence: null,
    fix: null,
    tags: [],
    ...overrides,
  }
}

export function makeConstraints(overrides: Partial<Constraints> = {}): Constraints {
  return {
    allowed_builtins: null,
    forbidden_builtins: [],
    allowed_imports: null,
    forbidden_imports: [],
    forbidden_methods: [],
    forbidden_constructs: [],
    required_constructs: [],
    origin: makeOrigin(),
    ...overrides,
  }
}

export function equalLine(text: string, lineno: number): DiffLine {
  return {
    op: 'equal',
    expected_lineno: lineno,
    actual_lineno: lineno,
    expected: text,
    actual: text,
    expected_eol: '\n',
    actual_eol: '\n',
    segments: [],
    hints: [],
    source: null,
  }
}

export function changedLine(
  segments: DiffSegment[],
  lineno: number,
  extra: Partial<DiffLine> = {},
): DiffLine {
  return {
    op: 'changed',
    expected_lineno: lineno,
    actual_lineno: lineno,
    expected: segments.map((s) => s.expected).join(''),
    actual: segments.map((s) => s.actual).join(''),
    expected_eol: '\n',
    actual_eol: '\n',
    segments,
    hints: [],
    source: null,
    ...extra,
  }
}

export function seg(op: DiffSegment['op'], expected: string, actual: string = op === 'equal' ? expected : ''): DiffSegment {
  return { op, expected, actual }
}

export function makeTextDiff(lines: DiffLine[], overrides: Partial<TextDiff> = {}): TextDiff {
  const join = (side: 'expected' | 'actual') =>
    lines
      .map((l) => (side === 'expected' ? (l.expected ?? '') + l.expected_eol : (l.actual ?? '') + l.actual_eol))
      .join('')
  return {
    expected: join('expected'),
    actual: join('actual'),
    equal: lines.every((l) => l.op === 'equal'),
    lines,
    kinds: [],
    summary: '',
    first_difference: null,
    ...overrides,
  }
}
