// Build the Actions reviewer's summary from the measured handoff and its last published run.
import {readFileSync, existsSync, appendFileSync} from "node:fs";
import {join} from "node:path";
const [out, previous] = process.argv.slice(2);
const read = (base, file) => JSON.parse(readFileSync(join(base, file), "utf8"));
const current = read(out, "authoring.json");
const geometry = read(out, "geometry.json");
const rejected = current.trace.filter(step => !step.accepted).length;
const validSizes = geometry.viewports.filter(row => !row.violations.length).length;
const lines = [
  "### Responsive HUD review",
  "",
  "| Model calls | Tokens | Rejected proposals | Passing viewport checks |",
  "| ---: | ---: | ---: | ---: |",
  `| ${current.model_calls} | ${current.inference_tokens} | ${rejected} | ${validSizes}/${geometry.viewports.length} |`,
];
if (existsSync(join(previous, "authoring.json"))) {
  const baseline = read(previous,"authoring.json");
  if (baseline.brief_sha256 === current.brief_sha256 && baseline.requested_model === current.requested_model && baseline.route === current.route) {
    lines.push("", `Previous published run used ${baseline.model_calls} calls and ${baseline.inference_tokens} tokens on this brief and model.`);
  }
}
const body = lines.join("\n") + "\n";
if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, body);
else process.stdout.write(body);
