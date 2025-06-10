from __future__ import annotations

from typing import Any, cast
from datetime import datetime, timedelta
import time
import json

from webrtc_models import (
    RTCConfiguration,
    RTCIceCandidate,
    RTCIceCandidateInit,
    RTCIceServer,
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
from ..xt_tuya_iot_ipc_manager import (
    XTIOTIPCManager,
)

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
    
    def __repr__(self) -> str:
        answer = ""
        if self.answer:
            if isinstance(self.final_answer, dict):
                answer = self.answer.get("sdp", f"{self.answer}")
            else:
                answer = f"{self.final_answer}"
        return (
            "\r\n[From TUYA]Config:\r\n" + f"{self.webrtc_config}" +
            "\r\n[From client]Original Offer\r\n" + f"{self.original_offer}" +
            "\r\n[From client]Offer\r\n" + f"{self.offer}" +
            "\r\n[From TUYA]Final answer:\r\n" + f"{answer}" + 
            "\r\nEND DEBUG INFO"
            )

class XTIOTWebRTCManager:
    def __init__(self, ipc_manager: XTIOTIPCManager) -> None:
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
            LOGGER.warning(f"SDP Answer {sdp_answer}")
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
            #LOGGER.warning(f"Returning ICE candidate {ice_candidate}")
            callback(WebRTCCandidate(candidate=RTCIceCandidate(candidate=ice_candidate)))

    def set_config(self, session_id: str, config: dict[str, Any]):
        self._create_session_if_necessary(session_id)

        #Format ICE Servers so that they can be used by GO2RTC
        p2p_config: dict = config.get("p2p_config", {})
        if ices := p2p_config.get("ices"):
            p2p_config["ices"] = json.dumps(ices).replace(': ', ':').replace(', ', ',')
        self.sdp_exchange[session_id].webrtc_config = config

    def set_sdp_offer(self, session_id: str, offer: str) -> None:
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].offer = offer
    
    def set_original_sdp_offer(self, session_id: str, offer: str) -> None:
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].original_offer = offer

    def _create_session_if_necessary(self, session_id: str) -> None:
        self._clean_cache()
        if session_id not in self.sdp_exchange:
            self.sdp_exchange[session_id] = XTIOTWebRTCSession()
    
    async def async_get_config(self, device_id: str, session_id: str | None, hass: HomeAssistant | None = None) -> dict | None:
        local_hass = hass
        if current_exchange := self.get_webrtc_session(session_id):
            if current_exchange.webrtc_config is not None:
                return current_exchange.webrtc_config
            if current_exchange.hass is not None:
                local_hass = hass
        if local_hass is not None:
            return await local_hass.async_add_executor_job(self._get_config_from_cloud, device_id, session_id)
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
    
    def _get_config_from_cloud(self, device_id: str, session_id: str | None) -> dict | None:
        webrtc_config = self.ipc_manager.api.get(f"/v1.0/devices/{device_id}/webrtc-configs")
        if webrtc_config.get("success"):
            result = webrtc_config.get("result", {})
            if session_id is not None:
                self.set_config(session_id, result)
            else:
                self.set_config(device_id, result)
            #LOGGER.warning(f"WebRTC Config: {result}")
            return result
        return None
    
    async def async_get_ice_servers(self, device_id: str, session_id: str | None, format: str, hass: HomeAssistant) -> str | None:
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
                            #TURN server
                            temp_str += " -T " + url.replace("turn:", "turn://").replace("turns:", "turns://").replace("://", f"://{username}:{password}@") + "?transport=tcp"
                            pass
                        else:
                            #STUN server
                            temp_str += " -S " + url.replace("stun:", "stun://")
                            pass
                    return temp_str.strip()

    def get_ice_servers(self, device_id: str, session_id: str | None, format: str) -> str | None:
        if config := self.get_config(device_id, session_id):
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
                            #TURN server
                            temp_str += " -T " + url.replace("turn:", "turn://").replace("turns:", "turns://").replace("://", f"://{username}:{password}@") + "?transport=tcp"
                            pass
                        else:
                            #STUN server
                            temp_str += " -S " + url.replace("stun:", "stun://")
                            pass
                    return temp_str.strip()

    def _get_stream_type(self, device_id: str, session_id: str, requested_channel: str) -> int:
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
                                    highest_res_stream_type = video_details["streamType"]
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

    def get_sdp_answer(self, device_id: str, session_id: str, sdp_offer: str, channel: str, wait_for_answers: int = 5) -> str | None:
        sleep_step = 0.01
        sleep_count: int = int(wait_for_answers / sleep_step)
        self.set_original_sdp_offer(session_id, sdp_offer)
        if webrtc_config := self.get_config(device_id, session_id):
            auth_token = webrtc_config.get("auth")
            moto_id =  webrtc_config.get("moto_id")
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
                self.ipc_manager.ipc_mq.mq_config is not None and 
                self.ipc_manager.ipc_mq.mq_config.sink_topic is not None and 
                moto_id is not None
            ):
                for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
                    topic = topic.replace("{device_id}", device_id)
                    topic = topic.replace("moto_id", moto_id)
                    payload = {
                        "protocol":302,
                        "pv":"2.2",
                        "t":int(time.time()),
                        "data":{
                            "header":{
                                "from":f"{self.ipc_manager.get_from()}",
                                "to":f"{device_id}",
                                #"sub_dev_id":"",
                                "sessionid":f"{session_id}",
                                "moto_id":f"{moto_id}",
                                #"tid":"",
                                "type":"offer",
                            },
                            "msg":{
                                "sdp":f"{sdp_offer}",
                                "auth":f"{auth_token}",
                                "mode":"webrtc",
                                "stream_type":self._get_stream_type(device_id, session_id, channel),
                            }
                        },
                    }
                    self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                    if offer_candidates:
                        for candidate in offer_candidates:
                            payload = {
                                "protocol":302,
                                "pv":"2.2",
                                "t":int(time.time()),
                                "data":{
                                    "header":{
                                        "type":"candidate",
                                        "from":f"{self.ipc_manager.get_from()}",
                                        "to":f"{device_id}",
                                        "sub_dev_id":"",
                                        "sessionid":f"{session_id}",
                                        "moto_id":f"{moto_id}",
                                        "tid":""
                                    },
                                    "msg":{
                                        "mode":"webrtc",
                                        "candidate": candidate
                                    }
                                },
                            }
                            self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                    for _ in range(sleep_count):
                        if session := self.get_webrtc_session(session_id):
                            if session.has_all_candidates:
                                break
                        time.sleep(sleep_step) #Wait for MQTT responses
                    if offer_candidates:
                        payload = {
                            "protocol":302,
                            "pv":"2.2",
                            "t":int(time.time()),
                            "data":{
                                "header":{
                                    "type":"candidate",
                                    "from":f"{self.ipc_manager.get_from()}",
                                    "to":f"{device_id}",
                                    "sub_dev_id":"",
                                    "sessionid":f"{session_id}",
                                    "moto_id":f"{moto_id}",
                                    "tid":""
                                },
                                "msg":{
                                    "mode":"webrtc",
                                    "candidate": ""
                                }
                            },
                        }
                        self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                    if session := self.get_webrtc_session(session_id):
                        #Format SDP answer and send it back
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
            moto_id =  webrtc_config.get("moto_id")
            payload = {
                "protocol":302,
                "pv":"2.2",
                "t":int(time.time()),
                "data":{
                    "header":{
                        "type":"disconnect",
                        "from":f"{self.ipc_manager.get_from()}",
                        "to":f"{device_id}",
                        "sub_dev_id":"",
                        "sessionid":f"{session_id}",
                        "moto_id":f"{moto_id}",
                        "tid":""
                    },
                    "msg":{
                        "mode":"webrtc"
                    }
                },
            }
            if self.ipc_manager.ipc_mq.mq_config is None:
                return None
            if self.ipc_manager.ipc_mq.mq_config.sink_topic is not None:
                for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
                    self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
                return ""
        return None
    
    def send_webrtc_trickle_ice(self, device_id: str, session_id: str, candidate: str) -> str | None:
        if webrtc_config := self.get_config(device_id, session_id):
            moto_id =  webrtc_config.get("moto_id")
            payload = {
                "protocol":302,
                "pv":"2.2",
                "t":int(time.time()),
                "data":{
                    "header":{
                        "type":"candidate",
                        "from":f"{self.ipc_manager.get_from()}",
                        "to":f"{device_id}",
                        "sub_dev_id":"",
                        "sessionid":f"{session_id}",
                        "moto_id":f"{moto_id}",
                        "tid":""
                    },
                    "msg":{
                        "mode":"webrtc",
                        "candidate": candidate
                    }
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
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage, device: XTDevice, hass: HomeAssistant
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
        sdp_offer_payload = self.format_offer_payload(session_id, offer_changed, device)
        self.send_to_ipc_mqtt(session_id, device, json.dumps(sdp_offer_payload))
        session_data.offer_sent = True
        for candidate in session_data.offer_candidate:
            if candidate_payload := self.format_offer_candidate(session_id, candidate, device):
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
        if session_data.offer_sent == False:
            session_data.offer_candidate.append(candidate_str)
        else:
            if payload := self.format_offer_candidate(session_id, candidate_str, device):
                self.send_to_ipc_mqtt(session_id, device, json.dumps(payload))
    
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

        #Find the send/receive mode of audio/video
        searched_offset = 0
        has_more_m_sections = True
        while has_more_m_sections:
            offset = offer_sdp.find("m=", searched_offset)
            if offset == -1:
                break
            end_of_section = offer_sdp.find("m=", offset+1)
            if end_of_section == -1:
                has_more_m_sections = False
                end_of_section = len(offer_sdp)
            audio_video = offer_sdp[offset+2:offset+7]
            if offer_sdp.find("a=sendrecv", offset, end_of_section) != -1:
                mode = "sendrecv"
            elif offer_sdp.find("a=recvonly", offset, end_of_section) != -1:
                mode = "recvonly"
            else:
                mode = "sendonly"
            searched_offset = end_of_section
            webrtc_session.modes[audio_video] = mode
        LOGGER.warning(f"Stored modes: {webrtc_session.modes}")
        return offer_sdp
    
    def fix_answer(self, answer_sdp: str, session_id: str) -> str:
        webrtc_session = self.get_webrtc_session(session_id)
        fingerprint_found = True
        searched_offset: int = 0

        if webrtc_session is None:
            return answer_sdp

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
        
        searched_offset = 0
        has_more_m_sections = True
        modes_to_search: list[str] = [f"a=sendrecv{ENDLINE}", f"a=recvonly{ENDLINE}", f"a=sendonly{ENDLINE}"]
        while has_more_m_sections:
            offset = answer_sdp.find("m=", searched_offset)
            if offset == -1:
                break
            end_of_section = answer_sdp.find("m=", offset+1)
            if end_of_section == -1:
                has_more_m_sections = False
                end_of_section = len(answer_sdp)
            audio_video = answer_sdp[offset+2:offset+7]
            searched_offset = end_of_section
            for mode_to_search in modes_to_search:
                mode_offset = answer_sdp.find(mode_to_search, offset, end_of_section)
                if mode_offset != -1:
                    answer_sdp = answer_sdp[0:offset] + webrtc_session.modes.get(audio_video, mode_to_search) + answer_sdp[offset+len(mode_to_search):]
                    break
        return answer_sdp
    
    def format_offer_payload(self, session_id: str, offer_sdp: str, device: XTDevice, channel: str = "1") -> dict[str, Any] | None:
        if webrtc_config := self.get_config(device.id, session_id):
            return {
                "protocol":302,
                "pv":"2.2",
                "t":int(time.time()),
                "data":{
                    "header":{
                        "type":"offer",
                        "from":f"{self.ipc_manager.get_from()}",
                        "to":f"{device.id}",
                        "sub_dev_id":"",
                        "sessionid":f"{session_id}",
                        "moto_id":f"{webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!")}",
                        "tid":"",
                    },
                    "msg":{
                        "mode":"webrtc",
                        "sdp":f"{offer_sdp}",
                        "stream_type":self._get_stream_type(device.id, session_id, channel),
                        "auth":f"{webrtc_config.get("auth", "!!!AUTH_NOT_FOUND!!!")}",
                    }
                },
            }
        return None
    
    def format_offer_candidate(self, session_id: str, candidate: str, device: XTDevice) -> dict[str, Any] | None:
        if webrtc_config := self.get_config(device.id, session_id):
            moto_id =  webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!")
            return {
                "protocol":302,
                "pv":"2.2",
                "t":int(time.time()),
                "data":{
                    "header":{
                        "type":"candidate",
                        "from":f"{self.ipc_manager.get_from()}",
                        "to":f"{device.id}",
                        "sub_dev_id":"",
                        "sessionid":f"{session_id}",
                        "moto_id":f"{moto_id}",
                        "tid":""
                    },
                    "msg":{
                        "mode":"webrtc",
                        "candidate": candidate
                    }
                },
            }
        return None
    
    def send_to_ipc_mqtt(self, session_id: str, device: XTDevice, payload: str):
        webrtc_config = self.get_config(device.id, session_id)
        if (
            self.ipc_manager.ipc_mq.mq_config is None or 
            self.ipc_manager.ipc_mq.mq_config.sink_topic is None or 
            webrtc_config is None
        ):
            return None
        for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
            topic = topic.replace("{device_id}", device.id)
            topic = topic.replace("moto_id", webrtc_config.get("moto_id", "!!!MOTO_ID_NOT_FOUND!!!"))
            #LOGGER.warning(f"Sending to IPC: {payload}")
            self.ipc_manager.publish_to_ipc_mqtt(topic, payload)