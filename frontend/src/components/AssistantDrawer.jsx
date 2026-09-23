import { Bot, Send, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import api from '../api.js';
import { useAuth } from '../context.jsx';

const SUGGESTIONS = [
  'What are my tasks today?',
  'Why was my behavior flagged?',
  'How long will my next task take?',
  'What training do you recommend?',
  'Show my recent incidents',
];

export default function AssistantDrawer({ open, onClose }) {
  const { operator } = useAuth();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: "Hi! I'm your Operator Companion. I answer using live app data - tasks, safety, behavior, predictions and training. Safety-critical alerts always come from deterministic rules, not from me.",
    },
  ]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const ask = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setBusy(true);
    try {
      const { data } = await api.post('/assistant/ask', {
        operator_id: operator.operator_id,
        message: q,
      });
      setMessages((m) => [...m, { role: 'assistant', text: data.answer }]);
    } catch {
      setMessages((m) => [...m, { role: 'assistant', text: 'Sorry, I could not reach the server.' }]);
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;
  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[420px] bg-cat-steel border-l border-cat-line shadow-2xl z-50 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-cat-line">
        <div className="flex items-center gap-2">
          <Bot className="text-cat-yellow" size={20} />
          <div>
            <div className="font-bold text-sm">Smart Assistant</div>
            <div className="text-[11px] text-zinc-400">Rule-based and grounded in live application data</div>
          </div>
        </div>
        <button onClick={onClose} className="text-zinc-400 hover:text-white">
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-cat-yellow text-cat-black font-medium'
                  : 'bg-zinc-800 text-zinc-100 border border-cat-line'
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
        {busy && <div className="text-xs text-zinc-400">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 pb-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => ask(s)}
            className="text-[11px] rounded-full border border-cat-line px-2.5 py-1 text-zinc-300 hover:border-cat-yellow hover:text-cat-yellow"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="p-4 border-t border-cat-line flex gap-2">
        <input
          className="input"
          placeholder="Ask about tasks, safety, behavior…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask()}
        />
        <button className="btn-primary" onClick={() => ask()} disabled={busy}>
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
