import { useEffect, useMemo, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  AlertTriangle,
  ChevronRight,
  Layers,
  Loader2,
  Search,
  Sparkles,
  Users,
} from 'lucide-react'
import { fetchEmployees, fetchSearch } from '#/lib/api'
import type { Employee, EmploymentStatus } from '#/lib/api'
import { FilterMenu } from '#/components/FilterMenu'
import type { FilterSpec } from '#/components/FilterMenu'
import { ProvenanceDrawer } from '#/components/ProvenanceDrawer'
import { STATUS_LABEL, formatSalary, topSeverity } from '#/lib/display'
import { STATUS_ORDER, buildFacet, buildProviderFacet } from '#/lib/facets'

export const Route = createFileRoute('/')({ component: EmployeesPage })

const PAGE_SIZE = 10

function matchesName(employee: Employee, query: string): boolean {
  return (employee.name.value ?? '').toLowerCase().includes(query)
}

// Labels for the AI-parsed filter chips (keys mirror proxy/query.py QueryFilter).
const FILTER_LABEL: Record<string, string> = {
  department: 'Department',
  role: 'Role',
  status: 'Status',
  hired_after: 'Hired after',
  hired_before: 'Hired before',
  provider_count: 'In # providers',
  providers: 'Providers',
  salary_min: 'Salary ≥',
  salary_max: 'Salary ≤',
  limit: 'Limit',
}

function formatFilterValue(key: string, value: unknown): string {
  if (Array.isArray(value)) return value.join(', ')
  if ((key === 'salary_min' || key === 'salary_max') && typeof value === 'number') {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)
  }
  return String(value)
}

const formatSalaryCompact = (n: number) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n)

function EmployeesPage() {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Employee | null>(null)
  const [nlInput, setNlInput] = useState('')
  const [nlQuery, setNlQuery] = useState('') // the submitted natural-language query
  const [selectedDepartments, setSelectedDepartments] = useState<Set<string>>(new Set())
  const [selectedRoles, setSelectedRoles] = useState<Set<string>>(new Set())
  const [selectedStatuses, setSelectedStatuses] = useState<Set<string>>(new Set())
  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(new Set())
  const [salaryRange, setSalaryRange] = useState<[number, number] | null>(null)
  const [page, setPage] = useState(1)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['employees'],
    queryFn: fetchEmployees,
  })

  const nlActive = nlQuery.trim() !== ''
  const searchQ = useQuery({
    queryKey: ['search', nlQuery],
    queryFn: () => fetchSearch(nlQuery),
    enabled: nlActive,
  })

  const employees = data?.employees ?? []

  // The AI search only returns the matching canonical ids; render the rich rows from
  // /employees so every row keeps its issues + provenance.
  const matchedIds = useMemo(() => {
    if (!nlActive || !searchQ.data?.employees) return null
    return new Set(searchQ.data.employees.map((e) => e.canonical_id))
  }, [nlActive, searchQ.data])

  const base = useMemo(
    () => (nlActive && matchedIds ? employees.filter((e) => matchedIds.has(e.canonical_id)) : employees),
    [employees, nlActive, matchedIds],
  )

  const departmentOptions = useMemo(() => buildFacet(base, (e) => e.department.value, (v) => v), [base])
  const statusOptions = useMemo(
    () => buildFacet(base, (e) => e.status.value, (v) => STATUS_LABEL[v], STATUS_ORDER),
    [base],
  )
  const providerOptions = useMemo(() => buildProviderFacet(base), [base])

  // Title is a sub-filter of Department: its options are scoped to the selected
  // department(s), so picking "Engineering" then narrows the Title list to engineering
  // job titles. With no department selected it offers every title in the base.
  const byDepartment = useMemo(
    () =>
      selectedDepartments.size === 0
        ? base
        : base.filter((e) => selectedDepartments.has(e.department.value)),
    [base, selectedDepartments],
  )
  const roleOptions = useMemo(
    () => buildFacet(byDepartment, (e) => e.title_normalized.role, (v) => v),
    [byDepartment],
  )
  // Drop any selected title that the current department scope no longer offers, so a
  // stale pick can't silently filter the table down to nothing.
  useEffect(() => {
    setSelectedRoles((prev) => {
      const available = new Set(byDepartment.map((e) => e.title_normalized.role))
      const next = new Set([...prev].filter((r) => available.has(r)))
      return next.size === prev.size ? prev : next
    })
  }, [byDepartment])

  // Slider track bounds come from whatever's currently loaded (same stable-base
  // convention as the other facets' option lists) — null when nothing parses, which
  // hides the control instead of rendering a degenerate 0–0 slider.
  const salaryBounds = useMemo<[number, number] | null>(() => {
    const values = base.map((e) => Number(e.salary_annual.value)).filter(Number.isFinite)
    if (values.length === 0) return null
    return [Math.min(...values), Math.max(...values)]
  }, [base])

  // Facets AND together; checkboxes within one facet OR together (standard faceted-search
  // convention). Layered after the NL search base, before the free-text name filter.
  const faceted = useMemo(() => {
    return base.filter((e) => {
      if (selectedDepartments.size > 0 && !selectedDepartments.has(e.department.value)) return false
      if (selectedRoles.size > 0 && !selectedRoles.has(e.title_normalized.role)) return false
      if (selectedStatuses.size > 0 && !selectedStatuses.has(e.status.value)) return false
      if (selectedProviders.size > 0 && !e.providers.some((p) => selectedProviders.has(p))) return false
      if (salaryRange) {
        const amount = Number(e.salary_annual.value)
        if (!Number.isFinite(amount) || amount < salaryRange[0] || amount > salaryRange[1]) return false
      }
      return true
    })
  }, [base, selectedDepartments, selectedRoles, selectedStatuses, selectedProviders, salaryRange])

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return faceted
    return faceted.filter((employee) => matchesName(employee, query))
  }, [faceted, search])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  useEffect(
    () => setPage(1),
    [search, selectedDepartments, selectedRoles, selectedStatuses, selectedProviders, salaryRange, nlQuery],
  )
  const paged = useMemo(
    () => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filtered, page],
  )

  const downProviders = data?.providers.filter((p) => !p.ok) ?? []
  const appliedFilter = searchQ.data?.applied_filter ?? null
  const clearNl = () => {
    setNlQuery('')
    setNlInput('')
  }

  const filterSpecs: FilterSpec[] = [
    { kind: 'facet', key: 'department', label: 'Department', options: departmentOptions, selected: selectedDepartments, onChange: setSelectedDepartments },
    { kind: 'facet', key: 'role', label: 'Title', options: roleOptions, selected: selectedRoles, onChange: setSelectedRoles },
    ...(salaryBounds
      ? [{ kind: 'range', key: 'salary', label: 'Salary', min: salaryBounds[0], max: salaryBounds[1], step: 1000, value: salaryRange, onChange: setSalaryRange, format: formatSalaryCompact } as FilterSpec]
      : []),
    { kind: 'facet', key: 'provider', label: 'Provider', options: providerOptions, selected: selectedProviders, onChange: setSelectedProviders },
    { kind: 'facet', key: 'status', label: 'Status', options: statusOptions, selected: selectedStatuses, onChange: setSelectedStatuses },
  ]

  return (
    <div className="mx-auto max-w-6xl px-8 pb-16 pt-8">
      <header>
        <h1 className="text-3xl font-semibold leading-tight text-black">Employees</h1>
        <p className="mt-1.5 text-sm text-[#6e6e6e]">
          Unified view across Atlas HR, Beacon People, and Cobalt Directory.
        </p>
      </header>

      {data && data.partial && (
        <div className="mt-4 flex gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">
              Showing partial data — {downProviders.length} provider
              {downProviders.length === 1 ? '' : 's'} unavailable.
            </p>
            <ul className="mt-1 space-y-0.5">
              {downProviders.map((p) => (
                <li key={p.provider}>
                  <span className="font-medium">{p.provider}</span>: {p.error}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Row 1 — deterministic narrowing: name search + the faceted "+ Filter" menu (no AI).
          Always-available controls come first, above the AI section. Gated on the raw list
          so it stays put regardless of what the natural-language search below returns. */}
      {!isPending && !isError && employees.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <div className="relative w-57.5">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter by name..."
              className="w-full rounded-md border border-[#ededed] bg-white py-2 pl-9 pr-3 text-xs text-gray-800 shadow-[0px_3px_3.25px_rgba(0,0,0,0.08)] placeholder:text-[#bcbcbc] focus:border-gray-300 focus:outline-none"
            />
          </div>
          <FilterMenu filters={filterSpecs} />
        </div>
      )}

      {/* Natural-language search (AI compiles the sentence → structured filter) and the table
          it produces — plain, unframed blocks under the deterministic filters row. */}
      <form
        className="mt-6 flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          setNlQuery(nlInput)
        }}
      >
        <div className="relative w-full max-w-140">
          <Sparkles className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#1e2143]" />
          <input
            value={nlInput}
            onChange={(event) => setNlInput(event.target.value)}
            placeholder="Ask in plain English — e.g. “engineering hired after 2021, only in one provider”"
            className="w-full rounded-md border border-[#ededed] bg-white py-2 pl-9 pr-3 text-xs text-gray-800 shadow-[0px_3px_3.25px_rgba(0,0,0,0.08)] placeholder:text-[#bcbcbc] focus:border-[#1e2143]/40 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="shrink-0 rounded-full bg-[#1e2143] px-5 py-2 text-xs font-medium text-white shadow-[0px_5px_20px_0px_rgba(0,0,0,0.12)] hover:bg-[#2a2e57]"
        >
          Search
        </button>
        {nlActive && (
          <button
            type="button"
            onClick={clearNl}
            className="shrink-0 rounded-full border border-[#ededed] bg-white px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            Clear
          </button>
        )}
      </form>

      {nlActive && (
        <div className="mt-2 text-sm">
          {searchQ.isPending ? (
            <span className="inline-flex items-center gap-2 text-[#1e2143]">
              <Loader2 className="size-4 animate-spin" /> Interpreting your query...
            </span>
          ) : searchQ.isError ? (
            <span className="text-red-600">Couldn't run the search. Is the proxy on :8000?</span>
          ) : appliedFilter ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-gray-500">Interpreted as</span>
              {Object.entries(appliedFilter).map(([key, value]) => (
                <span
                  key={key}
                  className="inline-flex items-center gap-1 rounded-full bg-[#1e2143]/5 px-2 py-0.5 text-xs font-medium text-[#1e2143] ring-1 ring-inset ring-[#1e2143]/15"
                >
                  {FILTER_LABEL[key] ?? key}: {formatFilterValue(key, value)}
                </span>
              ))}
              <span className="text-xs text-gray-400">· {base.length} matched</span>
            </div>
          ) : (
            <span className="inline-flex items-center gap-2 text-amber-700">
              <AlertTriangle className="size-4" />
              {searchQ.data?.note ?? 'Could not interpret the query.'}
            </span>
          )}
        </div>
      )}

      <div className="mt-6">
        {isPending && <LoadingState label="Loading employees..." />}
        {isError && <ErrorState message={(error as Error).message} onRetry={refetch} />}
        {!isPending && !isError && nlActive && searchQ.isPending && (
          <LoadingState label="Running search..." />
        )}
        {!isPending && !isError && !(nlActive && searchQ.isPending) &&
          (filtered.length === 0 ? (
            <EmptyState reason={employees.length === 0 ? 'none' : base.length === 0 ? 'query' : 'filters'} />
          ) : (
            <>
              <EmployeeTable employees={paged} onSelect={setSelected} />
              <Pagination page={page} pageCount={pageCount} total={filtered.length} pageSize={PAGE_SIZE} onChange={setPage} />
            </>
          ))}
      </div>

      {selected && <ProvenanceDrawer employee={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

/** Small row-level cue: data-quality issues take priority (severity-colored); otherwise
 *  show how many fields merely differ across sources (informational, not a problem). */
function RowSignal({ employee }: { employee: Employee }) {
  if (employee.issues.length > 0) {
    const sev = topSeverity(employee.issues.map((i) => i.severity))
    const tone = sev === 'high' ? 'text-red-600' : sev === 'medium' ? 'text-amber-600' : 'text-gray-500'
    return (
      <span
        title={`${employee.issues.length} data-quality issue${employee.issues.length === 1 ? '' : 's'}`}
        className={`inline-flex items-center gap-0.5 ${tone}`}
      >
        <AlertTriangle className="size-3.5" />
        <span className="text-xs font-medium">{employee.issues.length}</span>
      </span>
    )
  }
  if (employee.conflicts.length > 0) {
    return (
      <span
        title={`${employee.conflicts.length} field${employee.conflicts.length === 1 ? '' : 's'} differ across sources`}
        className="inline-flex items-center gap-0.5 text-gray-400"
      >
        <Layers className="size-3.5" />
        <span className="text-xs font-medium">{employee.conflicts.length}</span>
      </span>
    )
  }
  return null
}

// Subtle status cue — a colored dot + plain label, matching the Figma's text-based
// status column while still signalling state at a glance.
const STATUS_DOT: Record<EmploymentStatus, string> = {
  ACTIVE: 'bg-green-500',
  ON_LEAVE: 'bg-amber-500',
  TERMINATED: 'bg-gray-400',
  UNKNOWN: 'bg-gray-300',
}

function EmployeeTable({
  employees,
  onSelect,
}: {
  employees: Employee[]
  onSelect: (employee: Employee) => void
}) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full min-w-55 border-separate border-spacing-0 text-left">
        <thead>
          <tr className="bg-[#eee] text-xs text-black [&>th]:bg-[#eee]">
            <th className="w-65 rounded-l-md px-4 py-2.5 font-medium">Name</th>
            <th className="w-37.5 px-4 py-2.5 font-medium">Department</th>
            <th className="w-55 px-4 py-2.5 font-medium">Title</th>
            <th className="w-32.5 px-4 py-2.5 font-medium">Salary</th>
            <th className="w-27.5 px-4 py-2.5 font-medium">Hire date</th>
            <th className="w-20 px-4 py-2.5 font-medium">Status</th>
            <th className="rounded-r-md px-2 py-2.5">
              <span className="sr-only">View provenance</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {employees.map((employee) => (
            <tr
              key={employee.canonical_id}
              onClick={() => onSelect(employee)}
              className="group cursor-pointer [&>td]:border-b [&>td]:border-[#ededed] hover:[&>td]:bg-black/2"
            >
              <td className="px-4 py-3.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-medium text-black">{employee.name.value}</span>
                  <RowSignal employee={employee} />
                </div>
                <div className="mt-1 text-xs text-[#6e6e6e]">{employee.email}</div>
              </td>
              <td className="px-4 py-3.5 text-xs text-black">{employee.department.value}</td>
              <td className="px-4 py-3.5 text-xs text-black">{employee.title.value}</td>
              <td className="px-4 py-3.5 text-xs text-black">
                {formatSalary(employee.salary_annual.value, employee.currency)}
              </td>
              <td className="px-4 py-3.5 text-xs text-black">{employee.hire_date.value}</td>
              <td className="px-4 py-3.5">
                <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-black">
                  <span className={`size-1.5 shrink-0 rounded-full ${STATUS_DOT[employee.status.value]}`} />
                  {STATUS_LABEL[employee.status.value]}
                </span>
              </td>
              <td className="px-2 py-3.5 text-right">
                <ChevronRight className="inline size-4 text-gray-300 group-hover:text-gray-500" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Windowed page tokens: a run of 5 consecutive pages around the current one, always
 *  including the first and last with `…` gaps — e.g. `1 2 3 4 5 … 300` near the start,
 *  `1 … 148 149 150 151 152 … 300` in the middle. */
function pageTokens(current: number, count: number): (number | '…')[] {
  const WINDOW = 5
  if (count <= WINDOW + 2) return Array.from({ length: count }, (_, i) => i + 1)

  const end = Math.min(count, Math.max(current + 2, WINDOW))
  const start = Math.max(1, end - WINDOW + 1)
  const tokens: (number | '…')[] = []

  if (start > 1) {
    tokens.push(1)
    if (start > 2) tokens.push('…')
  }
  for (let p = start; p <= end; p++) tokens.push(p)
  if (end < count) {
    if (end < count - 1) tokens.push('…')
    tokens.push(count)
  }
  return tokens
}

function Pagination({
  page,
  pageCount,
  total,
  pageSize,
  onChange,
}: {
  page: number
  pageCount: number
  total: number
  pageSize: number
  onChange: (page: number) => void
}) {
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  const tokens = pageTokens(page, pageCount)
  return (
    <div className="mt-5 flex items-center justify-between px-2">
      <span className="text-[11px] text-[#6e6e6e]">
        Showing {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-1.25">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          className="flex h-8 items-center justify-center rounded-lg bg-white px-2.5 text-[13px] font-medium text-[#333] hover:bg-gray-50 disabled:text-[#ccc] disabled:hover:bg-white"
        >
          Prev
        </button>
        {tokens.map((token, i) =>
          token === '…' ? (
            <span
              key={`ellipsis-${i}`}
              className="flex size-8 items-center justify-center rounded-lg bg-white text-[13px] font-medium text-[#333]"
            >
              …
            </span>
          ) : (
            <button
              key={token}
              onClick={() => onChange(token)}
              className={`flex size-8 items-center justify-center rounded-lg text-[13px] font-medium ${
                token === page
                  ? 'bg-[#1c1f41] text-white'
                  : 'border border-[#f1f1f1] bg-white text-[#333] hover:bg-gray-50'
              }`}
            >
              {token}
            </button>
          ),
        )}
        <button
          onClick={() => onChange(page + 1)}
          disabled={page >= pageCount}
          className="flex h-8 items-center justify-center rounded-lg bg-white px-2.5 text-[13px] font-medium text-[#333] hover:bg-gray-50 disabled:text-[#ccc] disabled:hover:bg-white"
        >
          Next
        </button>
      </div>
      <span className="text-[10px] text-[#6e6e6e]">
        Page {page} of {pageCount}
      </span>
    </div>
  )
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-2 rounded-lg border border-gray-200 py-16 text-gray-500">
      <Loader2 className="size-4 animate-spin" />
      {label}
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-red-200 bg-red-50 py-16 text-red-700">
      <AlertCircle className="size-6" />
      <p className="text-sm font-medium">Couldn't load employees</p>
      <p className="text-xs text-red-600">{message}</p>
      <button
        onClick={() => onRetry()}
        className="mt-1 rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
      >
        Retry
      </button>
    </div>
  )
}

function EmptyState({ reason }: { reason: 'none' | 'query' | 'filters' }) {
  const message =
    reason === 'none'
      ? 'No employees found.'
      : reason === 'query'
        ? 'No employees match that query.'
        : 'No employees match these filters.'
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-gray-200 py-16 text-gray-500">
      {reason === 'none' ? <Users className="size-6" /> : <Search className="size-6" />}
      <p className="text-sm">{message}</p>
    </div>
  )
}
