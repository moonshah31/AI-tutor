import { storedToken } from "./auth";
import { apiUrl } from "./api";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
};

export type ChatResponse = {
  response: string;
  provider: string;
};

export class ChatApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ChatApiError";
  }
}

export async function authenticatedFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = storedToken();

  if (!token) {
    throw new ChatApiError(
      "Your session has ended. Please log in again.",
      401,
    );
  }

  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(apiUrl(path), {
      ...options,
      headers,
    });

    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as {
        detail?: string;
      } | null;

      throw new ChatApiError(
        body?.detail ||
          "The request could not be completed. Please try again.",
        response.status,
      );
    }

    return response;
  } catch (error) {
    if (error instanceof ChatApiError) {
      throw error;
    }

    throw new ChatApiError(
      "Network error. Check that the API is running and try again.",
    );
  }
}

export async function listConversations(): Promise<
  ConversationSummary[]
> {
  const response = await authenticatedFetch("/api/conversations");

  return response.json() as Promise<ConversationSummary[]>;
}

export async function createConversation(
  title = "New Conversation",
): Promise<Conversation> {
  const response = await authenticatedFetch("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });

  return response.json() as Promise<Conversation>;
}

export async function getConversation(
  conversationId: string,
): Promise<Conversation> {
  const response = await authenticatedFetch(
    `/api/conversations/${conversationId}`,
  );

  return response.json() as Promise<Conversation>;
}

export async function updateConversationTitle(
  conversationId: string,
  title: string,
): Promise<Conversation> {
  const response = await authenticatedFetch(
    `/api/conversations/${conversationId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ title }),
    },
  );

  return response.json() as Promise<Conversation>;
}

export async function deleteConversation(
  conversationId: string,
): Promise<void> {
  await authenticatedFetch(
    `/api/conversations/${conversationId}`,
    {
      method: "DELETE",
    },
  );
}

export async function sendChatMessage(
  conversationId: string,
  message: string,
): Promise<ChatResponse> {
  const response = await authenticatedFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
    }),
  });

  return response.json() as Promise<ChatResponse>;
}
