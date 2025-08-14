// Programmatically trigger a GitHub Actions workflow dispatch
// Env:
// - GITHUB_TOKEN (required): a token with workflow scope
// - GITHUB_OWNER (required): repo owner
// - GITHUB_REPO (required): repo name
// - WORKFLOW_ID (required): file name or workflow id, e.g. 'paperpile-to-notion.yml'
// - REF (optional): branch or tag to run on, defaults to 'master'
import { Octokit } from "@octokit/rest";

function getEnv(name, optional = false, fallback = undefined) {
  const v = process.env[name] ?? fallback;
  if (!optional && !v) {
    console.error(`${name} is required`);
    process.exit(1);
  }
  return v;
}

const token = getEnv("GITHUB_TOKEN");
const owner = getEnv("GITHUB_OWNER");
const repo = getEnv("GITHUB_REPO");
const workflow_id = getEnv("WORKFLOW_ID");
const ref = getEnv("REF", true, "master");

const octokit = new Octokit({ auth: token });

async function triggerWorkflow() {
  try {
    const res = await octokit.rest.actions.createWorkflowDispatch({ owner, repo, workflow_id, ref });
    console.log("Workflow dispatched:", { status: res.status, workflow_id, ref, repo: `${owner}/${repo}` });
  } catch (err) {
    console.error("Failed to dispatch workflow:", err?.response?.data || err.message || err);
    process.exit(1);
  }
}

triggerWorkflow();
