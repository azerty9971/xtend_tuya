# Xtend Tuya

Extended Tuya integration for Home Assistant.

## Purpose

This custom integration is there to add the missing entities on the [official Tuya integration](https://www.home-assistant.io/integrations/tuya/).

The reason why this is not merged in the official Tuya integration is because the way this is done is not officially supported by Home Assistant core team (i.e. this integration uses _hacks_ to do its job).

### Highlights

- Adds entities needed by the Energy dashboard
- Adds support for locks (requires [additional configuration](./docs/configure_locks.md))
- Much more...

### Comparison

The following table compares the features of this integration with the official one, as well as the different modes this integration supports. Legend:

- **_OT_**: Official Tuya integration
- **_OT+XT_**: Xtend Tuya **WITHOUT** Tuya cloud credentials and **ALONGSIDE** the official Tuya integration
- **_OT+XT+Cloud_**: Xtend Tuya **WITH** Tuya cloud credentials and **ALONGSIDE** the official Tuya integration
- **_XT_**: Xtend Tuya **WITHOUT** Tuya cloud credentials and **WITHOUT** the official Tuya integration
- **_XT+Cloud_**: Xtend Tuya **WITH** Tuya cloud credentials and **WITHOUT** the official Tuya integration

| Functionality                      |         OT         |       OT+XT        |    OT+XT+Cloud     |         XT         |      XT+Cloud      | Remarks                                                                                                   |
| :--------------------------------- | :----------------: | :----------------: | :----------------: | :----------------: | :----------------: | :-------------------------------------------------------------------------------------------------------- |
| official Tuya integration entities | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |                                                                                                           |
| Additional entities support        |        :x:         | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |                                                                                                           |
| All possible entities support      |        :x:         |        :x:         |        :x:         |        :x:         | :white_check_mark: | _OT+XT+Cloud_ is close but in some rare cases entities will be missing                                    |
| Autocorrection of some entities    |        :x:         |        :x:         |        :x:         |        :x:         | :white_check_mark: | _XT+Cloud_ uses multiple sources to determine the entity properties                                       |
| Multiple account support           |        :x:         | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | When using _OT+XT_, multiple accounts are only supported in Xtend Tuya, not the official Tuya integration |
| Shared device support              |        :x:         |        :x:         | :white_check_mark: |        :x:         | :white_check_mark: |                                                                                                           |
| Shared home support                | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |                                                                                                           |
| Localized entity names             | :white_check_mark: |        :x:         |        :x:         |        :x:         |        :x:         | Due to a limitation with custom components                                                                |

## Installation

Easiest install is via [HACS](https://hacs.xyz/):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=azerty9971&repository=xtend_tuya&category=integration)

1. Click the button above, and install this integration via HACS.
2. Restart Home Assistant.
3. Go to _Settings_ -> _Devices and integrations_ -> _Add integration_ and select **Xtend Tuya**.

## Usage

You can choose to use this integration alongside the official Tuya integration or not. The choice is yours, but using it **without** the official Tuya integration will give you some perks (see comparison table above).

When installed **without** the official Tuya integration, this integration will **provide all the devices and entities** by itself.

When installed **alongside** the official Tuya integration, this integration will **add the missing entities** to the existing devices provided by the official Tuya integration.

## Multiple accounts

If you have more than one Tuya account, go to the Xtend Tuya integration page (_Settings_ -> _Devices and integrations_ -> _Xtend Tuya_) and click _Add hub_. This will prompt for your new account, or it will automatically pull the next account from the official Tuya integration (you can repeat for more).

## Still missing entities?

If after adding this integration you still have entities which are missing, you can try inserting your Tuya Cloud credentials (_XT+Cloud_ in the table above). The full procedure is described [here](./docs/cloud_credentials.md).

After that, if you are still missing some entities, you can perform the [following procedure](./docs/enable_all_dpcodes.md)

## Want to discuss?

Feel free to come and say hi on the [Discord server](https://discord.gg/3EgfG5sZ4Y)
