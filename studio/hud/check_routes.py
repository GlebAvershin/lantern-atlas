"""Offline provider contracts, using Botocore's schema and a recording HTTP transport."""
import json
import os
import unittest
from unittest.mock import patch

import boto3
from botocore.stub import ANY, Stubber
import httpx

from routes import complete, gateway_policy


class Routes(unittest.TestCase):
    def test_converse(self):
        client = boto3.client("bedrock-runtime", region_name="us-east-1", aws_access_key_id="fixture",
                              aws_secret_access_key="fixture")
        result = {"output":{"message":{"role":"assistant","content":[{"text":'{"component":"board"}'}]}},
                  "stopReason":"end_turn","usage":{"inputTokens":20,"outputTokens":4,"totalTokens":24},
                  "metrics":{"latencyMs":1}}
        args = {"modelId":"fixture-model","messages":[{"role":"user","content":[{"text":ANY}]}],
                "inferenceConfig":{"maxTokens":64,"temperature":0.0}}
        with Stubber(client) as stub:
            stub.add_response("converse", result, args)
            self.assertEqual(complete("bedrock","fixture-model","Arrange the board",["board","clock"],
                                      bedrock=client), ("board", 24))
            stub.assert_no_pending_responses()

    def test_serving_endpoint(self):
        def serve(request):
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/serving-endpoints/studio-review/invocations")
            self.assertEqual(request.headers["Authorization"], "Bearer fixture")
            body = json.loads(request.content)
            self.assertEqual(body["max_tokens"],64)
            self.assertIn("Arrange the board", body["messages"][0]["content"])
            return httpx.Response(200,json={"choices":[{"message":{"content":'{"component":"board"}'}}],
                                            "usage":{"total_tokens":18}})
        with patch.dict(os.environ,DATABRICKS_HOST="https://studio.cloud.databricks.com",DATABRICKS_TOKEN="fixture"):
            self.assertEqual(complete("databricks","studio-review","Arrange the board",["clock","board"],
                                      transport=httpx.MockTransport(serve)), ("board",18))
            with self.assertRaises(ValueError):
                complete("databricks","studio-review","Arrange the board",["clock"],transport=httpx.MockTransport(serve))

    def test_gateway_policy(self):
        def serve(request):
            self.assertEqual(request.method,"GET")
            self.assertEqual(request.url.path,"/api/2.0/serving-endpoints/workshop")
            self.assertEqual(request.headers["Authorization"],"Bearer fixture")
            return httpx.Response(200,json={"ai_gateway":{"usage_tracking_config":{"enabled":True},
                "inference_table_config":{"enabled":False,"catalog_name":"internal"},
                "rate_limits":[{"key":"user_group","principal":"private","calls":12,"renewal_period":"minute"}]}})
        with patch.dict(os.environ,DATABRICKS_HOST="https://studio.cloud.databricks.com",DATABRICKS_TOKEN="fixture"):
            policy=gateway_policy("workshop",transport=httpx.MockTransport(serve))
        self.assertEqual(policy,{"configuration_returned":True,"usage_tracking":True,"payload_logging":False,
                       "rate_limits":[{"key":"user_group","calls":12,"renewal_period":"minute"}]})

    def test_foreign_workspace_origin(self):
        with patch.dict(os.environ,DATABRICKS_HOST="https://example.org"):
            with self.assertRaises(ValueError):
                complete("databricks","studio-review","x",["board"])


if __name__ == "__main__":
    unittest.main()
