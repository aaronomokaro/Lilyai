'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
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

export default function DocumentsPage() {
  const router = useRouter()
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [filterTags, setFilterTags] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [drag, setDrag] = useState(false)
  const [uploading, setUploading] = useState(false)

  // Initial load
  useEffect(() => {
    docsApi.list()
      .then(setDocs)
      .catch(e => setError(errMsg(e)))
      .finally(() => setLoading(false))
  }, [])

  // Poll while any document is still processing
  useEffect(() => {
    const hasProcessing = docs.some(d => d.status === 'processing' || d.status === 'pending')
    if (!hasProcessing) return
    const t = setTimeout(() => {
      docsApi.list().then(setDocs).catch(() => {})
    }, 3000)
    return () => clearTimeout(t)
  }, [docs])

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        await docsApi.upload(file)
      }
      setDocs(await docsApi.list())
    } catch (e) {
      setError(errMsg(e))
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm('Delete this document?')) return
    try {
      await docsApi.delete(id)
      setDocs(p => p.filter(d => d.id !== id))
    } catch (err) {
      setError(errMsg(err))
    }
  }

  const toggleTag = (t: string) =>
    setFilterTags(p => p.includes(t) ? p.filter(x => x !== t) : [...p, t])

  // Real tags drawn from the documents themselves
  const availableTags = Array.from(
    new Set(docs.flatMap(d => d.tags?.map(t => t.name) ?? []))
  ).sort()

  const filtered = docs.filter(d => {
    if (filterTags.length && !filterTags.some(t => d.tags?.some(dt => dt.name === t))) return false
    if (search && !d.filename.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="screen">
      <div className="screen-pad fade-in">

        <div className="lib-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Workspace</div>
            <h1 className="h-page">Library</h1>
          </div>
          <span className="count-note">{filtered.length} of {docs.length} document{docs.length !== 1 ? 's' : ''}</span>
        </div>

        {error && <div className="err-banner">{error}</div>}

        {/* dropzone */}
        <label
          className={`dropzone${drag ? ' drag' : ''}${uploading ? ' drag' : ''}`}
          onDragOver={e => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={e => { e.preventDefault(); setDrag(false); handleFiles(e.dataTransfer.files) }}
          style={{ cursor: uploading ? 'wait' : 'pointer' }}
        >
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            multiple
            style={{ display: 'none' }}
            onChange={e => handleFiles(e.target.files)}
            disabled={uploading}
          />
          <div className="dz-ic">
            <Icon name={uploading ? 'clock' : 'upload'} />
          </div>
          <div className="dz-text">
            <div className="t">
              {uploading ? 'Uploading…' : 'Drop documents to add them to your library'}
            </div>
            <div className="s">
              {uploading ? 'Processing your file' : <span>or <b>browse files</b> — LilyAI reads and indexes them for you</span>}
            </div>
          </div>
          <div className="dz-formats">PDF · DOCX · TXT<br />up to 200 MB</div>
        </label>

        {/* toolbar */}
        <div className="lib-toolbar">
          <div className="filter-chips">
            {availableTags.map(t => (
              <span
                key={t}
                className={`tag${filterTags.includes(t) ? ' sel' : ''}`}
                onClick={() => toggleTag(t)}
              >
                {t}
              </span>
            ))}
          </div>
          <div className="toolbar-right">
            <div className="search" style={{ minWidth: 200 }}>
              <Icon name="search" />
              <input
                placeholder="Filter by name…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div className="seg">
              <button className={view === 'grid' ? 'on' : ''} onClick={() => setView('grid')} title="Grid">
                <Icon name="grid" />
              </button>
              <button className={view === 'list' ? 'on' : ''} onClick={() => setView('list')} title="List">
                <Icon name="list" />
              </button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="empty">
            <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-faint)' }}>Loading…</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty">
            <Icon name="library" style={{ width: 32, height: 32, margin: '0 auto 14px', display: 'block' }} />
            <div className="e-title">{docs.length === 0 ? 'Your library is empty' : 'Nothing matches'}</div>
            <div className="e-sub">{docs.length === 0 ? 'Upload documents above to get started.' : 'Try clearing your filters.'}</div>
          </div>
        ) : view === 'grid' ? (
          <div className="doc-grid">
            {filtered.map(d => (
              <article key={d.id} className="gcard" onClick={() => router.push(`/documents/${d.id}`)}>
                <DocThumb kind={d.doc_type ?? d.file_type} status={d.status} />
                <div className="gcard-kind">{(d.doc_type ?? d.file_type).toUpperCase()}</div>
                <h3 className="gcard-title">{d.filename}</h3>
                <div className="gcard-foot">
                  <StatusTag status={d.status} />
                  <span className="pill">{formatBytes(d.file_size_bytes)}</span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="doc-listing">
            <div className="lrow head">
              <span />
              <span>Document</span>
              <span>Type</span>
              <span>Added</span>
              <span>Status</span>
              <span />
            </div>
            {filtered.map(d => (
              <div key={d.id} className="lrow" onClick={() => router.push(`/documents/${d.id}`)}>
                <div className="lthumb"><DocThumb kind={d.doc_type ?? d.file_type} status={d.status} tall /></div>
                <div style={{ minWidth: 0 }}>
                  <div className="ltitle">{d.filename}</div>
                  <div className="lsub">{d.page_count ? `${d.page_count} pp · ` : ''}{formatBytes(d.file_size_bytes)}</div>
                </div>
                <div className="lcell">{(d.doc_type ?? d.file_type).toUpperCase()}</div>
                <div className="lcell">{formatDate(d.created_at)}</div>
                <div><StatusTag status={d.status} /></div>
                <div className="lmore" onClick={(e) => handleDelete(d.id, e)} title="Delete">
                  <Icon name="trash" />
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  )
}
