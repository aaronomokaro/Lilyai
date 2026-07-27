'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { Icon } from '@/components/ui/Icon'
import { DocThumb } from '@/components/ui/DocThumb'
import { StatusTag } from '@/components/ui/StatusTag'
import { documents as docsApi } from '@/lib/api'
import type { Document } from '@/types/api'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function errMsg(e: unknown) {
  return e instanceof Error ? e.message : 'Something went wrong'
}

export default function DocumentDetailPage() {
  const router = useRouter()
  const params = useParams<{ id: string }>()
  const id = params.id

  const [doc, setDoc] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    docsApi.get(id)
      .then(setDoc)
      .catch(e => setError(errMsg(e)))
      .finally(() => setLoading(false))
  }, [id])

  async function handleDelete() {
    if (!doc || !confirm('Delete this document?')) return
    try {
      await docsApi.delete(doc.id)
      router.push('/documents')
    } catch (e) {
      setError(errMsg(e))
    }
  }

  if (loading) {
    return (
      <div className="screen">
        <div className="screen-pad">
          <div className="empty"><div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-faint)' }}>Loading…</div></div>
        </div>
      </div>
    )
  }

  if (error || !doc) {
    return (
      <div className="screen">
        <div className="screen-pad">
          <div className="back-link" onClick={() => router.push('/documents')}>
            <Icon name="arrowUR" /> Back to library
          </div>
          <div className="empty">
            <div className="e-title">Document not found</div>
            <div className="e-sub">{error ?? 'This document may have been removed.'}</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="docview">
      <div className="preview-col">
        <div className="back-link" onClick={() => router.push('/documents')}>
          <Icon name="arrowUR" /> Back to library
        </div>

        <div className="doc-hero">
          <div className="dh-thumb"><DocThumb kind={doc.doc_type ?? doc.file_type} status={doc.status} tall /></div>
          <div style={{ minWidth: 0 }}>
            <div className="dh-title">{doc.filename}</div>
            <div className="dh-meta">
              <span>{(doc.doc_type ?? doc.file_type).toUpperCase()}</span>
              <span className="sl">·</span>
              <span>{formatBytes(doc.file_size_bytes)}</span>
              {doc.page_count && <><span className="sl">·</span><span>{doc.page_count} pages</span></>}
            </div>
            <div style={{ marginTop: 14 }}><StatusTag status={doc.status} /></div>
          </div>
        </div>

        {doc.status === 'failed' && (
          <div className="err-banner">Processing failed for this document. Try re-uploading it.</div>
        )}
        {(doc.status === 'processing' || doc.status === 'pending') && (
          <div className="card" style={{ padding: '18px 20px', color: 'var(--ink-soft)', fontSize: 13.5 }}>
            LilyAI is still reading and indexing this document. It will be available to query once ready.
          </div>
        )}
        {doc.status === 'ready' && (
          <div className="card" style={{ padding: '18px 20px', color: 'var(--ink-soft)', fontSize: 13.5 }}>
            This document is indexed and ready. Ask LilyAI a question and it will cite passages from here.
          </div>
        )}
      </div>

      <div className="meta-col">
        <div className="meta-actions">
          <button className="btn accent" onClick={() => router.push('/query')} disabled={doc.status !== 'ready'}>
            <Icon name="ask" /> Ask about this document
          </button>
          <button className="btn" onClick={handleDelete}>
            <Icon name="trash" /> Delete
          </button>
        </div>

        <div className="meta-block">
          <div className="mb-label">Details</div>
          <div className="meta-grid">
            <div>
              <div className="mg-l">Type</div>
              <div className="mg-v">{(doc.doc_type ?? doc.file_type).toUpperCase()}</div>
            </div>
            <div>
              <div className="mg-l">Size</div>
              <div className="mg-v">{formatBytes(doc.file_size_bytes)}</div>
            </div>
            <div>
              <div className="mg-l">Pages</div>
              <div className="mg-v">{doc.page_count ?? '—'}</div>
            </div>
            <div>
              <div className="mg-l">Added</div>
              <div className="mg-v">{formatDate(doc.created_at)}</div>
            </div>
          </div>
        </div>

        {doc.tags && doc.tags.length > 0 && (
          <div className="meta-block">
            <div className="mb-label">Tags</div>
            <div className="filter-chips">
              {doc.tags.map(t => <span key={t.id} className="tag" style={{ cursor: 'default' }}>{t.name}</span>)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
