export type createDocument = {
  document_name: string; // matches Form parameter name in FastAPI
}

export type spawnResponse = {
  ok: boolean;
  user: string;
  nextUrl: string;
  message: string;
}

export type DocumentInfo = {
  name: string;
  path: string;
  relative_path: string;  // Path relative to user home directory (e.g., "apps/notebook.py")
  size: number;
  modified: number;
}

export type ListDocumentsResponse = {
  ok: boolean;
  documents: DocumentInfo[];
  message: string;
}

export type GetDocumentResponse = {
  ok: boolean;
  name: string;
  content: string;
  path: string;
}

export type ServerInfo = {
  name: string;
  ready: boolean;
  pending?: any;
  url?: string;
  progress_url?: string;
  started?: string;
  last_activity?: string;
  state?: string;
}

export type UserServersResponse = {
  ok: boolean;
  user_exists: boolean;
  servers: ServerInfo[];
  message: string;
  username?: string;
  server_count?: number;
}

export type ServerStatusResponse = {
  ok: boolean;
  server_exists: boolean;
  server?: ServerInfo;
  message: string;
}

export type MyServersStatusResponse = {
  ok: boolean;
  has_servers: boolean;
  has_running_servers: boolean;
  total_servers: number;
  running_servers_count: number;
  running_servers: Array<{
    name: string;
    url?: string;
    started?: string;
  }>;
  message: string;
}