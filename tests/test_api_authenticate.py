"""Unit tests for PerfectDraftApiClient.authenticate() against Cognito.

Runs with the stdlib only. The client module is loaded as part of a stub
``perfectdraft`` package so the integration's ``__init__.py`` (which needs
Home Assistant) never executes. If aiohttp is not installed a minimal stub
stands in for it; the client only touches ``aiohttp.ClientError`` at runtime.
No real network calls are made: a fake session records the request and
replays a canned response.
"""
import asyncio
import importlib
import json
import os
import sys
import types
import unittest

PKG_DIR = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "perfectdraft"
)

try:
    import aiohttp  # noqa: F401
except ImportError:  # pragma: no cover - depends on the environment
    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        """Stand-in for aiohttp.ClientError."""

    aiohttp.ClientError = ClientError
    aiohttp.ClientSession = object
    sys.modules["aiohttp"] = aiohttp

if "perfectdraft" not in sys.modules:
    _pkg = types.ModuleType("perfectdraft")
    _pkg.__path__ = [PKG_DIR]
    sys.modules["perfectdraft"] = _pkg

api = importlib.import_module("perfectdraft.api")
const = importlib.import_module("perfectdraft.const")
exceptions = importlib.import_module("perfectdraft.exceptions")


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def text(self):
        return self._body

    async def json(self, content_type="application/json"):
        if content_type is not None:
            # Cognito answers with application/x-amz-json-1.1, which aiohttp
            # rejects unless the caller passes content_type=None.
            raise AssertionError("json() must be called with content_type=None")
        return json.loads(self._body)


class FakeContext:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self._response

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, status=200, body="{}", error=None):
        self.status = status
        self.body = body
        self.error = error
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return FakeContext(FakeResponse(self.status, self.body), self.error)


SUCCESS_BODY = json.dumps(
    {
        "AuthenticationResult": {
            "AccessToken": "access-abc",
            "IdToken": "id-def",
            "RefreshToken": "refresh-ghi",
            "ExpiresIn": 3600,
            "TokenType": "Bearer",
        },
        "ChallengeParameters": {},
    }
)


def run(coro):
    return asyncio.run(coro)


class TestAuthenticateRequest(unittest.TestCase):
    def test_posts_initiate_auth_to_cognito(self):
        session = FakeSession(body=SUCCESS_BODY)
        client = api.PerfectDraftApiClient(session)

        run(client.authenticate("me@example.com", "hunter2", "captcha-token"))

        self.assertEqual(len(session.calls), 1)
        call = session.calls[0]
        self.assertEqual(call["url"], "https://cognito-idp.eu-west-1.amazonaws.com/")
        self.assertEqual(
            call["headers"],
            {
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
            },
        )
        self.assertEqual(
            call["json"],
            {
                "AuthFlow": "USER_PASSWORD_AUTH",
                "ClientId": const.COGNITO_CLIENT_ID,
                "AuthParameters": {
                    "USERNAME": "me@example.com",
                    "PASSWORD": "hunter2",
                },
                "ClientMetadata": {
                    "recaptchaToken": "captcha-token",
                    "recaptchaAction": "Magento/login",
                    "domain": "https://www.perfectdraft.com",
                },
            },
        )

    def test_does_not_send_gateway_api_key(self):
        session = FakeSession(body=SUCCESS_BODY)
        run(api.PerfectDraftApiClient(session).authenticate("a", "b", "c"))
        self.assertNotIn("x-api-key", session.calls[0]["headers"])


class TestAuthenticateResponse(unittest.TestCase):
    def test_parses_authentication_result_and_stores_tokens(self):
        client = api.PerfectDraftApiClient(FakeSession(body=SUCCESS_BODY))

        result = run(client.authenticate("a", "b", "c"))

        self.assertEqual(
            result,
            {
                "AccessToken": "access-abc",
                "IdToken": "id-def",
                "RefreshToken": "refresh-ghi",
            },
        )
        self.assertEqual(client.access_token, "access-abc")
        self.assertEqual(client.id_token, "id-def")
        self.assertEqual(client.refresh_token, "refresh-ghi")

    def test_challenge_instead_of_tokens_is_auth_error(self):
        body = json.dumps(
            {"ChallengeName": "NEW_PASSWORD_REQUIRED", "Session": "s", "ChallengeParameters": {}}
        )
        client = api.PerfectDraftApiClient(FakeSession(body=body))

        with self.assertRaises(exceptions.AuthenticationError) as ctx:
            run(client.authenticate("a", "b", "c"))

        self.assertEqual(ctx.exception.code, "NEW_PASSWORD_REQUIRED")
        self.assertIsNone(client.access_token)


class TestAuthenticateErrors(unittest.TestCase):
    def _fail(self, status, body):
        client = api.PerfectDraftApiClient(FakeSession(status=status, body=body))
        with self.assertRaises(exceptions.AuthenticationError) as ctx:
            run(client.authenticate("a", "secret-password", "secret-token"))
        return ctx.exception

    def test_400_lambda_rejection_is_token_kind(self):
        err = self._fail(
            400,
            json.dumps(
                {
                    "__type": "UserLambdaValidationException",
                    "message": "PreAuthentication failed with error 'domain'.",
                }
            ),
        )
        self.assertEqual(err.code, "UserLambdaValidationException")
        self.assertEqual(err.reason, "PreAuthentication failed with error 'domain'.")
        self.assertEqual(err.kind, "token")
        self.assertEqual(
            err.display_reason, "PreAuthentication failed with error 'domain'"
        )
        self.assertIn("400", str(err))

    def test_400_wrong_password_is_credentials_kind(self):
        err = self._fail(
            400,
            json.dumps(
                {
                    "__type": "NotAuthorizedException",
                    "message": "Incorrect username or password.",
                }
            ),
        )
        self.assertEqual(err.kind, "credentials")
        self.assertEqual(err.display_reason, "Incorrect username or password")

    def test_namespaced_type_is_unwrapped(self):
        err = self._fail(
            400,
            json.dumps(
                {
                    "__type": "com.amazonaws.cognito#UserNotFoundException",
                    "message": "User does not exist.",
                }
            ),
        )
        self.assertEqual(err.code, "UserNotFoundException")
        self.assertEqual(err.kind, "credentials")

    def test_legacy_gateway_shape_still_parsed(self):
        err = self._fail(
            400,
            json.dumps(
                {
                    "Message": "PreAuthentication failed with error 'domain'.",
                    "Code": "UserLambdaValidationException",
                }
            ),
        )
        self.assertEqual(err.kind, "token")

    def test_401_and_403_are_auth_errors(self):
        for status in (401, 403):
            with self.subTest(status=status):
                err = self._fail(status, "Forbidden")
                self.assertIsNone(err.code)
                self.assertEqual(err.kind, "other")
                self.assertEqual(err.display_reason, "Forbidden")

    def test_non_json_body_has_fallback_reason(self):
        err = self._fail(400, "")
        self.assertEqual(err.kind, "other")
        self.assertEqual(err.display_reason, "no reason given")

    def test_error_text_never_contains_password_or_token(self):
        err = self._fail(
            400,
            json.dumps({"__type": "NotAuthorizedException", "message": "nope"}),
        )
        self.assertNotIn("secret-password", str(err))
        self.assertNotIn("secret-token", str(err))

    def test_500_is_api_error(self):
        client = api.PerfectDraftApiClient(
            FakeSession(status=500, body="Internal Server Error")
        )
        with self.assertRaises(exceptions.PerfectDraftApiError) as ctx:
            run(client.authenticate("a", "b", "c"))
        self.assertEqual(ctx.exception.status, 500)

    def test_network_error_is_connection_error(self):
        client = api.PerfectDraftApiClient(
            FakeSession(error=aiohttp.ClientError("boom"))
        )
        with self.assertRaises(exceptions.PerfectDraftConnectionError):
            run(client.authenticate("a", "b", "c"))


class TestRefreshStillUsesCognito(unittest.TestCase):
    def test_refresh_posts_refresh_token_auth(self):
        session = FakeSession(body=SUCCESS_BODY)
        client = api.PerfectDraftApiClient(session)
        client.set_tokens(refresh_token="refresh-old")

        run(client.refresh_access_token())

        call = session.calls[0]
        self.assertEqual(call["url"], const.COGNITO_IDP_URL)
        self.assertEqual(call["json"]["AuthFlow"], "REFRESH_TOKEN_AUTH")
        self.assertEqual(
            call["json"]["AuthParameters"], {"REFRESH_TOKEN": "refresh-old"}
        )
        self.assertEqual(client.access_token, "access-abc")


if __name__ == "__main__":
    unittest.main()
