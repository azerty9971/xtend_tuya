from __future__ import annotations
from typing import Any
import uuid
import hashlib
import time
from datetime import datetime
import json
from tuya_sharing.customerapi import (
    CustomerApi,
    CustomerTokenInfo,
    _secret_generating,
    _form_to_json,
    _aes_gcm_encrypt,
    _restful_sign,
    _aex_gcm_decrypt,
)
from ....const import (
    LOGGER,
)

class XTSharingTokenInfo(CustomerTokenInfo):
    pass

class XTSharingAPI(CustomerApi):

    @staticmethod
    def get_api_from_customer_api(other_api: CustomerApi) -> XTSharingAPI:
        new_api = XTSharingAPI(token_info=other_api.token_info, client_id=other_api.client_id, user_code=other_api.user_code, end_point=other_api.endpoint, listener=other_api.token_listener)
        new_api.session = other_api.session
        return new_api

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Http Get.

        Requests the server to return specified resources.

        Args:
            path (str): api path
            params (map): request parameter

        Returns:
            response: response body
        """
        request_result =  self.__request("GET", path, params, None)
        return request_result if request_result is not None else {}

    def post(self, path: str, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> dict[
        str, Any]:
        """Http Post.

        Requests the server to update specified resources.

        Args:
            path (str): api path
            params (map): request parameter
            body (map): request body

        Returns:
            response: response body
        """
        request_result = self.__request("POST", path, params, body)
        return request_result if request_result is not None else {}
    
    def put(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Http Put.

        Requires the server to perform specified operations.

        Args:
            path (str): api path
            body (map): request body

        Returns:
            response: response body
        """
        request_result = self.__request("PUT", path, None, body)
        return request_result if request_result is not None else {}

    def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Http Delete.

        Requires the server to delete specified resources.

        Args:
            path (str): api path
            params (map): request param

        Returns:
            response: response body
        """
        request_result = self.__request("DELETE", path, params, None)
        return request_result if request_result is not None else {}
    
    def __request(
            self,
            method: str,
            path: str,
            params: dict[str, Any] | None = None,
            body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        start_time = datetime.now()
        self.refresh_access_token_if_need()

        rid = str(uuid.uuid4())
        sid = ""
        md5 = hashlib.md5()
        rid_refresh_token = rid + self.token_info.refresh_token
        md5.update(rid_refresh_token.encode('utf-8'))
        hash_key = md5.hexdigest()
        secret = _secret_generating(rid, sid, hash_key)

        query_encdata = ""
        if params is not None and len(params.keys()) > 0:
            query_encdata = _form_to_json(params)
            query_encdata = _aes_gcm_encrypt(query_encdata, secret)
            params = {
                "encdata": query_encdata
            }
            query_encdata = str(query_encdata, encoding="utf8")
        body_encdata = ""
        if body is not None and len(body.keys()) > 0:
            body_encdata = _form_to_json(body)
            body_encdata = _aes_gcm_encrypt(body_encdata, secret)
            body = {
                "encdata": str(body_encdata, encoding="utf8")
            }
            body_encdata = str(body_encdata, encoding="utf8")

        t = int(time.time() * 1000)
        headers = {
            "X-appKey": self.client_id,
            "X-requestId": rid,
            "X-sid": sid,
            "X-time": str(t),
        }
        if self.token_info is not None and len(self.token_info.access_token) > 0:
            headers["X-token"] = self.token_info.access_token

        sign = _restful_sign(hash_key,
                             query_encdata,
                             body_encdata,
                             headers)
        headers["X-sign"] = sign

        response = self.session.request(
            method, self.endpoint + path, params=params, json=body, headers=headers
        )

        if response.ok is False:
            LOGGER.error(
                f"Response error: code={response.status_code}, content={response.content}"
            )
            return None

        ret = response.json()
        time_taken = datetime.now() - start_time
        LOGGER.debug(
            f"[SHARING API][{time_taken}]Request: {method} {path} PARAMS: {json.dumps(params, ensure_ascii=False, indent=2) if params is not None else ''} BODY: {json.dumps(body, ensure_ascii=False, indent=2) if body is not None else ''}"
        )
        LOGGER.debug(
            f"[SHARING API][{time_taken}]Response: {json.dumps(ret, ensure_ascii=False, indent=2)}"
        )

        if not ret.get("success"):
            raise Exception(f"network error:({ret['code']}) {ret['msg']}")

        result = _aex_gcm_decrypt(ret.get("result"), secret)
        try:
            ret["result"] = json.loads(result)
        except json.decoder.JSONDecodeError:
            ret["result"] = result

        LOGGER.debug("response ret = %s", ret)
        return ret
