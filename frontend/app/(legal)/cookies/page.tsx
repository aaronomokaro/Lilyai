import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Cookie Policy — LilyAI',
  description: 'How LilyAI uses cookies and similar technologies.',
}

export default function CookiePolicyPage() {
  return (
    <>
      <p className="legal-note">
        DRAFT — pending review by a qualified solicitor before paid launch. Not yet legally vetted.
      </p>
      <article className="page-sheet">
        <div className="pp-kicker">LilyAI</div>
        <h1>Cookie Policy</h1>
        <p className="pp-updated">Last updated: 30 June 2026</p>
        <div className="pp-rule" />

        <p>
          This Cookie Policy explains how LilyAI (&ldquo;we&rdquo;, &ldquo;us&rdquo;) uses cookies and
          similar technologies when you use our service (the &ldquo;Service&rdquo;).
        </p>

        <h2>1. What cookies are</h2>
        <p>
          Cookies are small text files placed on your device when you visit a website. They are widely
          used to make websites work, and to provide information to the site&rsquo;s operators.
        </p>

        <h2>2. How we use cookies</h2>
        <ul>
          <li>
            <strong>Strictly necessary cookies:</strong> required to authenticate you and keep you
            signed in. These are set as part of our login flow and cannot be disabled.
          </li>
          <li>
            <strong>Preference cookies:</strong> remember settings such as your light or dark theme.
          </li>
        </ul>
        <p>
          We do not use advertising cookies, and we do not sell data collected through cookies.
        </p>

        <h2>3. Managing cookies</h2>
        <p>
          Most browsers allow you to refuse or delete cookies through their settings. Please note that
          blocking strictly necessary cookies will prevent you from signing in and using the Service.
        </p>

        <h2>4. Changes</h2>
        <p>
          We may update this Cookie Policy from time to time. The &ldquo;last updated&rdquo; date above
          indicates when it was last revised.
        </p>

        <h2>5. Contact</h2>
        <p>For questions about this Cookie Policy, contact us at privacy@lilyai.dev.</p>
      </article>
    </>
  )
}
