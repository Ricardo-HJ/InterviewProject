// Shared presentation helpers — labels, badge styles, and formatters used by
// both the employee table and the provenance drawer. Kept in one place so the
// two views stay visually consistent.

import type { EmploymentStatus, ProviderName, Severity } from '#/lib/api'

export const PROVIDER_LABEL: Record<ProviderName, string> = {
  atlas: 'Atlas',
  beacon: 'Beacon',
  cobalt: 'Cobalt',
}

export const PROVIDER_BADGE_STYLE: Record<ProviderName, string> = {
  atlas: 'bg-blue-50 text-blue-700 ring-blue-200',
  beacon: 'bg-purple-50 text-purple-700 ring-purple-200',
  cobalt: 'bg-teal-50 text-teal-700 ring-teal-200',
}

export const STATUS_LABEL: Record<EmploymentStatus, string> = {
  ACTIVE: 'Active',
  ON_LEAVE: 'On leave',
  TERMINATED: 'Terminated',
  UNKNOWN: 'Unknown',
}

export const STATUS_BADGE_STYLE: Record<EmploymentStatus, string> = {
  ACTIVE: 'bg-green-50 text-green-700 ring-green-200',
  ON_LEAVE: 'bg-amber-50 text-amber-700 ring-amber-200',
  TERMINATED: 'bg-gray-100 text-gray-600 ring-gray-200',
  UNKNOWN: 'bg-gray-100 text-gray-500 ring-gray-200',
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export const SEVERITY_BADGE_STYLE: Record<Severity, string> = {
  high: 'bg-red-50 text-red-700 ring-red-200',
  medium: 'bg-amber-50 text-amber-700 ring-amber-200',
  low: 'bg-gray-100 text-gray-600 ring-gray-200',
}

// A small pill for items the proxy has flagged as not-yet-seen by any client
// (`is_new` on Issue / ConflictSuggestion / MergeCandidate — see proxy/main.py's
// app.state.seen_ids bookkeeping).
export const NEW_BADGE_CLASS =
  'inline-flex rounded-full bg-[#1e2143]/5 px-2 py-0.5 text-[11px] font-medium text-[#2a2e57] ring-1 ring-inset ring-[#1e2143]/25'

const SEVERITY_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 }

/** The most severe level among a set of issues (for a single row-level badge). */
export function topSeverity(severities: Severity[]): Severity | null {
  if (severities.length === 0) return null
  return [...severities].sort((a, b) => SEVERITY_RANK[a] - SEVERITY_RANK[b])[0]
}

/** Salary arrives as a Decimal string (e.g. "840000.00"); render it grouped. */
export function formatSalary(value: string, currency: string | null): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return value
  const formatted = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(amount)
  return currency ? `${formatted} ${currency}` : formatted
}
