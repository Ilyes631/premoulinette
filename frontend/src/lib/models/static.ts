/** Mirror of backend/premoulinette/languages/python/static_models.py (AST analysis, no execution). */

export interface SyntaxErrorInfo {
  message: string
  line: number | null
  /** 1-based offset as reported by SyntaxError.offset */
  col: number | null
  end_col: number | null
  text: string | null
  kind: string
}

export interface ParamInfo {
  name: string
  annotation: string | null
  default: string | null
  kind: 'posonly' | 'positional' | 'vararg' | 'kwonly' | 'varkw'
}

export interface CallSite {
  name: string
  kind: 'builtin' | 'local' | 'method' | 'module_attr' | 'unknown'
  line: number
  col: number
  end_col: number | null
  in_function: string | null
  referenced_only: boolean
}

export interface ImportInfo {
  module: string
  names: string[]
  line: number
  in_function: string | null
}

export interface ConstructUse {
  name: string
  line: number
  in_function: string | null
}

export interface StringLiteral {
  value: string
  line: number
  end_line: number
  col: number
  end_col: number
  is_fstring: boolean
  in_call: string | null
  in_function: string | null
}

export interface ReturnInfo {
  line: number
  value_src: string | null
  value_kind: 'none' | 'constant' | 'name' | 'expression' | 'call'
  constant_type: string | null
}

export interface FunctionInfo {
  name: string
  line: number
  end_line: number
  params: ParamInfo[]
  return_annotation: string | null
  returns: ReturnInfo[]
  has_value_return: boolean
  prints: number[]
  inputs: number[]
  is_recursive: boolean
  nested: boolean
  decorators: string[]
  docstring: string | null
}

export interface TopLevelEffect {
  kind: 'print' | 'input' | 'call' | 'loop' | 'other'
  line: number
  src: string
}

export interface ModuleInfo {
  path: string
  ok: boolean
  syntax_error: SyntaxErrorInfo | null
  encoding_error: string | null
  line_count: number
  functions: FunctionInfo[]
  nested_functions: FunctionInfo[]
  classes: string[]
  imports: ImportInfo[]
  calls: CallSite[]
  constructs: ConstructUse[]
  strings: StringLiteral[]
  top_level_effects: TopLevelEffect[]
  has_main_guard: boolean
  defined_names: string[]
}
