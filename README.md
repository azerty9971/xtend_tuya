# xtend_tuya
HomeAssistant eXtend Tuya's integration

# Current status
The custom component is working as expected

# Purpose
This Custom Integration is there to add the missing entities in Tuya's integration.<br/>
The reason why this is not merged in the main Tuya integration is that the way this is done is not officially supported by HomeAssistant (AKA this integration is using hacks to do its job)

# Supported operation modes
This integration supports different operating modes:<br/>
- Regular Tuya integration (RT) (without XT or the cloud)<br/>
- Standalone without cloud credentials (ST) (use XT instead of the regular Tuya integration)<br/>
- Standalone with cloud credentials (ST+Cloud)<br/>
- Alongside Tuya without cloud credentials(TU) (use XT alongside the regular Tuya integration)<br/>
- Alongside Tuya with cloud credentials(TU+Cloud)<br/>
<br/>
The table below shows the different functionnalities of each operating mode<br/>

| Functionnality                  | RT  | ST  | ST+Cloud | TU  | TU+Cloud | Remarks                                                            |
| :------------------------------ | :-: | :-: | :------: | :-: | :------: | :----------------------------------------------------------------- |
| Regular Tuya entities           | X   | X   | X        | X   | X        |                                                                    |
| Additional supported entities   |     | X   | X        | X   | X        |                                                                    |
| All possible supported entities |     |     | X        |     |          | TU+Cloud is close but in some rare cases entitites will be missing |
| Autocorrection of some entities |     |     | X        |     |          | ST + Cloud uses multiple source to determine the entity props      |
| Multiple account support        |     | X   | X        | X   | X        | Only for multiple accounts in XT, not the regular Tuya integration |
| Shared device support           |     |     | X        |     | X        |                                                                    |
| Shared home support             | X   | X   | X        | X   | X        |                                                                    |


# Installation
You have 2 choices to install, either via Home Assistant Community Store (HACS) or using manual install:<br/>
1- HACS (recommended)<br/>
Add the current repository URL to your HACS repositories by going into HACS, click the 3 dots, add custom repository.<br/>
In the screen, fill azerty9971/xtend_tuya as the repository, select integration as type and click add.<br/>
Now you can download xtend_tuya directly from HACS (and get notified when I update it)<br/>
<br/>
2- Manual installation (advanced)<br/>
Clone the repository and put all the files using SSH to your /homeassistant/custom_components folder (final folder will look like: /homeassistant/custom_components/xtend_tuya)<br/>
Once this is done, restart your HomeAssistant instance, go to Settings -> Devices and integrations -> Add integration -> type "Tuya" and select Xtended Tuya<br/>

# Usage
Once installed, the base devices should have the new entities automatically added and they should be supported in the Energy dashboard for instance<br/>
If you have more than 1 tuya account, click go to the Xtended Tuya configuration page (Settings -> Devices and integrations -> Xtended Tuya) and click "Add a bridge", this will pull the next available Tuya configuration available (repeat for more)

# Adding your Tuya Cloud credentials
If you have missing entities, you can try inserting your Tuya Cloud API credentials.<br/>
To do that, go to the Xtended Tuya integration page, next to your account, click the "configure" button.<br/>
You'll be prompted for cloud credentials, for an assistance on how to get these, follow the following tutorial:<br/>
https://www.youtube.com/watch?v=y6kNHIYcJ5c<br/>
Please watch out that the username is the same as the username displayed in the regular Tuya integration<br/>
(the gg-106053160716494114782 in the following screenshot)<br/>
![image](https://github.com/user-attachments/assets/8f8ec9d3-1454-4ef5-8871-61ab4c12de90)

