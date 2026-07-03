// Types mirror the proxy's canonical model (see proxy/models.py) and the
// GET /employees response shape (see proxy/main.py).

export type ProviderName = 'atlas' | 'beacon' | 'cobalt'
export type EmploymentStatus = 'ACTIVE' | 'ON_LEAVE' | 'TERMINATED' | 'UNKNOWN'

export type SourceRef = {
  provider: ProviderName
  provider_id: string
  raw: unknown // the value BEFORE normalization (may be a primitive or a nested object)
  normalized: unknown // this provider's value AFTER normalization
}

export type FieldValue<T> = {
  value: T
  sources: SourceRef[]
}

// Mirrors proxy/issues.py (Issue) — deterministic data-quality findings.
export type IssueKind =
  | 'status_conflict'
  | 'salary_outlier'
  | 'salary_disagreement'
  | 'missing_data'
  | 'impossible_date'
export type Severity = 'high' | 'medium' | 'low'

export type Issue = {
  id: string
  canonical_id: string
  employee_name: string
  employee_email: string
  kind: IssueKind
  field: string | null
  severity: Severity
  summary: string
  evidence: Record<string, unknown>
  is_new: boolean
}

// Mirrors proxy/titles.py (CanonicalTitle) — normalized job-title taxonomy.
export type CanonicalTitle = {
  role: string
  family: string
  level: string
  source: 'ai' | 'fallback'
}

export type Employee = {
  canonical_id: string
  email: string
  name: FieldValue<string>
  title: FieldValue<string>
  department: FieldValue<string>
  salary_annual: FieldValue<string> // Decimal, serialized as a string e.g. "840000.00"
  currency: string | null
  hire_date: FieldValue<string> // ISO "YYYY-MM-DD"
  status: FieldValue<EmploymentStatus>
  providers: ProviderName[]
  provider_ids: Partial<Record<ProviderName, string>>
  conflicts: string[]
  // GET /employees embeds these per row (see proxy/main.py:list_employees).
  issues: Issue[]
  title_normalized: CanonicalTitle
}

export type ProviderFetchStatus = {
  provider: string
  ok: boolean
  count: number
  error: string | null
}

// A provider summary travels on every endpoint (partial + per-provider status).
type ProviderSummary = {
  partial: boolean
  providers: ProviderFetchStatus[]
}

export type EmployeesResponse = ProviderSummary & {
  employees: Employee[]
  count: number
}

export type IssuesResponse = ProviderSummary & {
  issues: Issue[]
  count: number
  by_kind: Record<string, number>
}

// Mirrors proxy/conflicts.py (ConflictSuggestion) — one per (employee, conflicting field).
export type CandidateValue = {
  provider: ProviderName
  value: string
}

export type ConflictSuggestion = {
  id: string
  canonical_id: string
  employee_name: string
  employee_email: string
  field: string
  candidates: CandidateValue[]
  current: string
  suggested: string
  reason: string
  is_new: boolean
}

export type ConflictsResponse = ProviderSummary & {
  conflicts: ConflictSuggestion[]
  count: number
  by_field: Record<string, number>
  changed_from_default: number
}

// Mirrors proxy/fuzzy.py (PersonRef / MergeCandidate) — probabilistic same-person pairs.
export type PersonRef = {
  canonical_id: string
  name: string
  email: string
  title: string
  department: string
  hire_date: string
  providers: ProviderName[]
}

export type MergeCandidate = {
  id: string
  left: PersonRef
  right: PersonRef
  score: number // deterministic confidence 0..1
  signals: Record<string, number> // per-field similarity breakdown
  is_new: boolean
}

export type MergeCandidatesResponse = ProviderSummary & {
  merge_candidates: MergeCandidate[]
  count: number
}

export const API_BASE_URL = 'http://localhost:8000'

async function getJson<T>(path: string, label: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`Failed to load ${label} (HTTP ${response.status})`)
  }
  return response.json()
}

export function fetchEmployees(): Promise<EmployeesResponse> {
  return getJson('/employees', 'employees')
}

export function fetchIssues(): Promise<IssuesResponse> {
  return getJson('/issues', 'issues')
}

export function fetchConflicts(): Promise<ConflictsResponse> {
  return getJson('/conflicts', 'conflicts')
}

export function fetchMergeCandidates(): Promise<MergeCandidatesResponse> {
  return getJson('/merge-candidates', 'merge candidates')
}

// GET /search?q= — the AI compiles a sentence into a structured filter (applied_filter)
// and returns the matching rows. We use it for the matched ids + the parsed filter; the
// full per-row data (issues, title) still comes from /employees.
export type SearchResponse = {
  query: string
  ai: boolean
  applied_filter: Record<string, unknown> | null
  count: number
  note?: string
  employees: { canonical_id: string }[]
  partial?: boolean
  providers?: ProviderFetchStatus[]
}

export function fetchSearch(q: string): Promise<SearchResponse> {
  return getJson(`/search?q=${encodeURIComponent(q)}`, 'search')
}

// GET /conflicts/bulk-filter?q= and /merge-candidates/bulk-filter?q= — same idea as
// /search (AI compiles free text into a small structured filter, applied
// deterministically) but for bulk-triage criteria. The server returns identifying keys
// only; the page already holds the full objects from /conflicts or /merge-candidates.
type BulkFilterResponse<TMatch> = {
  query: string
  ai: boolean
  applied_filter: Record<string, unknown> | null
  matched: TMatch[]
  count: number
  note?: string
}

export type ConflictBulkMatch = { canonical_id: string; field: string }
export type MergeBulkMatch = { left_id: string; right_id: string }

export function fetchConflictBulkFilter(q: string): Promise<BulkFilterResponse<ConflictBulkMatch>> {
  return getJson(`/conflicts/bulk-filter?q=${encodeURIComponent(q)}`, 'conflict bulk filter')
}

export function fetchMergeBulkFilter(q: string): Promise<BulkFilterResponse<MergeBulkMatch>> {
  return getJson(`/merge-candidates/bulk-filter?q=${encodeURIComponent(q)}`, 'merge bulk filter')
}

// --- Advisory AI features (see proxy/ai/*) ----------------------------------------
//
// Each lazy-fetched only when its UI opens. All degrade gracefully: when the proxy
// has no API key the payload is null and `note` explains that the AI layer is needed
// — the deterministic views (provenance, issue summaries, similarity breakdown) stand
// on their own without these.

// "What Happened to This Employee?" cross-provider narrative.
export type EmployeeSummaryResponse = { ai: boolean; summary: string | null; note: string | null }

export function fetchEmployeeSummary(canonicalId: string): Promise<EmployeeSummaryResponse> {
  return getJson(`/employees/${encodeURIComponent(canonicalId)}/summary`, 'employee summary')
}

// Root-cause explanation for one detected issue (id contains colons).
export type IssueRootCauseResponse = { ai: boolean; root_cause: string | null; note: string | null }

export function fetchIssueRootCause(issueId: string): Promise<IssueRootCauseResponse> {
  return getJson(`/issues/root-cause?id=${encodeURIComponent(issueId)}`, 'root-cause analysis')
}

// Merge simulation: predicted effects + risks for one candidate pair.
export type MergeEffect = { label: string; ok: boolean }
export type MergeRisk = { area: string; note: string }
export type MergeSimulation = { summary: string; effects: MergeEffect[]; risks: MergeRisk[] }
export type MergeSimulationResponse = { ai: boolean; simulation: MergeSimulation | null; note: string | null }

export function fetchMergeSimulation(candidateId: string): Promise<MergeSimulationResponse> {
  return getJson(`/merge-candidates/simulate?id=${encodeURIComponent(candidateId)}`, 'merge simulation')
}

// --- Self-healing schema mapping demo ---------------------------------------------
//
// Walks the fallback on a built-in "drifted" provider payload: the deterministic
// normalizer fails, the LLM infers a field map, and applying it yields a canonical
// Employee. inferred_mapping/healed_employee are null (with a note) when AI is off.

// Flat field map the LLM fills in (mirrors proxy/ai/schema_infer.py SchemaMapping).
export type SchemaMapping = Record<string, string>

// One drifted record run through the self-healing fallback (shared by the Schema Lab
// single-payload demo and the Recovered tab's list).
export type HealedRecord = {
  provider: ProviderName
  drifted_raw: Record<string, unknown>
  deterministic_error: string | null
  inferred_mapping: SchemaMapping | null
  recovered_employee: Employee | null
}

export type SchemaDemoResponse = HealedRecord & { ai: boolean; note: string | null }

export function fetchSchemaDemo(): Promise<SchemaDemoResponse> {
  return getJson('/schema-mapping/demo', 'schema mapping demo')
}

// GET /self-heal/recovered — employees recovered from forced-drift payloads, each with
// the evidence (drifted raw + deterministic error + inferred mapping).
export type RecoveredResponse = {
  ai: boolean
  records: HealedRecord[]
  note: string | null
}

export function fetchRecovered(): Promise<RecoveredResponse> {
  return getJson('/self-heal/recovered', 'recovered employees')
}
