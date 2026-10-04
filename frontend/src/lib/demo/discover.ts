/**
 * GET /api/projects/discover in the online demo: there is no PC to scan, so one sample entry is
 * listed. Picking it imports a local folder, which the demo refuses with the read-only notice.
 */
import type { DiscoverProjectsResult } from '../types'

const TWO_HOURS_MS = 2 * 3600_000

export function demoDiscoveredProjects(now: number): DiscoverProjectsResult {
  return {
    projects: [
      {
        path: '\\\\wsl.localhost\\Ubuntu\\root\\epita-prog-101-tp1-demo',
        name: 'epita-prog-101-tp1-demo',
        location: 'wsl',
        distro: 'Ubuntu',
        display_path: 'Ubuntu: /root/epita-prog-101-tp1-demo',
        branch: 'main',
        last_activity: new Date(now - TWO_HOURS_MS).toISOString(),
        last_message: 'commit: TP1 almost done',
        remote_url: null,
        is_school: true,
      },
    ],
    scanned: ['Online demo (sample entry)'],
    duration_ms: 0,
  }
}
