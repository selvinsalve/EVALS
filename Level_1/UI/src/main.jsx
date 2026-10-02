import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Upload,
  Sparkles,
  Sun,
  Moon,
  FileText,
  Download,
  AlertCircle,
  X,
  ChevronDown,
  ChevronUp,
  Activity,
  Gem,
} from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [files, setFiles] = useState([]);
  const [text, setText] = useState("");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("goldenforge-theme") || "dark",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("goldenforge-theme", theme);
  }, [theme]);

  const stats = useMemo(() => {
    if (!result?.goldens?.length) return null;
    const qs = result.goldens
      .map((x) => x.synthetic_input_quality)
      .filter((x) => typeof x === "number");
    const cs = result.goldens
      .map((x) => x.context_quality)
      .filter((x) => typeof x === "number");
    return {
      input: qs.length
        ? (qs.reduce((a, b) => a + b, 0) / qs.length).toFixed(2)
        : "—",
      context: cs.length
        ? (cs.reduce((a, b) => a + b, 0) / cs.length).toFixed(2)
        : "—",
      evolutions: [
        ...new Set(result.goldens.flatMap((x) => x.evolutions || [])),
      ].length,
    };
  }, [result]);

  async function checkHealth() {
    try {
      setHealth(await fetch(`${API}/api/health`).then((r) => r.json()));
    } catch {
      setHealth({ ollama_connected: false });
    }
  }
  useEffect(() => {
    checkHealth();
  }, []);

  function onDrop(e) {
    e.preventDefault();
    const incoming = [...e.dataTransfer.files];
    setFiles((prev) => [...prev, ...incoming].slice(0, 20));
  }

  async function generate() {
    setError("");
    if (!files.length && !text.trim())
      return setError("Upload a document or paste document text.");
    setLoading(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("num_goldens", count);
      if (text.trim()) fd.append("document_text", text);
      files.forEach((f) => fd.append("files", f));
      const res = await fetch(`${API}/api/generate-goldens`, {
        method: "POST",
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Generation failed");
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function exportData(type) {
    if (!result) return;
    const res = await fetch(`${API}/api/export/${type}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(result),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `goldens.${type}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="logo">
            <Gem size={19} />
          </div>
          <div>
            <b>EvalData Level I</b>
            <span>Evaluation of AI systems</span>
          </div>
        </div>
        <div className="top-actions">
          <div className={`status ${health?.ollama_connected ? "ok" : ""}`}>
            <span></span>
            {health?.ollama_connected ? "Ollama connected" : "Ollama offline"}
          </div>
          <button
            className="theme-toggle"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            <span>{theme === "dark" ? "Light" : "Dark"}</span>
          </button>
        </div>
      </header>

      <main>
        <section className="hero">
          <div>
            <div className="eyebrow">
              <Sparkles size={12} /> DATA EVALUATION
            </div>
            <h1>
              Evaluate your AI systems with
              <br />
              <em>Goldens</em> by EvalData
            </h1>
            <p>
              Upload source documents, let <b>EvalData</b> construct context
              around your AI system, and inspect every generated{" "}
              <em>
                <b>Goldens </b>
              </em>
              before exporting your dataset.
            </p>
          </div>
        </section>

        <div className="workspace">
          <aside className="panel controls">
            <div className="panel-title">
              <h2>Source data</h2>
            </div>
            <label
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
            >
              <input
                type="file"
                multiple
                hidden
                onChange={(e) =>
                  setFiles((prev) => [...prev, ...e.target.files].slice(0, 20))
                }
              />
              <Upload size={25} />
              <b>Drop files here</b>
              <small>or click to browse</small>
              <small className="formats">
                PDF · DOCX · TXT · MD · CSV · JSON · SQL · SQLite
              </small>
            </label>
            {!!files.length && (
              <div className="file-list">
                {files.map((f, i) => (
                  <div className="file" key={i}>
                    <FileText size={16} />
                    <span>
                      {f.name}
                      <small>{(f.size / 1024 / 1024).toFixed(2)} MB</small>
                    </span>
                    <button
                      onClick={() => setFiles(files.filter((_, j) => j !== i))}
                    >
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="or">
              <span>OR</span>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste document or markdown content here..."
            />
            <div className="panel-title compact">
              <h2>Generation</h2>
            </div>
            <label className="field">
              <span>Goldens per context</span>
              <input
                type="number"
                min="1"
                max="100"
                value={count}
                onChange={(e) =>
                  setCount(Math.min(100, Math.max(1, +e.target.value)))
                }
              />
            </label>
            <button className="generate" disabled={loading} onClick={generate}>
              {loading ? (
                <>
                  <span className="spinner" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  Generate Goldens
                </>
              )}
            </button>
            {error && (
              <div className="error">
                <AlertCircle size={17} />
                {error}
              </div>
            )}
          </aside>

          <section className="panel results">
            <div className="results-head">
              <div>
                <div className="panel-title">
                  <h2>Generated dataset</h2>
                </div>
                <small>
                  {result
                    ? `${result.total_generated} goldens generated in ${result.execution_time_seconds}s`
                    : "Results will appear here"}
                </small>
              </div>
              {result && (
                <div className="exports">
                  <button onClick={() => exportData("json")}>
                    <Download size={15} />
                    JSON
                  </button>
                  <button onClick={() => exportData("csv")}>
                    <Download size={15} />
                    CSV
                  </button>
                </div>
              )}
            </div>

            {result && stats && (
              <div className="metrics">
                <Metric label="Generated" value={result.total_generated} />
                <Metric label="Avg input quality" value={stats.input} />
                <Metric label="Avg context quality" value={stats.context} />
                <Metric label="Evolutions" value={stats.evolutions} />
              </div>
            )}

            {!result && !loading && (
              <div className="empty">
                <Sparkles size={42} />
                <h3>Your dataset starts here</h3>
                <p>
                  Configure a source on the left and generate synthetic
                  evaluation cases.
                </p>
              </div>
            )}
            {loading && (
              <div className="empty">
                <div className="loader-ring" />
                <h3>Constructing context & generating goldens</h3>
                <p>This can take a little while with a local model.</p>
              </div>
            )}

            {result?.goldens?.map((g, i) => (
              <GoldenCard
                key={g.id || i}
                golden={g}
                index={i}
                open={selected === i}
                onClick={() => setSelected(selected === i ? null : i)}
              />
            ))}
          </section>
        </div>
      </main>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}
function GoldenCard({ golden, index, open, onClick }) {
  return (
    <article className="golden">
      <button className="golden-head" onClick={onClick}>
        <div className="num">{String(index + 1).padStart(2, "0")}</div>
        <div className="question">{golden.input}</div>
        <div className="badges">
          {golden.evolutions?.map((e) => (
            <span key={e}>{e}</span>
          ))}
        </div>
        {open ? <ChevronUp /> : <ChevronDown />}
      </button>
      {open && (
        <div className="detail">
          <div>
            <div className="detail-label">EXPECTED OUTPUT</div>
            <p>{golden.expected_output || "—"}</p>
          </div>
          <div>
            <div className="detail-label">CONTEXT</div>
            <div className="context">
              {(golden.context || []).map((c, i) => (
                <p key={i}>{c}</p>
              ))}
            </div>
          </div>
          <div className="score-row">
            <span>
              Input quality <b>{golden.synthetic_input_quality ?? "—"}</b>
            </span>
            <span>
              Context quality <b>{golden.context_quality ?? "—"}</b>
            </span>
            <span>
              Source <b>{golden.source_file || "—"}</b>
            </span>
          </div>
        </div>
      )}
    </article>
  );
}

createRoot(document.getElementById("root")).render(<App />);
