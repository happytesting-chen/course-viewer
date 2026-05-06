const ALLOWED_ORIGIN = "https://happytesting-chen.github.io";

export default async function handler(req, res) {
  const origin = req.headers["origin"] || "";
  const allowedOrigin = origin === ALLOWED_ORIGIN ? ALLOWED_ORIGIN : "null";

  res.setHeader("Access-Control-Allow-Origin", allowedOrigin);
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Vary", "Origin");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  if (origin !== ALLOWED_ORIGIN) return res.status(403).json({ error: "Forbidden" });

  const { password } = req.body;
  if (!process.env.SITE_PASSWORD || password !== process.env.SITE_PASSWORD) {
    return res.status(401).json({ error: "Incorrect password" });
  }

  // Return the proxy token — only revealed after successful login
  return res.status(200).json({ token: process.env.PROXY_AUTH_TOKEN });
}

export const config = {
  api: { responseLimit: false },
};
