# Xtend Tuya

Extended Tuya integration for Home Assistant.

## Purpose

This custom integration is there to add the missing entities for the [official Tuya integration](https://www.home-assistant.io/integrations/tuya/).

The reason why this is not merged in the official Tuya integration is that the way this is done is not officially supported by Home Assistant (i.e. this integration is using _hacks_ to do its job).

### Comparison

The following table compares the features of this integration with the official one, as well as the different modes this integration supports.

Legend:

- _OT_: Official Tuya integration
- _OT+XT_: Xtend Tuya **without Tuya cloud credentials** but **alongside the official Tuya integration**
- _OT+XT+Cloud_: Xtend Tuya **with Tuya cloud credentials** but **alongside the official Tuya integration**
- _XT_: Xtend Tuya **without Tuya cloud credentials** and **without the official Tuya integration**
- _XT+Cloud_: Xtend Tuya **with Tuya cloud credentials** and **without the official Tuya integration**

| Functionality                   |         OT         |       OT+XT        |    OT+XT+Cloud     |         XT         |      XT+Cloud      | Remarks                                                                 |
| :------------------------------ | :----------------: | :----------------: | :----------------: | :----------------: | :----------------: | :---------------------------------------------------------------------- |
| Regular Tuya entities           | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |                                                                         |
| Additional supported entities   |        :x:         | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |                                                                         |
| All possible supported entities |        :x:         |        :x:         |        :x:         |        :x:         | :white_check_mark: | _OT+XT+Cloud_ is close but in some rare cases entitites will be missing |
| Autocorrection of some entities |        :x:         |        :x:         |        :x:         |        :x:         | :white_check_mark: | _XT+Cloud_ uses multiple source to determine the entity props           |
| Multiple account support        |        :x:         | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | Only for multiple accounts in _XT_, not the official Tuya integration   |
| Shared device support           |        :x:         |        :x:         | :white_check_mark: |        :x:         | :white_check_mark: |                                                                         |
| Shared home support             | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |                                                                         |
| Localized entity names          | :white_check_mark: |        :x:         |        :x:         |        :x:         |        :x:         | Due to a limitation with custom components                              |

## Installation

Easiest install is via [HACS](https://hacs.xyz/):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=azerty9971&repository=xtend_tuya&category=integration)

1. Click the button above, and install this integration via HACS.
2. Restart Home Assistant.
3. Go to _Settings_ -> _Devices and integrations_ -> _Add integration_ and select **Xtend Tuya**.

## Usage

Once installed, the devices provided by the official Tuya integration should now have the new entities automatically added and they should be supported in the Energy dashboard for instance.

If you have more than one Tuya account, go to the Xtend Tuya integration page (_Settings_ -> _Devices and integrations_ -> _Xtend Tuya_) and click _Add a bridge_. This will pull the next available Tuya account automatically (you can repeat for more).

### Adding your Tuya Cloud credentials

If after adding this integration you still have entities which are missing, you can try inserting your Tuya Cloud credentials (_XT+Cloud_ in the table above). The full procedure is described [here](./docs/cloud_credentials.md).
