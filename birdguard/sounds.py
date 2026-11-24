"""Random deterrent sounds.

Every trigger builds a brand-new clip of exactly `duration` seconds by
chaining randomly chosen sound "kinds" (synthetic raptor screech, owl,
crow caws, distress chirps, siren, noise bursts, bangs, beeps and any
.wav files you drop into the sounds/ folder). Each piece also gets a
random pitch, speed and loudness, so birds rarely hear the same thing
twice and are slower to get used to it.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

Generator = Callable[[np.random.Generator, int], np.ndarray]


# --------------------------------------------------------------------------
# small DSP helpers
# --------------------------------------------------------------------------

def _envelope(n: int, sr: int, attack: float = 0.01, release: float = 0.05) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    a = min(n, max(1, int(attack * sr)))
    r = min(n - a, max(1, int(release * sr))) if n > a else 0
    env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    if r > 0:
        env[n - r:] = np.linspace(1, 0, r, dtype=np.float32)
    return env


def _tone(freq: np.ndarray, sr: int, harmonics: list[tuple[int, float]]) -> np.ndarray:
    """Tone following a per-sample frequency curve, with harmonics."""
    phase = 2 * np.pi * np.cumsum(freq) / sr
    out = np.zeros_like(phase)
    for k, amp in harmonics:
        out += amp * np.sin(k * phase)
    return out.astype(np.float32)


def _bandpass(x: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    spec[(freqs < lo) | (freqs > hi)] = 0
    return np.fft.irfft(spec, n=len(x)).astype(np.float32)


def _silence(seconds: float, sr: int) -> np.ndarray:
    return np.zeros(int(seconds * sr), dtype=np.float32)


def _normalize(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    return (x / peak).astype(np.float32) if peak > 0 else x.astype(np.float32)


def resample(x: np.ndarray, factor: float) -> np.ndarray:
    """factor > 1 = higher pitch & shorter, < 1 = lower & longer."""
    n_out = max(1, int(len(x) / factor))
    src = np.linspace(0, len(x) - 1, n_out)
    return np.interp(src, np.arange(len(x)), x).astype(np.float32)


# --------------------------------------------------------------------------
# synthetic sound kinds
# --------------------------------------------------------------------------

def raptor_screech(rng: np.random.Generator, sr: int) -> np.ndarray:
    """Descending, rough screech - loosely like a hawk/falcon call."""
    parts = []
    for _ in range(rng.integers(1, 4)):
        dur = rng.uniform(0.7, 1.5)
        t = np.linspace(0, 1, int(dur * sr))
        f0, f1 = rng.uniform(2800, 3800), rng.uniform(1500, 2300)
        freq = f0 * (f1 / f0) ** t
        vib_rate, vib_depth = rng.uniform(20, 45), rng.uniform(0.03, 0.07)
        freq = freq * (1 + vib_depth * np.sin(2 * np.pi * vib_rate * t * dur))
        x = _tone(freq, sr, [(1, 1.0), (2, 0.6), (3, 0.35), (4, 0.15)])
        x += 0.15 * rng.standard_normal(len(x)).astype(np.float32)
        parts += [x * _envelope(len(x), sr, 0.04, 0.35), _silence(rng.uniform(0.1, 0.4), sr)]
    return np.concatenate(parts)


def owl_hoot(rng: np.random.Generator, sr: int) -> np.ndarray:
    parts = []
    base = rng.uniform(300, 450)
    for _ in range(rng.integers(2, 6)):
        dur = rng.uniform(0.3, 0.7)
        t = np.linspace(0, 1, int(dur * sr))
        freq = base * (1 + 0.08 * np.sin(np.pi * t)) * rng.uniform(0.95, 1.05)
        x = _tone(freq, sr, [(1, 1.0), (2, 0.2), (3, 0.05)])
        parts += [x * _envelope(len(x), sr, 0.08, 0.2), _silence(rng.uniform(0.15, 0.5), sr)]
    return np.concatenate(parts)


def crow_caw(rng: np.random.Generator, sr: int) -> np.ndarray:
    parts = []
    for _ in range(rng.integers(2, 5)):
        dur = rng.uniform(0.25, 0.45)
        t = np.linspace(0, 1, int(dur * sr))
        f0 = rng.uniform(450, 900)
        freq = f0 * (1 - 0.25 * t)
        x = _tone(freq, sr, [(k, 1.0 / k) for k in range(1, 12)])
        rough = 1 + 0.5 * _bandpass(rng.standard_normal(len(x)).astype(np.float32), sr, 30, 120)
        x = x * rough + 0.3 * _bandpass(rng.standard_normal(len(x)).astype(np.float32), sr, 800, 3000)
        parts += [x * _envelope(len(x), sr, 0.02, 0.12), _silence(rng.uniform(0.12, 0.35), sr)]
    return np.concatenate(parts)


def distress_chirps(rng: np.random.Generator, sr: int) -> np.ndarray:
    parts = []
    for _ in range(rng.integers(8, 26)):
        dur = rng.uniform(0.04, 0.12)
        t = np.linspace(0, 1, int(dur * sr))
        f0, f1 = rng.uniform(2000, 7000), rng.uniform(2000, 7000)
        x = _tone(f0 + (f1 - f0) * t, sr, [(1, 1.0), (2, 0.2)])
        parts += [x * _envelope(len(x), sr, 0.005, 0.02), _silence(rng.uniform(0.02, 0.15), sr)]
    return np.concatenate(parts)


def siren(rng: np.random.Generator, sr: int) -> np.ndarray:
    dur = rng.uniform(1.5, 3.0)
    t = np.arange(int(dur * sr)) / sr
    lo, hi = rng.uniform(600, 1500), rng.uniform(1800, 3200)
    rate = rng.uniform(1.0, 4.0)
    lfo = 0.5 * (1 + np.sin(2 * np.pi * rate * t))
    x = _tone(lo + (hi - lo) * lfo, sr, [(1, 1.0), (3, 0.33), (5, 0.2)])
    return x * _envelope(len(x), sr, 0.05, 0.2)


def noise_bursts(rng: np.random.Generator, sr: int) -> np.ndarray:
    parts = []
    lo = rng.uniform(300, 2000)
    hi = lo + rng.uniform(1000, 8000)
    for _ in range(rng.integers(4, 13)):
        n = int(rng.uniform(0.05, 0.3) * sr)
        x = _bandpass(rng.standard_normal(n).astype(np.float32), sr, lo, hi)
        parts += [_normalize(x) * _envelope(n, sr, 0.005, 0.03), _silence(rng.uniform(0.03, 0.25), sr)]
    return np.concatenate(parts)


def bangs(rng: np.random.Generator, sr: int) -> np.ndarray:
    parts = []
    for _ in range(rng.integers(2, 6)):
        n = int(0.4 * sr)
        t = np.arange(n) / sr
        decay = np.exp(-t / rng.uniform(0.04, 0.12))
        crack = rng.standard_normal(n).astype(np.float32) * decay
        thump = np.sin(2 * np.pi * rng.uniform(50, 90) * t) * np.exp(-t / 0.15)
        parts += [(crack + 0.8 * thump).astype(np.float32), _silence(rng.uniform(0.2, 0.8), sr)]
    return np.concatenate(parts)


def beeps(rng: np.random.Generator, sr: int) -> np.ndarray:
    parts = []
    f = rng.uniform(1000, 4000)
    for _ in range(rng.integers(4, 15)):
        n = int(rng.uniform(0.05, 0.15) * sr)
        freq = np.full(n, f * rng.choice([1.0, 1.0, 1.5, 0.75]))
        x = _tone(freq, sr, [(1, 1.0), (3, 0.3)])
        parts += [x * _envelope(n, sr, 0.003, 0.01), _silence(rng.uniform(0.03, 0.12), sr)]
    return np.concatenate(parts)


GENERATORS: dict[str, Generator] = {
    "raptor": raptor_screech,
    "owl": owl_hoot,
    "crow": crow_caw,
    "chirps": distress_chirps,
    "siren": siren,
    "noise": noise_bursts,
    "bangs": bangs,
    "beeps": beeps,
}


# --------------------------------------------------------------------------
# wav library
# --------------------------------------------------------------------------

def read_wav(path: Path, target_sr: int) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    elif width == 4:
        x = np.frombuffer(raw, "<i4").astype(np.float32) / 2147483648
    else:
        raise ValueError(f"unsupported sample width {width} in {path.name}")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != target_sr:
        x = resample(x, sr / target_sr)
    return x.astype(np.float32)


def write_wav(path: Path, x: np.ndarray, sr: int) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------
# composer
# --------------------------------------------------------------------------

class SoundComposer:
    def __init__(
        self,
        duration: float = 10.0,
        sample_rate: int = 44100,
        volume: float = 0.9,
        use_generated: bool = True,
        library_dir: Path | None = None,
        seed: int | None = None,
    ):
        self.duration = duration
        self.sr = sample_rate
        self.volume = max(0.0, min(1.0, volume))
        self.rng = np.random.default_rng(seed)
        self.kinds: dict[str, Callable[[], np.ndarray]] = {}
        if use_generated:
            for name, gen in GENERATORS.items():
                self.kinds[name] = (lambda g=gen: g(self.rng, self.sr))
        if library_dir is not None and library_dir.is_dir():
            for wav in sorted(library_dir.glob("*.wav")):
                try:
                    clip = read_wav(wav, self.sr)
                except Exception as exc:  # bad file shouldn't stop the app
                    log.warning("skipping %s: %s", wav.name, exc)
                    continue
                self.kinds[f"file:{wav.stem}"] = (lambda c=clip: self._random_segment(c))
                log.info("loaded sound file %s (%.1fs)", wav.name, len(clip) / self.sr)
        if not self.kinds:
            raise ValueError("no sounds available: enable use_generated or add .wav files")
        self._last_kind: str | None = None

    def _random_segment(self, clip: np.ndarray) -> np.ndarray:
        max_len = int(self.duration * self.sr)
        if len(clip) <= max_len:
            return clip.copy()
        start = int(self.rng.integers(0, len(clip) - max_len))
        return clip[start:start + int(self.rng.uniform(0.3, 1.0) * max_len)].copy()

    def _pick_kind(self) -> str:
        names = list(self.kinds)
        if len(names) > 1 and self._last_kind in names:
            names.remove(self._last_kind)  # never the same kind twice in a row
        kind = str(self.rng.choice(names))
        self._last_kind = kind
        return kind

    def compose(self) -> tuple[np.ndarray, list[str]]:
        """Returns (mono float32 samples of exactly `duration` s, kinds used)."""
        target = int(self.duration * self.sr)
        pieces: list[np.ndarray] = []
        used: list[str] = []
        total = 0
        while total < target:
            kind = self._pick_kind()
            clip = self.kinds[kind]()
            clip = resample(clip, float(self.rng.uniform(0.85, 1.2)))  # pitch + speed
            clip = _normalize(clip) * float(self.rng.uniform(0.6, 1.0))  # loudness
            gap = _silence(float(self.rng.uniform(0.05, 0.4)), self.sr)
            pieces += [clip, gap]
            used.append(kind)
            total += len(clip) + len(gap)
        out = np.concatenate(pieces)[:target]
        out *= _envelope(len(out), self.sr, 0.01, 0.3)  # smooth start & end
        return (_normalize(out) * self.volume).astype(np.float32), used
