'use client'

import { useState, useEffect } from 'react'
import { Icon } from '@/components/ui/Icon'
import { outputs as outputsApi } from '@/lib/api'
import type { Output } from '@/types/api'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function OutputsPage() {
  const [items, setItems] = useState<Output[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    outputsApi.list()
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="screen">
      <div className="screen-pad fade-in">
        <div className="lib-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Workspace</div>
            <h1 className="h-page">Outputs</h1>
          </div>
          {items.length > 0 && (
            <span className="count-note">{items.length} output{items.length !== 1 ? 's' : ''}</span>
          )}
        </div>

        {loading ? (
          <div className="empty"><div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-faint)' }}>Loading…</div></div>
        ) : items.length === 0 ? (
          <div className="empty">
            <Icon name="outputs" style={{ width: 32, height: 32, margin: '0 auto 14px', display: 'block' }} />
            <div className="e-title">No outputs yet</div>
            <div className="e-sub">Generated reports and exports will appear here.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {items.map(o => (
              <div key={o.id} className="card" style={{ padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ width: 38, height: 38, borderRadius: 8, background: 'var(--paper-3)', color: 'var(--ink-faint)', display: 'grid', placeItems: 'center', flex: 'none' }}>
                  <Icon name="file" style={{ width: 18, height: 18 }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: 'var(--ink)', marginBottom: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.title}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink-faint)' }}>
                    {o.output_type} · {formatDate(o.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
