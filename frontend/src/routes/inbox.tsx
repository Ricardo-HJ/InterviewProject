import { useMemo, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  AlertTriangle,
  Check,
  ChevronDown,
  Copy,
  GitMerge,
  Inbox as InboxIcon,
  Lightbulb,
  ListChecks,
  Loader2,
  Search,
  Sparkles,
  Undo2,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import {
  fetchConflicts,
  fetchEmployees,
  fetchIssueRootCause,
  fetchIssues,
  fetchMergeBulkFilter,
  fetchMergeCandidates,
} from '#/lib/api'
import type { ConflictSuggestion, Employee, EmployeesResponse, Issue, MergeCandidate, ProviderName } from '#/lib/api'
import { BulkActionBar } from '#/components/BulkActionBar'
import { CandidateCard, candidateId, type Decision } from '#/components/CandidateCard'
import { FilterMenu, type FilterSpec } from '#/components/FilterMenu'
import {
  NEW_BADGE_CLASS,
  PROVIDER_BADGE_STYLE,
  PROVIDER_LABEL,
  SEVERITY_BADGE_STYLE,
  SEVERITY_LABEL,
  STATUS_LABEL,
} from '#/lib/display'
import { buildFacet, buildProviderFacet, STATUS_ORDER } from '#/lib/facets'

export const Route = createFileRoute('/inbox')({ component: InboxPage })

const ISSUE_KIND_LABEL: Record<string, string> = {
  status_conflict: 'Status conflict',
  salary_outlier: 'Salary outlier',
  salary_disagreement: 'Salary disagreement',
  missing_data: 'Missing data',
  impossible_date: 'Impossible date',
}

const FIELD_LABEL: Record<string, string> = {
  name: 'Name',
  title: 'Title',
  department: 'Department',
}

// Issue kinds whose evidence is a genuine multi-value disagreement (a value to PICK
// between) rather than a single-value anomaly flag with nothing to choose from.
const CHANGEABLE_KINDS = new Set(['status_conflict', 'salary_disagreement'])

type Triage =
  | { kind: 'applied' }
  | { kind: 'acknowledged' }
  | { kind: 'dismissed' }
  | { kind: 'changed'; value: string }

const MERGE_FILTER_LABEL: Record<string, string> = { min_score: 'Min score', differs_only_in: 'Differs only in' }

function formatMergeFilterValue(key: string, value: unknown): string {
  if (key === 'min_score' && typeof value === 'number') return `${Math.round(value * 100)}%`
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}

type TabKey = 'needs-review' | 'issues' | 'suggestions' | 'duplicates'

// One unified queue item over the two feeds, with a stable id for triage tracking.
type Item =
  | { type: 'issue'; id: string; name: string; email: string; issue: Issue }
  | {
      type: 'suggestion'
      id: string
      name: string
      email: string
      suggestion: ConflictSuggestion
      actionable: boolean
    }

const SEV_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 }

function itemCanonicalId(item: Item): string {
  return item.type === 'issue' ? item.issue.canonical_id : item.suggestion.canonical_id
}

function matchesTab(item: Item, tab: TabKey): boolean {
  if (tab === 'duplicates') return false // duplicates are MergeCandidates, not Items
  if (tab === 'issues') return item.type === 'issue'
  if (tab === 'suggestions') return item.type === 'suggestion'
  // needs-review: problems + suggestions that actually change something.
  return item.type === 'issue' || item.actionable
}

function InboxPage() {
  const issuesQuery = useQuery({ queryKey: ['issues'], queryFn: fetchIssues })
  const conflictsQuery = useQuery({ queryKey: ['conflicts'], queryFn: fetchConflicts })
  const employeesQuery = useQuery({ queryKey: ['employees'], queryFn: fetchEmployees })
  const mergeQuery = useQuery({ queryKey: ['merge-candidates'], queryFn: fetchMergeCandidates })
  const queryClient = useQueryClient()

  const [tab, setTab] = useState<TabKey>('needs-review')
  const [search, setSearch] = useState('')
  const [triaged, setTriaged] = useState<Record<string, Triage>>({})
  const [decisions, setDecisions] = useState<Record<string, Decision>>({})
  const [showResolved, setShowResolved] = useState(false)
  const [selectedDepartments, setSelectedDepartments] = useState<Set<string>>(new Set())
  const [selectedStatuses, setSelectedStatuses] = useState<Set<string>>(new Set())
  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(new Set())

  const duplicateCandidates = useMemo(
    () => [...(mergeQuery.data?.merge_candidates ?? [])].sort((a, b) => b.score - a.score),
    [mergeQuery.data],
  )
  const pendingDuplicates = duplicateCandidates.filter((c) => !decisions[candidateId(c)])
  const resolvedDuplicates = duplicateCandidates.filter((c) => decisions[candidateId(c)])
  const pendingDuplicateIds = useMemo(() => new Set(pendingDuplicates.map(candidateId)), [pendingDuplicates])

  const decide = (id: string, value: Decision | undefined) =>
    setDecisions((prev) => {
      const next = { ...prev }
      if (value) next[id] = value
      else delete next[id]
      return next
    })

  const items = useMemo<Item[]>(() => {
    const issues = issuesQuery.data?.issues ?? []
    const suggestions = conflictsQuery.data?.conflicts ?? []
    return [
      ...issues.map(
        (issue): Item => ({
          type: 'issue',
          id: issue.id,
          name: issue.employee_name,
          email: issue.employee_email,
          issue,
        }),
      ),
      ...suggestions.map(
        (suggestion): Item => ({
          type: 'suggestion',
          id: `${suggestion.canonical_id}:${suggestion.field}`,
          name: suggestion.employee_name,
          email: suggestion.employee_email,
          suggestion,
          actionable: suggestion.suggested !== suggestion.current,
        }),
      ),
    ]
  }, [issuesQuery.data, conflictsQuery.data])

  // Join each item to its full Employee record (for the facet filters) by canonical_id.
  const employeeById = useMemo(() => {
    const map = new Map<string, Employee>()
    for (const e of employeesQuery.data?.employees ?? []) map.set(e.canonical_id, e)
    return map
  }, [employeesQuery.data])

  // Facet options are built from the employees behind currently-PENDING items (across
  // all tabs) — so counts read as "how many open items touch this department," not
  // "how many employees company-wide," and ticking one box doesn't reshuffle the rest.
  const pendingItemEmployees = useMemo(() => {
    const out: Employee[] = []
    for (const item of items) {
      if (triaged[item.id]) continue
      const emp = employeeById.get(itemCanonicalId(item))
      if (emp) out.push(emp)
    }
    return out
  }, [items, triaged, employeeById])

  const departmentOptions = useMemo(
    () => buildFacet(pendingItemEmployees, (e) => e.department.value, (v) => v),
    [pendingItemEmployees],
  )
  const statusOptions = useMemo(
    () => buildFacet(pendingItemEmployees, (e) => e.status.value, (v) => STATUS_LABEL[v], STATUS_ORDER),
    [pendingItemEmployees],
  )
  const providerOptions = useMemo(() => buildProviderFacet(pendingItemEmployees), [pendingItemEmployees])

  // Same unified "+ Filter" menu the Employees table uses, so both surfaces filter identically.
  const filterSpecs: FilterSpec[] = [
    { kind: 'facet', key: 'department', label: 'Department', options: departmentOptions, selected: selectedDepartments, onChange: setSelectedDepartments },
    { kind: 'facet', key: 'status', label: 'Status', options: statusOptions, selected: selectedStatuses, onChange: setSelectedStatuses },
    { kind: 'facet', key: 'provider', label: 'Provider', options: providerOptions, selected: selectedProviders, onChange: setSelectedProviders },
  ]

  const facetMatch = (item: Item) => {
    const emp = employeeById.get(itemCanonicalId(item))
    if (!emp) return true // employees still loading — don't hide items while we wait
    if (selectedDepartments.size > 0 && !selectedDepartments.has(emp.department.value)) return false
    if (selectedStatuses.size > 0 && !selectedStatuses.has(emp.status.value)) return false
    if (selectedProviders.size > 0 && !emp.providers.some((p) => selectedProviders.has(p))) return false
    return true
  }

  const query = search.trim().toLowerCase()
  const searchMatch = (item: Item) =>
    !query || item.name.toLowerCase().includes(query) || item.email.toLowerCase().includes(query)

  // Tab counts reflect the live queue: items still untriaged in that tab.
  const tabCount = (key: TabKey) =>
    items.filter((i) => matchesTab(i, key) && !triaged[i.id]).length

  const inTab = items.filter((item) => matchesTab(item, tab) && searchMatch(item) && facetMatch(item))
  const pending = inTab.filter((item) => !triaged[item.id]).sort(compareItems)
  const resolved = inTab.filter((item) => triaged[item.id])

  const isPending = issuesQuery.isPending || conflictsQuery.isPending
  const isError = issuesQuery.isError || conflictsQuery.isError
  const partial = Boolean(conflictsQuery.data?.partial || issuesQuery.data?.partial)

  const setItem = (id: string, value: Triage | undefined) =>
    setTriaged((prev) => {
      const next = { ...prev }
      if (value) next[id] = value
      else delete next[id]
      return next
    })

  // The new "change it" resolution for status/salary disagreements: picking a value
  // both resolves the issue here AND patches the shared `['employees']` cache, so the
  // Employees table + provenance drawer reflect the choice for the rest of the session
  // (there's no backend persistence anywhere in this app — this is a client-side
  // override, same as every other triage decision in the inbox).
  const changeIssue = (issue: Issue, value: string) => {
    if (issue.field) {
      const field = issue.field as 'status' | 'salary_annual'
      queryClient.setQueryData<EmployeesResponse>(['employees'], (old) => {
        if (!old) return old
        return {
          ...old,
          employees: old.employees.map((e) =>
            e.canonical_id === issue.canonical_id
              ? { ...e, [field]: { ...e[field], value }, issues: e.issues.filter((i) => i.id !== issue.id) }
              : e,
          ),
        }
      })
    }
    setItem(issue.id, { kind: 'changed', value })
  }

  return (
    <div className="mx-auto max-w-5xl px-8 pb-16 pt-8">
      <header>
        <h1 className="text-3xl font-semibold leading-tight text-black">Conflict inbox</h1>
        <p className="mt-1.5 text-sm text-[#6e6e6e]">
          Triage data-quality issues and cross-provider disagreements. Everything here is
          advisory — applying a suggestion records your decision for this session.
        </p>
      </header>

      {partial && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          Some providers were unavailable — this queue may be incomplete.
        </div>
      )}

      {/* Row 1 — queue tabs. Same rounded-pill family as the top navbar, but page-level:
          the active tab is a solid dark pill (vs. the nav's frosted-glass active), so the
          two rows read as related without ever being mistaken for one another. */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <Tab active={tab === 'needs-review'} onClick={() => setTab('needs-review')} icon={ListChecks} label="Needs review" count={tabCount('needs-review')} />
        <Tab active={tab === 'issues'} onClick={() => setTab('issues')} icon={AlertTriangle} label="Issues" count={tabCount('issues')} />
        <Tab active={tab === 'suggestions'} onClick={() => setTab('suggestions')} icon={Lightbulb} label="Suggestions" count={tabCount('suggestions')} />
        <Tab active={tab === 'duplicates'} onClick={() => setTab('duplicates')} icon={Copy} label="Possible duplicates" count={pendingDuplicates.length} />
      </div>

      {/* Row 2 — deterministic narrowing: name search + the faceted "+ Filter" menu. Hidden
          on the duplicates tab, which is a different shape (merge candidates, not queue items). */}
      {tab !== 'duplicates' && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by employee..."
              className="w-full rounded-md border border-[#ededed] bg-white py-2 pl-9 pr-3 text-xs shadow-[0px_3px_3.25px_rgba(0,0,0,0.08)] placeholder:text-[#bcbcbc] focus:border-gray-300 focus:outline-none"
            />
          </div>
          <FilterMenu filters={filterSpecs} />
        </div>
      )}

      {/* AI bulk-triage command bar — duplicates tab only. Bulk-approving a free-text
          criterion pays off for the merge queue; the issue/suggestion tabs stay uncluttered. */}
      {tab === 'duplicates' && (
        <div className="mt-6">
          <BulkActionBar
            placeholder='Bulk-approve a criterion — e.g. "approve any match >= 90%"'
            fetchFilter={fetchMergeBulkFilter}
            matchedIds={(matched) => new Set(matched.map((m) => `${m.left_id}|${m.right_id}`))}
            pendingIds={pendingDuplicateIds}
            onApply={(ids) => ids.forEach((id) => decide(id, 'confirmed'))}
            filterLabel={(key, value) => `${MERGE_FILTER_LABEL[key] ?? key}: ${formatMergeFilterValue(key, value)}`}
          />
        </div>
      )}

      <div className="mt-4">
        {tab === 'duplicates' ? (
          <>
            {mergeQuery.isPending && (
              <InboxState icon={<Loader2 className="size-4 animate-spin" />}>Scoring candidates...</InboxState>
            )}
            {mergeQuery.isError && (
              <InboxState icon={<AlertCircle className="size-5 text-red-500" />}>
                Couldn't load merge candidates. Is the proxy running on :8000?
              </InboxState>
            )}

            {!mergeQuery.isPending && !mergeQuery.isError && (
              <>
                {pendingDuplicates.length === 0 ? (
                  <InboxState icon={<GitMerge className="size-6 text-gray-400" />}>
                    {duplicateCandidates.length === 0 ? 'No likely duplicates found.' : 'All candidates reviewed.'}
                  </InboxState>
                ) : (
                  <ul className="space-y-4">
                    {pendingDuplicates.map((c) => (
                      <li key={candidateId(c)}>
                        <CandidateCard candidate={c} onDecide={(v) => decide(candidateId(c), v)} />
                      </li>
                    ))}
                  </ul>
                )}

                {resolvedDuplicates.length > 0 && (
                  <div className="mt-5">
                    <button
                      onClick={() => setShowResolved((v) => !v)}
                      className="flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-800"
                    >
                      <ChevronDown className={`size-4 transition-transform ${showResolved ? 'rotate-180' : ''}`} />
                      {resolvedDuplicates.length} decided this session
                    </button>
                    {showResolved && (
                      <ul className="mt-2 space-y-1.5">
                        {resolvedDuplicates.map((c) => (
                          <li key={candidateId(c)}>
                            <ResolvedDuplicateStrip
                              candidate={c}
                              decision={decisions[candidateId(c)]}
                              onUndo={() => decide(candidateId(c), undefined)}
                            />
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </>
            )}
          </>
        ) : (
          <>
            {isPending && <InboxState icon={<Loader2 className="size-4 animate-spin" />}>Loading inbox...</InboxState>}
            {isError && (
              <InboxState icon={<AlertCircle className="size-5 text-red-500" />}>
                Couldn't load the inbox. Is the proxy running on :8000?
              </InboxState>
            )}

            {!isPending && !isError && (
              <>
                {pending.length === 0 ? (
                  <InboxState icon={<InboxIcon className="size-6 text-gray-400" />}>
                    {resolved.length > 0 ? 'All caught up in this view.' : 'Nothing to review here.'}
                  </InboxState>
                ) : (
                  <ul className="space-y-3">
                    {pending.map((item) => (
                      <li key={item.id}>
                        <TriageCard item={item} onTriage={(v) => setItem(item.id, v)} onChangeIssue={changeIssue} />
                      </li>
                    ))}
                  </ul>
                )}

                {resolved.length > 0 && (
                  <div className="mt-5">
                    <button
                      onClick={() => setShowResolved((v) => !v)}
                      className="flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-800"
                    >
                      <ChevronDown className={`size-4 transition-transform ${showResolved ? 'rotate-180' : ''}`} />
                      {resolved.length} resolved this session
                    </button>
                    {showResolved && (
                      <ul className="mt-2 space-y-1.5">
                        {resolved.map((item) => (
                          <li key={item.id}>
                            <ResolvedStrip
                              item={item}
                              status={triaged[item.id]}
                              onUndo={() => setItem(item.id, undefined)}
                            />
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function compareItems(a: Item, b: Item): number {
  // Issues before suggestions; within issues by severity; within suggestions actionable first.
  const rank = (i: Item) => (i.type === 'issue' ? 0 : 1)
  if (rank(a) !== rank(b)) return rank(a) - rank(b)
  if (a.type === 'issue' && b.type === 'issue') {
    const d = SEV_RANK[a.issue.severity] - SEV_RANK[b.issue.severity]
    if (d !== 0) return d
    return a.name.localeCompare(b.name)
  }
  if (a.type === 'suggestion' && b.type === 'suggestion') {
    if (a.actionable !== b.actionable) return a.actionable ? -1 : 1
    if (a.suggestion.field !== b.suggestion.field)
      return a.suggestion.field.localeCompare(b.suggestion.field)
    return a.name.localeCompare(b.name)
  }
  return 0
}

/** A queue tab. Shares the rounded-pill shape + icon of the top navbar links so the two
 *  rows feel like one system, but flips the active treatment to a solid dark pill (the
 *  app's primary color) instead of the nav's frosted-glass one — a deliberate contrast so
 *  users never confuse "which section am I in" with "which queue am I viewing". */
function Tab({
  active,
  onClick,
  icon: Icon,
  label,
  count,
}: {
  active: boolean
  onClick: () => void
  icon: LucideIcon
  label: string
  count: number
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-medium transition-colors ${
        active
          ? 'border-transparent bg-[#1e2143] text-white shadow-[0px_5px_20px_0px_rgba(0,0,0,0.12)]'
          : 'border-[#ededed] bg-white/60 text-gray-600 hover:bg-white hover:text-gray-900'
      }`}
    >
      <Icon className="size-4 shrink-0" strokeWidth={1.75} />
      {label}
      <Count n={count} active={active} />
    </button>
  )
}

function Count({ n, active }: { n: number; active?: boolean }) {
  return (
    <span
      className={`rounded px-1.5 text-xs tabular-nums ${
        active ? 'bg-white/20 text-white' : 'bg-gray-200/70 text-gray-600'
      }`}
    >
      {n}
    </span>
  )
}

function ProviderTag({ provider }: { provider: ProviderName }) {
  return (
    <span
      className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ${PROVIDER_BADGE_STYLE[provider]}`}
    >
      {PROVIDER_LABEL[provider]}
    </span>
  )
}

const LEFT_ACCENT: Record<string, string> = {
  high: 'border-l-red-400',
  medium: 'border-l-amber-400',
  low: 'border-l-gray-300',
  actionable: 'border-l-amber-300',
  aligned: 'border-l-gray-200',
}

function TriageCard({
  item,
  onTriage,
  onChangeIssue,
}: {
  item: Item
  onTriage: (v: Triage) => void
  onChangeIssue: (issue: Issue, value: string) => void
}) {
  const accent =
    item.type === 'issue'
      ? LEFT_ACCENT[item.issue.severity]
      : item.actionable
        ? LEFT_ACCENT.actionable
        : LEFT_ACCENT.aligned

  // For a disagreement issue with multiple values to pick between, resolving = picking
  // a value. Those choices ARE the actions (below) — no separate acknowledge/dismiss.
  const byProvider =
    item.type === 'issue' ? (item.issue.evidence?.by_provider as Record<string, unknown> | undefined) : undefined
  const changeCandidates =
    item.type === 'issue' && CHANGEABLE_KINDS.has(item.issue.kind) && byProvider
      ? distinctCandidates(byProvider)
      : []
  const isChangeable = changeCandidates.length > 1

  return (
    <div className={`rounded-lg border border-l-4 border-gray-200 bg-white ${accent}`}>
      <div className="p-4">
        {item.type === 'issue' ? (
          <IssueBody issue={item.issue} />
        ) : (
          <SuggestionBody suggestion={item.suggestion} actionable={item.actionable} />
        )}
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-gray-100 px-4 py-2">
        {item.type === 'issue' && isChangeable ? (
          <>
            <span className="mr-auto text-xs text-gray-400">Resolve by setting the value:</span>
            {changeCandidates.map(({ value, providers }) => (
              <button
                key={value}
                onClick={() => onChangeIssue(item.issue, value)}
                className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-2.5 py-1.5 text-xs hover:border-[#1e2143]/40 hover:bg-[#1e2143]/5"
              >
                <span className="text-gray-400">
                  {providers.map((p) => PROVIDER_LABEL[p as ProviderName] ?? p).join(', ')}:
                </span>
                <span className="font-medium text-gray-700">{formatCandidateValue(value)}</span>
              </button>
            ))}
          </>
        ) : (
          <>
            {item.type === 'issue' ? (
              <button onClick={() => onTriage({ kind: 'acknowledged' })} className={PRIMARY_BTN}>
                Acknowledge
              </button>
            ) : item.actionable ? (
              <button onClick={() => onTriage({ kind: 'applied' })} className={PRIMARY_BTN}>
                <Check className="size-3.5" /> Apply suggestion
              </button>
            ) : null}
            <button onClick={() => onTriage({ kind: 'dismissed' })} className={SECONDARY_BTN}>
              Dismiss
            </button>
          </>
        )}
      </div>
    </div>
  )
}

const PRIMARY_BTN =
  'inline-flex items-center gap-1 rounded-md bg-[#1e2143] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#2a2e57]'
const SECONDARY_BTN =
  'inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50'

function CardHead({ name, email, right }: { name: string; email: string; right: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate font-medium text-gray-900">{name}</div>
        <div className="truncate text-xs text-gray-500">{email}</div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">{right}</div>
    </div>
  )
}

/** Distinct values among a disagreement's per-provider evidence, with which provider(s)
 *  reported each — drives the "change it" chips below. */
function distinctCandidates(byProvider: Record<string, unknown>): { value: string; providers: string[] }[] {
  const map = new Map<string, string[]>()
  for (const [provider, value] of Object.entries(byProvider)) {
    const key = String(value)
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(provider)
  }
  return [...map.entries()].map(([value, providers]) => ({ value, providers }))
}

function formatCandidateValue(value: string): string {
  if (/^\d+(\.\d+)?$/.test(value)) {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(value))
  }
  return value
}

/** AI Root-Cause Analysis. Collapsed by default; the fetch is gated on
 *  expanding, so we only spend an LLM call when a reviewer actually asks why. */
function RootCausePanel({ issueId }: { issueId: string }) {
  const [open, setOpen] = useState(false)
  const query = useQuery({
    queryKey: ['issue-root-cause', issueId],
    queryFn: () => fetchIssueRootCause(issueId),
    enabled: open,
    staleTime: Infinity,
  })

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-[#1e2143] hover:text-[#2a2e57]"
      >
        <Sparkles className="size-3.5" />
        {open ? 'Hide likely cause' : 'Explain likely cause'}
      </button>
      {open && (
        <div className="mt-1.5 rounded-md border border-[#1e2143]/10 bg-[#1e2143]/5 px-3 py-2 text-sm text-gray-700">
          {query.isPending ? (
            <span className="inline-flex items-center gap-2 text-gray-500">
              <Loader2 className="size-3.5 animate-spin" /> Analyzing…
            </span>
          ) : query.isError ? (
            <span className="text-gray-500">Couldn't load the analysis.</span>
          ) : query.data?.root_cause ? (
            <p className="leading-relaxed">{query.data.root_cause}</p>
          ) : (
            <span className="text-gray-500">{query.data?.note ?? 'No analysis available.'}</span>
          )}
        </div>
      )}
    </div>
  )
}

function IssueBody({ issue }: { issue: Issue }) {
  const [open, setOpen] = useState(false)
  const hasEvidence = issue.evidence && Object.keys(issue.evidence).length > 0

  return (
    <div>
      <CardHead
        name={issue.employee_name}
        email={issue.employee_email}
        right={
          <>
            {issue.is_new && <span className={NEW_BADGE_CLASS}>New</span>}
            <span
              className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${SEVERITY_BADGE_STYLE[issue.severity]}`}
            >
              {SEVERITY_LABEL[issue.severity]}
            </span>
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600 ring-1 ring-inset ring-gray-200">
              {ISSUE_KIND_LABEL[issue.kind] ?? issue.kind}
            </span>
          </>
        }
      />
      <p className="mt-2 text-sm text-gray-700">{issue.summary}</p>

      <RootCausePanel issueId={issue.id} />

      {hasEvidence && (
        <div className="mt-2">
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-800"
          >
            <ChevronDown className={`size-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
            Evidence
          </button>
          {open && <Evidence evidence={issue.evidence} />}
        </div>
      )}
    </div>
  )
}

function SuggestionBody({ suggestion, actionable }: { suggestion: ConflictSuggestion; actionable: boolean }) {
  return (
    <div>
      <CardHead
        name={suggestion.employee_name}
        email={suggestion.employee_email}
        right={
          <>
            {suggestion.is_new && <span className={NEW_BADGE_CLASS}>New</span>}
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600 ring-1 ring-inset ring-gray-200">
              {FIELD_LABEL[suggestion.field] ?? suggestion.field}
            </span>
            {actionable ? (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
                Change recommended
              </span>
            ) : (
              <span className="rounded-full bg-gray-50 px-2 py-0.5 text-[11px] font-medium text-gray-500 ring-1 ring-inset ring-gray-200">
                Already aligned
              </span>
            )}
          </>
        }
      />

      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {suggestion.candidates.map((c) => {
          const isSuggested = c.value === suggestion.suggested
          return (
            <span
              key={`${c.provider}-${c.value}`}
              className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs ${
                isSuggested ? 'border-green-300 bg-green-50/60' : 'border-gray-200'
              }`}
            >
              <ProviderTag provider={c.provider} />
              <span className="text-gray-700">{c.value}</span>
              {isSuggested && <Check className="size-3 text-green-600" />}
            </span>
          )
        })}
      </div>

      <p className="mt-2.5 text-sm text-gray-700">
        {actionable ? (
          <>
            Current <Token>{suggestion.current}</Token>{' '}
            <span className="text-gray-400">→</span> suggested <Token tone="good">{suggestion.suggested}</Token>
          </>
        ) : (
          <>
            Canonical value <Token>{suggestion.current}</Token> already matches the recommendation.
          </>
        )}
      </p>
      <p className="mt-1 text-xs text-gray-500">{suggestion.reason}</p>
    </div>
  )
}

function Token({ children, tone }: { children: React.ReactNode; tone?: 'good' }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 font-mono text-xs ${
        tone === 'good' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'
      }`}
    >
      {children}
    </span>
  )
}

// Generic evidence renderer — handles the per-provider maps that issues attach.
const PROVIDERS: ReadonlySet<string> = new Set(['atlas', 'beacon', 'cobalt'])

function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  return (
    <dl className="mt-2 space-y-1.5 rounded-md bg-gray-50 p-3 text-xs">
      {Object.entries(evidence).map(([key, value]) => (
        <div key={key} className="grid grid-cols-[7rem_1fr] gap-2">
          <dt className="text-gray-400">{key.replace(/_/g, ' ')}</dt>
          <dd className="min-w-0">
            <EvidenceValue value={value} />
          </dd>
        </div>
      ))}
    </dl>
  )
}

function EvidenceValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-gray-400">—</span>
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    return (
      <div className="space-y-0.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex flex-wrap items-center gap-1.5">
            {PROVIDERS.has(k) ? (
              <ProviderTag provider={k as ProviderName} />
            ) : (
              <span className="text-gray-400">{k}:</span>
            )}
            <span className="font-mono text-gray-700">
              {typeof v === 'object' ? JSON.stringify(v) : String(v)}
            </span>
          </div>
        ))}
      </div>
    )
  }
  return <span className="font-mono text-gray-700">{String(value)}</span>
}

const TRIAGE_LABEL: Record<Triage['kind'], string> = {
  applied: 'Applied',
  acknowledged: 'Acknowledged',
  dismissed: 'Dismissed',
  changed: 'Changed',
}

function ResolvedStrip({ item, status, onUndo }: { item: Item; status: Triage; onUndo: () => void }) {
  const what =
    item.type === 'issue'
      ? ISSUE_KIND_LABEL[item.issue.kind] ?? item.issue.kind
      : `${FIELD_LABEL[item.suggestion.field] ?? item.suggestion.field} suggestion`
  const label = status.kind === 'changed' ? `Changed to ${formatCandidateValue(status.value)}` : TRIAGE_LABEL[status.kind]
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-gray-100 bg-gray-50/60 px-3 py-1.5 text-sm">
      <div className="flex min-w-0 items-center gap-2 text-gray-500">
        {status.kind === 'dismissed' ? (
          <X className="size-3.5 shrink-0 text-gray-400" />
        ) : (
          <Check className="size-3.5 shrink-0 text-green-600" />
        )}
        <span className="truncate">
          <span className="font-medium text-gray-700">{item.name}</span> · {what}
        </span>
        <span className="shrink-0 text-xs text-gray-400">{label}</span>
      </div>
      <button
        onClick={onUndo}
        className="-my-1 inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800"
      >
        <Undo2 className="size-3.5" /> Undo
      </button>
    </div>
  )
}

function ResolvedDuplicateStrip({
  candidate,
  decision,
  onUndo,
}: {
  candidate: MergeCandidate
  decision: Decision
  onUndo: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-gray-100 bg-gray-50/60 px-3 py-1.5 text-sm">
      <div className="flex min-w-0 items-center gap-2 text-gray-500">
        {decision === 'confirmed' ? (
          <Check className="size-3.5 shrink-0 text-green-600" />
        ) : (
          <X className="size-3.5 shrink-0 text-gray-400" />
        )}
        <span className="truncate">
          <span className="font-medium text-gray-700">{candidate.left.name}</span> ⟷{' '}
          <span className="font-medium text-gray-700">{candidate.right.name}</span>
        </span>
        <span className="shrink-0 text-xs text-gray-400">{decision === 'confirmed' ? 'Merged' : 'Rejected'}</span>
      </div>
      <button
        onClick={onUndo}
        className="-my-1 inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800"
      >
        <Undo2 className="size-3.5" /> Undo
      </button>
    </div>
  )
}

function InboxState({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-gray-200 py-16 text-sm text-gray-500">
      {icon}
      {children}
    </div>
  )
}
