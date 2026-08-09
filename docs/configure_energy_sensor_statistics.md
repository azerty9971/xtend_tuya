# Configure energy sensor statistics

## Purpose

The purpose of this documentation is to correctly configure your energy sensors
using the Tuya IOT Cloud platform

## Prerequisite

For this, you will need a functioning Tuya IOT Cloud Platform account. If you
don't have one already please follow the following guide:
<https://github.com/azerty9971/xtend_tuya/blob/main/docs/cloud_credentials.md>

## Steps

1- Log in your Tuya IOT Cloud Platform account (<https://iot.tuya.com/>)\
(In some countries you need to use this url instead: (<https://platform.tuya.com/>)\
2- Hover on Cloud and select "Cloud Services"\
![image](https://github.com/user-attachments/assets/80d90a6a-f337-417c-9c22-6f298799b803)\
3- In the list, find the line that says "Beta APIs" and click the "Free Trial" link\
![image](https://github.com/user-attachments/assets/40c3f9da-ccd5-4d6a-b8b0-759baa753d47)\
4- Select "Continue"\
![image](https://github.com/user-attachments/assets/4d4ac605-b9fa-4aff-8fad-0669a22a7c9b)\
5- Verify that the "Beta APIs" is activated:\
![image](https://github.com/user-attachments/assets/9f8514a2-35f2-4b1e-84b7-7ae061420ae2)\
6- You should now be able to import energy consumption statistics using Xtend Tuya

## Power and energy values

Smart plugs commonly expose two different kinds of measurements:

- **Power** is the instantaneous load in W. An online plug that is switched off
  should normally report `0 W`. If the plug itself is offline, the power sensor
  is unavailable because there is no current measurement.
- **Consumption/energy** is a cumulative counter in kWh. It does not return to
  zero when the plug is switched off. Home Assistant calculates the energy used
  during a selected period from changes in this counter.

Use a cumulative Consumption or Total energy entity as an individual device in
Home Assistant's Energy dashboard. Do not use the Power entity there.

Xtend Tuya retains the last known cumulative energy value while a device is
offline. This is safe because the value is a total rather than a live
measurement; it also prevents temporary connectivity loss from making the
Energy dashboard statistic unavailable. Instantaneous Power, Current, and
Voltage entities remain unavailable until the device reconnects.

If a switch has no Power, Current, Voltage, Consumption, or Total energy entity,
download its Xtend Tuya device diagnostics and check whether the device exposes
the corresponding datapoints. Many wall switches and inexpensive USB relay
modules do not contain metering hardware, so the integration cannot derive
electricity usage for them.
