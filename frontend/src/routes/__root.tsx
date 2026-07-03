import { useEffect, useState } from 'react'
import { HeadContent, Link, Scripts, createRootRoute } from '@tanstack/react-router'
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools'
import { TanStackDevtools } from '@tanstack/react-devtools'
import { useQuery } from '@tanstack/react-query'
import { CloudCheck, Cpu, IdCard, TriangleAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { fetchConflicts, fetchIssues, fetchMergeCandidates } from '#/lib/api'

import appCss from '../styles.css?url'

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: 'utf-8',
      },
      {
        name: 'viewport',
        content: 'width=device-width, initial-scale=1',
      },
      {
        title: 'Employee Aggregator',
      },
    ],
    links: [
      {
        rel: 'stylesheet',
        href: appCss,
      },
    ],
  }),
  shellComponent: RootDocument,
})

function NavLink({
  to,
  exact,
  icon: Icon,
  children,
}: {
  to: string
  exact?: boolean
  icon: LucideIcon
  children: React.ReactNode
}) {
  return (
    <Link
      to={to}
      activeOptions={{ exact: exact ?? false }}
      className="flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs transition-colors"
      activeProps={{
        className:
          'border-[#ededed] bg-white/40 text-gray-900 shadow-[0px_3px_6.5px_0px_rgba(0,0,0,0.08)] backdrop-blur-sm',
      }}
      inactiveProps={{ className: 'border-transparent text-gray-600 hover:text-gray-900' }}
    >
      <Icon className="size-5.5 shrink-0" strokeWidth={1.75} />
      {children}
    </Link>
  )
}

/** Red pill on the Conflicts nav item: total open items in the inbox (data-quality
 *  issues + actionable change-suggestions + likely duplicates). Server totals — it
 *  doesn't subtract session-local triage, so it reads as "what's waiting on the server". */
function ConflictsBadge() {
  const issues = useQuery({ queryKey: ['issues'], queryFn: fetchIssues })
  const conflicts = useQuery({ queryKey: ['conflicts'], queryFn: fetchConflicts })
  const merge = useQuery({ queryKey: ['merge-candidates'], queryFn: fetchMergeCandidates })

  const actionable = (conflicts.data?.conflicts ?? []).filter((c) => c.suggested !== c.current).length
  const pending = (issues.data?.issues.length ?? 0) + actionable + (merge.data?.merge_candidates.length ?? 0)
  if (!pending) return null

  return (
    <span className="inline-flex min-w-4.5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-none text-white">
      {pending}
    </span>
  )
}

/** Sticky top nav. Sits transparent over the page background; once the page scrolls,
 *  it turns to frosted glass (translucent + backdrop-blur) so content reads through it. */
function TopNav() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav
      className={`sticky top-0 z-50 flex items-center justify-center px-6 py-3 transition-colors duration-200 ${
        scrolled
          ? 'border-b border-white/50 bg-white/55 shadow-[0px_4px_24px_0px_rgba(0,0,0,0.06)] backdrop-blur-xl'
          : 'border-b border-transparent'
      }`}
    >
      <img
        src="/aindez-logo.png"
        alt="aindez"
        className="absolute left-8 top-1/2 h-6 w-auto -translate-y-1/2 shrink-0"
      />
      <div className="flex items-center gap-x-10">
        <NavLink to="/" exact icon={IdCard}>
          Employees
        </NavLink>
        <NavLink to="/inbox" icon={TriangleAlert}>
          Conflicts
          <ConflictsBadge />
        </NavLink>
        <NavLink to="/schema" icon={Cpu}>
          Schema Lab
        </NavLink>
        <NavLink to="/recovered" icon={CloudCheck}>
          Recovered
        </NavLink>
      </div>
    </nav>
  )
}

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body className="bg-[#f9f7fa] text-gray-900">
        <TopNav />
        {children}
        <TanStackDevtools
          config={{
            position: 'bottom-right',
          }}
          plugins={[
            {
              name: 'Tanstack Router',
              render: <TanStackRouterDevtoolsPanel />,
            },
          ]}
        />
        <Scripts />
      </body>
    </html>
  )
}
