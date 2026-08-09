# Cloud credentials

## Purpose

The purpose of this documentation is to be able to configure the Tuya IOT
Platform cloud credentials in Xtend Tuya.

## READ THIS CAREFULLY

Some initial configurations have to be done right the first time, this is
because they are a pain to update afterward if you got them wrong.
To be prepared, please determine your correct data center:

- If in Europe: Central Europe Data Center
- If in US: Western America Data Center
- If in China: China Data Center
- If in India: India Data Center

DO NOT USE THE WESTERN EUROPE OR EASTERN AMERICA DATA CENTERS, THEY ARE RESERVED
FOR BUSINESS CONSUMERS\

## Steps

1- Create your Tuya IOT Platform account\
1.1- Go to <https://iot.tuya.com/>\
1.2- Create your account\
1.3- Login to your newly created account

2- Create a development project\
2.1- On the left, hover over Cloud then select Project Management:\
![image](https://github.com/user-attachments/assets/8c62729b-2dc0-4b12-aadc-cb4c0b00b35a)\
2.2- Click "Create Cloud Project"\
2.3- Give any relevant name and description to your project\
2.4- Set "Smart home" in both "Industry" and "Development Method"\
2.5- Set the correct data center (Refer to the notes at the beginning of the
development to do so, this is very important!)\
![image](https://github.com/user-attachments/assets/0459d8c2-a559-4665-b789-2f01b244c798)\
2.6- Click "Create"\
2.7- In the next screen, click "Authorize"\
![image](https://github.com/user-attachments/assets/8908079f-13f1-4231-9af7-3def0633ef8a)

3- Link you Tuya/SmartLife app to your cloud account\
3.1- On the left, hover over Cloud then select Project Management:\
![image](https://github.com/user-attachments/assets/8c62729b-2dc0-4b12-aadc-cb4c0b00b35a)\
3.2- Open your cloud project created in step 2 by clicking the "Open Project" link\
![image](https://github.com/user-attachments/assets/9d3abb65-392b-435a-a5cb-14afa15b4bba)\
3.3- Go to the "Devices" tab\
![image](https://github.com/user-attachments/assets/e34bb6e7-e525-4532-a150-3d977f69df4e)\
3.4- Click the "Link App Account"\
![image](https://github.com/user-attachments/assets/a6cf3c6f-2aea-4d55-a4ea-1bfa98b9aba9)\
3.5- Click the "Add App Account"\
![image](https://github.com/user-attachments/assets/ea2155ce-8d72-41fb-aaec-c0bf1019ee2f)\
3.6- Open your Tuya/SmartLife app, go to the "Profile" and use the Scan Barcode
button on the top right\
3.7- Scan the QR code generated in step 3.5 with your smartphone and approve the
connection\
3.8- In the next screen, select "Automatic Link" and click OK\
![image](https://github.com/user-attachments/assets/955971f3-d0f3-4112-adf6-f70150fc4bc4)\
3.9- In the end, you should have something that looks like this:\
![image](https://github.com/user-attachments/assets/e75c5da8-4523-40f9-98d6-3b1f97b0c1fa)

4- Gather the information needed by XT Tuya\
4.1- In the screen of 3.9, copy the value under the column "App Account" in a notepad\
![image](https://github.com/user-attachments/assets/43c8de07-890d-4b31-992a-c6b11d39d32f)\
4.2- Go to the Overview tab and copy the values of Client ID and Client Secret
in a notepad\
![image](https://github.com/user-attachments/assets/20146f3b-36dd-43af-b283-c3e6d99f47cc)

5- Enter your credentials in eXtend Tuya\
5.1- Go to the Settings page in HA\
![image](https://github.com/user-attachments/assets/57ac6999-742b-4622-9ad2-7a9670ebd1f7)\
5.2- Go to "Device & services"\
![image](https://github.com/user-attachments/assets/aa3a20aa-ae0a-4341-9d9a-4ffed4e0c7a1)\
5.3- Click on "Xtend Tuya"\
![image](https://github.com/user-attachments/assets/462d302a-7154-4fc3-ada9-e766aa0b5d4b)\
5.4- Click on the "Configure" button next to the account you want to configure\
![image](https://github.com/user-attachments/assets/be1e0eec-3743-4f7c-8497-eabbd2992fcb)\
5.5- In the popup, enter the following information

- Country is the country you are in
- Tuya IoT Access ID is the Client ID you retrieved in step 4.2
- Tuya IoT Access Secret is the Client Secret you retrieved in step 4.2
- SmartLife/Tuya account is the App Account you retrieved in step 4.1
- SmartLife/Tuya account password is the password you use when logging in the
SmartLife/Tuya app on your smartphone\
![image](https://github.com/user-attachments/assets/da4fb3d8-8fb5-4cf1-8ab2-d8a54c0bced0)\
5.6- Click Submit, if everything went correctly you should have a success message\
![image](https://github.com/user-attachments/assets/21c042a9-025b-4a52-9f31-bc3e30d2ba26)\
5.7- Restart your Home Assistant and enjoy!
