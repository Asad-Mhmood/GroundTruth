import { useState } from "react";
import { CalendarDays, Play, Quote, UserRound } from "lucide-react";

const CONFIDENCE_STYLES = {
  high: "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-200 text-slate-600",
};

export default function ResultCard({ result }) {
  const [playing, setPlaying] = useState(false);

  const badgeStyle = CONFIDENCE_STYLES[result.confidence] || CONFIDENCE_STYLES.low;

  return (
    <article className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200 transition hover:shadow-md">
      {playing ? (
        <iframe
          src={result.embed_url}
          title={result.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="aspect-video w-full"
        />
      ) : (
        <button
          type="button"
          onClick={() => setPlaying(true)}
          className="group relative block w-full"
          aria-label={`Play ${result.title} at ${result.timestamp_display}`}
        >
          <img
            src={result.thumbnail_url}
            alt=""
            loading="lazy"
            className="aspect-video w-full object-cover"
          />
          <span className="absolute inset-0 flex items-center justify-center bg-black/30 transition group-hover:bg-black/40">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-white/90 shadow-lg transition group-hover:scale-110">
              <Play className="ml-1 h-6 w-6 fill-indigo-600 text-indigo-600" aria-hidden="true" />
            </span>
          </span>
          <span className="absolute bottom-2 right-2 rounded-md bg-black/80 px-2 py-0.5 text-xs font-semibold text-white">
            {result.timestamp_display}
          </span>
        </button>
      )}

      <div className="p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span
            className={`rounded-full px-2 py-0.5 font-semibold capitalize ${badgeStyle}`}
          >
            {result.confidence} confidence
          </span>
          <span className="inline-flex items-center gap-1">
            <UserRound className="h-3.5 w-3.5" aria-hidden="true" />
            {result.channel_title}
          </span>
          {result.published_at && (
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
              {result.published_at}
            </span>
          )}
        </div>

        <h3 className="mt-2 line-clamp-2 text-base font-semibold leading-snug text-slate-900">
          {result.title}
        </h3>

        <p className="mt-3 rounded-xl bg-indigo-50 p-3 text-sm font-medium leading-relaxed text-indigo-950">
          {result.answer_summary}
        </p>

        {result.exact_quote && (
          <blockquote className="mt-3 flex gap-2 border-l-4 border-indigo-200 pl-3 text-sm italic leading-relaxed text-slate-600">
            <Quote className="mt-0.5 h-4 w-4 shrink-0 text-indigo-300" aria-hidden="true" />
            <span className="line-clamp-3">{result.exact_quote}</span>
          </blockquote>
        )}

        <a
          href={result.watch_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:from-indigo-500 hover:to-violet-500"
        >
          <Play className="h-4 w-4 fill-current" aria-hidden="true" />
          Watch answer at {result.timestamp_display}
        </a>
      </div>
    </article>
  );
}
