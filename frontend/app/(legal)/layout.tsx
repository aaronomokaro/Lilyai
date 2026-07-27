import Link from 'next/link'
import { Seal, Wordmark } from '@/components/ui/Seal'
import { Footer } from '@/components/layout/Footer'

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="legal-scroll">
      <header className="legal-top">
        <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <Seal size={26} />
          <Wordmark />
        </Link>
      </header>
      <div className="legal-body">{children}</div>
      <Footer />
    </div>
  )
}
