import { useState } from 'react'
import { Check, ChevronLeft, ChevronRight, Plus, X } from 'lucide-react'
import type { FacetOption } from '#/lib/facets'

// A single facet (multi-select checkbox list) the menu can drive.
export type FacetSpec = {
  kind: 'facet'
  key: string
  label: string
  options: FacetOption[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
}

// A numeric range (dual slider) the menu can drive. `value: null` = unset.
export type RangeSpec = {
  kind: 'range'
  key: string
  label: string
  min: number
  max: number
  step?: number
  value: [number, number] | null
  onChange: (next: [number, number] | null) => void
  format: (n: number) => string
}

export type FilterSpec = FacetSpec | RangeSpec

// Dual-range slider thumbs: two overlapping native range inputs, each capturing drags
// only on its own thumb (pointer-events trick) so the handles move independently.
const THUMB =
  'pointer-events-none absolute inset-y-0 w-full appearance-none bg-transparent ' +
  '[&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none ' +
  '[&::-webkit-slider-thumb]:size-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 ' +
  '[&::-webkit-slider-thumb]:border-[#1e2143] [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow ' +
  '[&::-webkit-slider-thumb]:cursor-pointer ' +
  '[&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:size-4 [&::-moz-range-thumb]:rounded-full ' +
  '[&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-[#1e2143] [&::-moz-range-thumb]:bg-white ' +
  '[&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:shadow'

type Pill = { id: string; label: string; remove: () => void }

function activeCount(spec: FilterSpec): number {
  return spec.kind === 'facet' ? spec.selected.size : spec.value ? 1 : 0
}

function pillsFor(filters: FilterSpec[]): Pill[] {
  const pills: Pill[] = []
  for (const f of filters) {
    if (f.kind === 'facet') {
      if (f.selected.size === 0) continue
      // One pill per column: collapse all selected values into a single chip.
      const labels = [...f.selected].map((v) => f.options.find((o) => o.value === v)?.label ?? v)
      const shown = labels.length <= 2 ? labels.join(', ') : `${labels[0]} +${labels.length - 1}`
      pills.push({
        id: f.key,
        label: `${f.label}: ${shown}`,
        remove: () => f.onChange(new Set()),
      })
    } else if (f.value) {
      pills.push({
        id: f.key,
        label: `${f.label}: ${f.format(f.value[0])}–${f.format(f.value[1])}`,
        remove: () => f.onChange(null),
      })
    }
  }
  return pills
}

/** A single "+ Filter" entry point: opens a dropdown of filter categories; picking one
 *  drills into its options; each selection surfaces as a removable pill alongside the
 *  button. Replaces the row of separate facet buttons so all filters share one consistent
 *  surface. */
export function FilterMenu({ filters }: { filters: FilterSpec[] }) {
  const [open, setOpen] = useState(false)
  const [activeKey, setActiveKey] = useState<string | null>(null)

  const pills = pillsFor(filters)
  const active = filters.find((f) => f.key === activeKey) ?? null

  const close = () => {
    setOpen(false)
    setActiveKey(null)
  }

  return (
    <>
      {pills.map((pill) => (
        <span
          key={pill.id}
          className="inline-flex items-center gap-1 rounded-full border border-[#ededed] bg-white px-2.5 py-1 text-xs text-gray-700 shadow-sm"
        >
          {pill.label}
          <button
            type="button"
            onClick={pill.remove}
            className="-mr-0.5 rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            aria-label={`Remove ${pill.label}`}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-full bg-[#1e2143] px-4 py-2 text-xs font-medium text-white shadow-[0px_5px_20px_0px_rgba(0,0,0,0.12)] hover:bg-[#2a2e57]"
        >
          <Plus className="size-3.5" />
          Filter
        </button>

        {open && (
          <>
            <div className="fixed inset-0 z-10" onClick={close} />
            <div className="absolute left-0 top-full z-20 mt-1.5 w-60 overflow-hidden rounded-md border border-white/60 bg-white/85 py-1.5 shadow-[0px_8px_30px_rgba(0,0,0,0.12)] backdrop-blur-xl">
              {active === null ? (
                // Level 1 — category list.
                <>
                  <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                    Add filter
                  </p>
                  {filters.map((f) => {
                    const count = activeCount(f)
                    return (
                      <button
                        key={f.key}
                        type="button"
                        onClick={() => setActiveKey(f.key)}
                        className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-50"
                      >
                        <span>{f.label}</span>
                        <span className="flex items-center gap-1.5 text-gray-400">
                          {count > 0 && (
                            <span className="rounded-full bg-[#1e2143]/10 px-1.5 text-xs font-medium text-[#1e2143]">
                              {count}
                            </span>
                          )}
                          <ChevronRight className="size-3.5" />
                        </span>
                      </button>
                    )
                  })}
                </>
              ) : (
                // Level 2 — the chosen category's controls.
                <>
                  <div className="flex items-center justify-between px-2 pb-1.5">
                    <button
                      type="button"
                      onClick={() => setActiveKey(null)}
                      className="flex items-center gap-1 rounded px-1 py-0.5 text-xs font-medium text-gray-500 hover:text-gray-800"
                    >
                      <ChevronLeft className="size-3.5" /> {active.label}
                    </button>
                    {activeCount(active) > 0 && (
                      <button
                        type="button"
                        onClick={() =>
                          active.kind === 'facet' ? active.onChange(new Set()) : active.onChange(null)
                        }
                        className="px-1 text-xs font-medium text-[#1e2143] hover:opacity-70"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  {active.kind === 'facet' ? (
                    <FacetOptions spec={active} />
                  ) : (
                    <RangeOptions spec={active} />
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}

function FacetOptions({ spec }: { spec: FacetSpec }) {
  const toggle = (value: string) => {
    const next = new Set(spec.selected)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    spec.onChange(next)
  }
  return (
    <div className="max-h-64 overflow-y-auto">
      {spec.options.length === 0 ? (
        <p className="px-3 py-1.5 text-sm text-gray-400">No options</p>
      ) : (
        spec.options.map((option) => {
          const checked = spec.selected.has(option.value)
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => toggle(option.value)}
              className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm hover:bg-gray-50"
            >
              <span className="flex items-center gap-2">
                <span
                  className={`flex size-4 items-center justify-center rounded border ${
                    checked ? 'border-[#1e2143] bg-[#1e2143] text-white' : 'border-gray-300'
                  }`}
                >
                  {checked && <Check className="size-3" strokeWidth={3} />}
                </span>
                <span className="text-gray-700">{option.label}</span>
              </span>
              <span className="text-xs text-gray-400">{option.count}</span>
            </button>
          )
        })
      )}
    </div>
  )
}

function RangeOptions({ spec }: { spec: RangeSpec }) {
  const { min, max, step = 1, value, onChange, format } = spec
  const [lo, hi] = value ?? [min, max]
  const pct = (v: number) => (max === min ? 0 : ((v - min) / (max - min)) * 100)
  return (
    <div className="px-3 pb-2 pt-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{format(lo)}</span>
        <span>{format(hi)}</span>
      </div>
      <div className="relative mt-2 h-4">
        <div className="absolute top-1/2 h-1.5 w-full -translate-y-1/2 rounded-full bg-gray-200" />
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-[#1e2143]"
          style={{ left: `${pct(lo)}%`, right: `${100 - pct(hi)}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={lo}
          onChange={(e) => onChange([Math.min(Number(e.target.value), hi), hi])}
          className={THUMB}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={hi}
          onChange={(e) => onChange([lo, Math.max(Number(e.target.value), lo)])}
          className={THUMB}
        />
      </div>
    </div>
  )
}
