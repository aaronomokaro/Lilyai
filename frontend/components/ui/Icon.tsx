const PATHS: Record<string, React.ReactNode> = {
  dashboard: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.3"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.3"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.3"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.3"/></>,
  library:   <><path d="M5 3.5h11l3.5 3.5v13.5H5z"/><path d="M15.5 3.5V7H19"/><path d="M8.5 12.5h7M8.5 16h7"/></>,
  ask:       <><path d="M4 5.5h16v10H10l-4 4v-4H4z"/><path d="M8.5 9h7M8.5 12h4"/></>,
  collections:<><rect x="3.5" y="6.5" width="13" height="13" rx="1.5"/><path d="M7.5 6.5V4.5h13v13h-2"/></>,
  search:    <><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/></>,
  sliders:   <><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2.2"/><circle cx="8" cy="17" r="2.2"/></>,
  sun:       <><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4"/></>,
  moon:      <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>,
  upload:    <><path d="M12 15.5V5.5M8 9l4-4 4 4"/><path d="M4.5 14.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/></>,
  grid:      <><rect x="4" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.2"/></>,
  list:      <><path d="M4 6h16M4 12h16M4 18h16"/></>,
  plus:      <path d="M12 5v14M5 12h14"/>,
  chevR:     <path d="M9 5l7 7-7 7"/>,
  chevD:     <path d="M5 9l7 7 7-7"/>,
  check:     <path d="M5 12.5l4.5 4.5L19 7"/>,
  x:         <path d="M6 6l12 12M18 6L6 18"/>,
  arrowUR:   <path d="M7 17L17 7M8.5 7H17v8.5"/>,
  send:      <path d="M5 12h13M12 5.5l6.5 6.5L12 18.5"/>,
  download:  <><path d="M12 4v11M8 11l4 4 4-4"/><path d="M5 19.5h14"/></>,
  dots:      <><circle cx="6" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="18" cy="12" r="1.4"/></>,
  file:      <><path d="M6 3.5h8l4 4V20.5H6z"/><path d="M13.5 3.5V8H18"/></>,
  tag:       <><path d="M4 4h7l9 9-7 7-9-9z"/><circle cx="8.5" cy="8.5" r="1.4"/></>,
  clock:     <><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/></>,
  bolt:      <path d="M13 3L5 13h6l-1 8 8-10h-6z"/>,
  trash:     <><path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13"/></>,
  link:      <><path d="M9 14.5l6-6"/><path d="M11 6.5l1.5-1.5a3.5 3.5 0 0 1 5 5L16 11.5M8 12.5l-1.5 1.5a3.5 3.5 0 0 0 5 5L13 17.5"/></>,
  quote:     <><path d="M9 7c-2.5 1-4 3-4 6v4h5v-5H6.5c.2-2 1.2-3.2 3-4zM19 7c-2.5 1-4 3-4 6v4h5v-5h-3.5c.2-2 1.2-3.2 3-4z"/></>,
  open:      <><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 4v16"/></>,
  outputs:   <><path d="M4 6h16M4 12h10M4 18h7"/><path d="M16 14l4 4-4 4"/></>,
  integrations: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1"/></>,
  settings:  <><circle cx="12" cy="12" r="3"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></>,
}

interface IconProps {
  name: string
  className?: string
  style?: React.CSSProperties
}

export function Icon({ name, className, style }: IconProps) {
  return (
    <svg
      className={className}
      style={style}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {PATHS[name] ?? null}
    </svg>
  )
}
