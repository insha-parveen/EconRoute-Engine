// components/EmptyState.tsx — friendly guidance when no requests exist yet.

export default function EmptyState() {
  return (
    <div className="rounded-xl bg-panel p-10 text-center shadow-card">
      <div className="text-4xl">💸</div>
      <h2 className="mt-3 text-lg font-semibold">No requests yet</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
        Send a request to <code className="rounded bg-slate-100 px-1">POST /v1/chat/completions</code>{" "}
        and it will stream in here live. Try:
      </p>
      <pre className="mx-auto mt-4 max-w-lg overflow-x-auto rounded-lg bg-slate-900 p-4 text-left text-xs text-slate-100">
{`curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"auto","messages":[{"role":"user","content":"What is the capital of France?"}]}'`}
      </pre>
    </div>
  );
}
