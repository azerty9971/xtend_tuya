"""OpenAPI HTTP timeout regression tests, with no Home Assistant or network.

Run: python tests/test_openapi_timeout.py
Only the package initializer and logger are bypassed; the real OpenAPI module,
token handling, signing, and requests exception classes are used.
"""

import importlib
import logging
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch

import requests


LIB = (
    Path(__file__).resolve().parent.parent
    / "custom_components/xtend_tuya/lib/tuya_iot"
)


def load_openapi():
    package = types.ModuleType("_timeout_test_tuya_iot")
    package.__path__ = [str(LIB)]
    logger_module = types.ModuleType(f"{package.__name__}.openlogging")
    logger_module.logger = logging.getLogger(__name__)
    with patch.dict(sys.modules, {
        package.__name__: package,
        logger_module.__name__: logger_module,
    }):
        return importlib.import_module(f"{package.__name__}.openapi")


api_module = load_openapi()
ENDPOINT = "https://example.invalid"
RESOURCE = "/v1.0/devices/test-device/commands"


def token_response():
    return {
        "success": True,
        "t": int(time.time() * 1000),
        "result": {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expire_time": 3600,
            "uid": "test-user",
        },
    }


class OpenAPITimeoutTests(unittest.TestCase):
    def make_api(self, auth_type=None, non_user=False, valid=True):
        session = Mock(spec=requests.Session)
        with patch.object(api_module.requests, "session", return_value=session):
            api = api_module.TuyaOpenAPI(
                ENDPOINT, "test-client", "test-secret", None,
                auth_type=auth_type or api_module.AuthType.SMART_HOME,
                non_user_specific_api=non_user,
            )
        if valid:
            api.token_info.update_token(token_response())
        return api

    def respond(self, api, *results):
        api.session.request.side_effect = [
            Mock(json=Mock(return_value=result)) for result in results
        ]

    def assert_requests(self, api, expected):
        calls = api.session.request.call_args_list
        self.assertEqual(len(calls), len(expected))
        for call, (method, path) in zip(calls, expected):
            self.assertEqual(call.args, (method, ENDPOINT + path))
            self.assertEqual(call.kwargs["timeout"], 60)

    def test_verbs_preserve_payload_headers_and_response(self):
        for verb in ("get", "post", "put", "delete"):
            with self.subTest(verb=verb):
                api = self.make_api()
                result = {"success": True, "result": {"value": 42}}
                payload = {"test": "value"}
                self.respond(api, result)
                self.assertIs(getattr(api, verb)(RESOURCE, payload), result)
                self.assert_requests(api, [(verb.upper(), RESOURCE)])
                kwargs = api.session.request.call_args.kwargs
                query = verb in ("get", "delete")
                self.assertEqual(kwargs["params"], payload if query else None)
                self.assertEqual(kwargs["json"], None if query else payload)
                self.assertEqual(kwargs["headers"]["access_token"], "test-access-token")
                self.assertEqual(kwargs["headers"]["sign_method"], "HMAC-SHA256")
                self.assertTrue(kwargs["headers"]["sign"])

    def login_route(self, auth_type, non_user):
        if non_user:
            path = (api_module.TO_C_CUSTOM_REFRESH_TOKEN_API
                    if auth_type == api_module.AuthType.CUSTOM
                    else api_module.TO_C_SMART_HOME_REFRESH_TOKEN_API)
            return "GET", path
        path = (api_module.TO_C_CUSTOM_TOKEN_API
                if auth_type == api_module.AuthType.CUSTOM
                else api_module.TO_C_SMART_HOME_TOKEN_API)
        return "POST", path

    def test_login_and_expired_token_renewal(self):
        for auth_type in api_module.AuthType:
            for non_user in (False, True):
                with self.subTest(auth_type=auth_type, non_user=non_user):
                    api = self.make_api(auth_type, non_user, valid=False)
                    login = token_response()
                    self.respond(api, login)
                    self.assertIs(api.connect(), login)
                    self.assertTrue(api.is_token_valid())
                    route = self.login_route(auth_type, non_user)
                    self.assert_requests(api, [route])
                    self.assertEqual(
                        api.session.request.call_args.kwargs["headers"]["dev_lang"],
                        "python",
                    )
                    api.session.request.reset_mock()
                    api.token_info.expire_time = 0
                    result = {"success": True, "result": []}
                    self.respond(api, token_response(), result)
                    self.assertIs(api.get(RESOURCE), result)
                    self.assert_requests(api, [route, ("GET", RESOURCE)])

    def test_timeouts_propagate_without_retry_for_every_verb(self):
        for error_type in (requests.ConnectTimeout, requests.ReadTimeout):
            for verb in ("get", "post", "put", "delete"):
                with self.subTest(error=error_type, verb=verb):
                    api = self.make_api()
                    error = error_type("simulated timeout")
                    api.session.request.side_effect = error
                    with self.assertRaises(error_type) as caught:
                        getattr(api, verb)(RESOURCE)
                    self.assertIs(caught.exception, error)
                    self.assert_requests(api, [(verb.upper(), RESOURCE)])

    def test_login_and_renewal_timeouts_do_not_send_resource_request(self):
        for error_type in (requests.ConnectTimeout, requests.ReadTimeout):
            for auth_type in api_module.AuthType:
                for non_user in (False, True):
                    for renewal in (False, True):
                        with self.subTest(error=error_type, auth=auth_type,
                                          non_user=non_user, renewal=renewal):
                            api = self.make_api(auth_type, non_user, valid=False)
                            error = error_type("simulated timeout")
                            api.session.request.side_effect = error
                            with self.assertRaises(error_type) as caught:
                                if renewal:
                                    api.get(RESOURCE)
                                else:
                                    api.connect()
                            self.assertIs(caught.exception, error)
                            self.assert_requests(api, [self.login_route(auth_type, non_user)])
                            # Reconnecting flag cleanup is the separate fix in #1114.
                            # Do not call reconnect again on this failed instance.

    def test_existing_invalid_token_replay_also_has_timeout(self):
        api = self.make_api()
        result = {"success": True, "result": []}
        self.respond(api, {"code": 1010}, token_response(), result)
        self.assertIs(api.get(RESOURCE), result)
        self.assert_requests(api, [
            ("GET", RESOURCE),
            ("POST", api_module.TO_C_SMART_HOME_TOKEN_API),
            ("GET", RESOURCE),
        ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
