/**
 * A realistic AnalysisReport for tests and local mocks (the buggy MysteryInc demo, trimmed).
 * `makeReport({ score: { verdict: 'ready' } })` deep-merges the score only.
 */
import { demoSpec } from '@/mocks/generated/demo-spec'
import { launchSession1Diff, pilotPromptDiff } from '@/mocks/generated/diffs'
import { makeCheck, makeEvidence, makeLocation, makeOrigin } from '@/mocks/builders'
import type { AnalysisListItem, AnalysisReport, CheckResult, ScoreSummary, TreeEntry } from '@/lib/types'

export const REPORT_ID = 'an-4'

export function makeReportChecks(): CheckResult[] {
  return [
    makeCheck({ id: 'structure:file:kelvin.py', title: 'kelvin.py is present', category: 'structure', file: 'kelvin.py' }),
    makeCheck({ id: 'syntax:kelvin.py', title: 'kelvin.py compiles', category: 'syntax', file: 'kelvin.py' }),
    makeCheck({
      id: 'test:to_kelvin#ex1',
      title: 'to_kelvin(0) returns 273.15',
      category: 'explicit_tests',
      exercise_id: 'kelvin',
      function: 'to_kelvin',
      test_id: 'to_kelvin#ex1',
      file: 'kelvin.py',
      evidence: makeEvidence({
        call: 'to_kelvin(0)',
        expected_value: { repr: '273.15', type: 'float' },
        actual_value: { repr: '273.15', type: 'float' },
        duration_ms: 12,
      }),
    }),
    makeCheck({
      id: 'test:landing_grade#ex2',
      title: 'landing_grade(3.2) returns True',
      category: 'explicit_tests',
      status: 'fail',
      severity: 'major',
      diagnosis: 'str_instead_of_bool',
      message: "Returned the string 'True' instead of the boolean True.",
      exercise_id: 'grade_landing',
      function: 'landing_grade',
      test_id: 'landing_grade#ex2',
      file: 'grade_landing.py',
      location: makeLocation('grade_landing.py', 12),
      evidence: makeEvidence({
        call: 'landing_grade(3.2)',
        expected_value: { repr: 'True', type: 'bool' },
        actual_value: { repr: "'True'", type: 'str' },
        duration_ms: 9,
        code: { file: 'grade_landing.py', start_line: 10, lines: ['def landing_grade(v):', '    if v < 5:', '        return "True"'], highlight: [12] },
      }),
      fix: {
        summary: 'Return the boolean True, not the string "True".',
        file: 'grade_landing.py',
        patch: '@@ -12,1 +12,1 @@\n-        return "True"\n+        return True\n',
        before: null,
        after: null,
        confidence: 'high',
      },
    }),
    makeCheck({
      id: 'test:is_safe#derived1',
      title: 'is_safe(90, 90) returns True',
      category: 'derived_tests',
      status: 'fail',
      severity: 'major',
      diagnosis: 'wrong_value',
      message: 'Boundary case: speed equal to the limit is safe.',
      exercise_id: 'safe_speed',
      function: 'is_safe',
      test_id: 'is_safe#derived1',
      file: 'safe_speed.py',
      origin: makeOrigin({ provenance: 'derived', confidence: 0.9 }),
      evidence: makeEvidence({
        call: 'is_safe(90, 90)',
        rule: 'speed <= limit → True',
        expected_value: { repr: 'True', type: 'bool' },
        actual_value: { repr: 'False', type: 'bool' },
        duration_ms: 8,
      }),
    }),
    makeCheck({
      id: 'test:launch_sequence#session1',
      title: 'launch_sequence.py session 1 output',
      category: 'output',
      status: 'fail',
      severity: 'minor',
      diagnosis: 'stdout_mismatch',
      message: 'The output differs from the subject on 3 lines.',
      exercise_id: 'launch_sequence',
      test_id: 'launch_sequence#session1',
      file: 'launch_sequence.py',
      location: makeLocation('launch_sequence.py', 31),
      evidence: makeEvidence({ stdin: 'Camille\n400\n2\ntrap\n', stdout_diff: launchSession1Diff, duration_ms: 41 }),
    }),
    makeCheck({
      id: 'prompt:launch_sequence:1',
      title: 'Prompt "Pilot name: "',
      category: 'output',
      status: 'fail',
      severity: 'minor',
      diagnosis: 'prompt_mismatch',
      message: 'Missing trailing space in the prompt.',
      exercise_id: 'launch_sequence',
      file: 'launch_sequence.py',
      location: makeLocation('launch_sequence.py', 3),
      evidence: makeEvidence({ value_diff: pilotPromptDiff }),
    }),
    makeCheck({
      id: 'test:to_kelvin#heur1',
      title: 'to_kelvin(-1000) returns a float',
      category: 'heuristic_tests',
      status: 'warning',
      severity: 'minor',
      mandatory: false,
      exercise_id: 'kelvin',
      test_id: 'to_kelvin#heur1',
      file: 'kelvin.py',
      origin: makeOrigin({ provenance: 'heuristic', confidence: 0.5 }),
      evidence: makeEvidence({ call: 'to_kelvin(-1000)', expected_value: null, actual_value: { repr: '-726.85', type: 'float' } }),
    }),
    makeCheck({
      id: 'constraint:fuel_share:forbidden_builtin:abs',
      title: 'Forbidden builtin abs() used',
      category: 'constraints',
      status: 'fail',
      severity: 'critical',
      diagnosis: 'forbidden_builtin',
      exercise_id: 'fuel_share',
      file: 'fuel_share.py',
      location: makeLocation('fuel_share.py', 7),
    }),
    makeCheck({
      id: 'git:untracked:access_code.py',
      title: 'access_code.py is not tracked by Git',
      category: 'git',
      status: 'fail',
      severity: 'major',
      diagnosis: 'untracked_file',
      file: 'access_code.py',
    }),
    makeCheck({
      id: 'structure:extra:notes.py',
      title: 'Extra file notes.py',
      category: 'structure',
      status: 'info',
      mandatory: false,
      file: 'notes.py',
    }),
    makeCheck({
      id: 'function:max_altitude:max_altitude',
      title: 'max_altitude() is not implemented',
      category: 'functions',
      status: 'bonus',
      mandatory: false,
      bonus: true,
      diagnosis: 'bonus_not_implemented',
      exercise_id: 'max_altitude',
      file: 'bonus/max_altitude.py',
    }),
  ]
}

export function makeScore(overrides: Partial<ScoreSummary> = {}): ScoreSummary {
  return {
    readiness: 96.4,
    mandatory_readiness: 96.4,
    mandatory_passed: 53,
    mandatory_total: 55,
    mandatory_failures: 2,
    bonus_completion: 25,
    bonus_passed: 1,
    bonus_total: 4,
    confidence: 'medium',
    confidence_reasons: ['Few tests for is_safe()', 'Heuristic warnings present'],
    categories: [
      { key: 'structure', label: 'Structure', passed: 9, total: 9, score: 100, failed: 0, warnings: 0 },
      { key: 'syntax', label: 'Compilation', passed: 11, total: 11, score: 100, failed: 0, warnings: 0 },
      { key: 'explicit_tests', label: 'Known tests', passed: 20, total: 21, score: 95.2, failed: 1, warnings: 0 },
      { key: 'runtime', label: 'Import safety', passed: 0, total: 0, score: null, failed: 0, warnings: 0 },
      { key: 'git', label: 'Git', passed: 2, total: 3, score: 66.7, failed: 1, warnings: 0 },
    ],
    exercises: [
      { exercise_id: 'kelvin', title: 'Kelvin', file: 'kelvin.py', bonus: false, required: true, status: 'pass', passed: 4, total: 4, score: 100, issues: 0 },
      { exercise_id: 'launch_sequence', title: 'Launch sequence', file: 'launch_sequence.py', bonus: false, required: true, status: 'fail', passed: 11, total: 12, score: 91.7, issues: 2 },
      { exercise_id: 'max_altitude', title: 'Max altitude', file: 'bonus/max_altitude.py', bonus: true, required: false, status: 'not_implemented', passed: 0, total: 3, score: 0, issues: 1 },
    ],
    files: [
      { file: 'launch_sequence.py', exercise_ids: ['launch_sequence'], present: true, passed: 11, total: 12, score: 92, issues: 2, worst_severity: 'minor' },
      { file: 'kelvin.py', exercise_ids: ['kelvin'], present: true, passed: 4, total: 4, score: 100, issues: 1, worst_severity: 'minor' },
    ],
    counts: { pass: 50, fail: 6, warning: 1, info: 1, bonus: 1, critical: 1, major: 3, minor: 3 },
    verdict: 'not_ready',
    verdict_title: 'DO NOT SUBMIT YET',
    verdict_message: '2 mandatory failures remain.',
    ...overrides,
  }
}

const TREE: TreeEntry[] = [
  { path: 'kelvin.py', kind: 'file', size: 120, status: 'expected', required: true, bonus: false, git: 'tracked', note: null },
  { path: 'launch_sequence.py', kind: 'file', size: 900, status: 'expected', required: true, bonus: false, git: 'modified', note: null },
  { path: 'access_code.py', kind: 'file', size: 300, status: 'expected', required: true, bonus: false, git: 'untracked', note: null },
  { path: 'bonus/max_altitude.py', kind: 'file', size: null, status: 'missing', required: false, bonus: true, git: null, note: null },
  { path: '__pycache__/kelvin.cpython-312.pyc', kind: 'file', size: 400, status: 'parasite', required: null, bonus: false, git: 'untracked', note: 'Python cache' },
]

export function makeReport(overrides: Partial<Omit<AnalysisReport, 'score'>> & { score?: Partial<ScoreSummary> } = {}): AnalysisReport {
  const { score, ...rest } = overrides
  return {
    id: REPORT_ID,
    number: 4,
    created_at: new Date(Date.now() - 120_000).toISOString(),
    duration_ms: 4200,
    subject: { id: 'subj-1', title: 'TP 1 — MysteryInc: First Launch', source_name: 'subject_demo.html', language: 'python', parser: 'heuristic' },
    project: {
      id: 'proj-1',
      name: 'mysteryinc_buggy',
      source_kind: 'path',
      path: 'C:\\Users\\me\\mysteryinc',
      detected_root: null,
      root_note: null,
      file_count: 14,
      python_files: 11,
      git: {
        is_repo: true,
        branch: 'main',
        head: 'a1b2c3d4e5f6',
        last_commit_message: 'Finish exercise 6',
        last_commit_date: new Date(Date.now() - 3_600_000).toISOString(),
        dirty: true,
        modified: ['launch_sequence.py'],
        untracked: ['access_code.py', '__pycache__/kelvin.cpython-312.pyc', 'notes.py'],
        staged: [],
        ignored_required: [],
        remote_url: null,
        tags: [],
        error: null,
      },
    },
    sandbox: { mode: 'docker', image: 'python:3.12-slim', python_version: '3.12.7', network: false, limits: {}, warnings: [] },
    spec: demoSpec,
    checks: makeReportChecks(),
    tree: TREE,
    score: makeScore(score),
    pipeline_warnings: [],
    ...rest,
  }
}

export function makeListItem(overrides: Partial<AnalysisListItem> = {}): AnalysisListItem {
  return {
    id: REPORT_ID,
    number: 4,
    created_at: new Date(Date.now() - 120_000).toISOString(),
    subject_id: 'subj-1',
    project_id: 'proj-1',
    subject_title: 'TP 1 — MysteryInc: First Launch',
    project_name: 'mysteryinc_buggy',
    readiness: 96.4,
    mandatory_readiness: 96.4,
    bonus_completion: 25,
    verdict: 'not_ready',
    mandatory_failures: 2,
    ...overrides,
  }
}
