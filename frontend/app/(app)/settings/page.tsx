import { Icon } from '@/components/ui/Icon'
import { auth0 } from '@/lib/auth0'

export default async function SettingsPage() {
  const session = await auth0.getSession()
  const user = session?.user

  return (
    <div className="screen">
      <div className="screen-pad fade-in">
        <div className="lib-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Account</div>
            <h1 className="h-page">Settings</h1>
          </div>
        </div>

        <div style={{ maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ padding: '20px 22px' }}>
            <div className="mb-label" style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 16 }}>Profile</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div className="avatar" style={{ width: 44, height: 44, borderRadius: 12, fontSize: 18 }}>
                {user?.name?.charAt(0)?.toUpperCase() ?? 'U'}
              </div>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--ink)' }}>{user?.name ?? '—'}</div>
                <div style={{ fontSize: 13, color: 'var(--ink-faint)' }}>{user?.email ?? '—'}</div>
              </div>
            </div>
          </div>

          <div className="card" style={{ padding: '20px 22px' }}>
            <div className="mb-label" style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 16 }}>Session</div>
            <a href="/auth/logout" className="btn" style={{ display: 'inline-flex' }}>
              <Icon name="x" /> Sign out
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
