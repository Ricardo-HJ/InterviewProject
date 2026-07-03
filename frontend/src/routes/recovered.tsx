import { useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, ChevronDown, HeartPulse, Loader2, Sparkles, XCircle } from 'lucide-react'
import { fetchRecovered } from '#/lib/api'
import type { HealedRecord } from '#/lib/api'
import { HealedEmployee, MappingTable } from '#/components/SchemaHealing'
import { PROVIDER_BADGE_STYLE, PROVIDER_LABEL } from '#/lib/display'

export const Route = createFileRoute('/recovered')({ component: RecoveredPage })

function RecoveredPage() {
  const query = useQuery({ queryKey: ['recovered'], queryFn: fetchRecovered, staleTime: Infinity })
  const records = query.data?.records ?? []
  const anyRecovered = records.some((r) => r.recovered_employee)

  return (
    <div className="mx-auto max-w-5xl px-8 pb-16 pt-8">
      <header>
        <h1 className="flex items-center gap-2 text-3xl font-semibold text-black">
          <HeartPulse className="size-7 text-[#1e2143]" />
          Recovered
        </h1>
        <p className="mt-1.5 text-sm text-[#6e6e6e]">
          These employees arrived in a shape our hand-written normalizers don't understand —
          a provider changed its fields. Instead of dropping them, self-healing infers the new
          field map and recovers them into proper canonical records. (The mocks never drift on
          their own, so these payloads are forced to demonstrate the live fallback.)
        </p>
      </header>

      {query.isPending && (
        <div className="mt-10 flex items-center justify-center gap-2 text-gray-500">
          <Loader2 className="size-5 animate-spin" /> Recovering…
        </div>
      )}
      {query.isError && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="size-5" /> Couldn't reach the proxy on :8000.
        </div>
      )}

      {query.data && !anyRecovered && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Sparkles className="size-5 shrink-0" />
          {query.data.note ?? 'Nothing to recover.'} The drifted payloads and the errors they
          cause are shown below — configure the AI layer to heal them.
        </div>
      )}

      {records.length > 0 && (
        <div className="mt-6 space-y-4">
          {records.map((record, i) => (
            <RecoveredCard key={`${record.provider}-${i}`} record={record} />
          ))}
        </div>
      )}
    </div>
  )
}

function RecoveredCard({ record }: { record: HealedRecord }) {
  const [showEvidence, setShowEvidence] = useState(false)
  const recovered = record.recovered_employee

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ${PROVIDER_BADGE_STYLE[record.provider]}`}
        >
          {PROVIDER_LABEL[record.provider]}
        </span>
        {recovered && (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-700 ring-1 ring-inset ring-green-200">
            <HeartPulse className="size-3" /> Recovered via self-healing
          </span>
        )}
        {recovered && <span className="text-sm font-medium text-gray-900">{String(recovered.name.value)}</span>}
      </div>

      {recovered ? (
        <HealedEmployee employee={recovered} />
      ) : (
        <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <Sparkles className="size-4 shrink-0" /> Not recovered — the AI layer is needed to infer the mapping.
        </div>
      )}

      <button
        onClick={() => setShowEvidence((v) => !v)}
        className="mt-3 flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-800"
      >
        <ChevronDown className={`size-3.5 transition-transform ${showEvidence ? 'rotate-180' : ''}`} />
        Evidence
      </button>

      {showEvidence && (
        <div className="mt-2 space-y-3">
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">Drifted payload</p>
            <pre className="overflow-x-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
              {JSON.stringify(record.drifted_raw, null, 2)}
            </pre>
          </div>

          {record.deterministic_error && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
                Hand-written normalizer
              </p>
              <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 font-mono text-sm text-red-700">
                <XCircle className="size-4 shrink-0" />
                {record.deterministic_error}
              </div>
            </div>
          )}

          {record.inferred_mapping && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">Inferred mapping</p>
              <MappingTable mapping={record.inferred_mapping} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
