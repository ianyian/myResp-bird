# Hardware & mounting

## What you have

| Part | Notes |
|---|---|
| Raspberry Pi 5 (16GB) | The computer |
| AI HAT+ (Hailo-8, 26 TOPS) | Runs the bird detection |
| Camera Module 3 + Pi 5 camera cable | The Pi 5 has a narrower camera socket: use the cable with one narrow end (Pi side) and one wide end (camera side) |
| Active Cooler | Required: the AI work makes the Pi hot |
| 27W USB-C power supply | Use this one. Phone chargers often can't supply enough power. |
| microSD card + USB reader | For the operating system |

## The speaker

> **Already have a Bluetooth speaker?** That works too. See **[BLUETOOTH.md](BLUETOOTH.md)**.
> It's fine for testing. For a device that runs unattended, a wired USB speaker is more
> reliable, because cheap Bluetooth speakers can switch themselves off or drop the connection.

⚠️ **The Pi 5 has no headphone jack.** Many cheap "USB speakers" only use
USB for *power* and send the sound through a 3.5mm cable. Those **won't work**
on their own. Either option below is fine for the PoC:

**Option A: a true USB audio speaker.** Look for "USB powered **and** USB audio",
"plug and play, no 3.5mm needed" or "USB sound bar for PC". It should have a single USB
cable and no 3.5mm plug.

**Option B (often cheapest and loudest): a USB sound card dongle + any speaker.**
A small "USB to 3.5mm audio adapter" (a few pounds/dollars) plus any powered
speaker with a 3.5mm input, or a battery Bluetooth speaker that has an AUX-in.
This also lets you swap in a bigger speaker later.

Tips:
- Louder is better outdoors. Look for 5W or more.
- Some USB speakers turn themselves off after a few minutes of silence (auto-standby). Avoid those if you can, or test before mounting.
- Check it works with `aplay -l` (it should be listed) and `python3 -m birdguard check`.

## Assembly order (power unplugged)

1. **Active Cooler:** peel the backing off the thermal pads, push the two spring pins through the Pi's holes until they click, and plug the fan cable into the **FAN** connector (next to the USB ports).
2. **Camera cable at the Pi end:** gently lift the black latch of the **CAM/DISP 0** connector, insert the narrow end of the cable with the contacts facing the latch side as shown in the Camera Module manual, then press the latch down. Do the same at the camera end with the wide connector.
3. **AI HAT+:** screw the 4 spacers onto the Pi, push the stacking GPIO header onto the Pi's 40 pins, connect the flat PCIe ribbon from the HAT to the Pi's **PCIe** port (latch up, insert, latch down), lower the HAT onto the header and spacers and screw it down. Route the camera cable out between the boards so it doesn't get pinched.
4. **Speaker:** plug it into a USB port.
5. **SD card**, then the **27W power supply** last.

Follow the leaflets in each box for pictures. If something doesn't fit,
don't force it.

## Mounting under the awning

- **Shelter the electronics.** An awning keeps off most rain, but blown rain and dew still get in. Put the Pi in a small ventilated enclosure (a plastic project box with the cable entry at the bottom), never sealed airtight, because the cooler needs airflow.
- **Avoid direct sun on the box.** Under the awning is ideal. Overheating will slow the Pi down.
- **Camera:** aim it at where birds actually land (railing, gutter, ledge). The closer, the better: a bird should fill at least about 5% of the picture. The phone clamp in your kit is handy for test positioning.
- Avoid pointing the camera straight at the sky or bright sunlight, because birds become dark silhouettes and are harder to detect.
- **Speaker:** point it toward the landing area, outside the enclosure if possible.
- **Power:** use a weather-protected outdoor socket. Keep the USB-C plug and power brick dry.
- **Wi-Fi:** check the signal where it's mounted. The dashboard's *Camera FPS* should stay steady and the live view should be smooth on your home Wi-Fi.

## Being a good neighbour

Ten seconds of loud sound at most every 30 seconds, only 07:00–18:00, is
reasonable, but busy days can add up. Check the "Chased today" counter, and
lower the volume or raise the cooldown if needed.
