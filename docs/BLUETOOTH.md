# Using a Bluetooth speaker

A cheap Bluetooth speaker works fine for testing (the proof of concept). The Pi 5 has Bluetooth built in.
You pair the speaker once. After that, BirdGuard reconnects it by itself
before every sound, and checks once a minute that it's still connected.

## Before you start

- **Power:** plug the speaker's charging cable (the small 5V socket) into a
  USB port on the Pi or a phone charger, so the battery never runs flat.
- **Don't** plug the Pi into the speaker's big **USB** socket. That socket
  only plays music files from a USB stick and won't take sound from the Pi.
- Put the speaker in **Bluetooth mode**. On most cheap speakers you press **M**
  until it says "Bluetooth" or a blue light blinks.
- Make sure it isn't connected to your phone. Turn Bluetooth off on your
  phone while pairing.

## 1. Pair it (one time only)

On the Pi (`ssh pi@birdguard.local`), start the Bluetooth tool:

```bash
bluetoothctl
```

The prompt changes to `[bluetooth]#`. Type these one at a time:

```
power on
agent on
default-agent
scan on
```

Wait until a line shows your speaker, for example
`[NEW] Device 41:42:3A:5C:7E:11 BT-SPEAKER`. The `41:42:...` part is the
speaker's **address**. Write it down, then type (using your address):

```
scan off
pair 41:42:3A:5C:7E:11
trust 41:42:3A:5C:7E:11
connect 41:42:3A:5C:7E:11
quit
```

The speaker usually beeps or says "connected".

> Not in the list? Press the speaker's **M** button to switch to Bluetooth mode, or
> hold the play button for about 3 seconds to make it discoverable, then wait 20 seconds.

## 2. Tell BirdGuard to use it

```bash
nano ~/myResp-bird/config.local.yaml
```

Add these lines, using your speaker's address. Indent with spaces, not tabs:

```yaml
deterrents:
  sound:
    bluetooth_mac: "41:42:3A:5C:7E:11"
```

If the file already has a `deterrents:` section, add `bluetooth_mac` under
the existing `sound:` instead of adding a second one. Save with **Ctrl+O, Enter**,
and exit with **Ctrl+X**.

## 3. Test

```bash
sudo systemctl stop birdguard
```

```bash
cd ~/myResp-bird && python3 -m birdguard check
```

```bash
python3 -m birdguard sound-test
```

```bash
sudo systemctl start birdguard
```

`check` should show `[OK ] speaker: Bluetooth 41:42:... connected`, and
`sound-test` should play 10 seconds of sound.

## If the speaker switches itself off

Many cheap speakers turn off after 5–15 minutes of silence. BirdGuard can
play a quiet low tone (you won't hear it) every few minutes to keep it
awake. Add this under `sound:` in `config.local.yaml`:

```yaml
    bluetooth_keepalive_seconds: 240
```

If yours still turns off, it probably has a fixed timer that ignores
audio. In that case, use a USB speaker or a USB sound adapter and a speaker with
an AUX input for the long term (see [HARDWARE.md](HARDWARE.md)).

## Troubleshooting

| Problem | Fix |
|---|---|
| `check` says NOT connected | Make sure the speaker is on and in Bluetooth mode, and not connected to your phone. Then run `bluetoothctl connect <address>`. |
| `aplay: ... bluealsa ... No such device` | The Bluetooth audio service isn't running. Run `sudo apt install -y bluez-alsa-utils`, then `sudo systemctl restart bluealsa`, then reboot. |
| It connects and then disconnects straight away | Remove the pairing and pair again: `bluetoothctl remove <address>`, then repeat step 1. |
| Sound starts a second late | Normal for Bluetooth. Waking a sleeping speaker can take 2–5 seconds. |
| Too quiet | Press the speaker's **+** button a few times. Its own volume is separate from BirdGuard's `volume`. |
