import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Loader2, Sparkles, Wand2, XCircle } from 'lucide-react'
import { fetchSchemaDemo } from '#/lib/api'
import { HealedEmployee, MappingTable } from '#/components/SchemaHealing'

export const Route = createFileRoute('/schema')({ component: SchemaLabPage })

function SchemaLabPage() {
  const query = useQuery({ queryKey: ['schema-demo'], queryFn: fetchSchemaDemo, staleTime: Infinity })

  return (
    <div className="mx-auto max-w-5xl px-8 pb-16 pt-8">
      <header>
        <h1 className="flex items-center gap-2 text-3xl font-semibold text-black">
          <Wand2 className="size-7 text-[#1e2143]" />
          Schema Lab
        </h1>
        <p className="mt-1.5 text-sm text-[#6e6e6e]">
          Self-healing schema mapping. When a provider changes its shape, the hand-written
          normalizer fails — instead of dropping those records, an LLM infers the new field
          map from a sample and the deterministic pipeline keeps going. Below is a Beacon
          payload with every field renamed, healed end-to-end.
        </p>
      </header>

      {query.isPending && (
        <div className="mt-10 flex items-center justify-center gap-2 text-gray-500">
          <Loader2 className="size-5 animate-spin" /> Running the demo…
        </div>
      )}
      {query.isError && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="size-5" /> Couldn't reach the proxy on :8000.
        </div>
      )}

      {query.data && (
        <div className="mt-6 space-y-5">
          <Stage n={1} title="A drifted provider payload">
            <p className="mb-2 text-sm text-gray-500">
              Beacon after a hypothetical rename — <code className="text-gray-700">compensation</code> →{' '}
              <code className="text-gray-700">pay_info</code>, <code className="text-gray-700">started_at</code> →{' '}
              <code className="text-gray-700">hire_timestamp</code>, and so on.
            </p>
            <pre className="overflow-x-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
              {JSON.stringify(query.data.drifted_raw, null, 2)}
            </pre>
          </Stage>

          <Stage n={2} title="The hand-written normalizer fails">
            {query.data.deterministic_error ? (
              <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 font-mono text-sm text-red-700">
                <XCircle className="size-4 shrink-0" />
                {query.data.deterministic_error}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No error — the payload parsed as-is.</p>
            )}
            <p className="mt-2 text-xs text-gray-500">
              Normally this record (and everyone in the same shape) would be silently skipped.
            </p>
          </Stage>

          <Stage n={3} title="The LLM infers a field map">
            {query.data.inferred_mapping ? (
              <MappingTable mapping={query.data.inferred_mapping} />
            ) : (
              <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <Sparkles className="size-4 shrink-0" />
                {query.data.note ?? 'No mapping available.'}
              </div>
            )}
          </Stage>

          <Stage n={4} title="Applied deterministically → canonical Employee">
            {query.data.recovered_employee ? (
              <HealedEmployee employee={query.data.recovered_employee} />
            ) : (
              <p className="text-sm text-gray-500">
                The healed record appears here once the AI layer is configured.
              </p>
            )}
          </Stage>
        </div>
      )}
    </div>
  )
}

function Stage({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900">
        <span className="flex size-5 items-center justify-center rounded-full bg-[#1e2143]/10 text-xs font-bold text-[#2a2e57]">
          {n}
        </span>
        {title}
      </h2>
      {children}
    </section>
  )
}
