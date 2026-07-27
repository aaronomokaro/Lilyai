import Link from 'next/link'

export function Footer() {
  const year = new Date().getFullYear()
  return (
    <footer className="site-footer">
      <span className="ft-copy">© {year} LilyAI</span>
      <nav className="ft-links">
        <Link href="/privacy">Privacy</Link>
        <Link href="/terms">Terms</Link>
        <Link href="/cookies">Cookies</Link>
      </nav>
    </footer>
  )
}
