import { useCallback, useState } from 'react'

/** localStorage keys of the subject / project currently selected on the home page. */
export const SELECTED_SUBJECT_KEY = 'premoulinette.home.subject'
export const SELECTED_PROJECT_KEY = 'premoulinette.home.project'

function read(key: string): string | null {
  try {
    const value = window.localStorage.getItem(key)
    return value && value.trim() ? value : null
  } catch {
    return null
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value) window.localStorage.setItem(key, value)
    else window.localStorage.removeItem(key)
  } catch {
    // storage unavailable (private mode): the selection simply is not remembered
  }
}

/** A string id persisted in localStorage (survives navigation and reloads). */
export function useStoredId(key: string): [string | null, (value: string | null) => void] {
  const [value, setValue] = useState<string | null>(() => read(key))
  const update = useCallback(
    (next: string | null) => {
      write(key, next)
      setValue(next)
    },
    [key],
  )
  return [value, update]
}

export function readSelection(): { subjectId: string | null; projectId: string | null } {
  return { subjectId: read(SELECTED_SUBJECT_KEY), projectId: read(SELECTED_PROJECT_KEY) }
}
