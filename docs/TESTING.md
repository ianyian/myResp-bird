# Testing BirdGuard

You can test in four levels, from "no hardware at all" to "real birds".
Do them in order: each one rules out a class of problems before the next.

## Level 1: Automated tests (Mac or Pi, 2 seconds)

These check the rules exactly, using a fake clock, so no waiting is needed:

```bash
python -m pytest
```

What's covered:
- a bird staying for 2 minutes triggers **exactly 4 times** (0s, 30s, 60s, 90s), never closer than 30s
- the 30s cooldown counts from when the sound **starts** (still locked at 10s, 29.9s; free at 30s)
- single-frame glitches never trigger; 3 of 5 frames are needed
- quiet hours: 06:59 and 18:00 are off, 07:00 and 17:59 are on; no sound outside them
- pause switch and test button behave correctly (the test button also starts the cooldown, so no overlap)
- every sound is exactly 10s long, different each time, and never repeats the same type back-to-back
- the web page and its API respond

## Level 2: Simulation on your Mac (no Pi, no camera)

```bash
python -m birdguard run --simulate --ignore-schedule
```

Open <http://localhost:8080>:

| Try this | Expected |
|---|---|
| Press **Simulate bird** | Bird flies across, red box drawn, sound plays for 10s, event with snapshot appears |
| Press it again straight away | No sound; *Cooldown* counts down from 30 |
| Press it after the cooldown | New sound, different from the last one |
| Press **Pause**, then simulate | No sound |
| Run **without** `--ignore-schedule` after 18:00 | Event logged as *quiet hours*, no sound |

For an unattended "soak test" (e.g. leave it running for an hour), set
this in `config.local.yaml` so a bird appears about every 45 seconds:

```yaml
simulation:
  random_bird_every_seconds: 45
```

Just the sounds:

```bash
python -m birdguard sound-test --count 5
```

```bash
python -m birdguard sound-test --count 5 --save sample.wav
```

## Level 3 (optional): Real AI detection with your Mac webcam

This tests the *detection* itself without the Pi:

```bash
pip install ultralytics opencv-python
```

```bash
python -m birdguard run --backend yolo-cpu --ignore-schedule
```

Hold up a bird photo or video on your phone in front of the webcam. macOS
will ask for camera permission for Terminal the first time; allow it, then
run again.

## Level 4: On the Pi with the real camera

1. Run `python3 -m birdguard check`. All items should show `[OK ]`.
2. Press **Test sound** on the dashboard. You should hear 10s of sound from the USB speaker.
3. **Fake bird:** play a bird video full-screen on your phone or a tablet (search YouTube for "pigeon close up" or "birds for cats to watch") and hold it 0.5–1m in front of the camera. You should see a red `bird 80%` box on the live view, then hear the sound.
4. To test outside 07:00–18:00, run it by hand with the schedule ignored:

```bash
sudo systemctl stop birdguard
```

```bash
cd ~/myResp-bird && python3 -m birdguard run --ignore-schedule
```

   Press Ctrl+C when done, then:

```bash
sudo systemctl start birdguard
```

5. **Remote:** turn off your phone's Wi-Fi and open `http://birdguard:8080` via Tailscale.
6. **Alerts:** with ntfy enabled, the first trigger sends a notification with a snapshot.

## Level 5: Real birds

Leave it running for a few days and look at the event history:
- Many events with no bird in the snapshot → raise `score_threshold` or `confirm_frames`.
- Birds visible on the live view but no red box → lower `score_threshold` or move the camera closer. Small, distant birds are the hardest for the AI.
- Birds come back quickly → add your own `.wav` recordings to `sounds/` for more variety.
