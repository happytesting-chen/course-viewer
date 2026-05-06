export const config = { runtime: "edge" };

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, x-auth-token",
};

export default async function handler(req) {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 200, headers: CORS });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: CORS });
  }

  const authToken = req.headers.get("x-auth-token");
  if (!process.env.PROXY_AUTH_TOKEN || authToken !== process.env.PROXY_AUTH_TOKEN) {
    return new Response("Unauthorized", { status: 401, headers: CORS });
  }

  let system, messages;
  try {
    ({ system, messages } = await req.json());
  } catch {
    return new Response("Invalid JSON", { status: 400, headers: CORS });
  }

  const claudeRes = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 1024,
      system,
      messages,
      stream: true,
    }),
  });

  if (!claudeRes.ok) {
    return new Response(`Claude API error: ${claudeRes.status}`, {
      status: claudeRes.status,
      headers: CORS,
    });
  }

  return new Response(claudeRes.body, {
    headers: { ...CORS, "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
  });
}
