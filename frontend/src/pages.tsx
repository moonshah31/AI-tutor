import { FormEvent, useEffect, useState } from "react";
import {
  Link,
  Navigate,
  useNavigate,
  useParams,
} from "react-router-dom";
import ReactMarkdown from "react-markdown";

import { useAuth } from "./auth/AuthContext";
import { DocumentsPanel } from "./DocumentsPanel";
import { register } from "./services/auth";
import {
  ChatApiError,
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  sendChatMessage,
  updateConversationTitle,
  type ChatMessage,
  type Conversation,
  type ConversationSummary,
} from "./services/chat";

import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";


function AuthForm({
  registerMode = false,
}: {
  registerMode?: boolean;
}) {
  const navigate = useNavigate();
  const { user, login } = useAuth();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");

    if (registerMode && password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);

    try {
      if (registerMode) {
        await register(name, email, password);
      }

      await login(email, password);
      navigate("/dashboard");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Something went wrong.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="auth-layout">
        <div className="auth-intro">
          <Link className="brand-lockup" to="/">
            <span className="brand-mark" aria-hidden="true">A</span>
            <span>Learnwell <small>AI TUTOR</small></span>
          </Link>
          <p className="eyebrow">A smarter way to study</p>
          <h1>Make every question a step forward.</h1>
          <p>Build understanding with a tutor that explains, guides, and learns alongside you.</p>
          <div className="auth-highlight"><span aria-hidden="true">✦</span> Clear explanations. Your pace. Your progress.</div>
        </div>

        <section className="auth-card">
          <p className="eyebrow">{registerMode ? "Get started" : "Your learning space"}</p>

        <h1>
          {registerMode
            ? "Create your account"
            : "Welcome back"}
        </h1>

        <p className="lead">
          {registerMode
            ? "Start learning with guidance that builds understanding."
            : "Sign in to continue learning."}
        </p>

        <form onSubmit={submit} noValidate>
          {registerMode && (
            <label>
              Name

              <input
                value={name}
                onChange={(event) =>
                  setName(event.target.value)
                }
                required
                minLength={1}
                maxLength={100}
              />
            </label>
          )}

          <label>
            Email

            <input
              type="email"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              required
            />
          </label>

          <label>
            Password

            <input
              type="password"
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              required
              minLength={registerMode ? 8 : 1}
            />
          </label>

          {registerMode && (
            <label>
              Confirm password

              <input
                type="password"
                value={confirm}
                onChange={(event) =>
                  setConfirm(event.target.value)
                }
                required
              />
            </label>
          )}

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <button disabled={busy}>
            {busy
              ? "Please wait…"
              : registerMode
                ? "Create account"
                : "Log in"}
          </button>
        </form>

        <p>
          {registerMode
            ? "Already have an account?"
            : "New to AI Tutor?"}{" "}

          <Link
            to={
              registerMode
                ? "/login"
                : "/register"
            }
          >
            {registerMode ? "Log in" : "Create one"}
          </Link>
        </p>
        </section>
      </section>
    </main>
  );
}


export const LoginPage = () => <AuthForm />;

export const RegisterPage = () => (
  <AuthForm registerMode />
);


export function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <main className="page-shell">
      <header className="dashboard-topbar">
        <Link className="brand-lockup" to="/">
          <span className="brand-mark" aria-hidden="true">A</span>
          <span>Learnwell <small>AI TUTOR</small></span>
        </Link>
        <button className="secondary-button" onClick={() => { logout(); navigate("/login"); }}>Log out</button>
      </header>

      <section className="dashboard-hero">
        <div className="dashboard-copy">
          <p className="eyebrow">Your learning space</p>
          <h1>Welcome back, {user?.name?.split(" ")[0] ?? "there"}.</h1>
          <p className="lead">Pick up where curiosity takes you. Your AI tutor is ready to explain concepts, work through problems, and help you build lasting understanding.</p>
          <button className="primary-cta" onClick={() => navigate("/tutor")}>Open your tutor <span aria-hidden="true">→</span></button>
        </div>
        <div className="dashboard-art" aria-hidden="true">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" />
          <div className="learning-card"><span>✦</span><strong>Learn with confidence</strong><small>One thoughtful question at a time</small></div>
        </div>
      </section>

      <section className="dashboard-features" aria-label="Ways to learn">
        <article className="feature-card"><span className="feature-icon">✦</span><div><h2>Ask anything</h2><p>Get clear explanations tailored to the way you learn.</p></div></article>
        <article className="feature-card"><span className="feature-icon">↗</span><div><h2>Work it through</h2><p>Take problems one step at a time with your tutor by your side.</p></div></article>
        <article className="feature-card"><span className="feature-icon">▤</span><div><h2>Learn from your notes</h2><p>Bring course materials into the tutor workspace when you need them.</p></div></article>
      </section>
    </main>
  );
}


const suggestedPrompts = [
  "Explain recursion",
  "Help me solve this algorithm problem",
  "Simplify this concept",
  "Give me an example",
];


export function TutorPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { conversationId } = useParams<{
    conversationId?: string;
  }>();

  const [conversations, setConversations] = useState<
    ConversationSummary[]
  >([]);

  const [currentConversation, setCurrentConversation] =
    useState<Conversation | null>(null);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [loadingConversations, setLoadingConversations] =
    useState(true);

  const [loadingConversation, setLoadingConversation] =
    useState(false);

  const [busy, setBusy] = useState(false);

  /*
   * Load the conversation list whenever the user
   * enters the tutor area.
   */
  useEffect(() => {
    async function loadConversationList() {
      try {
        setLoadingConversations(true);
        setError("");

        let items = await listConversations();

        /*
         * New users need one conversation to start with.
         */
        if (items.length === 0) {
          const created =
            await createConversation();

          items = [
            {
              id: created.id,
              title: created.title,
              created_at: created.created_at,
              updated_at: created.updated_at,
              message_count:
                created.messages.length,
            },
          ];
        }

        setConversations(items);

        /*
         * If there is no conversation ID in the URL,
         * send the user to the first conversation.
         */
        if (!conversationId) {
          navigate(
            `/tutor/${items[0].id}`,
            { replace: true },
          );

          return;
        }
      } catch (reason) {
        if (
          reason instanceof ChatApiError &&
          reason.status === 401
        ) {
          logout();
          navigate("/login", {
            replace: true,
          });

          return;
        }

        setError(
          reason instanceof Error
            ? reason.message
            : "Could not load your conversations.",
        );
      } finally {
        setLoadingConversations(false);
      }
    }

    void loadConversationList();
  }, [
    conversationId,
    logout,
    navigate,
  ]);

  /*
   * Load whichever conversation is represented
   * by the current URL.
   *
   * This makes refresh and browser navigation work.
   */
  useEffect(() => {
    if (
      !conversationId ||
      loadingConversations
    ) {
      return;
    }

    async function loadConversation() {
  if (!conversationId) {
    return;
  }

  try {
    setLoadingConversation(true);
    setError("");

    const conversation =
      await getConversation(
        conversationId,
      );

        setCurrentConversation(
          conversation,
        );
      } catch (reason) {
        if (
          reason instanceof ChatApiError &&
          reason.status === 401
        ) {
          logout();

          navigate("/login", {
            replace: true,
          });

          return;
        }

        /*
         * If the URL points to a conversation that
         * doesn't exist or doesn't belong to the user,
         * fall back to the first valid conversation.
         */
        if (
          reason instanceof ChatApiError &&
          reason.status === 404
        ) {
          const fallback =
            conversations[0];

          if (fallback) {
            navigate(
              `/tutor/${fallback.id}`,
              { replace: true },
            );
          }

          return;
        }

        setError(
          reason instanceof Error
            ? reason.message
            : "Could not load the conversation.",
        );
      } finally {
        setLoadingConversation(false);
      }
    }

    void loadConversation();
  }, [
    conversationId,
    conversations,
    loadingConversations,
    logout,
    navigate,
  ]);

  async function selectConversation(
    selectedConversationId: string,
  ) {
    if (
      selectedConversationId ===
        conversationId ||
      loadingConversation ||
      busy
    ) {
      return;
    }

    navigate(
      `/tutor/${selectedConversationId}`,
    );
  }

  async function handleNewConversation() {
    if (busy) {
      return;
    }

    try {
      setError("");

      const conversation =
        await createConversation();

      setConversations((current) => [
        {
          id: conversation.id,
          title: conversation.title,
          created_at:
            conversation.created_at,
          updated_at:
            conversation.updated_at,
          message_count: 0,
        },
        ...current,
      ]);

      navigate(
        `/tutor/${conversation.id}`,
      );
    } catch (reason) {
      if (
        reason instanceof ChatApiError &&
        reason.status === 401
      ) {
        logout();

        navigate("/login", {
          replace: true,
        });

        return;
      }

      setError(
        reason instanceof Error
          ? reason.message
          : "Could not create a new conversation.",
      );
    }
  }

  async function handleRenameConversation() {
    if (
      !currentConversation ||
      busy
    ) {
      return;
    }

    const title = window.prompt(
      "Enter a new conversation title:",
      currentConversation.title,
    );

    if (
      title === null ||
      !title.trim()
    ) {
      return;
    }

    try {
      setError("");

      const updated =
        await updateConversationTitle(
          currentConversation.id,
          title.trim(),
        );

      setCurrentConversation(updated);

      setConversations((current) =>
        current.map((conversation) =>
          conversation.id ===
          updated.id
            ? {
                ...conversation,
                title: updated.title,
                updated_at:
                  updated.updated_at,
              }
            : conversation,
        ),
      );
    } catch (reason) {
      if (
        reason instanceof ChatApiError &&
        reason.status === 401
      ) {
        logout();

        navigate("/login", {
          replace: true,
        });

        return;
      }

      setError(
        reason instanceof Error
          ? reason.message
          : "Could not rename the conversation.",
      );
    }
  }

  async function handleDeleteConversation() {
    if (
      !currentConversation ||
      busy
    ) {
      return;
    }

    const confirmed = window.confirm(
      "Delete this conversation? This cannot be undone.",
    );

    if (!confirmed) {
      return;
    }

    try {
      setError("");

      const deletedId =
        currentConversation.id;

      await deleteConversation(
        deletedId,
      );

      const remaining =
        conversations.filter(
          (conversation) =>
            conversation.id !==
            deletedId,
        );

      /*
       * Always keep the user inside the tutor.
       * If the deleted conversation was the last
       * one, create a fresh conversation.
       */
      if (remaining.length === 0) {
        const created =
          await createConversation();

        setConversations([
          {
            id: created.id,
            title: created.title,
            created_at:
              created.created_at,
            updated_at:
              created.updated_at,
            message_count: 0,
          },
        ]);

        setCurrentConversation(
          created,
        );

        navigate(
          `/tutor/${created.id}`,
          { replace: true },
        );

        return;
      }

      setConversations(remaining);

      /*
       * Prefer the next conversation in the list.
       */
      const nextConversation =
        remaining[0];

      navigate(
        `/tutor/${nextConversation.id}`,
        { replace: true },
      );
    } catch (reason) {
      if (
        reason instanceof ChatApiError &&
        reason.status === 401
      ) {
        logout();

        navigate("/login", {
          replace: true,
        });

        return;
      }

      setError(
        reason instanceof Error
          ? reason.message
          : "Could not delete the conversation.",
      );
    }
  }

  async function send(text = message) {
    const trimmed = text.trim();

    if (
      !trimmed ||
      busy ||
      !currentConversation
    ) {
      return;
    }

    const activeConversationId =
      currentConversation.id;

    setMessage("");
    setError("");
    setBusy(true);

    const optimisticUserMessage: ChatMessage = {
      role: "user",
      content: trimmed,
    };

    setCurrentConversation((current) =>
      current
        ? {
            ...current,
            messages: [
              ...current.messages,
              optimisticUserMessage,
            ],
          }
        : current,
    );

    try {
      const result =
        await sendChatMessage(
          activeConversationId,
          trimmed,
        );

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: result.response,
      };

      setCurrentConversation((current) =>
        current
          ? {
              ...current,
              messages: [
                ...current.messages,
                assistantMessage,
              ],
            }
          : current,
      );

      setConversations((current) =>
        current.map((conversation) =>
          conversation.id ===
          activeConversationId
            ? {
                ...conversation,
                message_count:
                  conversation.message_count +
                  2,
                updated_at:
                  new Date().toISOString(),
              }
            : conversation,
        ),
      );
    } catch (reason) {
      if (
        reason instanceof ChatApiError &&
        reason.status === 401
      ) {
        logout();

        navigate("/login", {
          replace: true,
        });

        return;
      }

      setError(
        reason instanceof Error
          ? reason.message
          : "The tutor could not complete your request.",
      );

      /*
       * MongoDB is authoritative, so recover the
       * conversation from the backend after a failure.
       */
      try {
        const refreshed =
          await getConversation(
            activeConversationId,
          );

        setCurrentConversation(
          refreshed,
        );
      } catch {}
    } finally {
      setBusy(false);
    }
  }

  const messages =
    currentConversation?.messages ?? [];

  return (
    <main className="tutor-shell">
      <aside className="conversation-sidebar">
        <div className="conversation-sidebar-header">
          <div>
            <p className="eyebrow">
              AI Tutor · {user?.name ?? "Student"}
            </p>

            <h2>
              Conversations
            </h2>
          </div>

          <button
            className="secondary-button"
            onClick={() =>
              void handleNewConversation()
            }
            disabled={busy}
          >
            New
          </button>
        </div>

        {loadingConversations ? (
          <p>
            Loading conversations…
          </p>
        ) : (
          <div className="conversation-list">
            {conversations.map(
              (conversation) => (
                <button
                  key={conversation.id}
                  className={`conversation-item ${
                    conversation.id ===
                    conversationId
                      ? "active"
                      : ""
                  }`}
                  onClick={() =>
                    void selectConversation(
                      conversation.id,
                    )
                  }
                  disabled={
                    loadingConversation ||
                    busy
                  }
                >
                  <strong>
                    {conversation.title}
                  </strong>

                  <span>
                    {
                      conversation.message_count
                    }{" "}
                    messages
                  </span>
                </button>
              ),
            )}
          </div>
        )}
      </aside>

      <section className="chat-main">
        <header className="tutor-header">
          <div>
            <p className="eyebrow">
              AI Tutor
            </p>

            <h1>
              {currentConversation?.title ??
                "Learn with confidence."}
            </h1>
          </div>

          <div>
            {currentConversation && (
              <>
                <button
                  className="secondary-button"
                  onClick={() =>
                    void handleRenameConversation()
                  }
                  disabled={busy}
                >
                  Rename
                </button>

                <button
                  className="secondary-button"
                  onClick={() =>
                    void handleDeleteConversation()
                  }
                  disabled={busy}
                >
                  Delete
                </button>
              </>
            )}

            <button
              className="secondary-button"
              onClick={() =>
                navigate("/dashboard")
              }
            >
              Dashboard
            </button>

            <button
              className="secondary-button"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Log out
            </button>
          </div>
        </header>

        <div className="tutor-workspace">
        <section
          className="chat-card"
          aria-label="Tutor chat"
        >
          <div
            className="message-list"
            aria-live="polite"
          >
            {messages.length === 0 ? (
              <div className="empty-chat">
                <h2>
                  Hi! I’m your AI Tutor.
                </h2>

                <p>
                  What would you like to
                  learn today?
                </p>

                <div className="suggestions">
                  {suggestedPrompts.map(
                    (prompt) => (
                      <button
                        key={prompt}
                        className="suggestion"
                        onClick={() =>
                          void send(prompt)
                        }
                        disabled={
                          busy ||
                          !currentConversation
                        }
                      >
                        {prompt}
                      </button>
                    ),
                  )}
                </div>
              </div>
            ) : (
              messages.map(
                (item, index) => (
                  <article
                    className={`message ${item.role}`}
                    key={`${item.role}-${index}`}
                  >
                    <span>
                      {item.role ===
                      "user"
                        ? "You"
                        : "Tutor"}
                    </span>

                    <div className="message-content">
                      {item.role ===
                      "assistant" ? (
                        <div className="prose prose-slate max-w-none text-slate-800 prose-headings:font-bold prose-headings:text-slate-900 prose-headings:mt-4 prose-headings:mb-2 prose-p:my-2 prose-ul:my-2 prose-table:my-4 prose-strong:text-slate-900">
                          <ReactMarkdown
                            remarkPlugins={[
                              remarkGfm,
                              remarkMath,
                            ]}
                            rehypePlugins={[
                              rehypeKatex,
                            ]}
                          >
                            {
                              item.content
                            }
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <p>
                          {item.content}
                        </p>
                      )}
                    </div>
                  </article>
                ),
              )
            )}

            {busy && (
              <article className="message assistant">
                <span>
                  Tutor
                </span>

                <p>
                  Thinking…
                </p>
              </article>
            )}
          </div>

          {error && (
            <p
              className="form-error chat-error"
              role="alert"
            >
              {error}
            </p>
          )}

          <form
            className="chat-form"
            onSubmit={(event) => {
              event.preventDefault();
              void send();
            }}
          >
            <label
              className="sr-only"
              htmlFor="tutor-message"
            >
              Ask the tutor
            </label>

            <textarea
              id="tutor-message"
              value={message}
              onChange={(event) =>
                setMessage(
                  event.target.value,
                )
              }
              placeholder="Ask a question…"
              maxLength={4000}
              disabled={
                busy ||
                !currentConversation
              }
              rows={3}
            />

            <button
              disabled={
                busy ||
                !message.trim() ||
                !currentConversation
              }
            >
              {busy
                ? "Sending…"
                : "Send"}
            </button>
          </form>
        </section>
        <DocumentsPanel />
        </div>
      </section>
    </main>
  );
}
