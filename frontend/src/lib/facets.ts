// Shared faceted-filter helpers — used by the Employees table and the Conflicts page so
// both build their checkbox facets (Department/Status/Provider) the same way.

import type { Employee, EmploymentStatus, ProviderName } from '#/lib/api'
import { PROVIDER_LABEL } from '#/lib/display'

// One checkbox option in a facet: the raw value, a display label, and the matching count.
export type FacetOption = { value: string; label: string; count: number }

// Fixed display orders (mirror the backend enums) so Status/Provider facets don't
// reorder themselves as data changes; Department/Family have no canonical order.
export const STATUS_ORDER: EmploymentStatus[] = ['ACTIVE', 'ON_LEAVE', 'TERMINATED', 'UNKNOWN']
export const PROVIDER_ORDER: ProviderName[] = ['atlas', 'beacon', 'cobalt']

/** Build one facet's checkbox options from a set of employees: distinct values
 *  present, each with a count. Compute against the same base list for every facet
 *  (not against each other's selections), so ticking one box never reshuffles
 *  another's option list. */
export function buildFacet<T extends string>(
  employees: Employee[],
  getValue: (e: Employee) => T | null | undefined,
  labelFor: (value: T) => string,
  order?: readonly T[],
): FacetOption[] {
  const counts = new Map<T, number>()
  for (const e of employees) {
    const value = getValue(e)
    if (!value) continue
    counts.set(value, (counts.get(value) ?? 0) + 1)
  }
  const values = order ? order.filter((v) => counts.has(v)) : [...counts.keys()].sort()
  return values.map((value) => ({ value, label: labelFor(value), count: counts.get(value)! }))
}

/** Provider is multi-valued per employee (`providers: ProviderName[]`), so it needs its
 *  own counting pass rather than `buildFacet`'s single-value-per-item assumption. */
export function buildProviderFacet(employees: Employee[]): FacetOption[] {
  const counts = new Map<ProviderName, number>()
  for (const e of employees) for (const p of e.providers) counts.set(p, (counts.get(p) ?? 0) + 1)
  return PROVIDER_ORDER.filter((p) => counts.has(p)).map((p) => ({
    value: p,
    label: PROVIDER_LABEL[p],
    count: counts.get(p)!,
  }))
}
