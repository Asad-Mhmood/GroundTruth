import { ChevronDown, SlidersHorizontal } from "lucide-react";

const LANGUAGES = [
  { code: "", label: "Auto-detect" },
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "ur", label: "Urdu" },
  { code: "pa", label: "Punjabi" },
  { code: "bn", label: "Bengali" },
  { code: "ar", label: "Arabic" },
  { code: "es", label: "Spanish" },
];

export default function FilterPanel({
  open,
  onToggle,
  channel,
  onChannelChange,
  language,
  onLanguageChange,
  disabled,
}) {
  const activeCount = (channel.trim() ? 1 : 0) + (language ? 1 : 0);

  return (
    <div className="w-full">
      <button
        type="button"
        onClick={onToggle}
        className="mx-auto flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
        aria-expanded={open}
      >
        <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
        Filters
        {activeCount > 0 && (
          <span className="rounded-full bg-indigo-600 px-1.5 text-xs font-semibold text-white">
            {activeCount}
          </span>
        )}
        <ChevronDown
          className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="mt-3 grid gap-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Channel / YouTuber (optional)
            </span>
            <input
              type="text"
              value={channel}
              onChange={(event) => onChannelChange(event.target.value)}
              placeholder="e.g. Dhruv Rathee"
              maxLength={100}
              disabled={disabled}
              className="w-full rounded-xl border-0 bg-slate-50 px-3 py-2 text-sm text-slate-900 ring-1 ring-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Video language
            </span>
            <select
              value={language}
              onChange={(event) => onLanguageChange(event.target.value)}
              disabled={disabled}
              className="w-full rounded-xl border-0 bg-slate-50 px-3 py-2 text-sm text-slate-900 ring-1 ring-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
    </div>
  );
}
