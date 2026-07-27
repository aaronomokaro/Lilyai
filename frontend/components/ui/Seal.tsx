interface SealProps {
  size?: number
}

export function Seal({ size = 28 }: SealProps) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.28,
        background: 'var(--accent)',
        color: 'var(--accent-ink)',
        display: 'grid',
        placeItems: 'center',
        flex: 'none',
        fontSize: size * 0.56,
        fontWeight: 700,
        lineHeight: 1,
        letterSpacing: '-0.02em',
      }}
    >
      L
    </div>
  )
}

export function Wordmark() {
  return (
    <span className="wordmark">
      Lily<span className="ai">AI</span>
    </span>
  )
}
