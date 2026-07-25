import { SearchX } from "lucide-react";

export default function EmptyState({ message }) {
  return (
    <div className="mx-auto w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-200">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
        <SearchX className="h-6 w-6 text-slate-400" aria-hidden="true" />
      </div>
      <h2 className="text-base font-semibold text-slate-900">
        No timestamped answers found
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-500">
        {message ||
          "We couldn't find a moment that clearly answers this question."}
      </p>
      <ul className="mt-4 space-y-1 text-left text-sm text-slate-500">
        <li>• Try rephrasing with more specific words</li>
        <li>• Remove the channel or language filter</li>
        <li>• Ask about something people say out loud in videos</li>
      </ul>
    </div>
  );
}
