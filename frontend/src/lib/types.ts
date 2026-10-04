/**
 * Single import point for every backend model mirrored in TypeScript.
 *
 *   import type { CheckResult, PracticalSpec, SubjectView } from '@/lib/types'
 *
 * Sources: spec/models.py, results/models.py, runner/models.py,
 * languages/python/static_models.py and the API views of ARCHITECTURE.md.
 */
export type * from './models/spec'
export type * from './models/results'
export type * from './models/runner'
export type * from './models/static'
export type * from './models/api'
export { SCHEMA_VERSION } from './models/spec'
