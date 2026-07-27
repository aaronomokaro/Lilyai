'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { Footer } from './Footer'

const TITLE_MAP: Record<string, string> = {
  '/dashboard':    'Dashboard',
  '/documents':    'Library',
  '/query':        'Ask LilyAI',
  '/collections':  'Collections',
  '/outputs':      'Outputs',
  '/integrations': 'Integrations',
  '/settings':     'Settings',
}

interface AppShellProps {
  children: React.ReactNode
  userName?: string
  orgName?: string
  initials?: string
}

export function AppShell({ children, userName, orgName, initials }: AppShellProps) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const pathname = usePathname()

  const title =
    TITLE_MAP[pathname] ??
    (pathname.startsWith('/documents/') ? 'Document' : 'LilyAI')

  function toggleTheme() {
    const next = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next === 'dark' ? 'dark' : '')
  }

  return (
    <div className="app">
      <Sidebar userName={userName} orgName={orgName} initials={initials} />
      <div className="main">
        <Topbar title={title} theme={theme} onToggleTheme={toggleTheme} />
        {children}
        <Footer />
      </div>
    </div>
  )
}
