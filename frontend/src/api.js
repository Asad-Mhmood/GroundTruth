// Backend client. The base URL comes from VITE_API_URL (see .env.example).

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/+$/,
  ""
);

export class ApiError extends Error {
  constructor(message, { retryable = false, status = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.retryable = retryable;
    this.status = status;
  }
}

/**
 * Fire-and-forget ping so the free Render instance starts waking up
 * as soon as the page loads (cold starts can take ~30-60s).
 */
export function pingHealth() {
  fetch(`${API_URL}/health`).catch(() => {});
}

export async function searchVideos({ query, channel, language }) {
  let response;
  try {
    response = await fetch(`${API_URL}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        channel_override: channel || null,
        language_override: language || null,
      }),
    });
  } catch {
    // Network-level failure — typical while the free backend is waking up.
    throw new ApiError("Could not reach the server.", { retryable: true });
  }

  if (!response.ok) {
    let detail = null;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      // Non-JSON error body (e.g. a gateway page while the server boots).
    }
    const retryable = [502, 503, 504].includes(response.status);
    throw new ApiError(detail || "Something went wrong. Please try again.", {
      retryable,
      status: response.status,
    });
  }

  return response.json();
}
