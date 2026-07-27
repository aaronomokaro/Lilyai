import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service — LilyAI',
  description: 'The terms governing your use of the LilyAI service.',
}

export default function TermsOfServicePage() {
  return (
    <>
      <p className="legal-note">
        DRAFT — pending review by a qualified solicitor before paid launch. Not yet legally vetted.
      </p>
      <article className="page-sheet">
        <div className="pp-kicker">LilyAI</div>
        <h1>Terms of Service</h1>
        <p className="pp-updated">Last updated: 30 June 2026</p>
        <div className="pp-rule" />

        <p>
          These Terms of Service (&ldquo;Terms&rdquo;) govern your access to and use of LilyAI (the
          &ldquo;Service&rdquo;). By creating an account or using the Service, you agree to be bound by
          these Terms.
        </p>

        <h2>1. Your account</h2>
        <p>
          You must provide accurate information when registering and are responsible for maintaining
          the confidentiality of your account. You must be at least 18 years old, or the age of legal
          majority in your jurisdiction, to use the Service.
        </p>

        <h2>2. Acceptable use</h2>
        <ul>
          <li>Do not upload content you do not have the right to use.</li>
          <li>Do not use the Service to violate any law or infringe the rights of others.</li>
          <li>Do not attempt to disrupt, reverse engineer, or gain unauthorised access to the Service.</li>
        </ul>

        <h2>3. Your content</h2>
        <p>
          You retain ownership of the documents and content you upload. You grant us a limited licence
          to process that content solely to provide the Service to you, including text extraction,
          indexing, and generating answers.
        </p>

        <h2>4. AI-generated output</h2>
        <p>
          The Service uses AI models to generate answers from your documents. Output may be inaccurate
          or incomplete and is provided for informational purposes only. You are responsible for
          reviewing and verifying any output before relying on it.
        </p>

        <h2>5. Subscriptions and limits</h2>
        <p>
          Access to certain features and usage levels depends on your subscription plan. Free-tier and
          paid-plan limits, including query and storage limits, apply as described in the Service.
        </p>

        <h2>6. Termination</h2>
        <p>
          You may stop using the Service at any time. We may suspend or terminate your access if you
          breach these Terms. On termination, your right to use the Service ends.
        </p>

        <h2>7. Disclaimers and liability</h2>
        <p>
          The Service is provided &ldquo;as is&rdquo; without warranties of any kind. To the maximum
          extent permitted by law, we are not liable for any indirect or consequential loss arising
          from your use of the Service.
        </p>

        <h2>8. Changes</h2>
        <p>
          We may update these Terms from time to time. We will notify you of material changes, and your
          continued use of the Service after changes take effect constitutes acceptance.
        </p>

        <h2>9. Contact</h2>
        <p>For questions about these Terms, contact us at legal@lilyai.dev.</p>
      </article>
    </>
  )
}
