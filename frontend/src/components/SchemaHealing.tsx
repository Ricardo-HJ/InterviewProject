import { ArrowRight } from 'lucide-react'
import type { Employee, SchemaMapping } from '#/lib/api'
import { STATUS_LABEL, formatSalary } from '#/lib/display'

// Curated view of the flat SchemaMapping: each canonical field, the raw path it was
// mapped from, and the transform/mode selector (if any). Keys mirror schema_infer.py.
const MAPPING_ROWS: { label: string; pathKey: string; transformKey?: string }[] = [
  { label: 'Employee ID', pathKey: 'provider_id_path' },
  { label: 'Email', pathKey: 'email_path' },
  { label: 'Name', pathKey: 'name_path', transformKey: 'name_mode' },
  { label: 'Title', pathKey: 'title_path' },
  { label: 'Department', pathKey: 'department_path' },
  { label: 'Salary', pathKey: 'salary_path', transformKey: 'salary_unit' },
  { label: 'Currency', pathKey: 'currency_path' },
  { label: 'Hire date', pathKey: 'hire_date_path', transformKey: 'hire_date_format' },
  { label: 'Status', pathKey: 'status_path', transformKey: 'status_mode' },
]

/** Renders an inferred SchemaMapping as `canonical field ← raw path · transform` rows. */
export function MappingTable({ mapping }: { mapping: SchemaMapping }) {
  return (
    <div className="divide-y divide-gray-100 rounded-md border border-gray-200">
      {MAPPING_ROWS.map(({ label, pathKey, transformKey }) => {
        const path = mapping[pathKey]
        if (!path) return null
        const transform = transformKey ? mapping[transformKey] : undefined
        return (
          <div key={label} className="grid grid-cols-[8rem_1fr] items-center gap-2 px-3 py-2 text-sm">
            <span className="font-medium text-gray-700">{label}</span>
            <span className="flex flex-wrap items-center gap-2 text-gray-600">
              <ArrowRight className="size-3.5 text-gray-300" />
              <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-800">{path}</code>
              {transform && (
                <span className="rounded-full bg-[#1e2143]/5 px-2 py-0.5 text-[11px] font-medium text-[#2a2e57] ring-1 ring-inset ring-[#1e2143]/25">
                  {transform}
                </span>
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}

/** A recovered canonical Employee shown as a compact, read-only field grid. */
export function HealedEmployee({ employee }: { employee: Employee }) {
  const rows: { label: string; value: string }[] = [
    { label: 'Name', value: String(employee.name.value ?? '—') },
    { label: 'Email', value: employee.email },
    { label: 'Title', value: String(employee.title.value ?? '—') },
    { label: 'Department', value: String(employee.department.value ?? '—') },
    { label: 'Salary', value: formatSalary(employee.salary_annual.value, employee.currency) },
    { label: 'Hire date', value: String(employee.hire_date.value ?? '—') },
    { label: 'Status', value: STATUS_LABEL[employee.status.value] },
  ]
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-2 rounded-md border border-green-200 bg-green-50/40 p-4 text-sm">
      {rows.map(({ label, value }) => (
        <div key={label} className="flex flex-col">
          <span className="text-xs text-gray-400">{label}</span>
          <span className="font-medium text-gray-800">{value}</span>
        </div>
      ))}
    </div>
  )
}
