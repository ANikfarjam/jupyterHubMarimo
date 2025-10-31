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