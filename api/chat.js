const ALLOWED_ORIGIN = "https://happytesting-chen.github.io";

export default async function handler(req, res) {
  const origin = req.headers["origin"] || "";
  const allowedOrigin = origin === ALLOWED_ORIGIN ? ALLOWED_ORIGIN : "null";

  res.setHeader("Access-Control-Allow-Origin", allowedOrigin);
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, x-auth-token");
  res.setHeader("Vary", "Origin");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

  // Block requests not coming from the GitHub Pages site
  if (origin !== ALLOWED_ORIGIN) {
    return res.status(403).json({ error: "Forbidden" });
  }

  const authToken = req.headers["x-auth-token"];
  if (!process.env.PROXY_AUTH_TOKEN || authToken !== process.env.PROXY_AUTH_TOKEN) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  const { system, messages } = req.body;

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
    return res.status(claudeRes.status).json({ error: `Claude API error: ${claudeRes.status}` });
  }

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  const reader = claudeRes.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    res.write(decoder.decode(value, { stream: true }));
  }
  res.end();
}

export const config = {
  api: { responseLimit: false },
};
