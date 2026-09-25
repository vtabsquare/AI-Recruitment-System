import { useEffect, useMemo, useState } from "react";
import "./App.css";

const COMPANY = {
  name: "VTAB SQUARE",
  agent: "VTAB AI AGENT",
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function apiRequest(path, options = {}, token = null) {
  const headers = {
    Accept: "application/json",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  let data = null;
  const text = await response.text();

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      `Request failed with HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return data;
}

function App() {
  // Candidate document links arrive as:
  // http://localhost:5173/documents?token=<secure-token>
  // Detect that route before rendering the normal AI OS.
  const documentToken = useMemo(() => {
    if (typeof window === "undefined") return "";
    if (window.location.pathname !== "/documents") return "";
    return new URLSearchParams(window.location.search).get("token") || "";
  }, []);

  const recoveryToken = useMemo(() => {
    if (typeof window === "undefined") return "";
    // Normalize hash: split on all '#' and join with '&' so '#type=recovery#access_token=xyz' is parsed cleanly
    const fullHash = (window.location.hash || "").replace(/^#+/, "");
    const normalizedHash = fullHash.replace(/#/g, "&");
    const hashParams = new URLSearchParams(normalizedHash);
    const searchParams = new URLSearchParams(window.location.search);

    const token =
      hashParams.get("access_token") ||
      searchParams.get("token") ||
      hashParams.get("token") ||
      searchParams.get("access_token") ||
      "";

    if (token && token !== "active") return token;

    // Direct regex extraction fallback in case of non-standard query/hash encoding
    const match = window.location.href.match(/[?&#](?:access_token|token)=([^&#]+)/);
    if (match && match[1] && match[1] !== "active") {
      return decodeURIComponent(match[1]);
    }
    return "";
  }, []);

  const isResetScreen = useMemo(() => {
    if (typeof window === "undefined") return false;
    const path = window.location.pathname || "";
    const hash = window.location.hash || "";
    const search = window.location.search || "";
    return (
      Boolean(recoveryToken) ||
      path === "/reset-password" ||
      hash.includes("type=recovery") ||
      search.includes("type=recovery") ||
      hash.includes("reset-password")
    );
  }, [recoveryToken]);

  const [screen, setScreen] = useState(() => (isResetScreen ? "reset-password" : "home"));
  const [resetToken, setResetToken] = useState(recoveryToken);
  const [menuOpen, setMenuOpen] = useState(false);
  const [portal, setPortal] = useState(null);
  const [session, setSession] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem("vtab_session") || "null");
    } catch {
      return null;
    }
  });

  const go = (next) => {
    setScreen(next);
    setMenuOpen(false);
  };

  const openPortal = (type) => {
    setPortal(type);
    setScreen("login");
    setMenuOpen(false);
  };

  const handleLogin = (loginResult) => {
    setSession(loginResult);
    try {
      sessionStorage.setItem("vtab_session", JSON.stringify(loginResult));
    } catch {
      // Session storage can fail in restrictive browser environments.
    }
    const userRole = String(loginResult?.staff?.role || "").toLowerCase();
    go(userRole === "manager" ? "manager" : "hr");
  };

  const handleLogout = async () => {
    const currentToken = session?.access_token;
    try {
      if (currentToken) {
        await apiRequest("/api/auth/logout", { method: "POST" }, currentToken);
      }
    } catch (err) {
      console.warn("Server logout notification failed:", err);
    } finally {
      setSession(null);
      try {
        sessionStorage.removeItem("vtab_session");
      } catch {
        // Ignore storage cleanup failures.
      }
      go("home");
    }
  };

  const handleAuthError = (error) => {
    if (error?.status === 401) {
      handleLogout();
    }
  };

  if (documentToken) {
    return <DocumentSubmission token={documentToken} />;
  }

  return (
    <div className="app-shell">
      <Background />

      <header className="site-header">
        <button
          className="menu-trigger"
          onClick={() => setMenuOpen(true)}
          aria-label="Open menu"
          aria-expanded={menuOpen}
          aria-controls="site-navigation"
        >
          <span />
          <span />
          <span />
        </button>

        <button className="brand-button" onClick={() => go("home")}>
          <span className="brand-v">V</span>
          <span>
            <b>{COMPANY.name}</b>
            <small>{COMPANY.agent}</small>
          </span>
        </button>

        <div className="system-pill">
          <i /> AI SYSTEM ONLINE
        </div>
      </header>

      {screen === "home" && <Home onAsk={() => go("candidate-ai")} />}

      {screen === "candidate-ai" && (
        <CandidateAI onBack={() => go("home")} />
      )}

      {screen === "login" && (
        <Login
          portal={portal}
          onBack={() => go("home")}
          onLogin={handleLogin}
          onForgotPassword={() => go("forgot-password")}
        />
      )}

      {screen === "forgot-password" && (
        <ForgotPassword
          portal={portal}
          onBack={() => go(portal ? "login" : "home")}
          onLoginClick={() => go("login")}
        />
      )}

      {screen === "reset-password" && (
        <ResetPassword
          token={resetToken}
          onBack={() => go("home")}
          onGoToForgot={() => go("forgot-password")}
          onSuccess={() => {
            if (typeof window !== "undefined" && window.history && window.history.replaceState) {
              window.history.replaceState(null, "", window.location.pathname);
            }
            setResetToken("");
            go("login");
          }}
        />
      )}

      {screen === "manager" && String(session?.staff?.role || "").toLowerCase() === "manager" && (
        <ManagerPortal
          session={session}
          onHome={handleLogout}
          onAuthError={handleAuthError}
        />
      )}

      {screen === "hr" && String(session?.staff?.role || "").toLowerCase() === "hr" && (
        <HRPortal
          session={session}
          onHome={handleLogout}
          onAuthError={handleAuthError}
        />
      )}

      {menuOpen && (
        <Menu
          onClose={() => setMenuOpen(false)}
          onHome={() => go("home")}
          onManager={() => openPortal("manager")}
          onHR={() => openPortal("hr")}
        />
      )}
    </div>
  );
}

function Background() {
  return (
    <div className="ambient" aria-hidden="true">
      <div className="ambient-grid" />
      <div className="ambient-glow glow-one" />
      <div className="ambient-glow glow-two" />
      <div className="ambient-orbit orbit-one" />
      <div className="ambient-orbit orbit-two" />
    </div>
  );
}

function Home({ onAsk }) {
  return (
    <main className="home-page" id="main-content">
      <section className="hero-copy">
        <div className="eyebrow">
          <span className="eyebrow-dot" /> AUTONOMOUS RECRUITMENT INTELLIGENCE
        </div>
        <h1>
          Meet the future of
          <br />
          <em>intelligent hiring.</em>
        </h1>
        <p>
          VTAB AI coordinates recruitment from application to onboarding,
          while keeping human decisions exactly where they belong.
        </p>
        <a
          href="https://www.vtabsquare.com/?demo=1&product=ai-recruitment-system&source=ai-recruitment-demo"
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: "inline-flex", alignItems: "center", gap: 8, marginTop: 20, color: "inherit", fontWeight: 700, textDecoration: "underline", textUnderlineOffset: 5 }}
        >
          Contact for Demo <span aria-hidden="true">↗</span>
        </a>
      </section>

      <button
        className="magic-ball"
        onClick={onAsk}
        aria-label="Open candidate AI assistant"
      >
        <span className="ball-ring ring-a" />
        <span className="ball-ring ring-b" />
        <span className="ball-ring ring-c" />
        <span className="ball-core">
          <span>V</span>
        </span>
        <span className="ball-label">ASK VTAB AI</span>
      </button>

      <section className="home-footer">
        <div>
          <span className="footer-key">01</span>
          <span>Resume intelligence</span>
        </div>
        <div>
          <span className="footer-key">02</span>
          <span>Interview orchestration</span>
        </div>
        <div>
          <span className="footer-key">03</span>
          <span>Human-led decisions</span>
        </div>
      </section>
    </main>
  );
}

function Menu({ onClose, onHome, onManager, onHR }) {
  return (
    <div className="menu-overlay" onClick={onClose}>
      <aside
        className="side-drawer"
        id="site-navigation"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="drawer-head">
          <div className="drawer-brand">
            <span className="brand-v">V</span>
            <div>
              <b>VTAB SQUARE</b>
              <small>AI RECRUITMENT OS</small>
            </div>
          </div>
          <button className="close-button" onClick={onClose} aria-label="Close navigation menu">
            ×
          </button>
        </div>

        <button className="drawer-home" onClick={onHome}>
          <span>⌂</span> Home
        </button>

        <div className="drawer-label">ENTERPRISE PORTALS</div>

        <button className="portal-card" onClick={onManager}>
          <span className="portal-icon">◈</span>
          <span>
            <b>Manager Login</b>
            <small>Interview evaluation & approvals</small>
          </span>
          <strong>→</strong>
        </button>

        <button className="portal-card" onClick={onHR}>
          <span className="portal-icon">◇</span>
          <span>
            <b>HR Login</b>
            <small>Verification, offer letters & onboarding</small>
          </span>
          <strong>→</strong>
        </button>

        <div className="drawer-note">
          <i /> Candidate access is through the AI assistant. No candidate
          portal login is required.
        </div>
      </aside>
    </div>
  );
}

function Login({ portal, onBack, onLogin, onForgotPassword }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const title = portal === "manager" ? "Manager Portal" : "HR Operations";
  const subtitle =
    portal === "manager"
      ? "Interview evaluation & hiring approvals"
      : "Verification, offer letters & onboarding";

  const submit = async (event) => {
    event.preventDefault();

    if (!email.trim() || !password) {
      setError("Enter both your company email and password.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await apiRequest("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      if (!result?.success || !result?.access_token || !result?.staff) {
        throw new Error("Authentication response is incomplete.");
      }

      const expectedRole = portal === "manager" ? "manager" : "hr";
      const actualRole = String(result.staff.role || "").toLowerCase();

      if (actualRole !== expectedRole) {
        throw new Error(
          `This account is registered as ${result.staff.role}, not ${expectedRole}.`
        );
      }

      onLogin(result);
    } catch (err) {
      setError(err.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="center-page" id="main-content">
      <button className="back-link" onClick={onBack}>
        ← Back to AI OS
      </button>

      <div className="login-card">
        <div className="login-mark">V</div>
        <div className="eyebrow">VTAB SQUARE / SECURE ACCESS</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>

        <form onSubmit={submit}>
          <label>
            EMAIL / USER ID
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Enter your company email"
              autoComplete="username"
            />
          </label>

          <label>
            PASSWORD
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </label>

          <div className="login-card-links">
            <button
              type="button"
              className="login-link"
              onClick={onForgotPassword}
            >
              Forgot password?
            </button>
          </div>

          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}

          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "AUTHENTICATING..." : "ENTER PORTAL"}
            <span>→</span>
          </button>
        </form>

        <div className="login-security">
          <i /> Authenticated enterprise access
        </div>
      </div>
    </main>
  );
}

function ForgotPassword({ portal, onBack, onLoginClick }) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const title = portal === "manager" ? "Manager Portal" : portal === "hr" ? "HR Operations" : "Staff Access";

  const submit = async (event) => {
    event.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError("Please enter your registered staff email address.");
      return;
    }
    const emailRegex = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
    if (!emailRegex.test(cleanEmail)) {
      setError("Please enter a valid email address.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await apiRequest("/api/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: cleanEmail }),
      });
      setSubmitted(true);
    } catch (err) {
      setError(err.message || "Failed to process password reset request.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="center-page" id="main-content">
      <button className="back-link" onClick={onBack}>
        ← Back to Login
      </button>

      <div className="login-card">
        <div className="login-mark">V</div>
        <div className="eyebrow">VTAB SQUARE / PASSWORD RECOVERY</div>
        <h1>Reset Password</h1>
        <p>{title} — Staff Account Recovery</p>

        {submitted ? (
          <div>
            <div className="login-success" role="status">
              If this email is associated with an active staff account, password reset instructions have been sent. Please check your inbox and spam folder.
            </div>
            <button
              className="primary-button"
              style={{ marginTop: "20px", width: "100%" }}
              type="button"
              onClick={onLoginClick}
            >
              RETURN TO LOGIN <span>→</span>
            </button>
          </div>
        ) : (
          <form onSubmit={submit}>
            <label>
              REGISTERED STAFF EMAIL
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Enter your company email"
                autoComplete="email"
              />
            </label>

            {error && (
              <div className="login-error" role="alert">
                {error}
              </div>
            )}

            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "SENDING INSTRUCTIONS..." : "SEND RESET INSTRUCTIONS"}
              <span>→</span>
            </button>

            <div className="login-card-links" style={{ justifyContent: "center", marginTop: "12px" }}>
              <button
                type="button"
                className="login-link"
                onClick={onLoginClick}
              >
                Remember your password? Back to Login
              </button>
            </div>
          </form>
        )}

        <div className="login-security">
          <i /> Authenticated enterprise recovery
        </div>
      </div>
    </main>
  );
}

function ResetPassword({ token, onBack, onSuccess, onGoToForgot }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState(false);

  const hasToken = Boolean(token && token !== "active");

  const submit = async (event) => {
    event.preventDefault();

    if (!hasToken) {
      setError("Password reset token is missing or invalid. Please click the reset link directly from your email, or request a fresh one.");
      return;
    }

    if (!password || !confirmPassword) {
      setError("Please fill in both password fields.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match. Please ensure both fields are identical.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await apiRequest("/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          token,
          password,
        }),
      });

      if (!result?.success) {
        throw new Error(result?.message || "Failed to update password.");
      }

      setCompleted(true);
    } catch (err) {
      setError(err.message || "Failed to reset password. The link may have expired.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="center-page" id="main-content">
      <button className="back-link" onClick={onBack}>
        ← Back to Home
      </button>

      <div className="login-card">
        <div className="login-mark">V</div>
        <div className="eyebrow">VTAB SQUARE / SET NEW PASSWORD</div>
        <h1>New Password</h1>
        <p>Enter your new password to regain access to your staff account.</p>

        {completed ? (
          <div>
            <div className="login-success" role="status">
              Your password has been reset successfully! You can now log in using your new credentials.
            </div>
            <button
              className="primary-button"
              style={{ marginTop: "20px", width: "100%" }}
              type="button"
              onClick={onSuccess}
            >
              PROCEED TO LOGIN <span>→</span>
            </button>
          </div>
        ) : (
          <div>
            {!hasToken && (
              <div
                className="login-error"
                role="alert"
                style={{
                  marginBottom: "16px",
                  lineHeight: "1.45",
                  fontSize: "13px",
                  borderLeft: "3px solid #ff4d4f",
                  padding: "10px 14px",
                  backgroundColor: "rgba(255, 77, 79, 0.08)",
                }}
              >
                No active password reset token was detected in your browser URL. If you navigated here directly or the security token expired, please click the link directly inside your email, or request a fresh reset link below.
              </div>
            )}

            {!hasToken && onGoToForgot && (
              <button
                type="button"
                className="primary-button"
                style={{ width: "100%", marginBottom: "16px" }}
                onClick={onGoToForgot}
              >
                REQUEST FRESH RESET LINK <span>→</span>
              </button>
            )}

            <form onSubmit={submit}>
              <label>
                NEW PASSWORD
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 6 characters"
                  autoComplete="new-password"
                  disabled={loading || !hasToken}
                />
              </label>

              <label>
                CONFIRM NEW PASSWORD
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Re-enter your new password"
                  autoComplete="new-password"
                  disabled={loading || !hasToken}
                />
              </label>

              {error && (
                <div className="login-error" role="alert">
                  {error}
                </div>
              )}

              <button
                className="primary-button"
                type="submit"
                disabled={loading || !hasToken}
              >
                {loading ? "UPDATING PASSWORD..." : "UPDATE PASSWORD"}
                <span>→</span>
              </button>
            </form>
          </div>
        )}

        <div className="login-security">
          <i /> End-to-end encrypted credential update
        </div>
      </div>
    </main>
  );
}

function CandidateAI({ onBack }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "ai",
      text:
        "Hello. I’m VTAB AI. I can answer candidate questions about the recruitment process, interviews, application information, company information and onboarding.",
    },
  ]);
  const [loading, setLoading] = useState(false);

  const suggested = [
    "What happens after my interview?",
    "What documents will I need?",
    "How does the interview process work?",
  ];

  const answer = async (value) => {
    const text = value.trim();
    if (!text || loading) return;

    setMessages((current) => [
      ...current,
      { role: "user", text },
    ]);
    setQuestion("");
    setLoading(true);

    try {
      const result = await apiRequest(
        "/api/candidate-ai",
        {
          method: "POST",
          body: JSON.stringify({ question: text }),
        }
      );

      const aiText =
        result?.answer ||
        result?.message ||
        "I’m unable to answer that right now. Please contact VTAB Square HR for assistance.";

      setMessages((current) => [
        ...current,
        { role: "ai", text: aiText },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "ai",
          text:
            "I’m unable to connect to the candidate AI service right now. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="candidate-ai-page" id="main-content" aria-label="Candidate AI assistant">
      <div className="ai-topline">
        <button className="back-link" onClick={onBack}>
          ← AI OS
        </button>
        <span>
          <i /> CANDIDATE ASSISTANT ONLY
        </span>
      </div>

      <div className="candidate-ai-layout">
        <div className="mini-ball" aria-hidden="true">
          <span>V</span>
        </div>

        <section className="chat-panel" aria-label="Chat with VTAB AI">
          <div className="chat-heading">
            <div>
              <div className="eyebrow">VTAB AI AGENT</div>
              <h1>How can I help?</h1>
            </div>
            <div className="chat-status" aria-live="polite" aria-atomic="true">
              <i /> {loading ? "Thinking..." : "Online"}
            </div>
          </div>

          <div
            className="chat-messages"
            aria-live="polite"
            aria-label="Chat messages"
            role="log"
            aria-relevant="additions"
          >
            {messages.map((message, index) => (
              <div
                className={`message ${message.role}`}
                key={`${message.role}-${index}`}
              >
                <span className="message-tag">
                  {message.role === "ai" ? "VTAB AI" : "YOU"}
                </span>
                <p>{message.text}</p>
              </div>
            ))}

            {loading && (
              <div className="message ai" aria-live="polite">
                <span className="message-tag">VTAB AI</span>
                <p>Thinking...</p>
              </div>
            )}
          </div>

          <div className="suggestions" role="group" aria-label="Suggested questions">
            {suggested.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => answer(suggestion)}
                disabled={loading}
                aria-label={`Ask: ${suggestion}`}
              >
                {suggestion}
              </button>
            ))}
          </div>

          <form
            className="chat-input"
            onSubmit={(event) => {
              event.preventDefault();
              answer(question);
            }}
            aria-label="Ask a question"
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a candidate-related question..."
              disabled={loading}
              aria-label="Type your question"
            />
            <button type="submit" disabled={loading || !question.trim()} aria-label="Send message">
              ↑
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}

/* -------------------------------------------------------------------------- */
/* CANDIDATE DOCUMENT SUBMISSION                                               */
/* -------------------------------------------------------------------------- */

function DocumentSubmission({ token }) {
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [requestData, setRequestData] = useState(null);
  const [files, setFiles] = useState({});
  const [uploaded, setUploaded] = useState({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [uploadProgress, setUploadProgress] = useState("");

  const loadRequest = async () => {
    setLoading(true);
    setError("");

    try {
      const result = await apiRequest(
        `/api/document-request?token=${encodeURIComponent(token)}`
      );

      if (!result?.success) {
        throw new Error(
          result?.message || "Unable to load the document request."
        );
      }

      setRequestData(result);
    } catch (err) {
      setError(
        err?.message ||
          "This document submission link is invalid or no longer active."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setError("The secure document submission token is missing.");
      return;
    }

    loadRequest();
  }, [token]);

  const requirements = Array.isArray(requestData?.requirements)
    ? requestData.requirements
    : [];

  const requiredRequirements = requirements.filter(
    (item) => item?.is_required !== false
  );

  const candidateName =
    requestData?.candidate?.name || "Candidate";

  const applicationId =
    requestData?.request?.application_id || "Application";

  const expiresAt = requestData?.request?.expires_at
    ? new Date(requestData.request.expires_at)
    : null;

  const expiryText =
    expiresAt && !Number.isNaN(expiresAt.getTime())
      ? expiresAt.toLocaleString()
      : "7 days from issue";

  const handleFileChange = (requirement, file) => {
    setError("");
    setSuccess("");

    if (!file) return;

    const extension = `.${file.name.split(".").pop()?.toLowerCase() || ""}`;
    const allowed = [".pdf", ".png", ".jpg", ".jpeg"];

    if (!allowed.includes(extension)) {
      setError(
        `${requirement?.document_name || "This document"} must be a PDF, PNG, JPG, or JPEG file.`
      );
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError(
        `${requirement?.document_name || "This document"} is larger than the 10 MB limit.`
      );
      return;
    }

    const key = requirement?.id || requirement?.document_name;

    setFiles((current) => ({
      ...current,
      [key]: file,
    }));
  };

  const uploadOne = async (requirement, file) => {
    const documentName =
      requirement?.document_name || "Document";

    const formData = new FormData();
    formData.append("token", token);
    formData.append("document_name", documentName);
    formData.append("file", file);

    const response = await fetch(
      `${API_BASE}/api/document-upload`,
      {
        method: "POST",
        body: formData,
      }
    );

    const responseText = await response.text();

    let data = null;

    try {
      data = responseText ? JSON.parse(responseText) : null;
    } catch {
      data = { detail: responseText };
    }

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          data?.message ||
          `Upload failed for ${documentName}.`
      );
    }

    if (!data?.success) {
      throw new Error(
        data?.message ||
          `Upload failed for ${documentName}.`
      );
    }

    return data;
  };

  const submitDocuments = async () => {
    setError("");
    setSuccess("");

    if (!requirements.length) {
      setError(
        "No document requirements were returned by the recruitment system."
      );
      return;
    }

    const missingRequired = requiredRequirements.filter((requirement) => {
      const key = requirement?.id || requirement?.document_name;
      return !files[key] && !uploaded[key];
    });

    if (missingRequired.length > 0) {
      setError(
        `Please select: ${missingRequired
          .map((item) => item?.document_name || "required document")
          .join(", ")}`
      );
      return;
    }

    const pendingUploads = requirements.filter((requirement) => {
      const key = requirement?.id || requirement?.document_name;
      return files[key] && !uploaded[key];
    });

    if (pendingUploads.length === 0) {
      setSuccess("All selected documents have already been uploaded.");
      return;
    }

    setUploading(true);

    try {
      for (let index = 0; index < pendingUploads.length; index += 1) {
        const requirement = pendingUploads[index];
        const key = requirement?.id || requirement?.document_name;

        setUploadProgress(
          `Uploading ${index + 1} of ${pendingUploads.length}: ${
            requirement?.document_name || "Document"
          }`
        );

        await uploadOne(requirement, files[key]);

        setUploaded((current) => ({
          ...current,
          [key]: true,
        }));
      }

      setUploadProgress("Submitting document package and running AI verification...");

      await apiRequest(
        "/api/document-submit",
        {
          method: "POST",
          body: JSON.stringify({ token }),
        }
      );

      setUploadProgress("");
      setSuccess(
        "All documents have been uploaded and submitted for AI verification. HR will review your submission."
      );
    } catch (err) {
      setUploadProgress("");
      setError(err?.message || "One or more documents could not be uploaded.");
    } finally {
      setUploading(false);
    }
  };

  const uploadedCount = requirements.filter((requirement) => {
    const key = requirement?.id || requirement?.document_name;
    return Boolean(uploaded[key]);
  }).length;

  const selectedCount = requirements.filter((requirement) => {
    const key = requirement?.id || requirement?.document_name;
    return Boolean(files[key]);
  }).length;

  if (loading) {
    return (
      <DocumentPageShell>
        <DocumentLoading />
      </DocumentPageShell>
    );
  }

  if (error && !requestData) {
    return (
      <DocumentPageShell>
        <div style={documentStyles.errorCard}>
          <div style={documentStyles.errorIcon}>!</div>
          <div>
            <div style={documentStyles.eyebrow}>DOCUMENT ACCESS</div>
            <h1 style={documentStyles.title}>Link unavailable</h1>
            <p style={documentStyles.text}>{error}</p>
            <p style={documentStyles.muted}>
              Please use the latest document submission email from VTAB Square.
            </p>
          </div>
        </div>
      </DocumentPageShell>
    );
  }

  return (
    <DocumentPageShell>
      <div style={documentStyles.page}>
        <header style={documentStyles.header}>
          <div style={documentStyles.brand}>
            <span style={documentStyles.brandMark}>V</span>
            <div>
              <strong>VTAB SQUARE</strong>
              <small>VTAB AI RECRUITMENT</small>
            </div>
          </div>

          <div style={documentStyles.secure}>
            <span style={documentStyles.onlineDot} />
            SECURE DOCUMENT SUBMISSION
          </div>
        </header>

        <main style={documentStyles.main}>
          <div style={documentStyles.eyebrow}>
            <span style={documentStyles.purpleDot} />
            POST-SELECTION ONBOARDING
          </div>

          <h1 style={documentStyles.heroTitle}>
            Submit your
            <br />
            <span>required documents.</span>
          </h1>

          <p style={documentStyles.heroText}>
            Hello {candidateName}. Your interview stage is complete.
            Please upload the requested documents below so VTAB Square HR
            can continue your verification and onboarding process.
          </p>

          <div style={documentStyles.infoGrid}>
            <div style={documentStyles.infoCard}>
              <span>APPLICATION ID</span>
              <strong>{applicationId}</strong>
            </div>

            <div style={documentStyles.infoCard}>
              <span>LINK STATUS</span>
              <strong style={{ color: "#65e6b4" }}>ACTIVE</strong>
            </div>

            <div style={documentStyles.infoCard}>
              <span>EXPIRES</span>
              <strong>{expiryText}</strong>
            </div>
          </div>

          {error && (
            <div style={documentStyles.alert}>
              <strong>Upload issue</strong>
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div style={documentStyles.success}>
              <strong>✓ Documents received</strong>
              <span>{success}</span>
            </div>
          )}

          <section style={documentStyles.panel}>
            <div style={documentStyles.panelHeader}>
              <div>
                <div style={documentStyles.eyebrow}>REQUIRED DOCUMENTS</div>
                <h2 style={documentStyles.panelTitle}>
                  Document checklist
                </h2>
              </div>

              <div style={documentStyles.counter}>
                {uploadedCount}/{requirements.length} uploaded
              </div>
            </div>

            {requirements.length === 0 ? (
              <div style={documentStyles.empty}>
                No active document requirements are configured yet.
                Please contact VTAB Square HR.
              </div>
            ) : (
              <div style={documentStyles.requirementList}>
                {requirements.map((requirement, index) => {
                  const key =
                    requirement?.id ||
                    requirement?.document_name ||
                    `requirement-${index}`;

                  const file = files[key];
                  const isUploaded = Boolean(uploaded[key]);
                  const isRequired =
                    requirement?.is_required !== false;

                  return (
                    <div
                      key={key}
                      style={{
                        ...documentStyles.requirement,
                        ...(isUploaded
                          ? documentStyles.requirementUploaded
                          : {}),
                      }}
                    >
                      <div style={documentStyles.requirementNumber}>
                        {String(index + 1).padStart(2, "0")}
                      </div>

                      <div style={documentStyles.requirementInfo}>
                        <div style={documentStyles.requirementName}>
                          {requirement?.document_name || "Document"}
                          {isRequired && (
                            <span style={documentStyles.requiredBadge}>
                              REQUIRED
                            </span>
                          )}
                        </div>

                        <p style={documentStyles.requirementDescription}>
                          {requirement?.description ||
                            "Upload the requested document for verification."}
                        </p>

                        {file && !isUploaded && (
                          <div style={documentStyles.fileName}>
                            Selected: {file.name}
                          </div>
                        )}

                        {isUploaded && (
                          <div style={documentStyles.uploadedText}>
                            ✓ Uploaded successfully
                          </div>
                        )}
                      </div>

                      <label
                        style={{
                          ...documentStyles.fileButton,
                          ...(isUploaded
                            ? documentStyles.fileButtonDone
                            : {}),
                        }}
                      >
                        {isUploaded ? "REPLACE" : "CHOOSE FILE"}
                        <input
                          type="file"
                          accept=".pdf,.png,.jpg,.jpeg"
                          onChange={(event) =>
                            handleFileChange(
                              requirement,
                              event.target.files?.[0]
                            )
                          }
                          disabled={uploading}
                          style={{ display: "none" }}
                        />
                      </label>
                    </div>
                  );
                })}
              </div>
            )}

            <div style={documentStyles.bottomBar}>
              <div>
                <span style={documentStyles.bottomLabel}>
                  ALLOWED FILES
                </span>
                <span style={documentStyles.bottomValue}>
                  PDF, PNG, JPG, JPEG · Maximum 10 MB each
                </span>
              </div>

              <button
                type="button"
                onClick={submitDocuments}
                disabled={uploading || requirements.length === 0}
                style={{
                  ...documentStyles.submitButton,
                  opacity:
                    uploading || requirements.length === 0 ? 0.55 : 1,
                  cursor:
                    uploading || requirements.length === 0
                      ? "not-allowed"
                      : "pointer",
                }}
              >
                {uploading
                  ? "UPLOADING..."
                  : uploadedCount === requirements.length
                  ? "DOCUMENTS SUBMITTED ✓"
                  : "SUBMIT DOCUMENTS"}
                <span>→</span>
              </button>
            </div>

            {uploadProgress && (
              <div style={documentStyles.progressBox}>
                <div style={documentStyles.progressTop}>
                  <span>SECURE UPLOAD</span>
                  <span>{uploadProgress}</span>
                </div>
                <div style={documentStyles.progressTrack}>
                  <div style={documentStyles.progressBar} />
                </div>
              </div>
            )}
          </section>

          <div style={documentStyles.securityNote}>
            <span>⌁</span>
            Your secure link is tied to this application and is only valid
            for the requested document submission workflow.
          </div>
        </main>
      </div>
    </DocumentPageShell>
  );
}

function DocumentPageShell({ children }) {
  return (
    <>
      <style>{`
        @keyframes vtab-document-progress {
          from { transform: translateX(-30%); }
          to { transform: translateX(75%); }
        }
        @media (max-width: 720px) {
          .vtab-doc-main {}
        }
      `}</style>
      <div
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at 50% 0%, rgba(105,88,255,.12), transparent 38%), #05070d",
        color: "#f4f6fb",
        fontFamily:
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      {children}
      </div>
    </>
  );
}

function DocumentLoading() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          width: "min(520px, 100%)",
          padding: 34,
          borderRadius: 20,
          background: "rgba(11,14,24,.88)",
          border: "1px solid rgba(255,255,255,.08)",
          boxShadow: "0 30px 100px rgba(0,0,0,.45)",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: 64,
            height: 64,
            margin: "0 auto 20px",
            borderRadius: "50%",
            display: "grid",
            placeItems: "center",
            background:
              "radial-gradient(circle at 35% 30%, #d7d3ff, #7466f2 45%, #171a38 100%)",
            boxShadow: "0 0 45px rgba(116,102,242,.35)",
            fontSize: 28,
            fontWeight: 800,
          }}
        >
          V
        </div>

        <div
          style={{
            color: "#8f86ff",
            fontSize: 10,
            letterSpacing: ".18em",
          }}
        >
          VTAB AI RECRUITMENT
        </div>

        <h2 style={{ margin: "12px 0 8px", fontSize: 24 }}>
          Secure document request
        </h2>

        <p style={{ margin: 0, color: "#7f8798", fontSize: 13 }}>
          Validating your secure submission link...
        </p>
      </div>
    </div>
  );
}

const documentStyles = {
  page: {
    minHeight: "100vh",
  },
  header: {
    height: 76,
    padding: "0 42px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottom: "1px solid rgba(255,255,255,.06)",
    background: "rgba(5,7,13,.72)",
    backdropFilter: "blur(18px)",
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  brandMark: {
    width: 38,
    height: 38,
    display: "grid",
    placeItems: "center",
    borderRadius: 10,
    border: "1px solid rgba(139,123,255,.5)",
    background: "rgba(105,88,255,.08)",
    color: "#f4f6fb",
    fontSize: 18,
    fontWeight: 800,
  },
  secure: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    color: "#65e6b4",
    fontSize: 9,
    letterSpacing: ".15em",
    fontWeight: 700,
  },
  onlineDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#65e6b4",
    boxShadow: "0 0 12px rgba(101,230,180,.7)",
  },
  main: {
    width: "min(1080px, calc(100% - 40px))",
    margin: "0 auto",
    padding: "76px 0 70px",
  },
  eyebrow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    color: "#8f86ff",
    fontSize: 10,
    letterSpacing: ".18em",
    fontWeight: 700,
  },
  purpleDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#8f86ff",
    boxShadow: "0 0 12px rgba(143,134,255,.7)",
  },
  heroTitle: {
    margin: "18px 0 18px",
    fontSize: "clamp(42px, 7vw, 76px)",
    lineHeight: .98,
    letterSpacing: "-.045em",
    fontWeight: 800,
  },
  heroText: {
    maxWidth: 690,
    margin: 0,
    color: "#858e9f",
    fontSize: 15,
    lineHeight: 1.75,
  },
  infoGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 12,
    marginTop: 36,
  },
  infoCard: {
    padding: "17px 18px",
    borderRadius: 13,
    background: "rgba(14,18,30,.72)",
    border: "1px solid rgba(255,255,255,.07)",
  },
  panel: {
    marginTop: 22,
    padding: 24,
    borderRadius: 20,
    background: "rgba(10,13,22,.82)",
    border: "1px solid rgba(255,255,255,.08)",
    boxShadow: "0 28px 90px rgba(0,0,0,.28)",
  },
  panelHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 20,
    paddingBottom: 22,
    borderBottom: "1px solid rgba(255,255,255,.06)",
  },
  panelTitle: {
    margin: "8px 0 0",
    fontSize: 26,
    letterSpacing: "-.025em",
  },
  counter: {
    padding: "8px 11px",
    borderRadius: 9,
    background: "rgba(101,230,180,.06)",
    border: "1px solid rgba(101,230,180,.15)",
    color: "#65e6b4",
    fontSize: 10,
    letterSpacing: ".08em",
  },
  requirementList: {
    display: "grid",
    gap: 10,
    marginTop: 18,
  },
  requirement: {
    display: "grid",
    gridTemplateColumns: "44px 1fr auto",
    alignItems: "center",
    gap: 16,
    padding: 17,
    borderRadius: 13,
    background: "rgba(255,255,255,.018)",
    border: "1px solid rgba(255,255,255,.06)",
  },
  requirementUploaded: {
    borderColor: "rgba(101,230,180,.18)",
    background: "rgba(101,230,180,.025)",
  },
  requirementNumber: {
    width: 36,
    height: 36,
    display: "grid",
    placeItems: "center",
    borderRadius: 9,
    background: "rgba(139,123,255,.08)",
    color: "#9e96ff",
    fontSize: 10,
    fontWeight: 700,
  },
  requirementInfo: {
    minWidth: 0,
  },
  requirementName: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
    color: "#eef0f6",
    fontSize: 13,
    fontWeight: 700,
  },
  requiredBadge: {
    padding: "3px 6px",
    borderRadius: 5,
    background: "rgba(255,184,92,.08)",
    color: "#ffbd68",
    fontSize: 8,
    letterSpacing: ".1em",
  },
  requirementDescription: {
    margin: "6px 0 0",
    color: "#727b8d",
    fontSize: 11,
    lineHeight: 1.5,
  },
  fileName: {
    marginTop: 7,
    color: "#b9b2ff",
    fontSize: 10,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  uploadedText: {
    marginTop: 7,
    color: "#65e6b4",
    fontSize: 10,
    fontWeight: 600,
  },
  fileButton: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minWidth: 110,
    padding: "10px 12px",
    borderRadius: 9,
    border: "1px solid rgba(139,123,255,.25)",
    background: "rgba(139,123,255,.06)",
    color: "#b9b2ff",
    fontSize: 9,
    letterSpacing: ".09em",
    fontWeight: 700,
    cursor: "pointer",
  },
  fileButtonDone: {
    borderColor: "rgba(101,230,180,.18)",
    background: "rgba(101,230,180,.05)",
    color: "#65e6b4",
  },
  bottomBar: {
    marginTop: 20,
    paddingTop: 20,
    borderTop: "1px solid rgba(255,255,255,.06)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 18,
  },
  bottomLabel: {
    display: "block",
    color: "#697386",
    fontSize: 8,
    letterSpacing: ".14em",
    marginBottom: 5,
  },
  bottomValue: {
    color: "#929aaa",
    fontSize: 10,
  },
  submitButton: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 18,
    minWidth: 190,
    padding: "13px 17px",
    border: "1px solid rgba(139,123,255,.45)",
    borderRadius: 10,
    background: "linear-gradient(135deg, #6f61e9, #8b7bff)",
    color: "#fff",
    fontSize: 10,
    letterSpacing: ".1em",
    fontWeight: 800,
    boxShadow: "0 12px 32px rgba(111,97,233,.2)",
  },
  progressBox: {
    marginTop: 18,
    padding: 14,
    borderRadius: 10,
    background: "rgba(139,123,255,.04)",
    border: "1px solid rgba(139,123,255,.1)",
  },
  progressTop: {
    display: "flex",
    justifyContent: "space-between",
    gap: 12,
    color: "#8f86ff",
    fontSize: 9,
    letterSpacing: ".08em",
  },
  progressTrack: {
    height: 4,
    marginTop: 10,
    borderRadius: 99,
    background: "rgba(255,255,255,.07)",
    overflow: "hidden",
  },
  progressBar: {
    width: "55%",
    height: "100%",
    borderRadius: 99,
    background: "linear-gradient(90deg, #6f61e9, #65d7ff)",
    animation: "vtab-document-progress 1.2s ease-in-out infinite alternate",
  },
  securityNote: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
    marginTop: 22,
    color: "#606a7d",
    fontSize: 10,
    textAlign: "center",
  },
  alert: {
    marginTop: 18,
    padding: 14,
    display: "grid",
    gap: 4,
    borderRadius: 11,
    background: "rgba(255,113,135,.055)",
    border: "1px solid rgba(255,113,135,.16)",
    color: "#ff9aaa",
    fontSize: 11,
  },
  success: {
    marginTop: 18,
    padding: 14,
    display: "grid",
    gap: 4,
    borderRadius: 11,
    background: "rgba(101,230,180,.045)",
    border: "1px solid rgba(101,230,180,.15)",
    color: "#65e6b4",
    fontSize: 11,
  },
  empty: {
    marginTop: 18,
    padding: 25,
    textAlign: "center",
    color: "#737d90",
    fontSize: 12,
  },
  errorCard: {
    width: "min(700px, calc(100% - 40px))",
    margin: "auto",
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    gap: 20,
  },
  errorIcon: {
    flex: "0 0 auto",
    width: 52,
    height: 52,
    display: "grid",
    placeItems: "center",
    borderRadius: 14,
    background: "rgba(255,113,135,.08)",
    border: "1px solid rgba(255,113,135,.18)",
    color: "#ff7187",
    fontWeight: 800,
    fontSize: 20,
  },
  title: {
    margin: "10px 0 10px",
    fontSize: 34,
    letterSpacing: "-.03em",
  },
  text: {
    margin: 0,
    color: "#b7bdc9",
    fontSize: 13,
    lineHeight: 1.6,
  },
  muted: {
    marginTop: 12,
    color: "#697386",
    fontSize: 11,
  },
};

function PortalLayout({
  role,
  active,
  setActive,
  onHome,
  children,
  error,
}) {
  const managerItems = ["Candidate Queue", "Interview Feedback", "Analytics"];
  const hrItems = ["Offer Approvals", "Employee Records", "AI Audit Logs"];
  const items = role === "manager" ? managerItems : hrItems;

  return (
    <main className="portal-page" id="main-content">
      <aside className="portal-sidebar" aria-label="Portal navigation">
        <button className="portal-brand" onClick={onHome} aria-label="Go to home page">
          <span className="brand-v">V</span>
          <div>
            <b>VTAB SQUARE</b>
            <small>
              {role === "manager" ? "MANAGER PORTAL" : "HR PORTAL"}
            </small>
          </div>
        </button>

        <div className="portal-nav-label" aria-hidden="true">
          {role === "manager" ? "DECISION CENTER" : "HR OPERATIONS"}
        </div>

        <nav aria-label={role === "manager" ? "Manager portal navigation" : "HR portal navigation"}>
          {items.map((item) => (
            <button
              key={item}
              className={`portal-nav ${active === item ? "active" : ""}`}
              onClick={() => setActive(item)}
              aria-current={active === item ? "page" : undefined}
            >
              <span aria-hidden="true">
                {item === "Analytics" || item === "AI Audit Logs"
                  ? "◌"
                  : item === "Interview Feedback"
                  ? "◎"
                  : item === "Offer Approvals"
                  ? "◇"
                  : "◈"}
              </span>
              {item}
            </button>
          ))}
        </nav>

        <div className="portal-side-bottom">
          <div className="online" aria-live="polite">
            <i /> AI services online
          </div>
          <button onClick={onHome} aria-label="Exit portal and return to home">Exit portal</button>
        </div>
      </aside>

      <section className="portal-main" aria-label={`${active} content`}>
        <header className="portal-header">
          <div>
            <div className="eyebrow">
              VTAB AI AGENT / {role.toUpperCase()}
            </div>
            <h1>{active}</h1>
          </div>

          <div className="profile-chip">
            <span aria-hidden="true">{role === "manager" ? "M" : "H"}</span>
            <div>
              <b>
                {role === "manager" ? "Interview Manager" : "HR Operations"}
              </b>
              <small>Authenticated</small>
            </div>
          </div>
        </header>

        {error && (
          <div
            style={{
              margin: "18px 38px 0",
              padding: "12px 14px",
              border: "1px solid rgba(255,110,131,.2)",
              background: "rgba(255,110,131,.05)",
              color: "#ff8b9b",
              borderRadius: "10px",
              fontSize: "11px",
            }}
            role="alert"
          >
            {error}
          </div>
        )}

        <div className="portal-content">{children}</div>
      </section>
    </main>
  );
}

function ManagerPortal({ session, onHome, onAuthError }) {
  const [active, setActive] = useState("Candidate Queue");
  const [pageError, setPageError] = useState("");

  const handleError = (error) => {
    setPageError(error.message || "Something went wrong.");
    onAuthError(error);
  };

  return (
    <PortalLayout
      role="manager"
      active={active}
      setActive={setActive}
      onHome={onHome}
      error={pageError}
    >
      {active === "Candidate Queue" && (
        <ManagerQueue token={session.access_token} onError={handleError} />
      )}

      {active === "Interview Feedback" && (
        <Feedback token={session.access_token} onError={handleError} />
      )}

      {active === "Analytics" && (
        <Analytics token={session.access_token} onError={handleError} />
      )}
    </PortalLayout>
  );
}

function ManagerQueue({ token, onError }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [decisionLoading, setDecisionLoading] = useState(null);

  const loadCandidates = async () => {
    setLoading(true);

    try {
      const result = await apiRequest("/api/candidates", {}, token);
      const items = Array.isArray(result?.items) ? result.items : [];
      setCandidates(items);
    } catch (error) {
      onError(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  const updateDecision = async (item, decision) => {
    const applicationId = item?.application?.id;

    if (!applicationId) {
      onError(new Error("Application ID is missing."));
      return;
    }

    const decisionLabel = decision === "approved" ? "approve" : "reject";

    if (
      !window.confirm(
        `Are you sure you want to ${decisionLabel} this application?`
      )
    ) {
      return;
    }

    setDecisionLoading(applicationId);

    try {
      const result = await apiRequest(
        "/api/manager/candidate-decision",
        {
          method: "POST",
          body: JSON.stringify({
            application_id: applicationId,
            decision,
          }),
        },
        token
      );

      const updatedApplication = result?.application;

      if (updatedApplication) {
        setCandidates((current) =>
          current.map((candidateItem) => {
            if (candidateItem?.application?.id !== applicationId) {
              return candidateItem;
            }

            return {
              ...candidateItem,
              application: {
                ...candidateItem.application,
                ...updatedApplication,
              },
              manager_view: {
                ...(candidateItem.manager_view || {}),
                status:
                  updatedApplication.status ||
                  candidateItem.manager_view?.status,
              },
            };
          })
        );

        setSelected((current) => {
          if (!current?.application?.id) return current;
          if (current.application.id !== applicationId) return current;

          return {
            ...current,
            application: {
              ...current.application,
              ...updatedApplication,
            },
            manager_view: {
              ...(current.manager_view || {}),
              status:
                updatedApplication.status ||
                current.manager_view?.status,
            },
            actionMessage:
              decision === "approved"
                ? "Application approved successfully."
                : "Application rejected successfully.",
          };
        });
      }

      await loadCandidates();
    } catch (error) {
      onError(error);
    } finally {
      setDecisionLoading(null);
    }
  };

  const readyCount = candidates.filter((item) =>
    [
      "shortlisted",
      "interview_pending",
      "interview_scheduled",
    ].includes(item?.application?.status)
  ).length;

  return (
    <div className="queue-wrap">
      <div className="section-intro">
        <div>
          <span className="eyebrow">
            LIVE DATABASE / AI-ASSISTED REVIEW
          </span>

          <h2>Candidate Queue</h2>

          <p>
            Real candidate applications loaded from Supabase through FastAPI.
          </p>
        </div>

        <div className="queue-stat">
          <b>{String(readyCount).padStart(2, "0")}</b>
          <span>ready for review</span>
        </div>
      </div>

      {loading && (
        <div className="candidate-card" aria-busy="true" aria-label="Loading candidates">
          <div className="candidate-main">
            <div className="candidate-avatar" aria-hidden="true">...</div>

            <div>
              <h3>Loading live candidates...</h3>
              <p>Fetching authenticated recruitment data</p>
            </div>
          </div>
        </div>
      )}

      {!loading && candidates.length === 0 && (
        <div className="candidate-card">
          <div>
            <h3>No candidate applications found</h3>
            <p>The authenticated API returned an empty queue.</p>
          </div>
        </div>
      )}

      {!loading &&
        candidates.map((item, index) => {
          const candidate = item?.candidate || {};
          const application = item?.application || {};
          const jobRole = item?.job_role || {};
          const evaluation = item?.ai_evaluation || {};
          const summary = item?.ai_summary || {};
          const view = item?.manager_view || {};

          const name =
            candidate.candidate_name ||
            view.candidate_name ||
            "Candidate";

          const role =
            jobRole.role_name ||
            view.role ||
            "Role not specified";

          const status =
            application.status ||
            view.status ||
            "unknown";

          const aiDecision =
            evaluation?.decision ||
            view?.ai_decision ||
            summary?.decision ||
            null;

          const overallEligible =
            evaluation?.overall_eligible ??
            view?.overall_eligible ??
            summary?.overall_eligible ??
            null;

          const matchedSkills = Array.isArray(
            evaluation?.matched_skills
          )
            ? evaluation.matched_skills
            : Array.isArray(summary?.matched_skills)
            ? summary.matched_skills
            : [];

          const missingSkills = Array.isArray(
            evaluation?.missing_skills
          )
            ? evaluation.missing_skills
            : Array.isArray(summary?.missing_skills)
            ? summary.missing_skills
            : [];

          const displayMatch =
            matchedSkills.length > 0
              ? `${matchedSkills.length}/${
                  jobRole?.required_skills?.length || 5
                }`
              : "AI";

          const skillsText =
            matchedSkills.length > 0
              ? matchedSkills.join(" · ")
              : jobRole.description ||
                "AI eligibility evidence available";

          const isUpdating =
            decisionLoading === application.id;

          return (
            <article
              className="candidate-card"
              key={`${
                application.id ||
                application.application_id ||
                "application"
              }-${index}`}
            >
              <div className="candidate-main">
                <div className="candidate-avatar large">
                  {name
                    .split(" ")
                    .map((part) => part[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()}
                </div>

                <div>
                  <h3>{name}</h3>

                  <p>
                    {role} ·{" "}
                    {application.application_id ||
                      "Application"}
                  </p>

                  <span className="skill-line">
                    {skillsText}
                  </span>
                </div>
              </div>

              <div className="match-score">
                <strong>{displayMatch}</strong>

                <span>
                  {matchedSkills.length > 0
                    ? "AI SKILL MATCH"
                    : "AI EVIDENCE"}
                </span>
              </div>

              <div className="candidate-status-chip">
                {String(status)
                  .replaceAll("_", " ")
                  .toUpperCase()}
              </div>

              <div className="candidate-actions">
                <button
                  onClick={() => setSelected(item)}
                  disabled={isUpdating}
                >
                  Review
                </button>

                <button
                  className="approve"
                  onClick={() =>
                    updateDecision(item, "approved")
                  }
                  disabled={
                    isUpdating ||
                    status === "approved" ||
                    status === "selected" ||
                    status === "rejected"
                  }
                >
                  {isUpdating ? "..." : "Approve"}
                </button>

                <button
                  className="reject"
                  onClick={() =>
                    updateDecision(item, "rejected")
                  }
                  disabled={
                    isUpdating ||
                    status === "rejected"
                  }
                >
                  {isUpdating ? "..." : "Reject"}
                </button>
              </div>
            </article>
          );
        })}

      {selected && (
        <div
          className="menu-overlay"
          onClick={() => setSelected(null)}
          aria-label="Close candidate review"
        >
          <div
            className="login-card"
            role="dialog"
            aria-modal="true"
            aria-label="Candidate application review"
            style={{
              maxWidth: 650,
              margin: "auto",
            }}
            onClick={(event) =>
              event.stopPropagation()
            }
          >
            {(() => {
              const candidate =
                selected?.candidate || {};

              const application =
                selected?.application || {};

              const jobRole =
                selected?.job_role || {};

              const evaluation =
                selected?.ai_evaluation || {};

              const summary =
                selected?.ai_summary || {};

              const managerView =
                selected?.manager_view || {};

              const name =
                candidate?.candidate_name ||
                "Candidate";

              const status =
                application?.status ||
                "unknown";

              const decision =
                evaluation?.decision ||
                managerView?.ai_decision ||
                summary?.decision ||
                null;

              const overallEligible =
                evaluation?.overall_eligible ??
                managerView?.overall_eligible ??
                summary?.overall_eligible ??
                null;

              const cgpaEligible =
                evaluation?.cgpa_eligible ??
                summary?.cgpa_eligible ??
                null;

              const skillsEligible =
                evaluation?.skills_eligible ??
                summary?.skills_eligible ??
                null;

              const matchedSkills =
                Array.isArray(
                  evaluation?.matched_skills
                )
                  ? evaluation.matched_skills
                  : Array.isArray(
                      summary?.matched_skills
                    )
                  ? summary.matched_skills
                  : [];

              const missingSkills =
                Array.isArray(
                  evaluation?.missing_skills
                )
                  ? evaluation.missing_skills
                  : Array.isArray(
                      summary?.missing_skills
                    )
                  ? summary.missing_skills
                  : [];

              const reason =
                evaluation?.reason ||
                summary?.reason ||
                "AI evaluation reason is not available.";

              const minimumSkillMatches =
                jobRole?.minimum_skill_matches ??
                jobRole?.required_skill_count ??
                "Not available";

              const isUpdating =
                decisionLoading === application?.id;

              return (
                <>
                  <div className="eyebrow">
                    APPLICATION REVIEW
                  </div>

                  <h1>{name}</h1>

                  <p>
                    {jobRole?.role_name ||
                      "Role"}{" "}
                    ·{" "}
                    {application?.application_id ||
                      "Application"}
                  </p>

                  <div
                    style={{
                      display: "grid",
                      gap: 12,
                      color: "#aeb6c4",
                      fontSize: 12,
                      marginTop: 20,
                    }}
                  >
                    <div>
                      <b>Status:</b>{" "}
                      {String(status).replaceAll(
                        "_",
                        " "
                      )}
                    </div>

                    <div>
                      <b>Email:</b>{" "}
                      {candidate?.email ||
                        "Not available"}
                    </div>

                    <div>
                      <b>Role requirement:</b>{" "}
                      {jobRole?.description ||
                        "Not available"}
                    </div>

                    <div>
                      <b>Minimum CGPA:</b>{" "}
                      {jobRole?.minimum_cgpa ??
                        "Not available"}
                    </div>

                    <div>
                      <b>Minimum skill matches:</b>{" "}
                      {minimumSkillMatches}
                    </div>
                  </div>

                  <div
                    style={{
                      marginTop: 24,
                      padding: 18,
                      borderRadius: 14,
                      background:
                        "rgba(140,123,255,.06)",
                      border:
                        "1px solid rgba(140,123,255,.18)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10,
                        letterSpacing: "0.16em",
                        color: "#8f86ff",
                        marginBottom: 14,
                      }}
                    >
                      VTAB AI ELIGIBILITY EVALUATION
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        alignItems: "center",
                        gap: 12,
                        marginBottom: 16,
                      }}
                    >
                      <span
                        style={{
                          color: "#aeb6c4",
                          fontSize: 12,
                        }}
                      >
                        AI Decision
                      </span>

                      <strong
                        style={{
                          color:
                            decision ===
                            "shortlisted"
                              ? "#65e6b4"
                              : decision ===
                                "rejected"
                              ? "#ff7187"
                              : "#b9b2ff",
                          textTransform:
                            "uppercase",
                          fontSize: 12,
                        }}
                      >
                        {decision ||
                          "NOT EVALUATED"}
                      </strong>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        alignItems: "center",
                        marginBottom: 10,
                      }}
                    >
                      <span
                        style={{
                          color: "#aeb6c4",
                          fontSize: 12,
                        }}
                      >
                        Overall Eligibility
                      </span>

                      <strong
                        style={{
                          color:
                            overallEligible ===
                            true
                              ? "#65e6b4"
                              : overallEligible ===
                                false
                              ? "#ff7187"
                              : "#737d90",
                          fontSize: 12,
                        }}
                      >
                        {overallEligible === true
                          ? "ELIGIBLE"
                          : overallEligible === false
                          ? "NOT ELIGIBLE"
                          : "NOT AVAILABLE"}
                      </strong>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        alignItems: "center",
                        marginBottom: 10,
                      }}
                    >
                      <span
                        style={{
                          color: "#aeb6c4",
                          fontSize: 12,
                        }}
                      >
                        CGPA Eligibility
                      </span>

                      <strong
                        style={{
                          color:
                            cgpaEligible === true
                              ? "#65e6b4"
                              : cgpaEligible === false
                              ? "#ff7187"
                              : "#737d90",
                          fontSize: 12,
                        }}
                      >
                        {cgpaEligible === true
                          ? "PASS"
                          : cgpaEligible === false
                          ? "FAIL"
                          : "NOT AVAILABLE"}
                      </strong>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        alignItems: "center",
                        marginBottom: 14,
                      }}
                    >
                      <span
                        style={{
                          color: "#aeb6c4",
                          fontSize: 12,
                        }}
                      >
                        Skill Eligibility
                      </span>

                      <strong
                        style={{
                          color:
                            skillsEligible === true
                              ? "#65e6b4"
                              : skillsEligible === false
                              ? "#ff7187"
                              : "#737d90",
                          fontSize: 12,
                        }}
                      >
                        {skillsEligible === true
                          ? "PASS"
                          : skillsEligible === false
                          ? "FAIL"
                          : "NOT AVAILABLE"}
                      </strong>
                    </div>

                    <div style={{ marginTop: 12 }}>
                      <div
                        style={{
                          color: "#737d90",
                          fontSize: 10,
                          letterSpacing: "0.12em",
                          marginBottom: 8,
                        }}
                      >
                        MATCHED SKILLS (
                        {matchedSkills.length})
                      </div>

                      {matchedSkills.length > 0 ? (
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: 7,
                          }}
                        >
                          {matchedSkills.map(
                            (skill) => (
                              <span
                                key={skill}
                                style={{
                                  padding:
                                    "6px 9px",
                                  borderRadius: 7,
                                  background:
                                    "rgba(101,230,180,.07)",
                                  border:
                                    "1px solid rgba(101,230,180,.18)",
                                  color: "#65e6b4",
                                  fontSize: 10,
                                }}
                              >
                                ✓ {skill}
                              </span>
                            )
                          )}
                        </div>
                      ) : (
                        <span
                          style={{
                            color: "#737d90",
                            fontSize: 11,
                          }}
                        >
                          No matched skills recorded.
                        </span>
                      )}
                    </div>

                    <div style={{ marginTop: 16 }}>
                      <div
                        style={{
                          color: "#737d90",
                          fontSize: 10,
                          letterSpacing: "0.12em",
                          marginBottom: 8,
                        }}
                      >
                        MISSING SKILLS (
                        {missingSkills.length})
                      </div>

                      {missingSkills.length > 0 ? (
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: 7,
                          }}
                        >
                          {missingSkills.map(
                            (skill) => (
                              <span
                                key={skill}
                                style={{
                                  padding:
                                    "6px 9px",
                                  borderRadius: 7,
                                  background:
                                    "rgba(255,113,135,.07)",
                                  border:
                                    "1px solid rgba(255,113,135,.18)",
                                  color: "#ff7187",
                                  fontSize: 10,
                                }}
                              >
                                × {skill}
                              </span>
                            )
                          )}
                        </div>
                      ) : (
                        <span
                          style={{
                            color: "#65e6b4",
                            fontSize: 11,
                          }}
                        >
                          No missing skills 🎯
                        </span>
                      )}
                    </div>

                    <div
                      style={{
                        marginTop: 18,
                        paddingTop: 14,
                        borderTop:
                          "1px solid rgba(255,255,255,.06)",
                      }}
                    >
                      <div
                        style={{
                          color: "#737d90",
                          fontSize: 10,
                          letterSpacing: "0.12em",
                          marginBottom: 7,
                        }}
                      >
                        AI REASON
                      </div>

                      <p
                        style={{
                          margin: 0,
                          color: "#c5cad4",
                          fontSize: 11,
                          lineHeight: 1.6,
                        }}
                      >
                        {reason}
                      </p>
                    </div>
                  </div>

                  {selected.actionMessage && (
                    <div
                      style={{
                        marginTop: 18,
                        padding: 12,
                        borderRadius: 10,
                        background:
                          "rgba(140,123,255,.06)",
                        border:
                          "1px solid rgba(140,123,255,.18)",
                        color: "#b9b2ff",
                        fontSize: 11,
                      }}
                    >
                      {selected.actionMessage}
                    </div>
                  )}

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 10,
                      marginTop: 22,
                    }}
                  >
                    <button
                      className="primary-button"
                      onClick={() =>
                        updateDecision(
                          selected,
                          "approved"
                        )
                      }
                      disabled={
                        isUpdating ||
                        status === "approved" ||
                        status === "selected" ||
                        status === "rejected"
                      }
                    >
                      {isUpdating
                        ? "UPDATING..."
                        : "APPROVE"}
                    </button>

                    <button
                      className="primary-button"
                      onClick={() =>
                        updateDecision(
                          selected,
                          "rejected"
                        )
                      }
                      disabled={
                        isUpdating ||
                        status === "rejected"
                      }
                      style={{
                        borderColor:
                          "rgba(255,113,135,.25)",
                        color: "#ff7187",
                      }}
                    >
                      {isUpdating
                        ? "UPDATING..."
                        : "REJECT"}
                    </button>
                  </div>

                  <button
                    className="primary-button"
                    style={{
                      marginTop: 10,
                      width: "100%",
                    }}
                    onClick={() =>
                      setSelected(null)
                    }
                  >
                    CLOSE REVIEW
                  </button>
                </>
              );
            })()}
          </div>
        </div>
      )}
    </div>
  );
}
function Feedback({ token, onError }) {
  const [candidates, setCandidates] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);

  const [values, setValues] = useState({
    technical_skills: "",
    communication: "",
    problem_solving: "",
    overall_performance: "",
    recommendation: "",
    reviewer_comments: "",
  });

  useEffect(() => {
    let mounted = true;

    apiRequest("/api/candidates", {}, token)
      .then((result) => {
        if (!mounted) return;

        const items = Array.isArray(result?.items) ? result.items : [];

        const interviewCandidates = items.filter((item) =>
          [
            "interview_scheduled",
            "interview_completed",
            "interview_pending",
          ].includes(item?.application?.status)
        );

        const availableCandidates =
          interviewCandidates.length > 0 ? interviewCandidates : items;

        setCandidates(availableCandidates);

        if (availableCandidates[0]?.application?.id) {
          setSelectedId(availableCandidates[0].application.id);
        }
      })
      .catch((error) => {
        console.error("Failed to load candidates:", error);
        onError(error);
      });

    return () => {
      mounted = false;
    };
  }, [token]);

  const selected = candidates.find(
    (item) => item?.application?.id === selectedId
  );

  const setField = (field, value) => {
    setValues((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const submitFeedback = async () => {
    if (!selectedId) {
      onError(new Error("Select an interview application first."));
      return;
    }

    const numericFields = [
      "technical_skills",
      "communication",
      "problem_solving",
      "overall_performance",
    ];

    const invalidRating = numericFields.some(
      (field) =>
        !values[field] ||
        Number(values[field]) < 1 ||
        Number(values[field]) > 5
    );

    if (invalidRating || !values.recommendation) {
      onError(
        new Error(
          "Complete all four ratings and select a recommendation before submitting."
        )
      );
      return;
    }

    setSaving(true);
    setSubmitted(false);

    try {
      console.log("========================================");
      console.log("SUBMITTING INTERVIEW FEEDBACK");
      console.log("Application ID:", selectedId);
      console.log("Candidate:", selected?.candidate?.candidate_name);
      console.log("========================================");

      const result = await apiRequest(
        "/api/interview-feedback",
        {
          method: "POST",
          body: JSON.stringify({
            application_id: selectedId,
            reviewer_name: "Interview Manager",
            technical_skills: Number(values.technical_skills),
            communication: Number(values.communication),
            problem_solving: Number(values.problem_solving),
            overall_performance: Number(values.overall_performance),
            recommendation: values.recommendation,
            reviewer_comments: values.reviewer_comments || "",
          }),
        },
        token
      );

      console.log("========================================");
      console.log("INTERVIEW FEEDBACK SUCCESS");
      console.log("Backend result:", result);
      console.log("========================================");

      setSubmitted(true);

      // Refresh candidate data so the new application status
      // appears immediately in the manager portal.
      try {
        const refreshed = await apiRequest(
          "/api/candidates",
          {},
          token
        );

        const refreshedItems = Array.isArray(refreshed?.items)
          ? refreshed.items
          : [];

        const refreshedInterviewCandidates = refreshedItems.filter((item) =>
          [
            "interview_scheduled",
            "interview_completed",
            "interview_pending",
            "selected",
            "approved",
          ].includes(item?.application?.status)
        );

        setCandidates(
          refreshedInterviewCandidates.length
            ? refreshedInterviewCandidates
            : refreshedItems
        );
      } catch (refreshError) {
        console.warn(
          "Feedback saved, but candidate list refresh failed:",
          refreshError
        );
      }
    } catch (error) {
      console.error("========================================");
      console.error("INTERVIEW FEEDBACK ERROR");
      console.error(error);
      console.error("========================================");

      setSubmitted(false);
      onError(error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="feedback-wrap">
      <div className="section-intro">
        <div>
          <span className="eyebrow">MANAGER ONLY / LIVE API</span>
          <h2>Interview Feedback</h2>
          <p>
            Submit interviewer evaluation through the FastAPI feedback service.
          </p>
        </div>
      </div>

      <div className="feedback-card">
        <label className="wide-label">
          INTERVIEW APPLICATION

          <select
            value={selectedId}
            onChange={(event) => {
              setSelectedId(event.target.value);
              setSubmitted(false);
            }}
          >
            <option value="">Select application</option>

            {candidates.map((item, index) => (
              <option
                key={`${item?.application?.id}-${index}`}
                value={item?.application?.id}
              >
                {item?.candidate?.candidate_name || "Candidate"} ·{" "}
                {item?.application?.application_id ||
                  item?.application?.id}
              </option>
            ))}
          </select>
        </label>

        <div className="feedback-candidate">
          <div className="candidate-avatar large">
            {(selected?.candidate?.candidate_name || "C")
              .split(" ")
              .map((part) => part[0])
              .slice(0, 2)
              .join("")
              .toUpperCase()}
          </div>

          <div>
            <h3>
              {selected?.candidate?.candidate_name ||
                "Select an application"}
            </h3>

            <p>
              {selected?.job_role?.role_name || "Interview application"} ·
              Manager evaluation
            </p>
          </div>

          <span className="candidate-status-chip">
            {selected?.application?.status
              ? String(selected.application.status).replaceAll("_", " ")
              : "Not selected"}
          </span>
        </div>

        <div className="rating-grid">
          {[
            ["technical_skills", "Technical Skills"],
            ["communication", "Communication"],
            ["problem_solving", "Problem Solving"],
            ["overall_performance", "Overall Performance"],
          ].map(([field, label]) => (
            <label key={field}>
              {label}

              <select
                value={values[field]}
                onChange={(event) =>
                  setField(field, event.target.value)
                }
              >
                <option value="">Select rating</option>
                <option value="5">5 - Excellent</option>
                <option value="4">4 - Good</option>
                <option value="3">3 - Average</option>
                <option value="2">2 - Needs improvement</option>
                <option value="1">1 - Poor</option>
              </select>
            </label>
          ))}
        </div>

        <label className="wide-label">
          RECOMMENDATION

          <select
            value={values.recommendation}
            onChange={(event) =>
              setField("recommendation", event.target.value)
            }
          >
            <option value="">Select recommendation</option>
            <option value="Selected">Selected</option>
            <option value="Rejected">Rejected</option>
            <option value="Next Round">Next Round</option>
          </select>
        </label>

        <label className="wide-label">
          INTERVIEW COMMENTS

          <textarea
            value={values.reviewer_comments}
            onChange={(event) =>
              setField("reviewer_comments", event.target.value)
            }
            placeholder="Add structured interviewer observations..."
          />
        </label>

        <button
          className="primary-button"
          onClick={submitFeedback}
          disabled={saving}
        >
          {saving
            ? "SAVING..."
            : submitted
            ? "FEEDBACK SAVED ✓"
            : "SUBMIT INTERVIEW FEEDBACK"}
        </button>
      </div>
    </div>
  );
}

function Analytics({ token, onError }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    apiRequest("/api/manager/analytics", {}, token)
      .then((result) => {
        if (mounted) setData(result);
      })
      .catch(onError)
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const metrics = useMemo(() => {
    if (!data) return [];

    const source = data?.analytics || data?.data || data;

    const findNumber = (...keys) => {
      for (const key of keys) {
        const value = source?.[key];
        if (typeof value === "number") return value;
        if (typeof value === "string" && value.trim() && !Number.isNaN(Number(value))) {
          return Number(value);
        }
      }
      return 0;
    };

    return [
      {
        label: "Total Applications",
        value: findNumber("total_applications", "total_candidates", "applications"),
        suffix: "",
      },
      {
        label: "Interviews Scheduled",
        value: findNumber(
          "interview_scheduled",
          "interviews_scheduled",
          "scheduled_interviews",
          "scheduled"
        ),
        suffix: "",
      },
      {
        label: "Interviews Completed",
        value: findNumber(
          "interview_completed",
          "interviews_completed",
          "completed_interviews",
          "completed"
        ),
        suffix: "",
      },
    ];
  }, [data]);

  return (
    <div>
      <div className="section-intro">
        <div>
          <span className="eyebrow">MANAGER ANALYTICS / LIVE API</span>
          <h2>Decision Intelligence</h2>
          <p>Operational metrics loaded from the authenticated backend.</p>
        </div>
      </div>

      {loading && <p style={{ color: "#737d90" }}>Loading live analytics...</p>}

      {!loading && metrics.length === 0 && (
        <div className="analytics-card">
          <span>Analytics response received</span>
          <strong>API</strong>
          <small>The backend did not expose numeric metric fields.</small>
        </div>
      )}

      <div className="analytics-grid">
        {metrics.map((metric) => (
          <div className="analytics-card" key={metric.label}>
            <span>{metric.label}</span>
            <strong>
              {metric.value}
              <small>{metric.suffix}</small>
            </strong>
            <div className="sparkline">
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function HRPortal({ session, onHome, onAuthError }) {
  const [active, setActive] = useState("Offer Approvals");
  const [pageError, setPageError] = useState("");

  const handleError = (error) => {
    setPageError(error.message || "Something went wrong.");
    onAuthError(error);
  };

  return (
    <PortalLayout
      role="hr"
      active={active}
      setActive={setActive}
      onHome={onHome}
      error={pageError}
    >
      {active === "Offer Approvals" && (
        <OfferApprovals token={session.access_token} onError={handleError} />
      )}

      {active === "Employee Records" && (
        <EmployeeRecords token={session.access_token} onError={handleError} />
      )}

      {active === "AI Audit Logs" && (
        <AuditLogs token={session.access_token} onError={handleError} />
      )}
    </PortalLayout>
  );
}

function OfferApprovals({ token, onError }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentActionLoading, setDocumentActionLoading] = useState(null);
  const [finalApproving, setFinalApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  const loadCandidates = async () => {
    setLoading(true);

    try {
      // HR uses the dedicated offer approvals endpoint.
      const result = await apiRequest(
        "/api/hr/offer-approvals",
        {},
        token
      );

      const items = Array.isArray(result?.items) ? result.items : [];
      setCandidates(items);

      // Load the document verification records used by HR review.
      setDocumentLoading(true);

      try {
        const documentResult = await apiRequest(
          "/api/hr/document-verification",
          {},
          token
        );

        const documentItems = Array.isArray(documentResult?.items)
          ? documentResult.items
          : Array.isArray(documentResult?.documents)
          ? documentResult.documents
          : [];

        setDocuments(documentItems);
      } catch (documentError) {
        console.error(
          "Document verification loading failed:",
          documentError
        );
        setDocuments([]);
      } finally {
        setDocumentLoading(false);
      }
    } catch (error) {
      onError(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  /*
   * HR should see candidates only after the manager has made the
   * hiring decision. "approved" is the status written by the
   * manager decision endpoint.
   *
   * "selected" is also accepted so this remains compatible with
   * older records that used that status.
   */
  const approvedCandidates = candidates.filter((item) =>
    [
      "approved",
      "selected",
      "manager_approved",
      "documents_pending",
      "documents_verifying",
      "onboarding",
    ].includes(item?.application?.status)
  );

  const getSelectedDocuments = (item) => {
    const applicationId =
      item?.application?.id ||
      item?.application?.application_id ||
      null;

    const candidateId = item?.candidate?.id || null;

    if (!applicationId && !candidateId) return [];

    const matched = documents.filter((document) => {
      const sameApplication =
        applicationId &&
        document?.application_id === applicationId;

      const sameCandidate =
        candidateId &&
        document?.candidate_id === candidateId;

      return sameApplication || sameCandidate;
    });

    const uniqueMap = new Map();
    for (const doc of matched) {
      const name = doc?.document_name || "Document";
      const existing = uniqueMap.get(name);
      if (!existing) {
        uniqueMap.set(name, doc);
      } else {
        const existingApproved = ["approved", "verified"].includes(existing?.verification_status);
        const currentApproved = ["approved", "verified"].includes(doc?.verification_status);
        if (currentApproved && !existingApproved) {
          uniqueMap.set(name, doc);
        }
      }
    }

    return Array.from(uniqueMap.values());
  };

  const approveDocument = async (document) => {
    if (!document?.id) {
      onError(new Error("Document ID is missing."));
      return;
    }

    if (
      !window.confirm(
        `Approve ${document?.document_name || "this document"} for HR verification?`
      )
    ) {
      return;
    }

    setDocumentActionLoading(document.id);

    try {
      const result = await apiRequest(
        `/api/documents/${document.id}/approve`,
        {
          method: "POST",
        },
        token
      );

      const updatedDocument = result?.document || result?.data || null;

      setDocuments((current) =>
        current.map((item) =>
          item?.id === document.id
            ? {
                ...item,
                ...(updatedDocument || {}),
                verification_status:
                  updatedDocument?.verification_status ||
                  updatedDocument?.status ||
                  "approved",
              }
            : item
        )
      );

      setSelected((current) => {
        if (!current) return current;

        return {
          ...current,
          documentActionMessage:
            `${document?.document_name || "Document"} approved successfully.`,
        };
      });
    } finally {
      setDocumentActionLoading(null);
    }
  };

  const selectedDocs = getSelectedDocuments(selected);
  const hasDocs = selectedDocs.length > 0;
  const allDocsApproved =
    hasDocs &&
    selectedDocs.every((doc) =>
      ["approved", "verified"].includes(doc?.verification_status)
    );

  const approveAndOnboardCandidate = async () => {
    const applicationId =
      selected?.application?.id || selected?.application?.application_id;

    if (!applicationId) {
      onError(new Error("Application ID is missing."));
      return;
    }

    if (!allDocsApproved) {
      onError(
        new Error(
          "All required documents must be approved before final HR approval."
        )
      );
      return;
    }

    if (
      !window.confirm(
        `Give final HR approval and initiate onboarding for ${
          selected?.candidate?.candidate_name || "this candidate"
        }?`
      )
    ) {
      return;
    }

    setFinalApproving(true);

    try {
      await apiRequest(
        `/api/hr/offer-approvals/${applicationId}/approve`,
        {
          method: "POST",
        },
        token
      );

      setSelected(null);
      await loadCandidates();
    } catch (error) {
      onError(error);
    } finally {
      setFinalApproving(false);
    }
  };

  const handleQuickApprove = async (item) => {
    const applicationId =
      item?.application?.id || item?.application?.application_id;
    if (!applicationId) return;

    if (
      !window.confirm(
        `Give final HR approval and initiate onboarding for ${
          item?.candidate?.candidate_name || "this candidate"
        }?`
      )
    ) {
      return;
    }

    setFinalApproving(true);
    try {
      await apiRequest(
        `/api/hr/offer-approvals/${applicationId}/approve`,
        { method: "POST" },
        token
      );
      setSelected(null);
      await loadCandidates();
    } catch (error) {
      onError(error);
    } finally {
      setFinalApproving(false);
    }
  };

  const handleQuickReject = async (item) => {
    const applicationId =
      item?.application?.id || item?.application?.application_id;
    if (!applicationId) return;

    if (
      !window.confirm(
        `Are you sure you want to REJECT ${
          item?.candidate?.candidate_name || "this candidate"
        }?`
      )
    ) {
      return;
    }

    setRejecting(true);
    try {
      await apiRequest(
        `/api/hr/offer-approvals/${applicationId}/reject`,
        { method: "POST" },
        token
      );
      setSelected(null);
      await loadCandidates();
    } catch (error) {
      onError(error);
    } finally {
      setRejecting(false);
    }
  };

  return (
    <div>
      <div className="section-intro">
        <div>
          <span className="eyebrow">HR OPERATIONS / LIVE DATA</span>
          <h2>Pending Offer Approvals</h2>
          <p>
            Candidates approved by the Manager are loaded from the same
            authenticated recruitment database.
          </p>
        </div>

        <div className="queue-stat">
          <b>{String(approvedCandidates.length).padStart(2, "0")}</b>
          <span>approved candidates</span>
        </div>
      </div>

      <div className="offer-table">
        <div className="table-head">
          <span>Candidate</span>
          <span>Role</span>
          <span>Status</span>
          <span>Application ID</span>
          <span>Action</span>
        </div>

        {loading && (
          <div className="table-row">
            <span>Loading...</span>
            <span>—</span>
            <span>—</span>
            <span>—</span>
            <span>—</span>
          </div>
        )}

        {!loading && approvedCandidates.length === 0 && (
          <div className="table-row">
            <span>No approved candidates</span>
            <span>—</span>
            <span>Waiting for manager decision</span>
            <span>—</span>
            <span>—</span>
          </div>
        )}

        {!loading &&
          approvedCandidates.map((item, index) => (
            <div
              className="table-row"
              key={`${item?.application?.id}-${index}`}
            >
              <span>
                <b>{item?.candidate?.candidate_name || "Candidate"}</b>
                <small>{item?.candidate?.email || "No email"}</small>
              </span>

              <span>{item?.job_role?.role_name || "—"}</span>

              <span className="verified">
                {String(
                  item?.application?.status || "unknown"
                ).replaceAll("_", " ")}
              </span>

              <span>
                {item?.application?.application_id ||
                  item?.application?.id ||
                  "—"}
              </span>

              {(() => {
                const itemDocs = getSelectedDocuments(item);
                const isItemApproved =
                  itemDocs.length > 0 &&
                  itemDocs.every((d) =>
                    ["approved", "verified"].includes(d?.verification_status)
                  );
                const isAlreadyOnboard =
                  item?.application?.status === "onboarding";

                return (
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      alignItems: "center",
                      flexWrap: "wrap",
                    }}
                  >
                    <button
                      className="small-button"
                      onClick={() => {
                        setSelected(item);
                        setDocumentActionLoading(null);
                      }}
                    >
                      Review
                    </button>

                    {!isAlreadyOnboard && (
                      <>
                        <button
                          className="small-button"
                          style={{
                            background: isItemApproved
                              ? "rgba(101,230,180,0.15)"
                              : "rgba(255,255,255,0.03)",
                            borderColor: isItemApproved
                              ? "#65e6b4"
                              : "rgba(255,255,255,0.1)",
                            color: isItemApproved ? "#65e6b4" : "#737d90",
                            cursor:
                              isItemApproved && !finalApproving
                                ? "pointer"
                                : "not-allowed",
                            opacity: isItemApproved ? 1 : 0.6,
                          }}
                          onClick={() => handleQuickApprove(item)}
                          disabled={!isItemApproved || finalApproving}
                          title={
                            isItemApproved
                              ? "Approve candidate & initiate onboarding"
                              : "All required documents must be approved first"
                          }
                        >
                          Approve
                        </button>

                        <button
                          className="small-button"
                          style={{
                            background: "rgba(255,92,92,0.1)",
                            borderColor: "rgba(255,92,92,0.3)",
                            color: "#ff5c5c",
                          }}
                          onClick={() => handleQuickReject(item)}
                          disabled={rejecting}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                );
              })()}
            </div>
          ))}
      </div>

      {selected && (
        <div
          className="menu-overlay"
          onClick={() => setSelected(null)}
          aria-label="Close HR offer review"
        >
          <div
            className="login-card"
            role="dialog"
            aria-modal="true"
            aria-label="HR offer review"
            style={{ maxWidth: 680, margin: "auto" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="eyebrow">HR OFFER REVIEW</div>

            <h1>
              {selected?.candidate?.candidate_name || "Candidate"}
            </h1>

            <p>
              {selected?.job_role?.role_name || "Role"} ·{" "}
              {selected?.application?.application_id ||
                selected?.application?.id ||
                "Application"}
            </p>

            <div
              style={{
                display: "grid",
                gap: 12,
                marginTop: 22,
                color: "#aeb6c4",
                fontSize: 12,
              }}
            >
              <div>
                <b>Status:</b>{" "}
                {String(
                  selected?.application?.status || "unknown"
                ).replaceAll("_", " ")}
              </div>

              <div>
                <b>Email:</b>{" "}
                {selected?.candidate?.email || "Not available"}
              </div>

              <div>
                <b>Phone:</b>{" "}
                {selected?.candidate?.phone_number || "Not available"}
              </div>

              <div>
                <b>AI Decision:</b>{" "}
                {selected?.ai_evaluation?.decision ||
                  selected?.manager_view?.ai_decision ||
                  "Not available"}
              </div>

              <div>
                <b>Overall Eligibility:</b>{" "}
                {selected?.ai_evaluation?.overall_eligible === true
                  ? "Eligible"
                  : selected?.ai_evaluation?.overall_eligible === false
                  ? "Not eligible"
                  : "Not available"}
              </div>

              <div>
                <b>AI Reason:</b>{" "}
                {selected?.ai_evaluation?.reason ||
                  selected?.ai_summary?.reason ||
                  "No AI evaluation reason available."}
              </div>
            </div>

            {/* Candidate documents returned by /api/hr/document-verification */}
            <div
              style={{
                marginTop: 24,
                padding: 18,
                borderRadius: 14,
                background: "rgba(140,123,255,.05)",
                border: "1px solid rgba(140,123,255,.15)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 14,
                }}
              >
                <div>
                  <div
                    style={{
                      color: "#8f86ff",
                      fontSize: 10,
                      letterSpacing: "0.16em",
                    }}
                  >
                    DOCUMENT VERIFICATION
                  </div>

                  <div
                    style={{
                      marginTop: 6,
                      color: "#eef0f6",
                      fontSize: 15,
                      fontWeight: 700,
                    }}
                  >
                    Required Documents
                  </div>
                </div>

                <span
                  style={{
                    color: "#737d90",
                    fontSize: 10,
                  }}
                >
                  {getSelectedDocuments(selected).length} document(s)
                </span>
              </div>

              {documentLoading ? (
                <div
                  style={{
                    color: "#737d90",
                    fontSize: 11,
                    padding: "10px 0",
                  }}
                >
                  Loading document verification records...
                </div>
              ) : getSelectedDocuments(selected).length === 0 ? (
                <div
                  style={{
                    color: "#737d90",
                    fontSize: 11,
                    padding: "10px 0",
                  }}
                >
                  No document verification records found for this
                  application.
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gap: 9,
                  }}
                >
                  {getSelectedDocuments(selected).map((document) => {
                    const status =
                      document?.verification_status || "unknown";

                    const statusLabel = String(status).replaceAll(
                      "_",
                      " "
                    );

                    const isApproved =
                      status === "approved" ||
                      status === "verified";

                    const isActionLoading =
                      documentActionLoading === document?.id;

                    const verificationResult =
                      document?.verification_result;

                    const aiMessage =
                      verificationResult?.message ||
                      verificationResult?.reason ||
                      null;

                    return (
                      <div
                        key={document?.id}
                        style={{
                          padding: 12,
                          borderRadius: 10,
                          background: "rgba(255,255,255,.018)",
                          border:
                            "1px solid rgba(255,255,255,.06)",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: 12,
                          }}
                        >
                          <div>
                            <div
                              style={{
                                color: "#eef0f6",
                                fontSize: 12,
                                fontWeight: 700,
                              }}
                            >
                              {document?.document_name || "Document"}
                            </div>

                            <div
                              style={{
                                marginTop: 5,
                                color: "#737d90",
                                fontSize: 10,
                              }}
                            >
                              {statusLabel}
                            </div>
                          </div>

                          <span
                            style={{
                              padding: "5px 8px",
                              borderRadius: 6,
                              background: isApproved
                                ? "rgba(101,230,180,.07)"
                                : "rgba(255,184,92,.07)",
                              border: isApproved
                                ? "1px solid rgba(101,230,180,.16)"
                                : "1px solid rgba(255,184,92,.16)",
                              color: isApproved
                                ? "#65e6b4"
                                : "#ffbd68",
                              fontSize: 9,
                              textTransform: "uppercase",
                            }}
                          >
                            {statusLabel}
                          </span>
                        </div>

                        {aiMessage && (
                          <div
                            style={{
                              marginTop: 9,
                              color: "#929aaa",
                              fontSize: 10,
                              lineHeight: 1.5,
                            }}
                          >
                            AI: {aiMessage}
                          </div>
                        )}

                        {!isApproved && (
                          <button
                            className="small-button"
                            style={{
                              marginTop: 10,
                              width: "100%",
                            }}
                            onClick={() =>
                              approveDocument(document)
                            }
                            disabled={isActionLoading}
                          >
                            {isActionLoading
                              ? "APPROVING..."
                              : "APPROVE DOCUMENT"}
                          </button>
                        )}

                        {isApproved && (
                          <div
                            style={{
                              marginTop: 10,
                              color: "#65e6b4",
                              fontSize: 10,
                              fontWeight: 600,
                            }}
                          >
                            ✓ HR approved
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {selected?.documentActionMessage && (
              <div
                style={{
                  marginTop: 14,
                  padding: 12,
                  borderRadius: 10,
                  background: "rgba(101,230,180,.045)",
                  border: "1px solid rgba(101,230,180,.15)",
                  color: "#65e6b4",
                  fontSize: 11,
                }}
              >
                {selected.documentActionMessage}
              </div>
            )}

            {selected?.application?.status !== "onboarding" && selected?.application?.status !== "rejected" && (
              <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 8 }}>
                <button
                  className="primary-button"
                  style={{
                    width: "100%",
                    background: allDocsApproved
                      ? "linear-gradient(135deg, #6d5ce7, #8f86ff)"
                      : "rgba(255,255,255,0.06)",
                    border: allDocsApproved
                      ? "1px solid #8f86ff"
                      : "1px solid rgba(255,255,255,0.1)",
                    color: allDocsApproved ? "#ffffff" : "#737d90",
                    opacity: allDocsApproved ? 1 : 0.6,
                    cursor:
                      allDocsApproved && !finalApproving
                        ? "pointer"
                        : "not-allowed",
                  }}
                  onClick={approveAndOnboardCandidate}
                  disabled={!allDocsApproved || finalApproving}
                >
                  {finalApproving
                    ? "APPROVING & ONBOARDING..."
                    : "APPROVE & ONBOARD CANDIDATE"}
                </button>

                {!allDocsApproved && (
                  <div
                    style={{
                      color: "#ff8c8c",
                      fontSize: 11,
                      textAlign: "center",
                      marginBottom: 4,
                    }}
                  >
                    All required documents must be approved before final approval.
                  </div>
                )}

                <button
                  className="primary-button"
                  style={{
                    width: "100%",
                    background: "rgba(255,92,92,0.12)",
                    border: "1px solid rgba(255,92,92,0.3)",
                    color: "#ff5c5c",
                  }}
                  onClick={() => handleQuickReject(selected)}
                  disabled={rejecting}
                >
                  {rejecting ? "REJECTING..." : "REJECT CANDIDATE"}
                </button>
              </div>
            )}

            <button
              className="primary-button"
              style={{ width: "100%", marginTop: selected?.application?.status === "onboarding" ? 24 : 8 }}
              onClick={() => setSelected(null)}
            >
              CLOSE REVIEW
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EmployeeRecords({ token, onError }) {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiRequest("/api/hr/employees", {}, token)
      .then((result) => {
        const data = result?.employees || result?.items || result?.data || result;
        setEmployees(Array.isArray(data) ? data : []);
      })
      .catch(onError)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="section-intro">
        <div>
          <span className="eyebrow">HR DIRECTORY / LIVE API</span>
          <h2>Employee Records</h2>
          <p>Employee records loaded from the authenticated HR endpoint.</p>
        </div>
      </div>

      {loading && (
        <p style={{ color: "#737d90" }}>Loading employee records...</p>
      )}

      {!loading && employees.length === 0 && (
        <div className="employee-card">
          <h3>No employee records returned</h3>
          <p>The HR endpoint returned an empty employee list.</p>
        </div>
      )}

      <div className="employee-grid">
        {employees.map((employee, index) => {
          const name =
            employee?.candidate?.candidate_name ||
            employee?.candidate_name ||
            employee?.full_name ||
            employee?.name ||
            employee?.employee_name ||
            "Employee";

          const role =
            employee?.job_role?.role_name ||
            employee?.role ||
            employee?.job_role ||
            employee?.designation ||
            "Employee";

          const status = String(
            employee?.application?.status ||
            employee?.status ||
            "onboarding"
          ).replaceAll("_", " ");

          const progress = Number(
            employee?.progress ??
              employee?.onboarding_progress ??
              employee?.completion_percentage ??
              100
          );

          return (
            <div className="employee-card" key={`${name}-${index}`}>
              <div className="candidate-main">
                <div className="candidate-avatar">{name[0]}</div>
                <div>
                  <h3>{name}</h3>
                  <p>{role}</p>
                </div>
              </div>

              <div className="employee-meta">
                <span>
                  STATUS
                  <b>{status}</b>
                </span>
                <span>
                  ONBOARDING
                  <b>{progress}%</b>
                </span>
              </div>

              <div className="progress-line">
                <i style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AuditLogs({ token, onError }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiRequest("/api/hr/audit-logs", {}, token)
      .then((result) => {
        const data = result?.logs || result?.items || result?.data || result;
        setLogs(Array.isArray(data) ? data : []);
      })
      .catch(onError)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="section-intro">
        <div>
          <span className="eyebrow">SYSTEM TRACE / LIVE API</span>
          <h2>AI Audit Logs</h2>
          <p>Operational history returned by the authenticated HR endpoint.</p>
        </div>
      </div>

      {loading && <p style={{ color: "#737d90" }}>Loading audit logs...</p>}

      {!loading && logs.length === 0 && (
        <div className="audit-list">
          <div className="audit-row">
            <span className="audit-index">01</span>
            <span className="audit-dot" />
            <div>
              <b>No audit records returned</b>
              <small>The HR audit endpoint returned an empty list.</small>
            </div>
            <time>—</time>
          </div>
        </div>
      )}

      {!loading && logs.length > 0 && (
        <div className="audit-list">
          {logs.map((log, index) => (
            <div className="audit-row" key={`${log?.id || "log"}-${index}`}>
              <span className="audit-index">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="audit-dot" />
              <div>
                <b>
                  {log?.action ||
                    log?.event ||
                    log?.message ||
                    "Recruitment event"}
                </b>
                <small>
                  {log?.description ||
                    log?.actor ||
                    log?.performed_by ||
                    "VTAB AI / Recruitment workflow"}
                </small>
              </div>
              <time dateTime={log?.created_at ? new Date(log.created_at).toISOString() : undefined}>
                {log?.created_at
                  ? new Date(log.created_at).toLocaleDateString()
                  : "Recent"}
              </time>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;