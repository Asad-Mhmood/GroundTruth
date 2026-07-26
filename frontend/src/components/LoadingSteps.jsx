import { useEffect, useState } from "react";
import { CheckCircle2, Circle, CloudSun, Loader2 } from "lucide-react";

const STEPS = [
  "Understanding your question…",
  "Searching YouTube…",
  "Reading transcripts…",
  "Locating answers…",
];

// When each step becomes "current", in ms since loading started. The single
// API call runs the whole time; this is a purely visual progression.
const STEP_STARTS_MS = [0, 2500, 7000, 13000];

export default function LoadingSteps({ waking }) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const timers = STEP_STARTS_MS.slice(1).map((delay, index) =>
      setTimeout(() => setCurrentStep(index + 1), delay)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="mx-auto w-full max-w-md rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <ul className="space-y-4">
        {STEPS.map((label, index) => {
          const isDone = index < currentStep;
          const isCurrent = index === currentStep;
          return (
            <li key={label} className="flex items-center gap-3">
              {isDone ? (
                <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" aria-hidden="true" />
              ) : isCurrent ? (
                <Loader2 className="h-5 w-5 shrink-0 animate-spin text-indigo-600" aria-hidden="true" />
              ) : (
                <Circle className="h-5 w-5 shrink-0 text-slate-300" aria-hidden="true" />
              )}
              <span
                className={`text-sm ${
                  isCurrent
                    ? "font-semibold text-slate-900"
                    : isDone
                      ? "text-slate-500"
                      : "text-slate-400"
                }`}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ul>

      {waking && (
        <p className="mt-5 flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-xs leading-relaxed text-amber-800">
          <CloudSun className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          The free backend is slow to respond right now — the first search can
          take up to a minute. Retrying automatically…
        </p>
      )}
    </div>
  );
}
