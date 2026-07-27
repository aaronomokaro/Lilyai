'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Icon } from '@/components/ui/Icon'
import { DocThumb } from '@/components/ui/DocThumb'
import { StatusTag } from '@/components/ui/StatusTag'
import { documents as docsApi, usage as usageApi } from '@/lib/api'
import type { Document, UsageStats } from '@/types/api'

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  const gb = bytes / (1024 * 1024 * 1024)
  return gb < 1 ? `${(bytes / (1024 * 1024)).toFixed(0)} MB` : `${gb.toFixed(1)} GB`
}

export default function DashboardPage() {
  const router = useRouter()
  const [recentDocs, setRecentDocs] = useState<Document[]>([])
  const [stats, setStats] = useState<UsageStats | null>(null)

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'

  useEffect(() => {
    docsApi.list()
      .then(all => setRecentDocs(all.slice(0, 5)))
      .catch(() => {})

    usageApi.get()
      .then(setStats)
      .catch(() => {})
  }, [])

  return (
    <div className="screen">
      <div className="screen-pad fade-in">

        <div className="dash-hero">
          <div className="eyebrow greet-time">{greeting}</div>
          <h1 className="h-page">
            What would you like to <em>understand</em> today?
          </h1>
        </div>

        <div className="ask-bar" onClick={() => router.push('/query')}>
          <div className="qmark"><Icon name="ask" /></div>
          <div className="ask-place">Ask across your library…</div>
          <div className="scope">
            <Icon name="collections" style={{ width: 14, height: 14 }} /> All documents
          </div>
        </div>

        <div className="stat-grid">
          <div className="card stat-card">
            <div className="s-ic"><Icon name="library" /></div>
            <div className="n">{stats?.documents_count ?? '—'}</div>
            <div className="l">Documents</div>
          </div>
          <div className="card stat-card">
            <div className="s-ic"><Icon name="ask" /></div>
            <div className="n">
              {stats ? <>{stats.queries_month}<small> / {stats.limits.queries_per_month}</small></> : '—'}
            </div>
            <div className="l">Queries this month</div>
          </div>
          <div className="card stat-card">
            <div className="s-ic"><Icon name="bolt" /></div>
            <div className="n">{stats ? formatBytes(stats.storage_bytes) : '—'}</div>
            <div className="l">Indexed storage</div>
          </div>
        </div>

        <div className="dash-cols">
          <section>
            <div className="sec-head">
              <h2 className="h-sec">Recently added</h2>
              <span className="link" onClick={() => router.push('/documents')}>
                Open library <Icon name="arrowUR" />
              </span>
            </div>
            <div className="rec-list card">
              {recentDocs.length === 0 ? (
                <div className="empty" style={{ padding: '36px 20px' }}>
                  <div className="e-title">No documents yet</div>
                  <div className="e-sub">Upload your first document to get started.</div>
                </div>
              ) : recentDocs.map(d => (
                <div key={d.id} className="rec-row" onClick={() => router.push(`/documents/${d.id}`)}>
                  <div className="rec-thumb"><DocThumb kind={d.doc_type ?? d.file_type} status={d.status} tall /></div>
                  <div className="rec-main">
                    <div className="rec-title">{d.filename}</div>
                    <div className="rec-meta">
                      <span>{(d.doc_type ?? d.file_type).toUpperCase()}</span>
                      {d.page_count && <><span className="sl">·</span><span>{d.page_count} pp</span></>}
                    </div>
                  </div>
                  <StatusTag status={d.status} />
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="sec-head">
              <h2 className="h-sec">Recent activity</h2>
            </div>
            <div className="empty card" style={{ padding: '40px 20px' }}>
              <Icon name="ask" style={{ width: 26, height: 26, margin: '0 auto 12px', display: 'block' }} />
              <div className="e-title">No conversations yet</div>
              <div className="e-sub">Your query history will appear here.</div>
            </div>
          </section>
        </div>

      </div>
    </div>
  )
}
