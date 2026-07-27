'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Icon } from '@/components/ui/Icon'
import { Seal } from '@/components/ui/Seal'
import { DocThumb } from '@/components/ui/DocThumb'
import { useStreamStore } from '@/stores/streamStore'
import { useProgressStore } from '@/stores/progressStore'
import { documents as docsApi, queries as queriesApi } from '@/lib/api'
import type { Document, Citation } from '@/types/api'

const STEP_LABELS: Record<string, string> = {
  classified:            'Intent classified',
  running_query:         'Retrieving sources…',
  running_risk_analysis: 'Analysing risks…',
  generating_output:     'Generating output…',
}

interface Message {
  role: 'user' | 'ai'
  text?: string
  citations?: Citation[]
  confirm?: boolean
}

function errMsg(e: unknown) {
  return e instanceof Error ? e.message : 'Something went wrong'
}

// Parse [Document: X, Page: Y, Chunk: Z] marks out of answer text.
// Numbering aligns with the Sources list (citation index); shows a hover popover.
function CitationMark({ text, citations }: { text: string; citations: Citation[] }) {
  const parts = text.split(/(\[Document:[^\]]+\])/g)
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/\[Document: (.+?), Page: (\d+), Chunk: (\d+)\]/)
        if (!match) return <span key={i}>{part}</span>
        const [, filename, page, chunk] = match
        const idx = citations.findIndex(
          c => c.filename === filename && c.page_number === Number(page) && c.chunk_index === Number(chunk)
        )
        // marks sit at odd indices of the split array → derive their ordinal without mutation
        const n = idx >= 0 ? idx + 1 : Math.floor(i / 2) + 1
        const cited = idx >= 0 ? citations[idx] : null
        return (
          <span key={i} className="cite" title={`${filename} · p.${page} §${chunk}`}>
            [{n}]
            {cited && (
              <span className="cite-pop">
                <span className="cp-doc">{cited.filename}</span>
                <span className="cp-quote">{cited.text}</span>
                <span className="cp-loc">Page {cited.page_number} · Chunk {cited.chunk_index}</span>
              </span>
            )}
          </span>
        )
      })}
    </>
  )
}

function ContextDoc({ doc, active, onToggle, onClick }: { doc: Document; active: boolean; onToggle: () => void; onClick: () => void }) {
  return (
    <div className={`ctx-doc${active ? '' : ' off'}`}>
      <div className="cd-thumb" onClick={onClick} style={{ cursor: 'pointer' }}>
        <DocThumb kind={doc.doc_type ?? doc.file_type} status={doc.status} tall />
      </div>
      <div className="cd-main" onClick={onClick} style={{ cursor: 'pointer' }}>
        <div className="cd-title">{doc.filename}</div>
        <div className="cd-meta">{(doc.doc_type ?? doc.file_type).toUpperCase()} · {doc.page_count ? `${doc.page_count} pp` : '—'}</div>
      </div>
      <div className={`ctx-toggle${active ? ' on' : ''}`} onClick={onToggle} />
    </div>
  )
}

export default function QueryPage() {
  const router = useRouter()
  const [availableDocs, setAvailableDocs] = useState<Document[]>([])
  const [activeDocs, setActiveDocs] = useState<Set<string>>(new Set())
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [conversationId] = useState<string | undefined>()
  const taRef = useRef<HTMLTextAreaElement>(null)
  const convRef = useRef<HTMLDivElement>(null)

  const { tokens, isStreaming, citations, clear: clearStream } = useStreamStore()
  const { step, clear: clearProgress } = useProgressStore()

  // Load ready documents for context panel
  useEffect(() => {
    docsApi.list().then(all => {
      const ready = all.filter(d => d.status === 'ready')
      setAvailableDocs(ready)
      setActiveDocs(new Set(ready.map(d => d.id)))
    }).catch(() => {})
  }, [])

  // Scroll to bottom when new content arrives
  useEffect(() => {
    if (convRef.current) convRef.current.scrollTop = convRef.current.scrollHeight
  }, [messages, tokens])

  // When streaming completes, commit the AI message
  useEffect(() => {
    if (!isStreaming && tokens) {
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.role === 'ai' && !last.text) {
          return [...prev.slice(0, -1), { role: 'ai', text: tokens, citations }]
        }
        return prev
      })
      clearStream()
      clearProgress()
      setSubmitting(false)
    }
  }, [isStreaming, tokens, citations, clearStream, clearProgress])

  async function send() {
    const text = draft.trim()
    if (!text || submitting) return

    clearStream()
    clearProgress()
    setDraft('')
    if (taRef.current) taRef.current.style.height = 'auto'

    setMessages(prev => [
      ...prev,
      { role: 'user', text },
      { role: 'ai' }, // placeholder while streaming
    ])
    setSubmitting(true)

    try {
      const result = await queriesApi.ask({
        question: text,
        conversation_id: conversationId,
        document_ids: Array.from(activeDocs),
      })

      if (result.requires_confirmation) {
        setMessages(prev => [
          ...prev.slice(0, -1),
          { role: 'ai', text: result.message, confirm: true },
        ])
        setSubmitting(false)
        return
      }

      // Streaming tokens arrive via WebSocket — handled in the effect above
    } catch (e) {
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: 'ai', text: `Error: ${errMsg(e)}` },
      ])
      setSubmitting(false)
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  function onInput(e: React.FormEvent<HTMLTextAreaElement>) {
    const el = e.currentTarget
    setDraft(el.value)
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }

  function toggleDoc(id: string) {
    setActiveDocs(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const activeCount = activeDocs.size
  const readyDocs = availableDocs.filter(d => d.status === 'ready')

  return (
    <div className="query-wrap">
      {/* context panel */}
      <div className="ctx-panel">
        <div className="ctx-head">
          <div className="eyebrow">In context</div>
          <div className="ctx-coll" style={{ marginTop: 10 }}>
            <Icon name="collections" style={{ width: 18, height: 18, color: 'var(--accent)' }} />
            All documents
          </div>
          <div className="ctx-sub">{activeCount} of {readyDocs.length} document{readyDocs.length !== 1 ? 's' : ''} active</div>
        </div>

        <div className="ctx-scroll">
          {readyDocs.length === 0 ? (
            <div style={{ padding: '20px 12px', textAlign: 'center' }}>
              <Icon name="library" style={{ width: 22, height: 22, color: 'var(--ink-ghost)', margin: '0 auto 10px', display: 'block' }} />
              <div style={{ fontSize: 12, color: 'var(--ink-faint)' }}>No ready documents.<br />Upload files in the Library.</div>
            </div>
          ) : readyDocs.map(doc => (
            <ContextDoc
              key={doc.id}
              doc={doc}
              active={activeDocs.has(doc.id)}
              onToggle={() => toggleDoc(doc.id)}
              onClick={() => router.push(`/documents/${doc.id}`)}
            />
          ))}
        </div>

        <div className="ctx-foot">
          <button className="btn ghost sm" onClick={() => router.push('/documents')}>
            <Icon name="plus" /> Add documents
          </button>
        </div>
      </div>

      {/* answer panel */}
      <div className="answer-panel">
        <div className="conv" ref={convRef}>
          <div className="conv-inner">
            {messages.length === 0 ? (
              <div style={{ textAlign: 'center', paddingTop: 72, color: 'var(--ink-faint)' }}>
                <div style={{ display: 'inline-flex' }}><Seal size={44} /></div>
                <p style={{ fontSize: 17, marginTop: 20, fontWeight: 600, color: 'var(--ink)' }}>
                  Ask a question about your documents
                </p>
                <p style={{ fontSize: 13.5, marginTop: 6 }}>
                  Every answer cites the passages it draws from.
                </p>
              </div>
            ) : messages.map((m, i) => (
              m.role === 'user' ? (
                <div key={i} className="msg-user">
                  <div className="ulabel">You asked</div>
                  <div className="utext">{m.text}</div>
                </div>
              ) : (
                <div key={i} className="msg-ai">
                  <div className="ai-label">
                    <Seal size={22} />
                    <span className="ai-name">LilyAI</span>
                    {i === messages.length - 1 && (isStreaming || submitting) ? (
                      <span className="ai-state">
                        <span className="dot busy" />
                        {step ? (STEP_LABELS[step] ?? step) : 'Thinking…'}
                      </span>
                    ) : m.text && !m.confirm ? (
                      <span className="ai-state" style={{ color: 'var(--ink-faint)' }}>
                        {m.citations?.length ? `Answered from ${m.citations.length} passage${m.citations.length !== 1 ? 's' : ''}` : 'Answered'}
                      </span>
                    ) : null}
                  </div>

                  {m.confirm ? (
                    <div className="confirm-callout">
                      <div className="cc-title"><Icon name="bolt" /> Confirmation required</div>
                      <div className="cc-body">{m.text}</div>
                    </div>
                  ) : (
                    <>
                      <div className="answer-text">
                        {i === messages.length - 1 && (isStreaming || (!m.text && submitting)) ? (
                          <p>
                            <CitationMark text={tokens} citations={[]} />
                            {isStreaming && <span className="stream-cur" />}
                          </p>
                        ) : m.text ? (
                          m.text.split('\n\n').map((para, pi) => (
                            <p key={pi}>
                              <CitationMark text={para} citations={m.citations ?? []} />
                            </p>
                          ))
                        ) : (
                          <p><span className="stream-cur" /></p>
                        )}
                      </div>

                      {m.text && m.citations && m.citations.length > 0 && (
                        <div className="sources">
                          <div className="s-title">Sources</div>
                          {m.citations.map((c, ci) => (
                            <div key={ci} className="src-row" onClick={() => router.push(`/documents/${c.document_id}`)}>
                              <span className="src-num">[{ci + 1}]</span>
                              <span className="src-title">{c.filename}</span>
                              <span className="src-loc">p.{c.page_number} §{c.chunk_index}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )
            ))}
          </div>
        </div>

        <div className="composer-wrap">
          <div className="composer">
            <div className="composer-box">
              <textarea
                ref={taRef}
                rows={1}
                placeholder="Ask a question about your documents…"
                value={draft}
                onInput={onInput}
                onKeyDown={onKey}
                disabled={submitting}
              />
              <button className="send-btn" disabled={!draft.trim() || submitting} onClick={send}>
                <Icon name="send" />
              </button>
            </div>
            <div className="composer-hint">
              <span>Answers cite the passages they draw from.</span>
              <span>
                <span className="kbd">↵</span> to send · <span className="kbd">⇧↵</span> new line
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
