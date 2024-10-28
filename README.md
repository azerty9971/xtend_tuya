# Xtend Tuya

Extended Tuya integration for Home Assistant.

## Purpose

This custom integration is there to add the missing entities for [Tuya's official integration](https://www.home-assistant.io/integrations/tuya/).

The reason why this is not merged in the official Tuya integration is that the way this is done is not officially supported by Home Assistant (i.e. this integration is using _hacks_ to do its job).

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

If after adding this integration you still have entities which are missing, you can try inserting your Tuya Cloud credentials. The full procedure is described [here](./docs/cloud_credentials.md).

### Supported operation modes

This integration supports different operating modes:

- Regular Tuya integration (RT) (without XT or the cloud)
- Standalone without cloud credentials (ST) (use XT instead of the regular Tuya integration)
- Standalone with cloud credentials (ST+Cloud)
- Alongside Tuya without cloud credentials (TU) (use XT alongside the regular Tuya integration)
- Alongside Tuya with cloud credentials (TU+Cloud)

The table below shows the different functionalities of each operating mode:

| Functionnality                  | RT  | ST  | ST+Cloud | TU  | TU+Cloud | Remarks                                                            |
| :------------------------------ | :-: | :-: | :------: | :-: | :------: | :----------------------------------------------------------------- |
| Regular Tuya entities           |  X  |  X  |    X     |  X  |    X     |                                                                    |
| Additional supported entities   |     |  X  |    X     |  X  |    X     |                                                                    |
| All possible supported entities |     |     |    X     |     |          | TU+Cloud is close but in some rare cases entitites will be missing |
| Autocorrection of some entities |     |     |    X     |     |          | ST+Cloud uses multiple source to determine the entity props        |
| Multiple account support        |     |  X  |    X     |  X  |    X     | Only for multiple accounts in XT, not the regular Tuya integration |
| Shared device support           |     |     |    X     |     |    X     |                                                                    |
| Shared home support             |  X  |  X  |    X     |  X  |    X     |                                                                    |
| Localized entity names          |  X  |     |          |     |          | Due to a limitation with custom components                         |
