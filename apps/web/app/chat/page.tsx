"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "How many type 2 diabetes patients are in the dataset?",
  "Search for metformin concepts",
  "What conditions are well represented in the data?",
  "Help me draft an application for a hypertension study",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text?: string) {
    const content = (text ?? input).trim();
    if (!content || loading) return;
    setInput("");
    setError(null);

    const next: Message[] = [...messages, { role: "user", content }];
    setMessages(next);
    setLoading(true);

    try {
      const { reply } = await api.llm.chat(next);
      setMessages([...next, { role: "assistant", content: reply }]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
      setMessages(next.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-5xl flex flex-col" style={{ height: "calc(100vh - 56px - 4rem)" }}>
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-6 text-white shrink-0">
        <h1 className="text-2xl font-bold">Discovery Assistant</h1>
        <p className="text-blue-200 text-sm mt-1">
          Ask about datasets, concepts, and patient counts - or draft an application.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto flex flex-col gap-4 mb-4 pr-1">
        {messages.length === 0 && (
          <div className="mt-2">
            <p className="text-sm text-gray-500 mb-3">Try asking:</p>
            <div className="flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-sm px-4 py-2.5 bg-white border border-gray-200 rounded-lg hover:border-blue-400 hover:text-blue-700 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${m.role === "user"
                ? "bg-blue-600 text-white rounded-br-sm"
                : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm"
                }`}
            >
              {m.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <div className="flex gap-1 items-center h-4">
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <p className="text-red-600 text-sm text-center">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="shrink-0">
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="text-xs text-gray-400 hover:text-gray-600 mb-2"
          >
            Clear conversation
          </button>
        )}
        <form
          onSubmit={(e) => { e.preventDefault(); send(); }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about the dataset..."
            disabled={loading}
            className="flex-1 bg-white border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-blue-600 text-white rounded-xl px-5 py-2.5 text-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
