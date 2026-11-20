"""Use an explicitly selected inference service; credentials stay with its transport."""
import json
import os
from urllib.parse import quote, urlsplit

import httpx


def parse_answer(text, allowed):
    choice = json.loads(text)["component"]
    if choice not in allowed:
        raise ValueError("Model returned a component outside the supplied catalog")
    return choice


def complete(route, model, prompt, allowed, *, transport=None, bedrock=None):
    schema = {"type": "object", "additionalProperties": False, "required": ["component"],
              "properties": {"component": {"type": "string", "enum": allowed}}}
    message = prompt + "\nAnswer with JSON matching " + json.dumps(schema)
    if route == "bedrock":
        if bedrock is None:
            import boto3
            from botocore.config import Config
            bedrock = boto3.client("bedrock-runtime", config=Config(connect_timeout=5, read_timeout=60,
                                                                    retries={"total_max_attempts": 2}))
        result = bedrock.converse(modelId=model, messages=[{"role": "user", "content": [{"text": message}]}],
                                  inferenceConfig={"maxTokens": 64, "temperature": 0.0})
        answer = "".join(block.get("text", "") for block in result["output"]["message"]["content"])
        return parse_answer(answer, allowed), result["usage"]["totalTokens"]

    payload = {"messages": [{"role": "user", "content": message}], "temperature": 0, "max_tokens": 64}
    headers = {}
    if route == "databricks":
        host = urlsplit(os.environ["DATABRICKS_HOST"])
        if (host.scheme != "https" or not host.hostname or host.netloc != host.hostname
                or not host.hostname.endswith((".cloud.databricks.com", ".azuredatabricks.net", ".gcp.databricks.com"))
                or host.path not in ("", "/") or host.query or host.fragment):
            raise ValueError("Expected a Databricks workspace origin")
        url = f"https://{host.hostname}/serving-endpoints/{quote(model, safe='')}/invocations"
        headers["Authorization"] = "Bearer " + os.environ["DATABRICKS_TOKEN"]
    elif route == "llama":
        url = "http://127.0.0.1:" + str(int(os.getenv("HUD_LLAMA_PORT", "18490"))) + "/v1/chat/completions"
        payload.update(model=model, seed=17, response_format={"type": "json_schema",
                       "json_schema": {"name": "binding", "schema": schema}})
    else:
        raise ValueError("Unknown route")
    with httpx.Client(transport=transport, timeout=60, follow_redirects=False) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
    return parse_answer(result["choices"][0]["message"]["content"], allowed), result["usage"]["total_tokens"]
