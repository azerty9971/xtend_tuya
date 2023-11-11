# xtend_tuya
HomeAssistant eXtend Tuya's integration

# Purpose
This Custom Integration is there to add the missing entities in Tuya's integration.<br/>
The reason why this is not merged in the main Tuya integration is that the way this is done is not officially supported by HomeAssistant (AKA this integration is using hacks to do its job)

# Installation
Clone the repository and put all the files using SSH to your /root/homeassistant/custom_components folder (final folder will look like: /root/homeassistant/custom_components/xtend_tuya)<br/>
Once this is done, restart your HomeAssistant instance, go to Settings -> Devices and integrations -> Add integration -> type "Tuya" and select Xtended Tuya<br/>
The fields don't have a text because the translations are missing but here is the order (this is all the same as the regular Tuya integration):<br/>
1 - Country<br/>
2 - Tuya IoT access ID<br/>
3 - Tuya IoT access secret<br/>
4 - Tuya account username<br/>
5 - Tuya account password<br/>

# Usage
Once installed, the base devices should have the new entities automatically added and they should be supported in the Energy dashboard for instance
