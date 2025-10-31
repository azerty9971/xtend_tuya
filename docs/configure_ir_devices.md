# Purpose
The purpose of this document is to show how to configure the IR devices in your HA

# Prerequisite
For this, you will need a functionning Tuya IOT Cloud Platform account. If you don't have one already please follow the following guide:
https://github.com/azerty9971/xtend_tuya/blob/main/docs/cloud_credentials.md

# Terms used
IR Hub: The physical device that sends the IR signals
IR Remote: The virtual device that is created under the hub to regroup keys that are to be sent to the receiving device
IR Key: The specific code that should be sent to the receiving device

Think of it like this: the HUB is a pile of remote controls (IR Remote), each remote has multiple buttons (IR Key) 

# Steps to create a new IR Remote
1- Go to the IR HUB device page and click the "Add IR device" button
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/36e33c27-875d-483a-968c-a16600486f8c" />
2- Go to the Integration page, you should see a new discovered device
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/aa4a3c9c-23eb-416c-b910-662074671548" />
3- Click the "Add button" of the newly discovered device and give the name of your new IR Remote
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/d889ee32-0865-4fb4-800c-942828fdc344" />
4- Give the IR remote category (if none apply, select DIY)
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/e6861a88-5b5a-43d9-a0ff-7664d6f47c57" />
5- Depending on the IR remote category, you might be asked to provide a brand for the IR Remote
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/9ffb945f-6bf3-4a6a-8466-d2e56715744d" />
6- Your new device should be created
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/2169d0aa-e50d-4013-beda-0cee0515ad97" />

# Steps to create a new IR Key
1- Go to the IR Remote device and click the "Register new IR key" button
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/92eac037-927a-48a3-88ed-d69e5a964612" />
2- Go to the Integration page, you should see a new discovered device
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/f5fc6059-d510-46fd-958a-112aebafa384" />
3- _(HAVE THE PHYSICAL REMOTE NEXT TO YOU AND THE HUB BEFORE VALIDATING)_ Click the "Add button" of the newly discovered device, you'll be asked for 2 things: The key display name (Friendly name) and the key technical name (usefull for cards that need a specific key name like Universal IR card)
<img width="1289" height="886" alt="image" src="https://github.com/user-attachments/assets/8faef4b3-aafe-4405-8481-054fa9c1f021" />
4- Click the "Submit" button then point the remote to the HUB and click the button you want to register (trick, avoid having any magnet such as phone case next to the IR HUB, it prevents the HUB from receiving the signal...)
<img width="1920" height="963" alt="image" src="https://github.com/user-attachments/assets/d2e3aa49-b48d-4672-9c96-d8c0db74b4b4" />
5- The new key is now available in your IR Remote
<img width="1920" height="963" alt="image" src="https://github.com/user-attachments/assets/741c182a-eaf1-4041-b0ce-b42adb18012b" />
