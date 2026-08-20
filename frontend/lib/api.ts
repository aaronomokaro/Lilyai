import type { Document, QueryRequest, QueryResult, UsageStats, Output, Tag, Conversation, ConversationTurn, IntegrationStatus } from '@/types/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL

async function getToken(): Promise<string> {
  const res = await fetch('/api/auth/token')
  if (!res.ok) throw new Error('Not authenticated')
  const { token } = await res.json()
  return token
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken()
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API ${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

// Documents
// NOTE: collection roots use a trailing slash to match the FastAPI routes
// (`@router.get("/")`). Calling them without it triggers a 307 redirect that
// the browser refuses to follow on an authorized CORS request.
export const documents = {
  list: () => request<Document[]>('/documents/'),

  upload: async (file: File): Promise<{ id: string; status: string }> => {
    const token = await getToken()
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API_URL}/documents/upload`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        // Backend requires a unique key per upload to prevent double-processing
        'Idempotency-Key': crypto.randomUUID(),
      },
      body: form,
    })
    if (!res.ok) {
      const body = await res.text()
      throw new Error(`Upload failed ${res.status}: ${body}`)
    }
    return res.json()
  },

  delete: (id: string) =>
    request<void>(`/documents/${id}`, { method: 'DELETE' }),

  get: (id: string) =>
    request<Document>(`/documents/${id}`),
}

// Queries
export const queries = {
  ask: (body: QueryRequest) =>
    request<QueryResult>('/queries/ask', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

// Conversations
export const conversations = {
  list: () => request<Conversation[]>('/conversations/'),
  get: (id: string) => request<ConversationTurn[]>(`/conversations/${id}/messages`),
}

// Usage
export const usage = {
  get: () => request<UsageStats>('/usage/'),
}

// Tags
export const tags = {
  list: () => request<Tag[]>('/tags/'),
  create: (name: string, color?: string) =>
    request<Tag>('/tags/', { method: 'POST', body: JSON.stringify({ name, color }) }),
}

// Outputs
export const outputs = {
  list: () => request<Output[]>('/outputs/'),
}

// Integrations
export const integrations = {
  status: () => request<IntegrationStatus>('/integrations/status'),
  connect: (provider: 'gmail' | 'drive') =>
    request<{ oauth_url: string; provider: string }>(`/integrations/${provider}/connect`),
}
