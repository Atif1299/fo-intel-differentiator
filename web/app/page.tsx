"use client";

import { FormEvent, useState, type CSSProperties } from "react";

type FirmRecord = {
  fo_id?: string;
  common_name?: string;
  fo_type?: string;
  hq_city?: string;
  hq_country?: string;
  website?: string;
};

type AskResponse = {
  status: string;
  message: string;
  query: string;
  answer: string | null;
  records: FirmRecord[];
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function statusLabel(status: string): string {
  if (status === "ok") return "Answer";
  if (status === "insufficient_evidence") return "Not enough evidence";
  if (status === "not_ready") return "System warming up";
  return status.replace(/_/g, " ");
}

function typeLabel(t?: string): string {
  if (t === "single_family_office") return "Single-family office";
  if (t === "multi_family_office") return "Multi-family office";
  return t || "";
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = (await res.json()) as AskResponse;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "2.5rem 1.25rem" }}>
      <h1 style={{ fontSize: "1.75rem", fontWeight: 600, color: "#1e3a5f", margin: "0 0 0.35rem" }}>
        FO Intel
      </h1>
      <p style={{ color: "#5c5c5c", marginBottom: "1.75rem" }}>
        Search verified family office intelligence. Answers stay within sourced records — we decline when
        evidence is insufficient.
      </p>

      <form onSubmit={onSubmit} style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. Which single-family offices have venture signals?"
          required
          style={{
            flex: 1,
            padding: "0.75rem 1rem",
            border: "1px solid #cfc8bc",
            borderRadius: 4,
            font: "inherit",
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "0.75rem 1.1rem",
            background: "#1e3a5f",
            color: "#fff",
            border: 0,
            borderRadius: 4,
            font: "inherit",
            cursor: "pointer",
          }}
        >
          {loading ? "Searching…" : "Ask"}
        </button>
      </form>

      {error && (
        <div style={cardStyle}>
          <div style={statusStyle}>Connection issue</div>
          <p style={{ margin: 0 }}>
            We could not reach the research service. Please try again shortly.
          </p>
        </div>
      )}

      {result && (
        <div style={cardStyle}>
          <div
            style={{
              ...statusStyle,
              color: result.status === "ok" ? "#1e3a5f" : "#8a5a00",
            }}
          >
            {statusLabel(result.status)}
          </div>
          {result.status === "ok" && result.answer ? (
            <p style={{ margin: "0 0 1rem", whiteSpace: "pre-wrap", lineHeight: 1.55 }}>{result.answer}</p>
          ) : (
            <p style={{ margin: "0 0 1rem", lineHeight: 1.55 }}>{result.message}</p>
          )}
          {result.records?.length > 0 && (
            <div>
              <div style={{ ...statusStyle, marginBottom: "0.5rem" }}>Firms used in this answer</div>
              <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                {result.records.map((r) => (
                  <li key={r.fo_id || r.common_name} style={{ marginBottom: "0.35rem" }}>
                    <strong>{r.common_name || r.fo_id}</strong>
                    {r.fo_type ? ` — ${typeLabel(r.fo_type)}` : ""}
                    {r.hq_city || r.hq_country
                      ? ` · ${[r.hq_city, r.hq_country].filter(Boolean).join(", ")}`
                      : ""}
                    {r.website ? (
                      <>
                        {" · "}
                        <a href={r.website.startsWith("http") ? r.website : `https://${r.website}`} target="_blank" rel="noreferrer">
                          website
                        </a>
                      </>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </main>
  );
}

const cardStyle: CSSProperties = {
  background: "#fff",
  border: "1px solid #ddd6c8",
  borderRadius: 6,
  padding: "1.25rem",
};

const statusStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#5c5c5c",
  marginBottom: "0.75rem",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};
