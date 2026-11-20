# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp==1.26.0", "onnxruntime==1.31.1", "tokenizers==0.23.3", "numpy==2.5.4", "httpx==0.28.1"]
# ///
"""Match wireframe lines to distinct existing components using sentence embeddings."""
import argparse
import asyncio
from itertools import permutations
import json
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from evaluate import BASELINE, CASES, TRANSFER

# Fresh briefs for the catalogue-matching method. Expected rows are used only when scoring.
EXTRA = [
    ("atlas", "Start with the command to take back a move\nShow the chapter heading next\nFinish with the constellation you can touch", ["controls", "logbook", "sky"]),
    ("freight", "Lead with navigation to the depot exit\nHow many batteries are in?\nFinish with tonight's shift identifier", ["bearing", "cargo", "shift"]),
    ("soccer", "Display the club badge at the top\nLet me accept or decline\nAt the foot, list the asking price", ["crest", "transfer", "terms"]),
]


class Matcher:
    def __init__(self, folder):
        self.tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.session = ort.InferenceSession(str(folder / "onnx/model_quantized.onnx"),
                                           providers=["CPUExecutionProvider"])
        self.documents = {}

    def embed(self, text):
        ids = np.array([self.tokenizer.encode(text).ids], dtype=np.int64)
        inputs = {"input_ids": ids, "attention_mask": np.ones_like(ids)}
        vector = self.session.run(["sentence_embedding"], inputs)[0][0]
        return vector / np.linalg.norm(vector)

    def draft(self, catalogue, wireframe):
        lines = [line.strip() for line in wireframe.splitlines() if line.strip()]
        keys = list(catalogue)
        if len(lines) != len(keys) or len(keys) != 3:
            raise ValueError("This prototype expects exactly three rows and components")
        docs = []
        for key in keys:
            description = f"title: {key} | text: {catalogue[key]}"
            if description not in self.documents:
                self.documents[description] = self.embed(description)
            docs.append(self.documents[description])
        queries = [self.embed("task: search result | query: " + line) for line in lines]
        scores = np.array(queries) @ np.array(docs).T
        assignments = [(sum(float(scores[i, col]) for i, col in enumerate(order)), order)
                       for order in permutations(range(len(keys)))]
        assignments.sort(reverse=True)
        score, winner = assignments[0]
        return {"rows": [keys[i] for i in winner],
                "margin_over_second": round(score - assignments[1][0], 4)}


async def main(args):
    matcher = Matcher(args.snapshot)
    params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("contracts.py"))])
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        async def draft(project, wireframe):
            resource = await session.read_resource(f"hud://catalogue/{project}")
            result = matcher.draft(json.loads(resource.contents[0].text), wireframe)
            check = await session.call_tool("check_rows", {"project": project, "rows": result["rows"]})
            if check.isError or not check.structuredContent["valid"]:
                raise ValueError("Draft failed the MCP contract")
            return result

        if args.brief:
            print(json.dumps(await draft(args.project, args.brief.read_text()), indent=2))
            return
        rows = []
        for group, cases in [("original", CASES), ("paraphrases", TRANSFER), ("additional", EXTRA)]:
            for project, wireframe, expected in cases:
                start = time.perf_counter()
                result = await draft(project, wireframe)
                rows.append({"group": group, "project": project, "wireframe": wireframe, **result,
                             "expected": expected, "exact": expected == result["rows"],
                             "fixed_order_exact": BASELINE[project] == expected,
                             "ms": round(1000 * (time.perf_counter() - start), 2)})
        report = {"model": "onnx-community/embeddinggemma-300m-ONNX, quantized, CPU",
                  "exact": sum(r["exact"] for r in rows), "n": len(rows), "trials": rows}
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(report["exact"], "/", report["n"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--project", choices=sorted(BASELINE), default="atlas")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--brief", type=Path)
    mode.add_argument("--output", type=Path)
    asyncio.run(main(parser.parse_args()))
