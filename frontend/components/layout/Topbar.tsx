'use client'

import { useRouter } from 'next/navigation'
import { Icon } from '@/components/ui/Icon'

interface TopbarProps {
  title: string
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

export function Topbar({ title, theme, onToggleTheme }: TopbarProps) {
  const router = useRouter()

  return (
    <header className="topbar">
      <div className="topbar-title">{title}</div>

      <div className="topbar-actions">
        <div className="search">
          <Icon name="search" />
          <input placeholder="Search documents & answers" />
          <span className="kbd">/</span>
        </div>

        <button className="icon-btn" onClick={onToggleTheme} title="Toggle theme" aria-label="Toggle theme">
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
        </button>

        <button className="btn accent sm" onClick={() => router.push('/query')}>
          <Icon name="ask" /> New query
        </button>
      </div>
    </header>
  )
}
