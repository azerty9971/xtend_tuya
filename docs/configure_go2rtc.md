# Purpose
The purpose of this documentation is to correctly configure go2rtc to communicate with your Tuya cameras using WebRTC

# Prerequisite
For this, you will need a functionning Tuya IOT Cloud Platform account.<br/>
If you don't have one already please follow the following guide:
https://github.com/azerty9971/xtend_tuya/blob/main/docs/cloud_credentials.md<br/>
You will also need to have a properly configured Tuya IOT Cloud Platform.<br/>
Please follow the procedure of https://github.com/azerty9971/xtend_tuya/blob/main/docs/enable_webrtc.md<br/>
<br/>
# Steps
1- Configure a long-lived access token<br/>
1.1- In your user profile, click the "security" tab and scroll down at the bottom to click the "Create token" button<br/>
![image](https://github.com/user-attachments/assets/a03f3c61-a27d-4f1f-9c03-d6a9a2063936)<br/>
1.2- Store the newly created token into a notepad<br/><br/>
2- Get the device ID of your camera<br/>
2.1- Find your device in Home Assistant and click the "Download diagnostic" button<br/>
![image](https://github.com/user-attachments/assets/aecbed92-1006-403b-a993-b3472e64f619)<br/>
2.2- Open the downloaded file and search for the key "id" of the subnode "data"<br/>
![image](https://github.com/user-attachments/assets/5527b163-c469-40d7-883a-4a60eafb8b18)<br/>
2.3- Store this device ID in a notepad<br/><br/>
3- Configure go2rtc<br/>
3.1- Add the following lines to your go2rtc configuration:<br/>
```
camera_name:
  - webrtc:https://<HA_URL>#format=xtend_tuya#device_id=<DEVICE_ID>#channel=high#auth_token=<AUTH_TOKEN>
```
Replace <HA_URL> by the URL of your home assistant (eg: 192.168.1.12:8123)<br/>
Replace <DEVICE_ID> by the device ID found in step 2<br/>
Replace <AUTH_TOKEN> by the long-lived access token found in step 1<br/><br/>
4- Restart go2rtc and enjoy!
