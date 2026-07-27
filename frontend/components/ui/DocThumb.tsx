import { Icon } from './Icon'

interface DocThumbProps {
  kind?: string
  status?: string
  tall?: boolean
}

export function DocThumb({ kind, status, tall }: DocThumbProps) {
  return (
    <div className={`doc-thumb${tall ? ' tall' : ''}`}>
      <div className="ph" style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Icon name="file" style={{ width: 22, height: 22, opacity: 0.6 }} />
        <span>{(kind ?? 'DOC').toUpperCase()}</span>
      </div>
      {status === 'processing' && (
        <div className="thumb-proc">
          <span className="dot busy" />
        </div>
      )}
    </div>
  )
}
