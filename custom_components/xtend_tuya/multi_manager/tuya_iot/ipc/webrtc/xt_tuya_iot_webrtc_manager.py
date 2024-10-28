from __future__ import annotations

from datetime import datetime, timedelta
import time
import json

from .....const import (
    LOGGER,  # noqa: F401
)
from ..xt_tuya_iot_ipc_manager import (
    XTIOTIPCManager,
)

class XTIOTWebRTCSession:
    webrtc_config: dict[str, any]
    original_offer: str
    offer: str
    answer: dict
    final_answer: str
    answer_candidates: list[dict]
    has_all_candidates: bool

    def __init__(self, ttl: int = 600) -> None:
        self.webrtc_config = {}
        self.original_offer = None
        self.offer = None
        self.answer = {}
        self.final_answer = None
        self.answer_candidates = []
        self.valid_until = datetime.now() + timedelta(0, ttl)
        self.has_all_candidates = False
    
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
    
    def get_webrtc_session(self, session_id: str) -> XTIOTWebRTCSession | None:
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
    
    def set_sdp_answer(self, session_id: str, answer: str) -> None:
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].answer = answer
    
    def add_sdp_answer_candidate(self, session_id: str, candidate: dict) -> None:
        self._create_session_if_necessary(session_id)
        self.sdp_exchange[session_id].answer_candidates.append(candidate)
        candidate_str = candidate.get("candidate", None)
        if candidate_str == '':
            self.sdp_exchange[session_id].has_all_candidates = True

    def set_config(self, session_id: str, config: dict[str, any]):
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
    
    def get_config(self, device_id: str, session_id: str) -> dict | None:
        if current_exchange := self.get_webrtc_session(session_id):
            if current_exchange.webrtc_config:
                return current_exchange.webrtc_config
        
        webrtc_config = self.ipc_manager.api.get(f"/v1.0/devices/{device_id}/webrtc-configs")
        if webrtc_config.get("success"):
            result = webrtc_config.get("result")
            self.set_config(session_id, result)
            return result
        return None
    
    def get_ice_servers(self, device_id: str, session_id: str, format: str) -> None:
        if config := self.get_config(device_id, session_id):
            p2p_config: dict = config.get("p2p_config", {})
            ice_str = p2p_config.get("ices", None)
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
        any_stream_type = 1
        highest_res_stream_type = any_stream_type
        cur_highest = 0
        lowest_res_stream_type = any_stream_type
        cur_lowest = 0
        if webrtc_config := self.get_config(device_id, session_id):
            if skill := webrtc_config.get("skill"):
                try:
                    skill_json: dict = json.loads(skill)
                    video_list: list[dict[str, any]] = skill_json.get("videos")
                    if video_list:
                        for video_details in video_list:
                            if (
                                    "streamType" in video_details
                                and "width" in video_details
                                and "height" in video_details
                            ):
                                any_stream_type = video_details["streamType"]
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
                    return any_stream_type
        return any_stream_type

    def get_sdp_answer(self, device_id: str, session_id: str, sdp_offer: str, channel: str, wait_for_answers: int = 5) -> str | None:
        sleep_step = 0.01
        sleep_count: int = int(wait_for_answers / sleep_step)
        ENDLINE = "\r\n"
        self.set_original_sdp_offer(session_id, sdp_offer)
        if webrtc_config := self.get_config(device_id, session_id):
            auth_token = webrtc_config.get("auth")
            moto_id =  webrtc_config.get("moto_id")
            topic: str = None
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
            for topic in self.ipc_manager.ipc_mq.mq_config.sink_topic.values():
                self.ipc_manager.publish_to_ipc_mqtt(topic, json.dumps(payload))
            return ""
        return None