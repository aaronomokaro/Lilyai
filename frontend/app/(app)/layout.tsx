import { redirect } from 'next/navigation'
import { auth0 } from '@/lib/auth0'
import { AppShell } from '@/components/layout/AppShell'
import { WebSocketProvider } from '@/components/layout/WebSocketProvider'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth0.getSession()

  if (!session) {
    redirect('/auth/login')
  }

  const { user } = session
  const name = user.name ?? user.email ?? 'User'
  const initials = name.charAt(0).toUpperCase()

  // sub is the Auth0 user ID — used for the WebSocket connection
  const userId = user.sub

  return (
    <WebSocketProvider userId={userId}>
      <AppShell userName={name} initials={initials}>
        {children}
      </AppShell>
    </WebSocketProvider>
  )
}
