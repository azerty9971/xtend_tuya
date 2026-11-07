"""Self-check: TuyaOpenAPI debug logs must not contain tokens or the login body.

Standalone (no Home Assistant import): loads lib/tuya_iot/openapi.py by path.
openlogging.py imports the HA-bound const for its logger, so it is loaded from
source with that one import replaced by a plain logger; filter_logger itself is
the real one.

Run: `python tests/test_openapi_log_filter.py` (needs `requests`)
"""

import importlib.util
import logging
import pathlib
import sys
import time
import types

PKG_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components/xtend_tuya/lib/tuya_iot"
)
PKG = "xt_tuya_iot_log_filter_under_test"

package = types.ModuleType(PKG)
package.__path__ = [str(PKG_DIR)]
sys.modules[PKG] = package

openlogging = types.ModuleType(f"{PKG}.openlogging")
source = (PKG_DIR / "openlogging.py").read_text(encoding="utf-8")
source = source.replace(
    "from ...const import LOGGER as logger",
    f"logger = logging.getLogger({PKG!r})",
)
exec(compile(source, str(PKG_DIR / "openlogging.py"), "exec"), openlogging.__dict__)
sys.modules[f"{PKG}.openlogging"] = openlogging

spec = importlib.util.spec_from_file_location(f"{PKG}.openapi", PKG_DIR / "openapi.py")
assert spec is not None and spec.loader is not None
openapi = importlib.util.module_from_spec(spec)
sys.modules[f"{PKG}.openapi"] = openapi
spec.loader.exec_module(openapi)

SECRETS = ("AT-SECRET", "RT-SECRET", "PW-HASH-SECRET")
TOKEN_RESPONSE = {
    "success": True,
    "t": int(time.time() * 1000),  # issued now, so the token is valid
    "result": {
        "access_token": "AT-SECRET",
        "refresh_token": "RT-SECRET",
        "expire_time": 7200,
        "uid": "uid-1",
    },
}


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _capture():
    handler = _ListHandler()
    log = logging.getLogger(PKG)
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    return handler


def _make_api(non_user_specific):
    return openapi.TuyaOpenAPI(
        "https://example.invalid",
        "id",
        "secret",
        shared_token_info=None,
        non_user_specific_api=non_user_specific,
    )


def _assert_no_secrets(messages):
    joined = "\n".join(messages)
    assert joined, "expected some debug output"
    for secret in SECRETS:
        assert secret not in joined, f"{secret} leaked into the log"


def test_connect_non_user_specific_does_not_log_tokens():
    api = _make_api(non_user_specific=True)
    api.get = lambda *args, **kwargs: dict(TOKEN_RESPONSE)
    handler = _capture()
    api.connect_non_user_specific()
    _assert_no_secrets(handler.messages)


def test_request_logs_do_not_contain_body_or_response_secrets():
    api = _make_api(non_user_specific=False)

    class _Response:
        ok = True

        @staticmethod
        def json():
            return dict(TOKEN_RESPONSE)

    api.session.request = lambda *args, **kwargs: _Response()
    # A valid token, so the request carries (and the second-pass log used to print) it
    api.token_info.update_token(dict(TOKEN_RESPONSE))
    assert api.token_info.access_token == "AT-SECRET"
    handler = _capture()
    request = getattr(api, "_TuyaOpenAPI__request")
    for first_pass in (True, False):
        request(
            "POST",
            "/v1.0/iot-01/associated-users/actions/authorized-login",
            params={"access_token": "AT-SECRET"},
            body={"username": "user", "password": "PW-HASH-SECRET"},
            first_pass=first_pass,
        )
    _assert_no_secrets(handler.messages)


def test_filter_logger_masks_at_any_depth_and_never_raises():
    filter_logger = openlogging.filter_logger
    odd_shapes = [
        {"result": [None, "access_token", 1, ["x"]]},
        {"result": "plain"},
        {"result": None},
        {},
    ]
    for shape in odd_shapes:
        assert filter_logger(shape) == shape  # nothing to mask, nothing raised
    masked = filter_logger(
        {
            "password": "PW-HASH-SECRET",
            "result": {
                "list": [{"access_token": "AT-SECRET", "name": "lamp"}],
                "credentials": {"refresh_token": "RT-SECRET"},
            },
        }
    )
    _assert_no_secrets([repr(masked)] + ["placeholder"])
    assert masked["result"]["list"][0]["name"] == "lamp"
    assert filter_logger(None) is None


def test_request_with_list_result_still_returns_the_response():
    api = _make_api(non_user_specific=False)
    payload = {"success": True, "t": 0, "result": [None, "id-1", 2]}

    class _Response:
        ok = True

        @staticmethod
        def json():
            return dict(payload)

    api.session.request = lambda *args, **kwargs: _Response()
    api.token_info.update_token(dict(TOKEN_RESPONSE))
    _capture()
    request = getattr(api, "_TuyaOpenAPI__request")
    for first_pass in (True, False):
        assert request("GET", "/v1.0/devices", first_pass=first_pass)["result"] == payload["result"]


def test_failed_connect_error_message_has_no_tokens():
    api = _make_api(non_user_specific=True)
    failed = {"success": False, "result": {"access_token": "AT-SECRET"}}
    api.get = lambda *args, **kwargs: dict(failed)
    try:
        api.connect_non_user_specific()
    except Exception as err:  # noqa: BLE001 - the integration raises a bare Exception here
        # The API error itself, not a crash inside the filter
        assert type(err) is Exception, repr(err)
        message = str(err)
        assert message.startswith("[IOT API] connect_non_user_specific error:"), message
        assert "'access_token': '***'" in message, message
        _assert_no_secrets([message])
    else:
        raise AssertionError("expected connect_non_user_specific to raise")


if __name__ == "__main__":
    test_connect_non_user_specific_does_not_log_tokens()
    test_request_logs_do_not_contain_body_or_response_secrets()
    test_filter_logger_masks_at_any_depth_and_never_raises()
    test_request_with_list_result_still_returns_the_response()
    test_failed_connect_error_message_has_no_tokens()
    print("ok")
