import { authenticatedFetch } from "./chat";

export type DocumentStatus =
  | "uploaded"
  | "processing"
  | "ready"
  | "failed";

export type TutorDocument = {
  id: string;
  original_filename: string;
  content_type: string;
  file_extension: string;
  file_size: number;
  status: DocumentStatus;
  processing_error: string | null;
  section_count: number;
  created_at: string;
  updated_at: string;
};

export async function uploadDocument(file: File): Promise<TutorDocument> {
  const form = new FormData();
  form.append("file", file);

  const response = await authenticatedFetch("/api/documents", {
    method: "POST",
    body: form,
  });

  return response.json() as Promise<TutorDocument>;
}

export async function listDocuments(): Promise<TutorDocument[]> {
  const response = await authenticatedFetch("/api/documents");
  return response.json() as Promise<TutorDocument[]>;
}

export async function getDocument(documentId: string): Promise<TutorDocument> {
  const response = await authenticatedFetch(
    `/api/documents/${encodeURIComponent(documentId)}`,
  );

  return response.json() as Promise<TutorDocument>;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await authenticatedFetch(
    `/api/documents/${encodeURIComponent(documentId)}`,
    { method: "DELETE" },
  );
}
