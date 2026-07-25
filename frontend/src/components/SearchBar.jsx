import { Search } from "lucide-react";

export default function SearchBar({ value, onChange, onSubmit, disabled }) {
  function handleSubmit(event) {
    event.preventDefault();
    if (!disabled && value.trim().length >= 3) onSubmit();
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex items-center gap-2 rounded-2xl bg-white p-2 shadow-lg shadow-indigo-100 ring-1 ring-slate-200 focus-within:ring-2 focus-within:ring-indigo-500 transition-shadow">
        <Search className="ml-2 h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
        <input
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder='Try "Burj Khalifa 124th floor ticket price"'
          maxLength={300}
          disabled={disabled}
          aria-label="Ask a question"
          className="min-w-0 flex-1 bg-transparent py-2 text-base text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={disabled || value.trim().length < 3}
          className="shrink-0 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:from-indigo-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50 sm:px-6"
        >
          Search
        </button>
      </div>
    </form>
  );
}
