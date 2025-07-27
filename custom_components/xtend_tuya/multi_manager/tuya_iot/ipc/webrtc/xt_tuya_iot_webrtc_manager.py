from __future__ import annotations
from typing import Any, cast
from datetime import datetime, timedelta
import time
import json
from webrtc_models import (
    RTCIceCandidate,
    RTCIceCandidateInit,
)
from homeassistant.core import HomeAssistant
from homeassistant.components.camera.webrtc import (
    WebRTCSendMessage,
    WebRTCCandidate,
    WebRTCAnswer,
)
from .....const import (
    LOGGER,  # noqa: F401
)
import custom_components.xtend_tuya.multi_manager.tuya_iot.ipc.xt_tuya_iot_ipc_manager as ipc_man
from ....shared.shared_classes import (
    XTDevice,
)

ENDLINE = "\r\n"


class XTIOTWebRTCSession:
    webrtc_config: dict[str, Any] | None
    original_offer: str | None
    offer: str | None
    answer: dict
    final_answer: str | None
    answer_candidates: list[dict]
    has_all_candidates: bool
    message_callback: WebRTCSendMessage | None = None
    offer_candidate: list[str]
    hass: HomeAssistant | None
    offer_sent: bool = False
    modes: dict[str, str]
    offer_codec_manager: XTIOTWebRTCCodecManager | None = None
    answer_codec_manager: XTIOTWebRTCCodecManager | None = None

    def __init__(self, ttl: int = 600) -> None:
        self.webrtc_config = None
        self.original_offer = None
        self.offer = None
        self.answer = {}
        self.final_answer = None
        self.answer_candidates = []
        self.valid_until = datetime.now() + timedelta(0, ttl)
        self.has_all_candidates = False
        self.message_callback = None
        self.offer_candidate = []
        self.offer_sent = False
        self.modes = {}
        self.offer_codec_manager = None
        self.answer_codec_manager = None

    def __repr__(self) -> str:
        answer = ""
        if self.answer:
            if isinstance(self.final_answer, dict):
                answer = self.answer.get("sdp", f"{self.answer}")
            else:
                answer = f"{self.final_answer}"
        return (
            "\r\n[From TUYA]Config:\r\n"
            + f"{self.webrtc_config}"
            + "\r\n[From client]Original Offer\r\n"
            + f"{self.original_offer}"
            + "\r\n[From client]Offer\r\n"
            + f"{self.offer}"
            + "\r\n[From TUYA]Final answer:\r\n"
            + f"{answer}"
            + "\r\nEND DEBUG INFO"
        )


class XTIOTWebRTCManager:
    def __init__(self, ipc_manager: ipc_man.XTIOTIPCManager) -> None:
        self.sdp_exchange: dict[str, XTIOTWebRTCSession] = {}
        self.ipc_manager = ipc_manager

    def get_webrtc_session(self, session_id: str | None) -> XTIOTWebRTCSession | None:
        if session_id is None:
            return None
        self._clean_cache()
        if result := self.sdp_exchange.get(session_id):
            return result
        return None

    def _clean_cache(self) -> None:
        current_time = datetime.now()
        to_clean = []
        for session_id in self.sdp_exchange:
            if self.sdp_exchange[session_id].valid_until < current_time:
                to_clean.append(session_id)
        for session_id in to_clean:
            self.sdp_exchange.pop(session_id)

    def set_sdp_answer(self, session_id: str | None, answer: dict) -> None:
        if session_id is None:
            return
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].answer = answer
        if callback := self.sdp_exchange[session_id].message_callback:
            sdp_answer = answer.get("sdp", "")
            sdp_answer = self.fix_answer(sdp_answer, session_id)
            callback(WebRTCAnswer(answer=sdp_answer))

    def add_sdp_answer_candidate(self, session_id: str | None, candidate: dict) -> None:
        if session_id is None:
            return
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].answer_candidates.append(candidate)
        candidate_str = cast(str, candidate.get("candidate", ""))
        if candidate_str == "":
            self.sdp_exchange[session_id].has_all_candidates = True
        if callback := self.sdp_exchange[session_id].message_callback:
            ice_candidate = candidate_str.removeprefix("a=").removesuffix(ENDLINE)
            callback(
                WebRTCCandidate(candidate=RTCIceCandidate(candidate=ice_candidate))
            )

    def set_resolution(
        self, session_id: str, resolution: int, device: XTDevice
    ) -> None:
        resolution_payload = self.format_resolution(session_id, resolution, device)
        self.send_to_ipc_mqtt(session_id, device, json.dumps(resolution_payload))

    def set_config(self, session_id: str, config: dict[str, Any]):
        self._create_session_if_necessary(session_id)

        # Format ICE Servers so that they can be used by GO2RTC
        p2p_config: dict = config.get("p2p_config", {})
        if ices := p2p_config.get("ices"):
            p2p_config["ices"] = json.dumps(ices).replace(": ", ":").replace(", ", ",")
        self.sdp_exchange[session_id].webrtc_config = config

    def set_sdp_offer(self, session_id: str, offer: str) -> None:
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].offer = offer
        self.sdp_exchange[session_id].offer_codec_manager = XTIOTWebRTCCodecManager(
            offer
        )

    def set_original_sdp_offer(self, session_id: str, offer: str) -> None:
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].original_offer = offer

    def _create_session_if_necessary(self, session_id: str) -> None:
        self._clean_cache()
        if session_id not in self.sdp_exchange:
            self.sdp_exchange[session_id] = XTIOTWebRTCSession()

    async def async_get_config(
        self, device_id: str, session_id: str | None, hass: HomeAssistant | None = None
    ) -> dict | None:
        local_hass = hass
        if current_exchange := self.get_webrtc_session(session_id):
            if current_exchange.webrtc_config is not None:
                return current_exchange.webrtc_config
            if current_exchange.hass is not None:
                local_hass = hass
        if local_hass is not None:
            return await local_hass.async_add_executor_job(
                self._get_config_from_cloud, device_id, session_id
            )
        else:
            return self._get_config_from_cloud(device_id, session_id)

    def get_config(self, device_id: str, session_id: str | None) -> dict | None:
        if current_exchange := self.get_webrtc_session(session_id):
            if current_exchange.webrtc_config is not None:
                return current_exchange.webrtc_config
        elif session_id is not None:
            if current_exchange := self.get_webrtc_session(device_id):
                if current_exchange.webrtc_config is not None:
                    self.set_config(session_id, current_exchange.webrtc_config)
        return self._get_config_from_cloud(device_id, session_id)

    def _get_config_from_cloud(
        self, device_id: str, session_id: str | None
    ) -> dict | None:
        webrtc_config = self.ipc_manager.api.get(
            f"/v1.0/devices/{device_id}/webrtc-configs"
        )
        self.ipc_manager.multi_manager.device_watcher.report_message(
            device_id, f"webrtc_config {webrtc_config}")
        if webrtc_config.get("success"):
            result = webrtc_config.get("result", {})
            if session_id is not None:
                self.set_config(session_id, result)
            else:
                self.set_config(device_id, result)
            return result
        return None

    async def async_get_ice_servers(
        self, device_id: str, session_id: str | None, format: str, hass: HomeAssistant
    ) -> str | None:
        if config := await self.async_get_config(device_id, session_id, hass):
            p2p_config: dict = config.get("p2p_config", {})
            ice_str = p2p_config.get("ices", "{}")
            match format:
                case "GO2RTC":
                    return ice_str
                case "SimpleWHEP":
                    temp_str: str = ""
                    ice_list = json.loads(ice_str)
                    for ice in ice_list:
                        password: str = ice.get("credential", None)
                        username: str = ice.get("username", None)
                        url: str = ice.get("urls", None)
                        if url is None:
                            continue
                        if username is not None and password is not None:
                            # TURN server
                            temp_str += (
                                " -T "
                                + url.replace("turn:", "turn://")
                                .replace("turns:", "turns://")
                                .replace("://", f"://{username}:{password}@")
                                + "?transport=tcp"
                            )
                            pass
                        else:
                            # STUN server
                            temp_str += " -S " + url.replace("stun:", "stun://")
                            pass
                    return temp_str.strip()

    def get_ice_servers(
        self, device_id: str, session_id: str | None, format: str
    ) -> tuple[str, dict] | None:
        if config := self.get_config(device_id, session_id):
            p2p_config: dict = config.get("p2p_config", {})
            ice_str = p2p_config.get("ices", "{}")
            match format:
                case "GO2RTC":
                    return ice_str, config
                case "SimpleWHEP":
                    temp_str: str = ""
                    ice_list = json.loads(ice_str)
                    for ice in ice_list:
                        password: str = ice.get("credential", None)
                        username: str = ice.get("username", None)
                        url: str = ice.get("urls", None)
                        if url is None:
                            continue
                        if username is not None and password is not None:
                            # TURN server
                            temp_str += (
                                " -T "
                                + url.replace("turn:", "turn://")
                                .replace("turns:", "turns://")
                                .replace("://", f"://{username}:{password}@")
                                + "?transport=tcp"
                            )
                            pass
                        else:
                            # STUN server
                            temp_str += " -S " + url.replace("stun:", "stun://")
                            pass
                    return temp_str.strip(), config

    def _get_stream_type(
        self, device_id: str, session_id: str, requested_channel: str
    ) -> int:
        Any_stream_type = 1
        highest_res_stream_type = Any_stream_type
        cur_highest = 0
        lowest_res_stream_type = Any_stream_type
        cur_lowest = 0
        if webrtc_config := self.get_config(device_id, session_id):
            if skill := webrtc_config.get("skill"):
                try:
                    skill_json: dict = json.loads(skill)
                    video_list: list[dict[str, Any]] | None = skill_json.get("videos")
                    if video_list:
                        for video_details in video_list:
                            if (
                                "streamType" in video_details
                                and "width" in video_details
                                and "height" in video_details
                            ):
                                Any_stream_type = video_details["streamType"]
                                width = int(video_details["width"])
                                height = int(video_details["height"])
                                cur_value = width * height
                                if cur_highest < cur_value:
                                    cur_highest = cur_value
                                    highest_res_stream_type = video_details[
                                        "streamType"
                                    ]
                                if cur_lowest == 0 or cur_lowest > cur_value:
                                    cur_lowest = cur_value
                                    lowest_res_stream_type = video_details["streamType"]
                    if requested_channel == "high":
                        return highest_res_stream_type
                    elif requested_channel == "low":
                        return lowest_res_stream_type
                    else:
                        return int(requested_channel)
                except Exception:
                    return Any_stream_type
        return Any_stream_type

    def get_sdp_answer(
        self,
        device_id: str,
        session_id: str,
        sdp_offer: str,
        channel: str,
        wait_for_answers: int = 5,
    ) -> str | None:
        sleep_step = 0.01
        sleep_count: int = int(wait_for_answers / sleep_step)
        self.set_original_sdp_offer(session_id, sdp_offer)
        if webrtc_config := self.get_config(device_id, session_id):
            auth_token = webrtc_config.get("auth")
            moto_id = webrtc_config.get("moto_id")
            offer_candidates = []
            candidate_found = True
            while candidate_found:
                offset = sdp_offer.find("a=candidate:")
                if offset == -1:
                    candidate_found = False
                    break
                end_offset = sdp_offer.find(ENDLINE, offset) + len(ENDLINE)
                if end_offset <= offset:
                    break
                candidate_str = sdp_offer[offset:end_offset]
                if candidate_str not in offer_candidates:
                    offer_candidates.append(candidate_str)
                sdp_offer = sdp_offer.replace(candidate_str, "")
            sdp_offer = sdp_offer.replace("a=end-of-candidates" + ENDLINE, "")
            self.set_sdp_offer(session_id, sdp_offer)
            if (
                self.ipc_manager.ipc_mq.mq_config is not None
                and self.ipc_manager.ipc_mq.mq_config.sink_topic is not None
                and moto_id is not None
            ):
                for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
                    topic = topic.replace("{device_id}", device_id)
                    topic = topic.replace("moto_id", moto_id)
                    payload = {
                        "protocol": 302,
                        "pv": "2.2",
                        "t": int(time.time()),
                        "data": {
                            "header": {
                                "from": f"{self.ipc_manager.get_from()}",
                                "to": f"{device_id}",
                                # "sub_dev_id":"",
                                "sessionid": f"{session_id}",
                                "moto_id": f"{moto_id}",
                                # "tid":"",
                                "type": "offer",
                            },
                            "msg": {
                                "sdp": f"{sdp_offer}",
                                "auth": f"{auth_token}",
                                "mode": "webrtc",
                                "stream_type": self._get_stream_type(
                                    device_id, session_id, channel
                                ),
                            },
                        },
                    }
                    self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                    if offer_candidates:
                        for candidate in offer_candidates:
                            payload = {
                                "protocol": 302,
                                "pv": "2.2",
                                "t": int(time.time()),
                                "data": {
                                    "header": {
                                        "type": "candidate",
                                        "from": f"{self.ipc_manager.get_from()}",
                                        "to": f"{device_id}",
                                        "sub_dev_id": "",
                                        "sessionid": f"{session_id}",
                                        "moto_id": f"{moto_id}",
                                        "tid": "",
                                    },
                                    "msg": {"mode": "webrtc", "candidate": candidate},
                                },
                            }
                            self.ipc_manager.publish_to_ipc_mqtt(
                                topic, json.dumps(payload)
                            )
                    for _ in range(sleep_count):
                        if session := self.get_webrtc_session(session_id):
                            if session.has_all_candidates:
                                break
                        time.sleep(sleep_step)  # Wait for MQTT responses
                    if offer_candidates:
                        payload = {
                            "protocol": 302,
                            "pv": "2.2",
                            "t": int(time.time()),
                            "data": {
                                "header": {
                                    "type": "candidate",
                                    "from": f"{self.ipc_manager.get_from()}",
                                    "to": f"{device_id}",
                                    "sub_dev_id": "",
                                    "sessionid": f"{session_id}",
                                    "moto_id": f"{moto_id}",
                                    "tid": "",
                                },
                                "msg": {"mode": "webrtc", "candidate": ""},
                            },
                        }
                        self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                    if session := self.get_webrtc_session(session_id):
                        # Format SDP answer and send it back
                        sdp_answer: str = session.answer.get("sdp", "")
                        candidates: str = ""
                        if session.answer_candidates:
                            for candidate in session.answer_candidates:
                                candidates += candidate.get("candidate", "")
                            sdp_answer += candidates + "a=end-of-candidates" + ENDLINE
                        session.final_answer = f"{sdp_answer}"
                        return sdp_answer

            if not auth_token or not moto_id:
                return None

        return None

    def delete_webrtc_session(self, device_id: str, session_id: str) -> str | None:
        if webrtc_config := self.get_config(device_id, session_id):
            moto_id = webrtc_config.get("moto_id")
            payload = {
                "protocol": 302,
                "pv": "2.2",
                "t": int(time.time()),
                "data": {
                    "header": {
                        "type": "disconnect",
                        "from": f"{self.ipc_manager.get_from()}",
                        "to": f"{device_id}",
                        "sub_dev_id": "",
                        "sessionid": f"{session_id}",
                        "moto_id": f"{moto_id}",
                        "tid": "",
                    },
                    "msg": {"mode": "webrtc"},
                },
            }
            if self.ipc_manager.ipc_mq.mq_config is None:
                return None
            if self.ipc_manager.ipc_mq.mq_config.sink_topic is not None:
                for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
                    self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                return ""
        return None

    def send_webrtc_trickle_ice(
        self, device_id: str, session_id: str, candidate: str
    ) -> str | None:
        if webrtc_config := self.get_config(device_id, session_id):
            moto_id = webrtc_config.get("moto_id")
            payload = {
                "protocol": 302,
                "pv": "2.2",
                "t": int(time.time()),
                "data": {
                    "header": {
                        "type": "candidate",
                        "from": f"{self.ipc_manager.get_from()}",
                        "to": f"{device_id}",
                        "sub_dev_id": "",
                        "sessionid": f"{session_id}",
                        "moto_id": f"{moto_id}",
                        "tid": "",
                    },
                    "msg": {"mode": "webrtc", "candidate": candidate},
                },
            }
            if self.ipc_manager.ipc_mq.mq_config is None:
                return None
            if self.ipc_manager.ipc_mq.mq_config.sink_topic is not None:
                for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
                    self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                return ""
        return None

    async def async_handle_async_webrtc_offer(
        self,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
        device: XTDevice,
        hass: HomeAssistant,
    ) -> None:
        self._create_session_if_necessary(session_id)
        session_data = self.get_webrtc_session(session_id)
        if session_data is None:
            return None
        session_data.message_callback = send_message
        session_data.hass = hass
        await self.async_get_config(device.id, session_id, hass)
        self.set_original_sdp_offer(session_id, offer_sdp)
        offer_changed = self.get_candidates_from_offer(session_id, offer_sdp)
        offer_changed = self.fix_offer(offer_changed, session_id)
        self.set_sdp_offer(session_id, offer_changed)
        sdp_offer_payload = await hass.async_add_executor_job(
            self.format_offer_payload, session_id, offer_changed, device
        )
        self.send_to_ipc_mqtt(session_id, device, json.dumps(sdp_offer_payload))
        session_data.offer_sent = True
        for candidate in session_data.offer_candidate:
            if candidate_payload := await hass.async_add_executor_job(
                self.format_offer_candidate, session_id, candidate, device
            ):
                self.send_to_ipc_mqtt(session_id, device, json.dumps(candidate_payload))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit, device: XTDevice
    ) -> None:
        self.on_webrtc_candidate(session_id, candidate, device)

    def on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit, device: XTDevice
    ) -> None:
        session_data = self.get_webrtc_session(session_id)
        if session_data is None:
            return None
        candidate_str = candidate.candidate
        if candidate_str != "":
            candidate_str = f"a={candidate.candidate}"
        if not session_data.offer_sent:
            session_data.offer_candidate.append(candidate_str)
        else:
            if payload := self.format_offer_candidate(
                session_id, candidate_str, device
            ):
                self.send_to_ipc_mqtt(session_id, device, json.dumps(payload))

    def on_webrtc_close_session(self, session_id: str, device: XTDevice) -> None:
        session_data = self.get_webrtc_session(session_id)
        if session_data is None:
            return None
        if payload := self.format_close_session(session_id, device):
            self.send_to_ipc_mqtt(session_id, device, json.dumps(payload))
        return None

    def get_candidates_from_offer(self, session_id: str, offer_sdp: str) -> str:
        session_data = self.get_webrtc_session(session_id)
        sdp_offer = str(offer_sdp)
        if session_data is None:
            return sdp_offer
        offer_candidates = []
        candidate_found = True
        while candidate_found:
            offset = sdp_offer.find("a=candidate:")
            if offset == -1:
                candidate_found = False
                break
            end_offset = sdp_offer.find(ENDLINE, offset) + len(ENDLINE)
            if end_offset <= offset:
                break
            candidate_str = sdp_offer[offset:end_offset]
            if candidate_str not in offer_candidates:
                offer_candidates.append(candidate_str)
            sdp_offer = sdp_offer.replace(candidate_str, "")
        if len(offer_candidates) > 0:
            session_data.offer_candidate = offer_candidates
        return sdp_offer

    def fix_offer(self, offer_sdp: str, session_id: str) -> str:
        webrtc_session = self.get_webrtc_session(session_id)
        extmap_found = True
        searched_offset: int = 0

        if webrtc_session is None:
            return offer_sdp

        while extmap_found:
            offset = offer_sdp.find("a=extmap:")
            if offset == -1:
                extmap_found = False
                break
            end_offset = offer_sdp.find(ENDLINE, offset) + len(ENDLINE)
            if end_offset <= offset:
                break
            extmap_str = offer_sdp[offset:end_offset]
            offer_sdp = offer_sdp.replace(extmap_str, "")

        # Find the send/receive mode of audio/video
        searched_offset = 0
        has_more_m_sections = True
        modes_to_search: list[str] = [
            f"a=sendrecv{ENDLINE}",
            f"a=recvonly{ENDLINE}",
            f"a=sendonly{ENDLINE}",
        ]
        while has_more_m_sections:
            offset = offer_sdp.find("m=", searched_offset)
            if offset == -1:
                break
            end_of_section = offer_sdp.find("m=", offset + 1)
            if end_of_section == -1:
                has_more_m_sections = False
                end_of_section = len(offer_sdp)
            audio_video = offer_sdp[offset + 2 : offset + 7]
            for mode_to_search in modes_to_search:
                if offer_sdp.find(mode_to_search, offset, end_of_section) != -1:
                    webrtc_session.modes[audio_video] = mode_to_search
                    break
            searched_offset = end_of_section
        return offer_sdp

    def fix_answer(self, answer_sdp: str, session_id: str) -> str:
        webrtc_session = self.get_webrtc_session(session_id)
        fingerprint_found = True
        searched_offset: int = 0
        if webrtc_session is None:
            return answer_sdp

        webrtc_session.answer_codec_manager = XTIOTWebRTCCodecManager(answer_sdp)

        if webrtc_session.offer_codec_manager is not None:
            m_sections: list[str] = webrtc_session.answer_codec_manager.get_m_sections()
            for m_section in m_sections:
                match_tuple = (
                    webrtc_session.answer_codec_manager.get_closest_same_codec_rtpmap(
                        webrtc_session.offer_codec_manager, m_section
                    )
                )
                if match_tuple is not None:
                    full_match_found, best_answer_rtpmap, best_offer_rtpmap = (
                        match_tuple
                    )
                    if full_match_found is False:
                        # Fix the RTPMAP based on the offer RTPMAP
                        string_replacements = (
                            best_answer_rtpmap.get_string_replacements(
                                best_offer_rtpmap
                            )
                        )
                        for source in string_replacements:
                            answer_sdp = answer_sdp.replace(
                                source, string_replacements[source]
                            )

        while fingerprint_found:
            offset = answer_sdp.find("a=fingerprint:", searched_offset)
            if offset == -1:
                fingerprint_found = False
                break
            end_offset = answer_sdp.find(ENDLINE, offset) + len(ENDLINE)
            if end_offset <= offset:
                break
            searched_offset = end_offset
            fingerprint_orig_str = answer_sdp[offset:end_offset]
            offset = fingerprint_orig_str.find(" ")
            if offset != -1:
                fingerprint_orig_str = fingerprint_orig_str[offset:]
            fingerprint_new_str = fingerprint_orig_str.upper()
            answer_sdp = answer_sdp.replace(fingerprint_orig_str, fingerprint_new_str)

        if (
            webrtc_session.offer is not None
            and webrtc_session.offer.find("mozilla") != -1
        ):
            # Firefox has a much more strict SDP checking mecanism than Chrome, fix the answer so that it accepts it

            # Fix send/receive mode for Firefox
            searched_offset = 0
            has_more_m_sections = True
            modes_to_search: dict[str, str] = {
                f"a=sendrecv{ENDLINE}": f"a=sendrecv{ENDLINE}",
                f"a=recvonly{ENDLINE}": f"a=sendonly{ENDLINE}",
                f"a=sendonly{ENDLINE}": f"a=recvonly{ENDLINE}",
            }
            while has_more_m_sections:
                offset = answer_sdp.find("m=", searched_offset)
                if offset == -1:
                    break
                end_of_section = answer_sdp.find("m=", offset + 1)
                if end_of_section == -1:
                    has_more_m_sections = False
                    end_of_section = len(answer_sdp)
                audio_video = answer_sdp[offset + 2 : offset + 7]
                searched_offset = end_of_section
                for mode_to_search in modes_to_search:
                    mode_offset = answer_sdp.find(
                        mode_to_search, offset, end_of_section
                    )
                    if mode_offset != -1:
                        new_mode = webrtc_session.modes.get(audio_video, None)
                        if new_mode is not None:
                            new_mode = modes_to_search.get(new_mode, new_mode)
                        else:
                            new_mode = mode_to_search
                        answer_sdp = (
                            answer_sdp[0:mode_offset]
                            + new_mode
                            + answer_sdp[mode_offset + len(mode_to_search) :]
                        )
                        break
        return answer_sdp

    def format_offer_payload(
        self, session_id: str, offer_sdp: str, device: XTDevice, channel: str = "high"
    ) -> dict[str, Any] | None:
        if webrtc_config := self.get_config(device.id, session_id):
            return {
                "protocol": 302,
                "pv": "2.2",
                "t": int(time.time()),
                "data": {
                    "header": {
                        "type": "offer",
                        "from": f"{self.ipc_manager.get_from()}",
                        "to": f"{device.id}",
                        "sub_dev_id": "",
                        "sessionid": f"{session_id}",
                        "moto_id": f"{webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!")}",
                        "tid": "",
                    },
                    "msg": {
                        "mode": "webrtc",
                        "sdp": f"{offer_sdp}",
                        "stream_type": self._get_stream_type(
                            device.id, session_id, channel
                        ),
                        "auth": f"{webrtc_config.get("auth", "!!!AUTH_NOT_FOUND!!!")}",
                    },
                },
            }
        return None

    def format_offer_candidate(
        self, session_id: str, candidate: str, device: XTDevice
    ) -> dict[str, Any] | None:
        if webrtc_config := self.get_config(device.id, session_id):
            moto_id = webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!")
            return {
                "protocol": 302,
                "pv": "2.2",
                "t": int(time.time()),
                "data": {
                    "header": {
                        "type": "candidate",
                        "from": f"{self.ipc_manager.get_from()}",
                        "to": f"{device.id}",
                        "sub_dev_id": "",
                        "sessionid": f"{session_id}",
                        "moto_id": f"{moto_id}",
                        "tid": "",
                    },
                    "msg": {"mode": "webrtc", "candidate": candidate},
                },
            }
        return None

    def format_resolution(
        self, session_id: str, resolution: int, device: XTDevice
    ) -> dict[str, Any] | None:
        # resolution 0 if HD, 1 is SD
        if webrtc_config := self.get_config(device.id, session_id):
            moto_id = webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!")
            return {
                "protocol": 312,
                "pv": "2.2",
                "t": int(time.time()),
                "data": {
                    "header": {
                        "type": "resolution",
                        "from": f"{self.ipc_manager.get_from()}",
                        "to": f"{device.id}",
                        "sub_dev_id": "",
                        "sessionid": f"{session_id}",
                        "moto_id": f"{moto_id}",
                        "tid": "",
                    },
                    "msg": {"mode": "webrtc", "cmdValue": resolution},
                },
            }
        return None

    def format_close_session(
        self, session_id: str, device: XTDevice
    ) -> dict[str, Any] | None:
        if webrtc_config := self.get_config(device.id, session_id):
            moto_id = webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!")
            return {
                "protocol": 302,
                "pv": "2.2",
                "t": int(time.time()),
                "data": {
                    "header": {
                        "type": "disconnect",
                        "from": f"{self.ipc_manager.get_from()}",
                        "to": f"{device.id}",
                        "sub_dev_id": "",
                        "sessionid": f"{session_id}",
                        "moto_id": f"{moto_id}",
                        "tid": "",
                    },
                    "msg": {"mode": "webrtc"},
                },
            }
        return None

    def send_to_ipc_mqtt(self, session_id: str, device: XTDevice, payload: str):
        webrtc_config = self.get_config(device.id, session_id)
        if (
            self.ipc_manager.ipc_mq.mq_config is None
            or self.ipc_manager.ipc_mq.mq_config.sink_topic is None
            or webrtc_config is None
        ):
            return None
        for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
            topic = topic.replace("{device_id}", device.id)
            topic = topic.replace(
                "moto_id", webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!")
            )
            self.ipc_manager.publish_to_ipc_mqtt(topic, payload)


class XTIOTWebRTCCodecManager:
    def __init__(self, sdp_offer_answer: str) -> None:
        self.sdp_offer_answer = sdp_offer_answer
        self.rtpmap: dict[str, dict[str, list[XTIOTWebRTCRTPMap]]] = {}
        self._parse_offer_answer()

    def __repr__(self) -> str:
        return f"{self.rtpmap}"

    def _parse_offer_answer(self):
        sdp_lines = self.sdp_offer_answer.split(ENDLINE)
        m_line: str | None = None
        id_dict: dict[int, XTIOTWebRTCRTPMap] = {}
        for sdp_line in sdp_lines:
            if sdp_line.startswith("m="):
                m_line = sdp_line
            if sdp_line.startswith("a=rtpmap:"):
                if m_line is not None:
                    rtpmap = XTIOTWebRTCRTPMap(sdp_line, m_line)
                    if codec := rtpmap.get_codec():
                        m_line_section = rtpmap.get_m_line_section()
                        if m_line_section not in self.rtpmap:
                            self.rtpmap[m_line_section] = {}
                        if codec not in self.rtpmap[m_line_section]:
                            self.rtpmap[m_line_section][codec] = []
                        self.rtpmap[m_line_section][codec].append(rtpmap)
                        if rtpmap_id := rtpmap.get_rtpmap_id():
                            id_dict[rtpmap_id] = rtpmap
        for sdp_line in sdp_lines:
            if sdp_line.startswith("a=rtcp-fb:") or sdp_line.startswith("a=fmtp:"):
                if rtpmap_id := XTIOTWebRTCRTPMap.get_a_line_id(sdp_line):
                    if rtpmap_id in id_dict:
                        id_dict[rtpmap_id].add_a_line(sdp_line)

    def get_m_sections(self) -> list[str]:
        return_list: list[str] = []
        for m_section in self.rtpmap:
            return_list.append(m_section)
        return return_list

    def get_closest_same_codec_rtpmap(
        self, other_codec_manager: XTIOTWebRTCCodecManager, m_line_section: str
    ) -> tuple[bool, XTIOTWebRTCRTPMap, XTIOTWebRTCRTPMap] | None:
        if (
            m_line_section not in self.rtpmap
            or m_line_section not in other_codec_manager.rtpmap
        ):
            return None
        own_codec_map = self.rtpmap[m_line_section]
        other_codec_map = other_codec_manager.rtpmap[m_line_section]
        match_score: float = -1
        best_own_rtpmap: XTIOTWebRTCRTPMap | None = None
        best_other_rtpmap: XTIOTWebRTCRTPMap | None = None
        for codec in own_codec_map:
            if codec in other_codec_map:
                for own_rtpmap in own_codec_map[codec]:
                    for other_rtpmap in other_codec_map[codec]:
                        total, matching = own_rtpmap.get_comparison_score(other_rtpmap)
                        if total == matching:
                            # Found a full match, return it
                            return True, own_rtpmap, other_rtpmap
                        if total == 0:
                            continue
                        cur_match_score = matching / total
                        if cur_match_score > match_score:
                            match_score = cur_match_score
                            best_own_rtpmap = own_rtpmap
                            best_other_rtpmap = other_rtpmap
        if best_own_rtpmap is not None and best_other_rtpmap is not None:
            return False, best_own_rtpmap, best_other_rtpmap
        return None


class XTIOTWebRTCRTPMap:
    def __init__(self, rtpmap_line: str, m_line: str) -> None:
        self.rtpmap = rtpmap_line
        self.m_line = m_line
        self.a_lines: dict[str, XTIOTWebRTCRTPMapALineGroup] = (
            {}
        )  # dict[a=...:, tokens]

    def __repr__(self) -> str:
        return_str = self.rtpmap + ENDLINE
        for a_tag in self.a_lines:
            for a_lines in self.a_lines[a_tag].raw_a_lines:
                return_str += a_lines + ENDLINE
        return return_str

    def get_m_line_section(self) -> str:
        m_line_split = self.m_line.split(" ", 1)
        if len(m_line_split) > 1:
            return m_line_split[0][2:]
        return self.m_line

    @staticmethod
    def get_a_line_id(a_line: str) -> int | None:
        rtpmap_split = a_line.split(" ")
        if len(rtpmap_split) > 1:
            left = rtpmap_split[0]
            left_split = left.split(":")
            if len(left_split) > 1:
                id = left_split[1]
                if id.isdigit():
                    return int(id)
        return None

    def get_rtpmap_id(self) -> int | None:
        return XTIOTWebRTCRTPMap.get_a_line_id(self.rtpmap)

    def get_codec(self) -> str | None:
        rtpmap_split = self.rtpmap.split(" ", 1)
        if len(rtpmap_split) > 1:
            return rtpmap_split[1]
        return None

    def add_a_line(self, a_line: str) -> None:
        a_line_split = a_line.split(":")
        if len(a_line_split) > 1:
            a_line_left = a_line_split[0]
            if a_line_left not in self.a_lines:
                self.a_lines[a_line_left] = XTIOTWebRTCRTPMapALineGroup()
            self.a_lines[a_line_left].add_a_line_tokens(a_line)
        return None

    def get_comparison_score(self, other_rtpmap: XTIOTWebRTCRTPMap) -> tuple[int, int]:
        total_lines: int = 0
        matching_lines: int = 0
        a_left_list: list[str] = []
        for a_left in self.a_lines:
            if a_left not in a_left_list:
                a_left_list.append(a_left)
        for a_left in other_rtpmap.a_lines:
            if a_left not in a_left_list:
                a_left_list.append(a_left)
        for a_left in a_left_list:
            if a_left in self.a_lines and a_left in other_rtpmap.a_lines:
                compare_total_lines, compare_matching_lines = self.a_lines[
                    a_left
                ].get_comparison_score(other_rtpmap.a_lines[a_left])
            elif a_left in self.a_lines:
                compare_total_lines, compare_matching_lines = self.a_lines[
                    a_left
                ].get_comparison_score(None)
            else:
                compare_total_lines, compare_matching_lines = other_rtpmap.a_lines[
                    a_left
                ].get_comparison_score(None)
            total_lines += compare_total_lines
            matching_lines += compare_matching_lines
        return total_lines, matching_lines

    def get_string_replacements(
        self, result_rtpmap: XTIOTWebRTCRTPMap
    ) -> dict[str, str]:
        return_dict: dict[str, str] = {}
        matching_a_tags: list[str] = []
        not_in_other_a_tag: list[str] = []
        not_in_my_a_tag: list[str] = []
        new_a_line = ""
        for a_tag in self.a_lines:
            if a_tag in result_rtpmap.a_lines:
                matching_a_tags.append(a_tag)
            else:
                not_in_other_a_tag.append(a_tag)
        for a_tag in result_rtpmap.a_lines:
            if a_tag not in self.a_lines:
                not_in_my_a_tag.append(a_tag)
        for a_tag in not_in_other_a_tag:
            for a_lines in self.a_lines[a_tag].raw_a_lines:
                return_dict[a_lines + ENDLINE] = ""
        for a_tag in not_in_my_a_tag:
            for a_lines in result_rtpmap.a_lines[a_tag].raw_a_lines:
                new_a_line = new_a_line + a_lines + ENDLINE
        for a_tag in matching_a_tags:
            a_lines: str | None = None
            for a_lines in self.a_lines[a_tag].raw_a_lines:
                return_dict[a_lines + ENDLINE] = ""
            if a_lines is not None:
                for a_lines_result in result_rtpmap.a_lines[a_tag].raw_a_lines:
                    new_a_line = new_a_line + a_lines_result + ENDLINE
                return_dict[a_lines + ENDLINE] = new_a_line
                new_a_line = ""
        return return_dict


class XTIOTWebRTCRTPMapALineGroup:
    def __init__(self) -> None:
        self.a_line_tokens: dict[str, str | None] = {}
        self.raw_a_lines: list[str] = []

    def add_a_line_tokens(self, a_line: str) -> None:
        if a_line not in self.raw_a_lines:
            self.raw_a_lines.append(a_line)
        a_line_split = a_line.split(" ", 1)
        if len(a_line_split) > 1:
            values_raw = a_line_split[1]
            value_props = values_raw.split(";")
            for value_prop in value_props:
                value_prop_split = value_prop.split("=", 1)
                if len(value_prop_split) == 2:
                    self.a_line_tokens[value_prop_split[0]] = value_prop_split[1]
                else:
                    self.a_line_tokens[value_prop] = None

    def get_comparison_score(
        self, other_rtpmap_a_line_group: XTIOTWebRTCRTPMapALineGroup | None
    ) -> tuple[int, int]:
        total_lines: int = 0
        matching_lines: int = 0
        if other_rtpmap_a_line_group is None:
            # Get the number of attributes + values and return it as unmatched lines
            for token in self.a_line_tokens:
                if self.a_line_tokens[token] is None:
                    total_lines += 1
                else:
                    total_lines += 2
        else:
            for token in self.a_line_tokens:
                if token in other_rtpmap_a_line_group.a_line_tokens:
                    total_lines += 1
                    matching_lines += 1
                    if (
                        self.a_line_tokens[token]
                        == other_rtpmap_a_line_group.a_line_tokens[token]
                    ):
                        total_lines += 1
                        matching_lines += 1
                    else:
                        total_lines += 1
                else:
                    if self.a_line_tokens[token] is None:
                        total_lines += 1
                    else:
                        total_lines += 2
            for token in other_rtpmap_a_line_group.a_line_tokens:
                if token not in self.a_line_tokens:
                    if other_rtpmap_a_line_group.a_line_tokens[token] is None:
                        total_lines += 1
                    else:
                        total_lines += 2
        return total_lines, matching_lines
