interface StatusTagProps {
  status: string
}

export function StatusTag({ status }: StatusTagProps) {
  if (status === 'processing' || status === 'pending') {
    return (
      <span className="status proc">
        <span className="dot busy" />
        {status === 'pending' ? 'Queued' : 'Processing'}
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="status failed">
        <span className="dot danger" />
        Failed
      </span>
    )
  }
  return (
    <span className="status ready">
      <span className="dot ok" />
      Ready
    </span>
  )
}
