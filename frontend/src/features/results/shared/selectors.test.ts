import { describe, expect, it } from 'vitest'
import { makeCheck, makeEvidence, makeLocation, makeOrigin } from '@/mocks/builders'
import { buildReportSections } from '../report/report-sections'
import { makeReport, makeReportChecks, makeScore } from '../testing/mock-report'
import {
  buildTreeRows,
  DEFAULT_ISSUE_FILTERS,
  groupIssuesByFile,
  isIssue,
  matchesIssueFilters,
  previousAnalysis,
  shortValues,
  testCallLabel,
  testOrigin,
  topIssues,
  vscodeUrl,
} from './selectors'
import { isResultTab } from './tabs'
import { verdictCopy } from './meta'

describe('groupIssuesByFile', () => {
  it('groups by spec file (falling back to the location) and sorts groups worst first', () => {
    const checks = [
      makeCheck({ id: 'a', title: 'minor', status: 'fail', severity: 'minor', file: 'b.py' }),
      makeCheck({ id: 'b', title: 'critical', status: 'fail', severity: 'critical', file: 'a.py' }),
      makeCheck({ id: 'c', title: 'warning', status: 'warning', severity: 'major', file: 'b.py' }),
      makeCheck({ id: 'd', title: 'located', status: 'fail', severity: 'minor', location: makeLocation('src/c.py', 3) }),
      makeCheck({ id: 'e', title: 'general', status: 'fail', severity: 'minor' }),
    ]
    const groups = groupIssuesByFile(checks, makeScore().files)
    expect(groups.map((g) => g.key)).toEqual(['a.py', 'b.py', 'src/c.py', ''])
    expect(groups[1]?.checks.map((c) => c.id)).toEqual(['a', 'c'])
    expect(groups[2]?.label).toBe('c.py')
    expect(groups[3]?.label).toBe('Project-wide')
  })

  it('attaches the file score, also through the detected root', () => {
    const files = makeScore().files
    const [group] = groupIssuesByFile([makeCheck({ id: 'x', title: 'x', status: 'fail', file: 'proj/launch_sequence.py' })], files, 'proj')
    expect(group?.score?.score).toBe(92)
  })
})

describe('issue filters', () => {
  const checks = makeReportChecks()
  it('defaults to fail, warning and bonus (skipped counts as fail, info hidden)', () => {
    const shown = checks.filter((c) => matchesIssueFilters(c, DEFAULT_ISSUE_FILTERS)).map((c) => c.status)
    expect(new Set(shown)).toEqual(new Set(['fail', 'warning', 'bonus']))
    const skipped = makeCheck({ id: 's', title: 's', status: 'skipped' })
    expect(matchesIssueFilters(skipped, DEFAULT_ISSUE_FILTERS)).toBe(true)
    expect(isIssue(skipped)).toBe(true)
  })

  it('filters by severity, provenance and multi-term search', () => {
    const f = { ...DEFAULT_ISSUE_FILTERS, severity: 'critical' as const }
    expect(checks.filter((c) => matchesIssueFilters(c, f)).map((c) => c.id)).toEqual([
      'constraint:fuel_share:forbidden_builtin:abs',
    ])
    const p = { ...DEFAULT_ISSUE_FILTERS, provenance: 'derived' as const }
    expect(checks.filter((c) => matchesIssueFilters(c, p)).map((c) => c.id)).toEqual(['test:is_safe#derived1'])
    const q = { ...DEFAULT_ISSUE_FILTERS, query: 'LAUNCH prompt' }
    expect(checks.filter((c) => matchesIssueFilters(c, q)).map((c) => c.id)).toEqual(['prompt:launch_sequence:1'])
  })

  it('puts critical mandatory failures on top', () => {
    expect(topIssues(checks, 2).map((c) => c.id)).toEqual([
      'constraint:fuel_share:forbidden_builtin:abs',
      'test:landing_grade#ex2',
    ])
  })
})

describe('tests helpers', () => {
  it('classifies origins by category and provenance', () => {
    expect(testOrigin(makeCheck({ id: '1', title: '', category: 'heuristic_tests' }))).toBe('heuristic')
    expect(testOrigin(makeCheck({ id: '2', title: '', category: 'derived_tests' }))).toBe('derived')
    expect(testOrigin(makeCheck({ id: '3', title: '', category: 'output', origin: makeOrigin() }))).toBe('explicit')
  })

  it('summarizes values, outputs and exceptions', () => {
    const [, , , landing, , session] = makeReportChecks()
    expect(shortValues(landing as never)).toEqual({ expected: 'True', actual: "'True'" })
    const s = shortValues(session as never)
    expect(s.expected).toMatch(/^L1: "Pilot name: Starting fuel/)
    expect(s.actual).toMatch(/^L1: "Pilot name:Starting fuel/)
    const crash = makeCheck({
      id: 'c',
      title: 'c',
      evidence: makeEvidence({
        expected_value: { repr: '3', type: 'int' },
        exception: { type: 'ZeroDivisionError', message: 'division by zero', traceback: '', location: null },
      }),
    })
    expect(shortValues(crash)).toEqual({ expected: '3', actual: 'ZeroDivisionError: division by zero' })
    expect(testCallLabel(session as never)).toBe('python3 launch_sequence.py · session 1')
  })
})

describe('buildTreeRows', () => {
  it('inserts missing parent folders and lists folders first', () => {
    const rows = buildTreeRows(makeReport().tree)
    expect(rows.map((r) => [r.entry.path, r.depth])).toEqual([
      ['__pycache__', 0],
      ['__pycache__/kelvin.cpython-312.pyc', 1],
      ['bonus', 0],
      ['bonus/max_altitude.py', 1],
      ['access_code.py', 0],
      ['kelvin.py', 0],
      ['launch_sequence.py', 0],
    ])
    expect(rows[3]?.ancestors).toEqual(['bonus'])
  })
})

describe('misc', () => {
  it('builds VS Code links from Windows and POSIX roots', () => {
    expect(vscodeUrl('C:\\Users\\me\\my tp', 'src/kelvin.py', 31)).toBe('vscode://file/C:/Users/me/my%20tp/src/kelvin.py:31')
    expect(vscodeUrl('/home/me/tp/', 'kelvin.py', null)).toBe('vscode://file/home/me/tp/kelvin.py')
    expect(vscodeUrl(null, 'kelvin.py', 1)).toBeNull()
  })

  it('validates tabs', () => {
    expect(isResultTab('issues')).toBe(true)
    expect(isResultTab('nope')).toBe(false)
    expect(isResultTab(undefined)).toBe(false)
  })

  it('picks the previous analysis of the pair', () => {
    const items = [
      { id: 'a', number: 1 },
      { id: 'c', number: 3 },
      { id: 'b', number: 2 },
    ].map((x) => ({ ...x, created_at: '', subject_id: '', project_id: '', subject_title: '', project_name: '', readiness: 0, mandatory_readiness: 0, bonus_completion: null, verdict: 'ready' as const, mandatory_failures: 0 }))
    expect(previousAnalysis(items, { id: 'c', number: 3 })?.id).toBe('b')
    expect(previousAnalysis(items, { id: 'a', number: 1 })).toBeNull()
  })

  it('words the verdict', () => {
    expect(verdictCopy(makeScore({ mandatory_failures: 1 })).message).toBe('1 mandatory failure remains.')
    const ready = verdictCopy(makeScore({ verdict: 'ready', mandatory_failures: 0, verdict_message: 'All good.' }))
    expect(ready).toEqual({ title: 'READY TO SUBMIT', message: 'All good. Hidden grader tests may still exist.' })
  })

  it('builds the 14 report sections in the export order', () => {
    const sections = buildReportSections(makeReport())
    expect(sections.map((s) => s.title)).toEqual([
      'Repository',
      'Subject',
      'Mandatory requirements',
      'Optional requirements',
      'Structure',
      'Functions',
      'Scripts',
      'Constraints',
      'Static analysis',
      'Runtime analysis',
      'Known tests',
      'Derived tests',
      'Warnings',
      'Bonus',
    ])
    const scripts = sections.find((s) => s.id === 'scripts')
    expect(scripts?.checks.map((c) => c.id).sort()).toEqual(['prompt:launch_sequence:1', 'test:launch_sequence#session1'])
    expect(sections.find((s) => s.id === 'constraints')?.tone).toBe('fail')
    expect(sections.find((s) => s.id === 'known-tests')?.checks.map((c) => c.id)).toEqual([
      'test:landing_grade#ex2',
      'test:to_kelvin#ex1',
    ])
  })
})
