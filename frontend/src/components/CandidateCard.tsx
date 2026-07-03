import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, GitMerge, Loader2, Sparkles, X } from 'lucide-react'
import type { MergeCandidate, PersonRef, ProviderName } from '#/lib/api'
import { fetchMergeSimulation } from '#/lib/api'
import { NEW_BADGE_CLASS, PROVIDER_BADGE_STYLE, PROVIDER_LABEL } from '#/lib/display'

export type Decision = 'confirmed' | 'rejected'

export function candidateId(c: MergeCandidate): string {
  return `${c.left.canonical_id}|${c.right.canonical_id}`
}

// Field rows + their scoring weight — mirrors WEIGHTS in proxy/fuzzy.py, shown so the
// confidence number is transparent rather than a black box.
const SIGNALS: { key: keyof PersonRef; label: string; weight: number }[] = [
  { key: 'name', label: 'Name', weight: 0.25 },
  { key: 'email', label: 'Email', weight: 0.15 },
  { key: 'title', label: 'Title', weight: 0.15 },
  { key: 'department', label: 'Department', weight: 0.15 },
  { key: 'hire_date', label: 'Hire date', weight: 0.3 },
]

type Tone = 'green' | 'amber' | 'gray'
const BAR_FILL: Record<Tone, string> = { green: 'bg-green-500', amber: 'bg-amber-500', gray: 'bg-gray-400' }
const CONF_PILL: Record<Tone, string> = {
  green: 'bg-green-50 text-green-700 ring-green-200',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  gray: 'bg-gray-100 text-gray-600 ring-gray-200',
}
const signalTone = (v: number): Tone => (v >= 0.85 ? 'green' : v >= 0.6 ? 'amber' : 'gray')

function confidence(score: number): { label: string; tone: Tone } {
  if (score >= 0.9) return { label: 'High confidence', tone: 'green' }
  if (score >= 0.85) return { label: 'Medium confidence', tone: 'amber' }
  return { label: 'Possible match', tone: 'gray' }
}

function ProviderTags({ providers }: { providers: ProviderName[] }) {
  return (
    <span className="inline-flex gap-1">
      {providers.map((p) => (
        <span
          key={p}
          className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ${PROVIDER_BADGE_STYLE[p]}`}
        >
          {PROVIDER_LABEL[p]}
        </span>
      ))}
    </span>
  )
}

/** AI Merge Simulator. Collapsed until the reviewer asks; the LLM call
 *  is gated on expanding so we only simulate the pairs someone actually inspects. */
function MergeSimPanel({ id }: { id: string }) {
  const [open, setOpen] = useState(false)
  const query = useQuery({
    queryKey: ['merge-simulation', id],
    queryFn: () => fetchMergeSimulation(id),
    enabled: open,
    staleTime: Infinity,
  })
  const sim = query.data?.simulation

  return (
    <div className="border-t border-gray-100 px-4 py-2.5">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-[#1e2143] hover:text-[#2a2e57]"
      >
        <Sparkles className="size-3.5" />
        {open ? 'Hide merge simulation' : 'Simulate merge'}
      </button>

      {open && (
        <div className="mt-2 rounded-md border border-[#1e2143]/10 bg-[#1e2143]/5 px-3 py-2.5 text-sm">
          {query.isPending ? (
            <span className="inline-flex items-center gap-2 text-gray-500">
              <Loader2 className="size-3.5 animate-spin" /> Predicting impact…
            </span>
          ) : query.isError ? (
            <span className="text-gray-500">Couldn't load the simulation.</span>
          ) : sim ? (
            <div className="space-y-2.5">
              <p className="leading-relaxed text-gray-700">{sim.summary}</p>
              {sim.effects.length > 0 && (
                <ul className="space-y-1">
                  {sim.effects.map((e, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-gray-700">
                      {e.ok ? (
                        <Check className="mt-0.5 size-3.5 shrink-0 text-green-600" />
                      ) : (
                        <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
                      )}
                      <span>{e.label}</span>
                    </li>
                  ))}
                </ul>
              )}
              {sim.risks.length > 0 && (
                <div className="space-y-1 border-t border-[#1e2143]/10 pt-2">
                  {sim.risks.map((r, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-gray-700">
                      <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
                      <span>
                        <span className="font-medium">{r.area}:</span> {r.note}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <span className="text-gray-500">{query.data?.note ?? 'No simulation available.'}</span>
          )}
        </div>
      )}
    </div>
  )
}

export function CandidateCard({
  candidate,
  onDecide,
}: {
  candidate: MergeCandidate
  onDecide: (v: Decision) => void
}) {
  const { left, right, score, signals, is_new } = candidate
  const conf = confidence(score)
  const pct = Math.round(score * 100)

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center justify-between gap-4 border-b border-gray-100 bg-gray-50/60 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="text-xl font-semibold tabular-nums text-gray-900">{pct}%</div>
          <div className="w-28">
            <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
              <div className={`h-full rounded-full ${BAR_FILL[conf.tone]}`} style={{ width: `${pct}%` }} />
            </div>
            <span
              className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${CONF_PILL[conf.tone]}`}
            >
              {conf.label}
            </span>
          </div>
          {is_new && <span className={NEW_BADGE_CLASS}>New</span>}
        </div>
        <div className="text-right text-xs text-gray-400">
          Same person?
          <div className="mt-0.5 font-mono">
            {left.canonical_id.slice(0, 6)} ⟷ {right.canonical_id.slice(0, 6)}
          </div>
        </div>
      </div>

      {/* Field-by-field comparison; the Match column shows each signal's similarity. */}
      <div className="px-4 py-3">
        <div className="grid grid-cols-[6.5rem_1fr_1fr_7rem] items-center gap-x-3 border-b border-gray-100 pb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
          <span>Field</span>
          <ProviderTags providers={left.providers} />
          <ProviderTags providers={right.providers} />
          <span className="text-right">Match</span>
        </div>
        {SIGNALS.map(({ key, label, weight }) => {
          const lv = String(left[key])
          const rv = String(right[key])
          const sim = signals[key] ?? 0
          const differs = lv !== rv
          return (
            <div
              key={key}
              className="grid grid-cols-[6.5rem_1fr_1fr_7rem] items-center gap-x-3 border-b border-gray-50 py-1.5 text-sm last:border-0"
            >
              <span className="text-xs text-gray-500">
                {label}
                <span className="ml-1 text-gray-300">·{Math.round(weight * 100)}%</span>
              </span>
              <span className={`min-w-0 wrap-break-word ${differs ? 'text-gray-900' : 'text-gray-500'}`}>{lv}</span>
              <span className={`min-w-0 wrap-break-word ${differs ? 'text-gray-900' : 'text-gray-500'}`}>{rv}</span>
              <span className="flex items-center justify-end gap-1.5">
                <span className="h-1.5 w-12 overflow-hidden rounded-full bg-gray-200">
                  <span
                    className={`block h-full rounded-full ${BAR_FILL[signalTone(sim)]}`}
                    style={{ width: `${Math.round(sim * 100)}%` }}
                  />
                </span>
                <span className="w-8 text-right text-xs tabular-nums text-gray-500">{Math.round(sim * 100)}%</span>
              </span>
            </div>
          )
        })}
      </div>

      <MergeSimPanel id={candidateId(candidate)} />

      <div className="flex items-center justify-end gap-2 border-t border-gray-100 px-4 py-2.5">
        <button
          onClick={() => onDecide('rejected')}
          className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
        >
          <X className="size-3.5" /> Not the same
        </button>
        <button
          onClick={() => onDecide('confirmed')}
          className="inline-flex items-center gap-1 rounded-md bg-[#1e2143] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#2a2e57]"
        >
          <GitMerge className="size-3.5" /> Confirm merge
        </button>
      </div>
    </div>
  )
}
