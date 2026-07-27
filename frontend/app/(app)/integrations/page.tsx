'use client'

import { useState, useEffect } from 'react'
import { Icon } from '@/components/ui/Icon'
import { integrations as integrationsApi } from '@/lib/api'
import type { IntegrationStatus } from '@/types/api'

const PROVIDERS = [
  { key: 'gmail', name: 'Gmail', desc: 'Send answers and reports via email directly from a conversation.' },
  { key: 'drive', name: 'Google Drive', desc: 'Save generated outputs to your Drive with one click.' },
] as const

export default function IntegrationsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    integrationsApi.status()
      .then(setStatus)
      .catch(() => setError('Could not load integration status.'))
  }, [])

  async function handleConnect(provider: 'gmail' | 'drive') {
    setError(null)
    setConnecting(provider)
    try {
      const { oauth_url } = await integrationsApi.connect(provider)
      window.location.assign(oauth_url)
    } catch (e) {
      setConnecting(null)
      const message = e instanceof Error ? e.message : ''
      setError(
        message.includes('403')
          ? 'This integration requires a higher plan.'
          : 'Could not start the connection. Please try again.'
      )
    }
  }

  return (
    <div className="screen">
      <div className="screen-pad fade-in">
        <div className="lib-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Account</div>
            <h1 className="h-page">Integrations</h1>
          </div>
        </div>
        <p className="sub" style={{ marginBottom: 28 }}>
          Connect third-party services to send and save from within LilyAI.
        </p>

        {error && (
          <div className="err-banner" style={{ maxWidth: 560 }}>{error}</div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 560 }}>
          {PROVIDERS.map(item => {
            const state = status?.[item.key]
            const connected = state?.connected ?? false
            const available = state?.available ?? true

            return (
              <div key={item.key} className="card" style={{ padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--paper-3)', display: 'grid', placeItems: 'center', color: 'var(--ink-faint)', flex: 'none' }}>
                  <Icon name="integrations" style={{ width: 18, height: 18 }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: 'var(--ink)', marginBottom: 3 }}>{item.name}</div>
                  <div style={{ fontSize: 13, color: 'var(--ink-faint)' }}>{item.desc}</div>
                </div>

                {!status ? (
                  <span className="status">…</span>
                ) : connected ? (
                  <span className="status ready"><span className="dot ok" /> Connected</span>
                ) : !available ? (
                  <span className="pill">Upgrade required</span>
                ) : (
                  <button
                    className="btn sm"
                    onClick={() => handleConnect(item.key)}
                    disabled={connecting === item.key}
                  >
                    {connecting === item.key ? 'Connecting…' : 'Connect'}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
