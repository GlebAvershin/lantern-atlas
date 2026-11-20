"""Exercise route eligibility without starting the model servers or Postgres."""
import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

import gateway


class FailoverTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_transient_inference_responses_qualify(self):
        brief = {"options": {"coastal_route": {}}}
        for status in (400, 401, 403, 404, 408, 429, 500, 503):
            transport = httpx.MockTransport(lambda request: httpx.Response(status))
            async with httpx.AsyncClient(transport=transport) as client:
                with patch.object(gateway.app.state, "client", client, create=True), patch.dict(
                    os.environ, QWEN_URL="http://inference.test"
                ):
                    error = gateway.ModelUnavailable if status in (408, 429, 500, 503) else httpx.HTTPStatusError
                    with self.subTest(status=status), self.assertRaises(error):
                        await gateway.generate("qwen", brief)

    async def test_smol_can_fall_back_to_qwen_but_verifier_errors_propagate(self):
        state = gateway.app.state
        with patch.object(state, "tokens", {"example": "qa"}, create=True), patch.object(
            state, "brief", {"options": {"coastal_route": {}}}, create=True
        ), patch.object(state, "slots", asyncio.Semaphore(1), create=True), patch.dict(os.environ, HOSTNAME="worker"):
            request = gateway.Request(model="smol")
            respond = AsyncMock(side_effect=[gateway.ModelUnavailable("smol"), {"cache": "miss"}])
            with patch.object(gateway, "cached_review", respond):
                answer = await gateway.review(request, "Bearer example")
            self.assertTrue(answer["fallback"])
            self.assertEqual((answer["requested_model"], answer["model"]), ("smol", "qwen"))
            self.assertEqual([call.args[:2] for call in respond.await_args_list], [("qa", "smol"), ("qa", "qwen")])

            for status in (422, 502):
                reject = AsyncMock(side_effect=HTTPException(status, "Verifier rejection or error"))
                with patch.object(gateway, "cached_review", reject), self.assertRaises(HTTPException) as caught:
                    await gateway.review(request, "Bearer example")
                self.assertEqual(caught.exception.status_code, status)
                reject.assert_awaited_once()
