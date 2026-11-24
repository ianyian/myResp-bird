# Extra sounds (optional)

BirdGuard already has 8 built-in synthetic sound types (raptor screech, owl,
crow caws, distress chirps, siren, noise bursts, bangs, beeps), randomised
on every trigger.

To add real recordings, drop `.wav` files in this folder (e.g. hawk, eagle
or crow distress calls). They are mixed into the random rotation alongside
the built-in sounds, with random pitch/speed/volume applied.

- Format: `.wav` (16-bit PCM is safest). Any sample rate, mono or stereo.
- Use recordings you have the right to use, e.g. CC0 clips from freesound.org.
- To convert an mp3 on your Mac: `afconvert -f WAVE -d LEI16 hawk.mp3 hawk.wav`
- Restart after adding files: `sudo systemctl restart birdguard`
