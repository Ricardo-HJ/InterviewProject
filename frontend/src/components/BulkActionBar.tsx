import { useState } from 'react'
import { AlertTriangle, Check, Loader2, Sparkles } from 'lucide-react'

type BulkFilterResult<T> = {
  ai: boolean
  applied_filter: Record<string, unknown> | null
  matched: T[]
  count: number
  note?: string
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  return String(value)
}

/** AI bulk-triage command bar: type a criterion, preview which pending items match,
 *  then one click applies it to all of them. Generic over the page's match-row shape
 *  (T) so the same preview/confirm machinery serves both the Inbox and Merge review —
 *  only `fetchFilter` (which endpoint) and `matchedIds` (how to read the match rows
 *  back into this page's own item ids) differ per page. */
export function BulkActionBar<T>({
  placeholder,
  fetchFilter,
  matchedIds,
  pendingIds,
  onApply,
  filterLabel,
}: {
  placeholder: string
  fetchFilter: (q: string) => Promise<BulkFilterResult<T>>
  matchedIds: (matched: T[]) => Set<string>
  pendingIds: Set<string>
  onApply: (ids: Set<string>) => void
  filterLabel?: (key: string, value: unknown) => string
}) {
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'preview' | 'error'>('idle')
  const [result, setResult] = useState<BulkFilterResult<T> | null>(null)

  const reset = () => {
    setStatus('idle')
    setResult(null)
    setInput('')
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!input.trim()) return
    setStatus('loading')
    try {
      const data = await fetchFilter(input.trim())
      setResult(data)
      setStatus('preview')
    } catch {
      setResult(null)
      setStatus('error')
    }
  }

  const matchedPending = result
    ? new Set([...matchedIds(result.matched)].filter((id) => pendingIds.has(id)))
    : new Set<string>()

  const apply = () => {
    onApply(matchedPending)
    reset()
  }

  return (
    <div>
      <form onSubmit={submit} className="flex gap-2">
        <div className="relative flex-1">
          <Sparkles className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#1e2143]" />
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={placeholder}
            disabled={status === 'preview'}
            className="w-full rounded-md border border-[#ededed] bg-white py-2 pl-9 pr-3 text-xs text-gray-800 shadow-[0px_3px_3.25px_rgba(0,0,0,0.08)] placeholder:text-[#bcbcbc] focus:border-[#1e2143]/40 focus:outline-none disabled:bg-gray-50 disabled:text-gray-400"
          />
        </div>
        {status === 'preview' ? (
          <button
            type="button"
            onClick={reset}
            className="shrink-0 rounded-full border border-[#ededed] bg-white px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            Cancel
          </button>
        ) : (
          <button
            type="submit"
            disabled={status === 'loading' || !input.trim()}
            className="shrink-0 rounded-full bg-[#1e2143] px-5 py-2 text-xs font-medium text-white shadow-[0px_5px_20px_0px_rgba(0,0,0,0.12)] hover:bg-[#2a2e57] disabled:opacity-50"
          >
            {status === 'loading' ? <Loader2 className="size-4 animate-spin" /> : 'Find matches'}
          </button>
        )}
      </form>

      {status === 'error' && (
        <p className="mt-2 text-sm text-red-600">Couldn't run that. Is the proxy on :8000?</p>
      )}

      {status === 'preview' &&
        result &&
        (result.applied_filter ? (
          <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-[#1e2143]/25 bg-[#1e2143]/5 px-3 py-2">
            <span className="text-xs text-[#2a2e57]">Interpreted as</span>
            {Object.entries(result.applied_filter).map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-xs font-medium text-[#2a2e57] ring-1 ring-inset ring-[#1e2143]/25"
              >
                {filterLabel ? filterLabel(key, value) : `${key}: ${formatValue(value)}`}
              </span>
            ))}
            <span className="text-xs text-[#1e2143]">
              · {matchedPending.size} of {pendingIds.size} pending match
            </span>
            <button
              type="button"
              onClick={apply}
              disabled={matchedPending.size === 0}
              className="ml-auto inline-flex items-center gap-1 rounded-md bg-[#1e2143] px-3 py-1 text-xs font-medium text-white hover:bg-[#2a2e57] disabled:opacity-40"
            >
              <Check className="size-3.5" /> Apply to {matchedPending.size}
            </button>
          </div>
        ) : (
          <p className="mt-2 inline-flex items-center gap-2 text-sm text-amber-700">
            <AlertTriangle className="size-4" />
            {result.note ?? 'Could not interpret that.'}
          </p>
        ))}
    </div>
  )
}
