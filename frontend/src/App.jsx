import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Info, Play, RotateCcw } from "lucide-react";
import { pingHealth, searchVideos } from "./api.js";
import SearchBar from "./components/SearchBar.jsx";
import FilterPanel from "./components/FilterPanel.jsx";
import ResultCard from "./components/ResultCard.jsx";
import LoadingSteps from "./components/LoadingSteps.jsx";
import EmptyState from "./components/EmptyState.jsx";

const EXAMPLE_QUERIES = [
  "How much is the Burj Khalifa 124th floor ticket?",
  "Best time of year to visit Skardu valley",
  "Where did WildLens by Abrar film snow leopards?",
];

const RETRY_DELAY_MS = 12000;
const MAX_AUTO_RETRIES = 2;

export default function App() {
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState("");
  const [language, setLanguage] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  // phase: idle | loading | done | error
  const [phase, setPhase] = useState("idle");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [waking, setWaking] = useState(false);

  const searchIdRef = useRef(0);

  // Wake the free Render backend as soon as the page loads.
  useEffect(() => {
    pingHealth();
  }, []);

  async function runSearch(overrideQuery) {
    const trimmed = (overrideQuery ?? query).trim();
    if (trimmed.length < 3) return;

    const searchId = ++searchIdRef.current;
    setPhase("loading");
    setWaking(false);
    setError(null);
    setData(null);

    for (let attempt = 0; attempt <= MAX_AUTO_RETRIES; attempt++) {
      try {
        const result = await searchVideos({
          query: trimmed,
          channel: channel.trim(),
          language,
        });
        if (searchIdRef.current !== searchId) return; // superseded
        setData(result);
        setPhase("done");
        return;
      } catch (err) {
        if (searchIdRef.current !== searchId) return;
        if (err.retryable && attempt < MAX_AUTO_RETRIES) {
          // Likely a Render cold start — surface a note and retry.
          setWaking(true);
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
          if (searchIdRef.current !== searchId) return;
          continue;
        }
        setError(err);
        setPhase("error");
        return;
      }
    }
  }

  function handleExample(example) {
    setQuery(example);
    runSearch(example);
  }

  const hasSearched = phase !== "idle";
  const results = data?.results ?? [];
  const parsed = data?.parsed;

  return (
    <div className="flex min-h-screen flex-col">
      {/* Decorative gradient backdrop */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-96 bg-gradient-to-b from-indigo-100/80 via-violet-50/40 to-transparent"
        aria-hidden="true"
      />

      <header className="mx-auto flex w-full max-w-3xl items-center gap-2.5 px-4 pt-6">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 shadow-sm">
          <Play className="ml-0.5 h-5 w-5 fill-white text-white" aria-hidden="true" />
        </span>
        <span className="text-lg font-bold tracking-tight text-slate-900">
          GroundTruth
        </span>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 pb-16">
        {/* Hero — large and centered before the first search, compact after */}
        <section className={hasSearched ? "pt-6" : "pt-16 sm:pt-24"}>
          {!hasSearched && (
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">
                Find answers{" "}
                <span className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
                  inside
                </span>{" "}
                YouTube videos
              </h1>
              <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-slate-500 sm:text-lg">
                Ask a question and get videos that open at the exact second the
                answer is spoken — no scrubbing through 20-minute vlogs.
              </p>
            </div>
          )}

          <SearchBar
            value={query}
            onChange={setQuery}
            onSubmit={() => runSearch()}
            disabled={phase === "loading"}
          />

          <div className="mt-3">
            <FilterPanel
              open={filtersOpen}
              onToggle={() => setFiltersOpen((open) => !open)}
              channel={channel}
              onChannelChange={setChannel}
              language={language}
              onLanguageChange={setLanguage}
              disabled={phase === "loading"}
            />
          </div>

          {!hasSearched && (
            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {EXAMPLE_QUERIES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => handleExample(example)}
                  className="rounded-full bg-white px-3.5 py-1.5 text-xs font-medium text-slate-600 ring-1 ring-slate-200 transition hover:bg-indigo-50 hover:text-indigo-700 hover:ring-indigo-200 sm:text-sm"
                >
                  {example}
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="mt-10">
          {phase === "loading" && <LoadingSteps waking={waking} />}

          {phase === "error" && (
            <div className="mx-auto w-full max-w-md rounded-2xl bg-white p-6 text-center shadow-sm ring-1 ring-red-100">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-50">
                <AlertTriangle className="h-6 w-6 text-red-500" aria-hidden="true" />
              </div>
              <h2 className="text-base font-semibold text-slate-900">
                Search failed
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                {error?.message}
              </p>
              {error?.retryable && (
                <p className="mt-2 text-xs leading-relaxed text-slate-400">
                  The backend runs on free hosting — the first request after a
                  quiet period can take up to a minute.
                </p>
              )}
              <button
                type="button"
                onClick={() => runSearch()}
                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                Try again
              </button>
            </div>
          )}

          {phase === "done" && (
            <>
              {parsed && (
                <p className="mb-4 text-center text-xs text-slate-400">
                  Searched YouTube for{" "}
                  <span className="font-medium text-slate-600">
                    “{parsed.search_topic}”
                  </span>
                  {parsed.channel_name && (
                    <>
                      {" "}
                      on channel{" "}
                      <span className="font-medium text-slate-600">
                        {parsed.channel_name}
                      </span>
                    </>
                  )}
                  {parsed.language && (
                    <>
                      {" "}
                      · language{" "}
                      <span className="font-medium uppercase text-slate-600">
                        {parsed.language}
                      </span>
                    </>
                  )}
                </p>
              )}

              {results.length === 0 ? (
                <EmptyState message={data?.message} />
              ) : (
                <>
                  <div className="grid gap-5 sm:grid-cols-2">
                    {results.map((result) => (
                      <ResultCard key={result.video_id} result={result} />
                    ))}
                  </div>
                  <p className="mx-auto mt-6 flex max-w-md items-start justify-center gap-1.5 text-center text-xs leading-relaxed text-slate-400">
                    <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    Answers come from video content and may be outdated — check
                    the upload date.
                  </p>
                </>
              )}
            </>
          )}
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white py-4">
        <p className="text-center text-xs text-slate-400">
          GroundTruth · answers straight from YouTube videos
        </p>
      </footer>
    </div>
  );
}
