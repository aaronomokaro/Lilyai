'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Seal, Wordmark } from '@/components/ui/Seal'

export default function SignupPage() {
  const [agreed, setAgreed] = useState(false)

  function handleContinue() {
    if (!agreed) return
    // Hand off to Auth0 Universal Login in sign-up mode.
    window.location.assign('/auth/login?screen_hint=signup')
  }

  return (
    <div
      style={{
        height: '100%',
        overflowY: 'auto',
        background: 'var(--canvas)',
        display: 'grid',
        placeItems: 'center',
        padding: '40px 22px',
      }}
    >
      <div className="card" style={{ width: '100%', maxWidth: 420, padding: '34px 32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
          <Seal size={28} />
          <Wordmark />
        </div>

        <div className="eyebrow" style={{ marginBottom: 10 }}>Get started</div>
        <h1 className="h-page" style={{ fontSize: 28, marginBottom: 10 }}>Create your account</h1>
        <p className="sub" style={{ marginBottom: 26 }}>
          Agree to our terms, then continue to create your account securely.
        </p>

        <label
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 11,
            cursor: 'pointer',
            marginBottom: 22,
            fontSize: 13.5,
            color: 'var(--ink-soft)',
            lineHeight: 1.5,
          }}
        >
          <input
            type="checkbox"
            checked={agreed}
            onChange={e => setAgreed(e.target.checked)}
            style={{ marginTop: 2, width: 16, height: 16, accentColor: 'var(--accent)', flex: 'none', cursor: 'pointer' }}
          />
          <span>
            I agree to the{' '}
            <Link href="/terms" style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link href="/privacy" style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
              Privacy Policy
            </Link>
            .
          </span>
        </label>

        <button
          className="btn accent"
          onClick={handleContinue}
          disabled={!agreed}
          style={{ width: '100%', justifyContent: 'center', opacity: agreed ? 1 : 0.45, cursor: agreed ? 'pointer' : 'not-allowed' }}
        >
          Continue
        </button>

        <p style={{ marginTop: 18, fontSize: 13, color: 'var(--ink-faint)', textAlign: 'center' }}>
          Already have an account?{' '}
          <a href="/auth/login" style={{ color: 'var(--accent)' }}>Sign in</a>
        </p>
      </div>
    </div>
  )
}
