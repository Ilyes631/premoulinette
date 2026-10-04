import { describe, expect, it } from 'vitest'
import { demoSpec } from '@/mocks/generated/demo-spec'
import {
  buildTree,
  parseSpecJson,
  cloneSpec,
  formatCall,
  formatLoc,
  formatRule,
  formatSignature,
  markEdited,
  newExercise,
  newFunctionTest,
  normalizeExercise,
  stepsToIo,
  uniqueId,
  validateExerciseDraft,
} from './spec-utils'

const exercise = (id: string) => {
  const ex = demoSpec.exercises.find((e) => e.id === id)
  if (!ex) throw new Error(`missing ${id}`)
  return cloneSpec(ex)
}

describe('spec rendering helpers', () => {
  it('formats signatures, rules and calls', () => {
    const fn = exercise('safe_speed').functions[0]!
    expect(formatSignature(fn.signature)).toBe('def is_safe(speed: int, limit: int) -> bool')
    expect(formatRule(fn.rules[0]!)).toEqual({ condition: 'speed <= limit', outcome: 'True', otherwise: false })
    expect(formatRule(fn.rules[1]!)).toEqual({ condition: 'otherwise', outcome: 'False', otherwise: true })
    expect(formatCall({ function: 'f', args: ['1', "'a'"], kwargs: { k: 'None' } })).toBe("f(1, 'a', k=None)")
    expect(formatSignature({ name: 'g', params: [{ name: 'x', annotation: null, default: '0' }], return_annotation: null })).toBe('def g(x=0)')
  })

  it('maps FastAPI locations to spec paths', () => {
    expect(formatLoc(['body', 'exercises', 2, 'functions', 0, 'tests', 1, 'args', 0])).toBe('exercises[2].functions[0].tests[1].args[0]')
    expect(formatLoc(['body'])).toBe('spec')
  })
})

describe('spec editing helpers', () => {
  it('marks only edited items as user-provided', () => {
    const original = exercise('safe_speed')
    const draft = cloneSpec(original)
    draft.functions[0]!.rules[1]!.returns = 'None'
    const marked = markEdited(original, draft)
    expect(marked.origin.provenance).toBe('explicit')
    expect(marked.functions[0]!.origin.provenance).toBe('explicit')
    expect(marked.functions[0]!.rules[0]!.origin.provenance).toBe('explicit')
    expect(marked.functions[0]!.rules[1]!.origin).toMatchObject({ provenance: 'user', confidence: 1 })
    // The subject excerpt is kept for traceability.
    expect(marked.functions[0]!.rules[1]!.origin.source?.line).toBe(73)
  })

  it('recomputes stdin and expected stdout when session steps change', () => {
    const original = exercise('launch_sequence')
    const draft = cloneSpec(original)
    const test = draft.script!.tests[0]!
    test.steps = [
      { kind: 'output', text: 'Pilot name: ' },
      { kind: 'input', text: 'Velma' },
      { kind: 'output', text: 'Hi Velma\n' },
    ]
    const marked = markEdited(original, draft)
    const saved = marked.script!.tests[0]!
    expect(saved.origin.provenance).toBe('user')
    expect(saved.stdin).toBe('Velma\n')
    expect(saved.expected_stdout).toBe('Pilot name: Hi Velma\n')
    expect(marked.script!.tests[1]!.origin.provenance).toBe('explicit')
  })

  it('keeps prompt trailing spaces and forces bonus exercises to be optional', () => {
    const ex = exercise('countdown')
    ex.required = true
    ex.script!.prompts = ['Start: ']
    const normalized = normalizeExercise(ex)
    expect(normalized.required).toBe(false)
    expect(normalized.script!.prompts).toEqual(['Start: '])
  })

  it('validates drafts minimally', () => {
    const ex = exercise('safe_speed')
    const fn = ex.functions[0]!
    fn.tests.push({ ...newFunctionTest(fn, new Set(['is_safe#user1'])) })
    const issues = validateExerciseDraft(ex, new Set(['kelvin']), new Set())
    expect(issues.map((i) => i.message)).toEqual([
      'Test 3: argument 1 is empty.',
      'Test 3: argument 2 is empty.',
      'Test 3: expected value is empty.',
    ])
    expect(fn.tests[2]!.id).toBe('is_safe#user2')
    const dup = validateExerciseDraft(ex, new Set(['safe_speed']), new Set(['is_safe#ex1']))
    expect(dup.map((i) => i.path)).toEqual(expect.arrayContaining(['id', 'functions[0].tests[0].id']))
  })

  it('creates unique ids', () => {
    expect(uniqueId('a', new Set(['a']))).toBe('a2')
    expect(uniqueId('t#user', new Set(['t#user1']), 1)).toBe('t#user2')
    expect(newExercise(new Set(['exercise1'])).id).toBe('exercise2')
    expect(stepsToIo([{ kind: 'input', text: 'x' }])).toEqual({ stdin: 'x\n', stdout: '' })
  })
})

describe('structure tree and JSON parsing', () => {
  it('builds a nested tree from POSIX paths', () => {
    const tree = buildTree(demoSpec.structure.files)
    const root = tree.find((n) => n.name === 'MysteryInc')
    expect(root?.children.length).toBeGreaterThan(0)
    expect(tree.some((n) => n.name === '.gitignore' && n.file?.required)).toBe(true)
  })

  it('reports JSON syntax and shape problems', () => {
    expect(parseSpecJson('{').issues[0]?.path).toBe('json')
    expect(parseSpecJson('[]').issues[0]?.message).toMatch(/object/)
    expect(parseSpecJson('{"exercises": []}').issues.map((i) => i.path)).toEqual(['metadata', 'structure', 'global_constraints'])
    expect(parseSpecJson(JSON.stringify(demoSpec)).spec?.metadata.title).toBe(demoSpec.metadata.title)
  })
})
