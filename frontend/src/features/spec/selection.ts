/**
 * Current subject / project selection, shared with the home page through localStorage.
 * The keys are owned by the home page (src/features/home/selection.ts):
 *   SELECTED_SUBJECT_KEY  id of the selected subject (SubjectView.id)
 *   SELECTED_PROJECT_KEY  id of the selected project (ProjectView.id)
 */
import { SELECTED_PROJECT_KEY, SELECTED_SUBJECT_KEY, readSelection } from '@/features/home/selection'

export { SELECTED_PROJECT_KEY, SELECTED_SUBJECT_KEY, readSelection }

/** Makes `subjectId` the subject selected on the home page. */
export function selectSubject(subjectId: string): void {
  try {
    window.localStorage.setItem(SELECTED_SUBJECT_KEY, subjectId)
  } catch {
    // storage unavailable: the selection is simply not remembered
  }
}
