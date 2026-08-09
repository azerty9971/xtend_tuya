# Configure locks

## Purpose

The purpose of this documentation is to correctly configure your locks (G30, any
other lock) using the Tuya IOT Cloud platform

## Prerequisite

For this, you will need a functioning Tuya IOT Cloud Platform account. If you
don't have one already please follow the following guide:
<https://github.com/azerty9971/xtend_tuya/blob/main/docs/cloud_credentials.md>

## Steps

1. Log in your Tuya IOT Cloud Platform account (<https://iot.tuya.com/>)
2. Hover on Cloud and select "Cloud Services"\
    ![image](https://github.com/user-attachments/assets/80d90a6a-f337-417c-9c22-6f298799b803)
3. In the list, find the line that says "Smart Lock Open Service" and click the
"Free Trial" link\
    ![image](https://github.com/user-attachments/assets/5d8ae9d2-141e-436f-b459-324663974e91)
4. Select "Continue"\
    ![image](https://github.com/user-attachments/assets/2560d24c-d71c-49d5-9d22-00dc1efbc203)
5. Verify that the "Smart Lock Open Service" is activated:\
    ![image](https://github.com/user-attachments/assets/bfbb2c03-9a96-4ac3-9f7f-63a35cd4a7a6)
6. You should now be able to open/close your locks using Xtend Tuya

## Understanding Locking Mechanisms

If your lock does not work with the default settings, you can manually choose a
locking mechanism in the integration options. Here is how to identify which one
fits your device based on how it behaves in the official Tuya / Smart Life app:

* **Automatic (Auto):**
  * *What it does:* Tells the integration to try all methods automatically.
  * *When to use:* The default option for most locks. Leave it here unless
    your lock is failing to lock/unlock.
* **Door operate API:**
  * *What it does:* Sends a standard lock/unlock command to turn the motor.
  * *When to use:* Use this if your device is a standard deadbolt/lock that you
  can lock and unlock directly by tapping a button on the main screen of the
  Tuya app without any confirmation popups.
* **Door open API:**
  * *What it does:* Tells the lock to open the latch immediately.
  * *When to use:* Use this for simple buzzers, gates, or intercoms that latch
  open instantly when triggered.
* **Ticket flow:**
  * *What it does:* Requests a secure, temporary authorization ticket from Tuya
  first, then uses it to authenticate the unlock request (mimics a secure
  passcode handshake).
  * *When to use:* Use this if your lock requires secure remote verification.
  This is very common for locks that require someone to press the doorbell first
  to "wake it up" and authorize a remote unlock within a short window of time,
  or if the Tuya app asks for a password, fingerprint, or confirmation dialog
  before letting you unlock it remotely.
* **DPCode command:**
  * *What it does:* Bypasses standard lock protocols and sends a raw function
  command (datapoint) directly to the device.
  * *When to use:* Best for custom relays, DIY smart locks, or non-standard
  controllers that behave like a switch rather than an official lock.
