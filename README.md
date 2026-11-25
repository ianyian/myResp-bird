# 🐦 BirdGuard

A Raspberry Pi 5 + AI HAT+ + Camera Module 3 that spots birds and plays a
**random** scary sound to send them away. You can watch it from your
phone anywhere, and it sends you alerts.

**How it behaves**

| Rule | Default |
|---|---|
| A bird must be seen in 3 of 5 frames in a row (fewer false alarms) | `trigger.confirm_frames` |
| Each sound lasts **10 seconds** and is **different every time** | `deterrents.sound` |
| After a sound **starts**, nothing can re-trigger for **30 seconds** (no overlaps) | `trigger.cooldown_seconds` |
| Active **07:00–18:00** only. Outside these hours birds are logged but no sound plays | `schedule` |
| Live view, history with snapshots, test button and pause switch on your phone | web dashboard, port 8080 |
| Phone push alerts (max 1 every 5 min) | ntfy |

Guides: **[Testing](docs/TESTING.md)** · **[Hardware & mounting](docs/HARDWARE.md)** · **[Bluetooth speaker](docs/BLUETOOTH.md)**

---

## Contents
1. [Try it on your Mac first (no Pi needed)](#1-try-it-on-your-mac-first)
2. [Assemble the hardware](#2-assemble-the-hardware)
3. [Prepare the SD card on your Mac](#3-prepare-the-sd-card-on-your-mac)
4. [First boot and connecting from your Mac](#4-first-boot-and-connecting-from-your-mac)
5. [Install BirdGuard on the Pi](#5-install-birdguard-on-the-pi)
6. [Watch from your phone anywhere (Tailscale)](#6-watch-from-your-phone-anywhere-tailscale)
7. [Phone alerts (ntfy)](#7-phone-alerts-ntfy)
8. [Everyday commands](#8-everyday-commands)
9. [Troubleshooting](#9-troubleshooting)
10. [Adding accessories later](#10-adding-accessories-later)

---

## 1. Try it on your Mac first

This takes about 5 minutes and lets you see the whole thing working before
you touch the Pi. Open **Terminal** (Cmd+Space, type "Terminal"):

```bash
git clone https://github.com/ianyian/myResp-bird.git
cd myResp-bird
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

> If macOS asks to install "command line developer tools", click Install, then run the commands again.


Hear what the random sounds are like (it plays 3 different ones through your Mac speakers):

```bash
python -m birdguard sound-test --count 3
```

Run the whole program with a fake camera:

```bash
python -m birdguard run --simulate --ignore-schedule
```

Open **http://localhost:8080** in your browser and press **🐦 Simulate bird**.
A bird flies across, the sound plays, and an event with a snapshot appears.
Press it again within 30 seconds and nothing happens (that's the cooldown).
Press **Ctrl+C** in Terminal to stop.

## 2. Assemble the hardware

See **[docs/HARDWARE.md](docs/HARDWARE.md)** for the full version (and which speaker to buy). In short, **with the power unplugged**:

1. Stick the **Active Cooler** onto the Pi and plug its small fan cable into the **FAN** socket.
2. Connect the **camera cable** to the Pi's **CAM/DISP 0** port (lift the latch, insert, press the latch down).
3. Fit the **AI HAT+**: push the tall GPIO header onto the Pi's pins, attach the flat PCIe ribbon to the Pi's PCIe port, and screw the HAT down on the spacers. Feed the camera cable out past the HAT.
4. Plug the **USB speaker** into a USB port. Using a **Bluetooth speaker** instead? Pair it after installing, using [docs/BLUETOOTH.md](docs/BLUETOOTH.md).
5. Put the SD card in after step 3 of the next section.

## 3. Prepare the SD card on your Mac

1. Put the microSD card in the purple USB card reader and plug it into your Mac (use a USB-C adapter if needed).
2. Install **Raspberry Pi Imager** from <https://www.raspberrypi.com/software/> and open it.
3. Choose:
   - **Device:** Raspberry Pi 5
   - **OS:** **Raspberry Pi OS (64-bit)**, the version with a desktop. You can then use the Pi's
     desktop remotely from your Mac or phone (section 4b), which is handy for settings and Bluetooth.
     *(Prefer no desktop? Choose Raspberry Pi OS (other) → Lite (64-bit). BirdGuard works on both.)*
   - **Storage:** your SD card
4. When asked about **OS customisation**, click **Edit settings**:
   - **Hostname:** `birdguard`
   - **Username / password:** choose your own (e.g. `pi` and a strong password). Write them down.
   - **Wireless LAN:** your home Wi-Fi name and password, country = where you live
   - **Locale:** your **time zone** ⚠️ this matters, because quiet hours use the Pi's clock
   - **Services** tab: tick **Enable SSH** → *Use password authentication*
5. Save → Yes → wait for it to write and verify. Eject the card and put it in the Pi.

> Your Pi joins your home Wi-Fi automatically on first boot. To change Wi-Fi later:
> `sudo nmtui` on the Pi.

## 4. First boot and connecting from your Mac

1. Plug in the **27W USB-C power supply**. Wait about 2 minutes (the first boot is slow).
2. On your Mac, in Terminal (use your username):

```bash
ssh pi@birdguard.local
```

Type `yes` the first time, then your password. You're now typing commands **on the Pi**.

> `birdguard.local` not found? Wait another minute, make sure your Mac is on the same Wi-Fi, or find the Pi's IP address in your router's app and use `ssh pi@192.168.x.x`.

Update the Pi once:

```bash
sudo apt update && sudo apt full-upgrade -y
```

## 4b. Remote desktop (optional, desktop version only)

You don't need a screen, keyboard or mouse: you can see and use the Pi's desktop
from your Mac or phone. Pick one:

**Raspberry Pi Connect** (easiest, works from anywhere, free). On the Pi via SSH:

```bash
rpi-connect on
```

```bash
rpi-connect signin
```

Open the link it prints, sign in or create a free Raspberry Pi ID, and give
the device a name. Then go to <https://connect.raspberrypi.com> on your Mac or phone,
open your Pi, and choose **Screen sharing**.

**VNC** (home Wi-Fi, or anywhere through Tailscale). On the Pi:

```bash
sudo raspi-config nonint do_vnc 0
```

Install **RealVNC Viewer** on your Mac (free), connect to `birdguard.local`, and log in
with your Pi username and password. If the screen looks tiny, set a bigger size with
`sudo raspi-config` → *Display Options* → *VNC Resolution*, then reboot.

## 5. Install BirdGuard on the Pi

On the Pi, download the code and install it:

```bash
sudo apt install -y git
```

```bash
git clone https://github.com/ianyian/myResp-bird.git ~/myResp-bird
```

```bash
cd ~/myResp-bird && ./install.sh
```

> If you ever make the repo private again, the Pi needs a read-only "deploy key":
> run `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""` and `cat ~/.ssh/id_ed25519.pub`,
> add the printed line on GitHub under **Settings → Deploy keys**, then run
> `git -C ~/myResp-bird remote set-url origin git@github.com:ianyian/myResp-bird.git`.

The first time, it will tell you to reboot (to load the AI HAT driver):

```bash
sudo reboot
```

Reconnect (`ssh pi@birdguard.local`) and check everything:

```bash
cd ~/myResp-bird && python3 -m birdguard check
```

You want `[OK ]` for **speaker, AI model, camera and AI HAT**. BirdGuard now
starts automatically every time the Pi powers on.

Open **http://birdguard.local:8080** on your Mac or phone (while on home Wi-Fi).

## 6. Watch from your phone anywhere (Tailscale)

Tailscale is free for personal use. It creates a private, encrypted link
between your phone and the Pi, so you don't need to change any router
settings and the Pi is never exposed to the internet.

1. Create an account at <https://tailscale.com> (sign in with Google/Apple is fine).
2. On the Pi:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

```bash
sudo tailscale up
```

   Open the link it prints (on your Mac or phone) and log in. The Pi is now on your Tailscale network.
3. On your phone, install the **Tailscale** app, log in with the same account and switch it on.
4. Turn off Wi-Fi on your phone (to test over mobile data) and open **http://birdguard:8080**.
   If that name doesn't work, use the Pi's Tailscale address shown in the app (`http://100.x.y.z:8080`).

> Tip: add the page to your phone's home screen (Share → *Add to Home Screen*) to use it like an app.
> The live view is resized to save mobile data (`web.stream_width` / `web.stream_fps`).

## 7. Phone alerts (ntfy)

1. Install the **ntfy** app on your phone (App Store / Google Play).
2. In the app, tap **+** and subscribe to a topic with a long random name, e.g. `birdguard-k7p2x9q4m1`. Anyone who knows the name can read it, so keep it secret.
3. On the Pi:

```bash
nano ~/myResp-bird/config.local.yaml
```

   Set `enabled: true` and `topic:` to the same name. Save with **Ctrl+O, Enter**, exit with **Ctrl+X**.
4. Test and apply:

```bash
cd ~/myResp-bird && python3 -m birdguard check
```

```bash
sudo systemctl restart birdguard
```

You get at most one alert every 5 minutes (`min_interval_seconds`), with a snapshot attached.

## 8. Everyday commands

Run these on the Pi (after `ssh pi@birdguard.local`):

| What | Command |
|---|---|
| Is it running? | `systemctl status birdguard` |
| Live log (Ctrl+C to exit) | `journalctl -u birdguard -f` |
| Restart (after changing settings) | `sudo systemctl restart birdguard` |
| Stop / start | `sudo systemctl stop birdguard` / `sudo systemctl start birdguard` |
| Play a test sound | `sudo systemctl stop birdguard && python3 -m birdguard sound-test; sudo systemctl start birdguard` |
| Health check | `cd ~/myResp-bird && python3 -m birdguard check` |
| Update to the latest code | `cd ~/myResp-bird && git pull && sudo systemctl restart birdguard` |
| Change settings | `nano ~/myResp-bird/config.local.yaml` then restart |
| Shut down safely before unplugging | `sudo shutdown now` |

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `check` says **speaker FAIL** (Bluetooth) | See [docs/BLUETOOTH.md](docs/BLUETOOTH.md#troubleshooting) |
| `check` says **speaker FAIL** (USB) | Plug the USB speaker in, then run `aplay -l` to see whether it's listed. Many cheap speakers only take *power* over USB and need a 3.5mm jack, which the Pi 5 doesn't have. See [HARDWARE.md](docs/HARDWARE.md). |
| Sound is too quiet | Turn the speaker's own knob up, run `alsamixer` (F6 to pick the USB card, arrow up for volume) and set `volume: 1.0` |
| **camera FAIL** | Power off, reseat the ribbon cable at both ends (contacts facing the right way, latch closed) |
| **AI HAT FAIL** | Reseat the PCIe ribbon, check `sudo apt install hailo-all`, then reboot |
| Picture upside down | Set `detector: vflip: true` and `hflip: true` in `config.local.yaml` |
| False alarms (leaves, etc.) | Raise `score_threshold` to 0.55–0.6 or `confirm_frames` to 4 |
| Birds missed | Lower `score_threshold` to 0.35 and move the camera closer to where birds land |
| Nothing happens at all | Check the **Mode** on the dashboard (quiet hours? paused?) and that the Pi's clock/time zone is right: `timedatectl` |
| Can't reach the dashboard from outside | Make sure the Tailscale app is ON on your phone and run `tailscale status` on the Pi |

## 10. Adding accessories later

Each scaring device is a separate add-on (a "deterrent"). The camera and AI
just announce "bird!", and every enabled deterrent reacts. To add, say, a
light or a sprinkler on a relay:

- The built-in **`gpio_output`** deterrent already switches a GPIO pin on for N seconds. Wire a relay module to it and enable it in `config.local.yaml`:

  ```yaml
  deterrents:
    gpio_output:
      enabled: true
      pin: 17
      seconds: 10
  ```

- For something more complex, add a class in `birdguard/deterrents/` and register it in `birdguard/deterrents/__init__.py`.

> ⚠️ **About lasers:** a laser pointed outdoors can hurt eyes (people, pets,
> neighbours) and dazzle pilots. In many countries that's a criminal offence.
> A water sprinkler or bright strobe works well, and is the safer choice.

---

## Project layout

```
birdguard/
  __main__.py      command line: run / sound-test / check
  app.py           main loop: detect -> decide -> deterrents -> log/alert
  trigger.py       confirmation, 30 s cooldown, active hours
  sounds.py        random sound generator (8 types + your .wav files)
  audio.py         playback (aplay on Pi, afplay on Mac)
  detectors/       hailo (Pi), simulated (testing), yolo_cpu (Mac webcam)
  deterrents/      sound, gpio_output (+ future accessories)
  web.py           phone dashboard
  notify.py        ntfy push alerts
  events.py        history + snapshots in data/
config.yaml        all settings (override in config.local.yaml)
install.sh         Pi installer + auto-start service
tests/             automated tests (python -m pytest)
```
