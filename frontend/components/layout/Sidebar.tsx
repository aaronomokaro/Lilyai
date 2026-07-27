'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Icon } from '@/components/ui/Icon'
import { Seal, Wordmark } from '@/components/ui/Seal'

const MAIN_NAV = [
  { href: '/dashboard',     label: 'Dashboard',    icon: 'dashboard' },
  { href: '/documents',     label: 'Library',      icon: 'library'   },
  { href: '/query',         label: 'Ask LilyAI',   icon: 'ask'       },
]

const BOTTOM_NAV = [
  { href: '/outputs',       label: 'Outputs',      icon: 'outputs'      },
  { href: '/integrations',  label: 'Integrations', icon: 'integrations' },
  { href: '/settings',      label: 'Settings',     icon: 'settings'     },
]

interface SidebarProps {
  userName?: string
  orgName?: string
  initials?: string
}

export function Sidebar({ userName = 'User', orgName = '', initials = 'U' }: SidebarProps) {
  const pathname = usePathname()

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + '/')

  return (
    <aside className="sidebar">
      <div className="brand">
        <Seal size={26} />
        <Wordmark />
      </div>

      <nav className="nav">
        <div className="nav-label">Workspace</div>
        {MAIN_NAV.map(item => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-item${isActive(item.href) ? ' active' : ''}`}
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      <div className="nav-foot">
        <nav className="nav">
          {BOTTOM_NAV.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item${isActive(item.href) ? ' active' : ''}`}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="nav-sep" />
        <div className="user-chip">
          <div className="avatar">{initials}</div>
          <div className="who">
            <div className="nm">{userName}</div>
            {orgName && <div className="pl">{orgName}</div>}
          </div>
        </div>
      </div>
    </aside>
  )
}
