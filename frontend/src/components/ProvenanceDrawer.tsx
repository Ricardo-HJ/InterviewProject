import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, ChevronDown, Layers, Loader2, Sparkles, X } from 'lucide-react'
import type { Employee, EmploymentStatus, FieldValue, Issue } from '#/lib/api'
import { fetchEmployeeSummary } from '#/lib/api'
import {
  PROVIDER_BADGE_STYLE,
  PROVIDER_LABEL,
  SEVERITY_BADGE_STYLE,
  SEVERITY_LABEL,
  STATUS_BADGE_STYLE,
  STATUS_LABEL,
  formatSalary,
} from '#/lib/display'

// The drawer is a dark-glass overlay: a translucent deep-navy panel with backdrop blur.
// Inner surfaces are subtle white tints (bg-white/5) over it; the shared pastel provider /
// severity / status chips stay as light accent pops, which read well on the dark panel.

// The canonical fields shown in the drawer, in display order. Each maps to a
// FieldValue<...> on Employee that carries the chosen value + every source.
type FieldKey = 'name' | 'title' | 'department' | 'salary_annual' | 'hire_date' | 'status'

const FIELD_ROWS: { key: FieldKey; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'title', label: 'Title' },
  { key: 'department', label: 'Department' },
  { key: 'salary_annual', label: 'Annual salary' },
  { key: 'hire_date', label: 'Hire date' },
  { key: 'status', label: 'Status' },
]

/** Human-readable form of a field's chosen canonical value. */
function canonicalDisplay(employee: Employee, key: FieldKey): string {
  if (key === 'salary_annual') return formatSalary(employee.salary_annual.value, employee.currency)
  if (key === 'status') return STATUS_LABEL[employee.status.value]
  return String((employee[key] as FieldValue<unknown>).value)
}

/** Render a raw upstream value faithfully — primitives inline, objects as key/value lines. */
function RawValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-white/35">—</span>
  if (typeof value === 'object') {
    return (
      <div className="space-y-0.5">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k}>
            <span className="text-white/40">{k}:</span> <span className="text-gray-200">{String(v)}</span>
          </div>
        ))}
      </div>
    )
  }
  return <span className="text-gray-200">{String(value)}</span>
}

function ProviderBadge({ provider }: { provider: Employee['providers'][number] }) {
  return (
    <span
      className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ${PROVIDER_BADGE_STYLE[provider]}`}
    >
      {PROVIDER_LABEL[provider]}
    </span>
  )
}

function FieldProvenance({ employee, fieldKey, label }: { employee: Employee; fieldKey: FieldKey; label: string }) {
  const field = employee[fieldKey] as FieldValue<unknown>
  const isConflict = employee.conflicts.includes(fieldKey)
  const canonical = canonicalDisplay(employee, fieldKey)

  return (
    <div className="rounded-lg border border-white/10 bg-white/5">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-white/50">{label}</span>
          {isConflict && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-400/15 px-2 py-0.5 text-[11px] font-medium text-amber-200 ring-1 ring-inset ring-amber-400/30">
              <AlertTriangle className="size-3" />
              Sources differ
            </span>
          )}
        </div>
        <span className="truncate text-right text-sm font-medium text-white">{canonical}</span>
      </div>

      <div className="space-y-2 p-3">
        {field.sources.map((source) => {
          const matches = String(source.normalized) === String(field.value)
          const tone = !isConflict
            ? 'border-white/10 bg-white/[0.03]'
            : matches
              ? 'border-emerald-400/30 bg-emerald-400/10'
              : 'border-amber-400/30 bg-amber-400/10'
          return (
            <div key={`${source.provider}-${source.provider_id}`} className={`rounded-md border px-3 py-2 ${tone}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <ProviderBadge provider={source.provider} />
                  <span className="font-mono text-xs text-white/40">{source.provider_id}</span>
                </div>
                {isConflict &&
                  (matches ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-300">
                      <Check className="size-3" /> matches canonical
                    </span>
                  ) : (
                    <span className="text-[11px] font-medium text-amber-300">differs</span>
                  ))}
              </div>
              <dl className="mt-2 grid grid-cols-[5rem_1fr] gap-x-2 gap-y-1 text-xs">
                <dt className="text-white/40">raw</dt>
                <dd className="min-w-0 break-words font-mono">
                  <RawValue value={source.raw} />
                </dd>
                <dt className="text-white/40">normalized</dt>
                <dd className="min-w-0 break-words font-mono text-gray-200">
                  {source.normalized === null || source.normalized === undefined ? (
                    <span className="text-white/35">—</span>
                  ) : (
                    String(source.normalized)
                  )}
                </dd>
              </dl>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** AI "What Happened to This Employee?" summary. Lazy-loaded with the drawer;
 *  advisory only — degrades to a "needs AI" note rather than blocking the view. */
function AiSummarySection({ employee }: { employee: Employee }) {
  const query = useQuery({
    queryKey: ['employee-summary', employee.canonical_id],
    queryFn: () => fetchEmployeeSummary(employee.canonical_id),
    staleTime: Infinity, // advisory + stable per employee — cache it for the session
  })

  return (
    <section className="rounded-lg border border-white/10 bg-white/5 p-4">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
        <Sparkles className="size-4 text-indigo-300" />
        AI summary
      </h3>
      <div className="mt-2 text-sm text-gray-200">
        {query.isPending ? (
          <span className="inline-flex items-center gap-2 text-white/50">
            <Loader2 className="size-4 animate-spin" /> Summarizing across providers…
          </span>
        ) : query.isError ? (
          <span className="text-white/50">Couldn't load the AI summary.</span>
        ) : query.data?.summary ? (
          <p className="leading-relaxed">{query.data.summary}</p>
        ) : (
          <span className="text-white/50">{query.data?.note ?? 'No summary available.'}</span>
        )}
      </div>
    </section>
  )
}

function IssueCard({ issue }: { issue: Issue }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/5 px-3 py-2">
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${SEVERITY_BADGE_STYLE[issue.severity]}`}
        >
          {SEVERITY_LABEL[issue.severity]}
        </span>
        <span className="font-mono text-[11px] text-white/45">{issue.kind}</span>
      </div>
      <p className="mt-1.5 text-sm text-gray-200">{issue.summary}</p>
    </div>
  )
}

export function ProvenanceDrawer({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  // Mount → slide in on the next frame; lock body scroll; Escape closes.
  const [open, setOpen] = useState(false)
  // Field provenance is detailed — collapsed by default so the drawer stays scannable.
  const [showProvenance, setShowProvenance] = useState(false)
  useEffect(() => {
    setOpen(true)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

  const title = employee.title_normalized

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-label={`Provenance for ${employee.name.value}`}>
      <div
        className={`absolute inset-0 bg-gray-900/40 backdrop-blur-sm transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0'}`}
        onClick={onClose}
      />
      <aside
        className={`absolute right-0 top-0 flex h-full w-full max-w-xl flex-col border-l border-white/10 bg-[#1b1d38]/40 text-gray-100 shadow-2xl backdrop-blur-2xl transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-white">{employee.name.value}</h2>
            <p className="truncate text-sm text-white/55">{employee.email}</p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {employee.providers.map((provider) => (
                <ProviderBadge key={provider} provider={provider} />
              ))}
              <span
                className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS_BADGE_STYLE[employee.status.value as EmploymentStatus]}`}
              >
                {STATUS_LABEL[employee.status.value]}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 shrink-0 rounded-md p-1.5 text-white/50 hover:bg-white/10 hover:text-white"
          >
            <X className="size-5" />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <AiSummarySection employee={employee} />

          {employee.issues.length > 0 && (
            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <AlertTriangle className="size-4 text-amber-400" />
                Data-quality issues
              </h3>
              <div className="space-y-2">
                {employee.issues.map((issue) => (
                  <IssueCard key={issue.id} issue={issue} />
                ))}
              </div>
            </section>
          )}

          <section>
            <button
              onClick={() => setShowProvenance((v) => !v)}
              className="flex w-full items-center gap-2 text-sm font-semibold text-white"
            >
              <Layers className="size-4 text-white/45" />
              Field provenance
              <ChevronDown
                className={`ml-auto size-4 text-white/45 transition-transform ${showProvenance ? 'rotate-180' : ''}`}
              />
            </button>
            {showProvenance && (
              <>
                <p className="mb-3 mt-1 text-xs text-white/50">
                  Each field's canonical value and how every source contributed (raw → normalized).
                </p>
                <div className="space-y-3">
                  {FIELD_ROWS.map(({ key, label }) => (
                    <FieldProvenance key={key} employee={employee} fieldKey={key} label={label} />
                  ))}
                </div>
              </>
            )}
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-white">Normalized title</h3>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1.5 rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm">
              <Meta label="Role" value={title.role} />
              <Meta label="Family" value={title.family} />
              <Meta label="Level" value={title.level} />
              <span
                className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
                  title.source === 'ai'
                    ? 'bg-indigo-400/15 text-indigo-200 ring-indigo-400/30'
                    : 'bg-white/10 text-white/65 ring-white/15'
                }`}
              >
                {title.source === 'ai' ? 'AI-refined' : 'Rule-based'}
              </span>
            </div>
          </section>

          <p className="border-t border-white/10 pt-3 font-mono text-[11px] text-white/40">
            canonical_id: {employee.canonical_id}
          </p>
        </div>
      </aside>
    </div>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <span className="text-white/45">{label}:</span> <span className="font-medium text-gray-100">{value}</span>
    </span>
  )
}
