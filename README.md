# xtend_tuya
HomeAssistant eXtend Tuya's integration

# Current status
The custom component is working as expected

# Purpose
This Custom Integration is there to add the missing entities in Tuya's integration.<br/>
The reason why this is not merged in the main Tuya integration is that the way this is done is not officially supported by HomeAssistant (AKA this integration is using hacks to do its job)

# Installation
Clone the repository and put all the files using SSH to your /homeassistant/custom_components folder (final folder will look like: /homeassistant/custom_components/xtend_tuya)<br/>
Once this is done, restart your HomeAssistant instance, go to Settings -> Devices and integrations -> Add integration -> type "Tuya" and select Xtended Tuya<br/>

# Usage
Once installed, the base devices should have the new entities automatically added and they should be supported in the Energy dashboard for instance<br/>
If you have more than 1 tuya account, click go to the Xtended Tuya configuration page (Settings -> Devices and integrations -> Xtended Tuya) and click "Add a bridge", this will pull the next available Tuya configuration available (repeat for more)
