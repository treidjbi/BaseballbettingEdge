/**
 * trigger-pipeline.js
 * Proxies a GitHub Actions workflow_dispatch event.
 * Keeps the GitHub PAT server-side so it's never exposed in the dashboard.
 *
 * Required Netlify env vars (set in Netlify dashboard, not committed to repo):
 *   GITHUB_PAT      — Fine-grained PAT with Actions:Write for this repo
 *   GITHUB_REPO     — "owner/repo" e.g. "treidjbi/baseballbettingedge"
 *   GITHUB_WORKFLOW — Workflow filename e.g. "pipeline.yml"
 */
exports.handler = async (event) => {
  // Only accept POST requests
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: JSON.stringify({ error: "Method not allowed" }) };
  }

  const { GITHUB_PAT, GITHUB_REPO, GITHUB_WORKFLOW } = process.env;
  if (!GITHUB_PAT || !GITHUB_REPO || !GITHUB_WORKFLOW) {
    console.error("trigger-pipeline: missing env vars");
    return { statusCode: 500, body: JSON.stringify({ error: "Server misconfigured" }) };
  }

  try {
    const res = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${GITHUB_WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GITHUB_PAT}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
      }
    );

    if (res.status === 204) {
      return {
        statusCode: 200,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "triggered" }),
      };
    }

    const text = await res.text();
    console.error("trigger-pipeline: GitHub API error", res.status, text);
    return {
      statusCode: res.status,
      body: JSON.stringify({ error: "GitHub dispatch failed", details: text }),
    };
  } catch (err) {
    console.error("trigger-pipeline: fetch error", err);
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
