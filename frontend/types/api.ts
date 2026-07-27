export interface Document {
  id: string
  filename: string
  original_filename: string
  file_type: string
  file_size_bytes: number
  page_count: number | null
  status: 'pending' | 'processing' | 'ready' | 'failed'
  doc_type: string | null
  created_at: string
  updated_at: string
  tags?: Tag[]
}

export interface Tag {
  id: string
  name: string
  color: string | null
}

export interface Collection {
  id: string
  name: string
  description: string | null
  parent_id: string | null
  created_at: string
}

export interface Conversation {
  id: string
  title: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface ConversationTurn {
  id: string
  role: 'user' | 'assistant'
  content: string
  turn_index: number
  created_at: string
}

export interface QueryRequest {
  question: string
  conversation_id?: string
  document_ids?: string[]
}

export interface QueryResult {
  status: string
  intent?: string
  requires_confirmation?: boolean
  message?: string
}

export interface Output {
  id: string
  title: string
  output_type: string
  content: string
  created_at: string
}

export interface UsageStats {
  queries_today: number
  queries_month: number
  documents_count: number
  storage_bytes: number
  plan: string
  limits: {
    queries_per_day: number
    queries_per_month: number
    max_documents: number
    storage_limit_mb: number
  }
}

export interface Citation {
  document_id: string
  filename: string
  page_number: number
  chunk_index: number
  text: string
}

export interface IntegrationState {
  connected: boolean
  available: boolean
}

export interface IntegrationStatus {
  gmail: IntegrationState
  drive: IntegrationState
}

export type WsEvent =
  | { event: 'orchestrator_progress'; step: string; intent?: string }
  | { event: 'query_token'; token: string; query_id: string }
  | { event: 'query_complete'; query_id: string; citations: Citation[] }
