#!/usr/bin/env python3
"""Generate the local nursery-rhyme library with synthesized vocals."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from pydub import AudioSegment

SERVER_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = SERVER_ROOT / "music" / "儿歌"
SAMPLE_RATE = 22050
VOICE_BASE_HZ = 220.0

NOTE_OFFSETS = {
    "C": -9,
    "C#": -8,
    "D": -7,
    "D#": -6,
    "E": -5,
    "F": -4,
    "F#": -3,
    "G": -2,
    "G#": -1,
    "A": 0,
    "A#": 1,
    "B": 2,
}


def note(name: str, beats: float = 1.0) -> tuple[int, float]:
    match = re.fullmatch(r"([A-G]#?)(\d)", name)
    if not match:
        raise ValueError(f"Invalid note: {name}")
    pitch_class, octave = match.groups()
    midi = 12 * (int(octave) + 1) + NOTE_OFFSETS[pitch_class]
    return midi, beats


def line(lyric: str, notes: list[tuple[int, float]]) -> dict:
    chars = re.findall(r"[\u4e00-\u9fff]", lyric)
    if len(chars) != len(notes):
        raise ValueError(f"Lyric and notes differ: {lyric} ({len(chars)} != {len(notes)})")
    return {"lyric": lyric, "chars": chars, "notes": notes}


SONGS = {
    "小星星": {
        "bpm": 100,
        "lines": [
            line("一闪一闪亮晶晶", [note("C4"), note("C4"), note("G4"), note("G4"), note("A4"), note("A4"), note("G4", 2)]),
            line("满天都是小星星", [note("F4"), note("F4"), note("E4"), note("E4"), note("D4"), note("D4"), note("C4", 2)]),
            line("挂在天上放光明", [note("C4"), note("C4"), note("G4"), note("G4"), note("A4"), note("A4"), note("G4", 2)]),
            line("好像许多小眼睛", [note("F4"), note("F4"), note("E4"), note("E4"), note("D4"), note("D4"), note("C4", 2)]),
            line("一闪一闪亮晶晶", [note("C4"), note("C4"), note("G4"), note("G4"), note("A4"), note("A4"), note("G4", 2)]),
            line("满天都是小星星", [note("F4"), note("F4"), note("E4"), note("E4"), note("D4"), note("D4"), note("C4", 2)]),
        ],
    },
    "两只老虎": {
        "bpm": 120,
        "lines": [
            line("两只老虎", [note("C4"), note("D4"), note("E4"), note("C4")]),
            line("两只老虎", [note("C4"), note("D4"), note("E4"), note("C4")]),
            line("跑得快", [note("E4"), note("F4"), note("G4")]),
            line("跑得快", [note("E4"), note("F4"), note("G4")]),
            line("一只没有眼睛", [note("G4"), note("A4"), note("G4"), note("F4"), note("E4"), note("C4")]),
            line("一只没有尾巴", [note("G4"), note("A4"), note("G4"), note("F4"), note("E4"), note("C4")]),
            line("真奇怪", [note("C4"), note("G4"), note("C4")]),
            line("真奇怪", [note("C4"), note("G4"), note("C4", 2)]),
        ],
    },
    "拍拍手": {
        "bpm": 110,
        "lines": [
            line("小手小手拍一拍", [note("C4"), note("D4"), note("E4"), note("G4"), note("E4"), note("D4"), note("C4")]),
            line("大家一起来", [note("E4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("左手右手碰一碰", [note("D4"), note("E4"), note("F4"), note("A4"), note("F4"), note("E4"), note("D4")]),
            line("笑容多可爱", [note("D4"), note("E4"), note("G4"), note("E4"), note("C4")]),
            line("小手小手拍一拍", [note("C4"), note("D4"), note("E4"), note("G4"), note("E4"), note("D4"), note("C4")]),
            line("大家一起来", [note("E4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("左手右手碰一碰", [note("D4"), note("E4"), note("F4"), note("A4"), note("F4"), note("E4"), note("D4")]),
            line("笑容多可爱", [note("D4"), note("E4"), note("G4"), note("E4"), note("C4")]),
            line("大家一起拍拍手", [note("C4"), note("D4"), note("E4"), note("G4"), note("A4"), note("G4"), note("C5", 2)]),
        ],
    },
    "数一数": {
        "bpm": 100,
        "lines": [
            line("一二三四五", [note("C4"), note("D4"), note("E4"), note("G4"), note("G4")]),
            line("五个小积木", [note("A4"), note("G4"), note("E4"), note("D4"), note("C4")]),
            line("六七八九十", [note("E4"), note("F4"), note("G4"), note("A4"), note("A4")]),
            line("十个好朋友", [note("G4"), note("E4"), note("D4"), note("D4"), note("C4")]),
            line("一二三四五", [note("C4"), note("D4"), note("E4"), note("G4"), note("G4")]),
            line("五个小积木", [note("A4"), note("G4"), note("E4"), note("D4"), note("C4")]),
            line("六七八九十", [note("E4"), note("F4"), note("G4"), note("A4"), note("A4")]),
            line("十个好朋友", [note("G4"), note("E4"), note("D4"), note("D4"), note("C4", 2)]),
        ],
    },
    "洗手歌": {
        "bpm": 108,
        "lines": [
            line("小手小手伸出来", [note("C4"), note("E4"), note("G4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("肥皂轻轻搓一搓", [note("D4"), note("F4"), note("A4"), note("A4"), note("G4"), note("F4"), note("D4")]),
            line("手心手背都干净", [note("E4"), note("G4"), note("C5"), note("C5"), note("A4"), note("G4"), note("E4")]),
            line("清水冲一冲", [note("D4"), note("F4"), note("E4"), note("D4"), note("C4")]),
            line("小手小手伸出来", [note("C4"), note("E4"), note("G4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("肥皂轻轻搓一搓", [note("D4"), note("F4"), note("A4"), note("A4"), note("G4"), note("F4"), note("D4")]),
            line("手心手背都干净", [note("E4"), note("G4"), note("C5"), note("C5"), note("A4"), note("G4"), note("E4")]),
            line("清水冲一冲", [note("D4"), note("F4"), note("E4"), note("D4"), note("C4", 2)]),
        ],
    },
    "晚安小月亮": {
        "bpm": 82,
        "lines": [
            line("月亮月亮挂天上", [note("E4"), note("E4"), note("G4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("星星眨眼睛", [note("D4"), note("E4"), note("G4"), note("E4"), note("D4")]),
            line("闭上小眼睛", [note("C4"), note("D4"), note("E4"), note("D4"), note("C4")]),
            line("做一个好梦", [note("E4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("晚安晚安", [note("C4"), note("D4"), note("E4"), note("C4")]),
            line("月亮月亮挂天上", [note("E4"), note("E4"), note("G4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("星星眨眼睛", [note("D4"), note("E4"), note("G4"), note("E4"), note("D4")]),
            line("闭上小眼睛", [note("C4"), note("D4"), note("E4"), note("D4"), note("C4")]),
            line("做一个好梦", [note("E4"), note("G4"), note("A4"), note("G4"), note("E4")]),
            line("晚安", [note("C4", 2), note("C4", 2)]),
        ],
    },
}


def midi_to_hz(midi: int) -> float:
    return 440.0 * (2 ** ((midi - 69) / 12))


def render_unique_vocals(chars: list[str], temp_dir: Path) -> dict[str, Path]:
    json_path = temp_dir / "syllables.json"
    vocals_dir = temp_dir / "vocals"
    json_path.write_text(json.dumps(chars, ensure_ascii=False), encoding="utf-8")
    script = SERVER_ROOT / "scripts" / "render_vocals.ps1"
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-InputJson",
            str(json_path),
            "-OutputDir",
            str(vocals_dir),
        ],
        check=True,
    )
    return {char: vocals_dir / f"{index:03d}.wav" for index, char in enumerate(chars)}


def trim_samples(samples: np.ndarray) -> np.ndarray:
    threshold = max(0.015, float(np.max(np.abs(samples))) * 0.05)
    active = np.flatnonzero(np.abs(samples) > threshold)
    if not len(active):
        return samples
    start = max(0, int(active[0]) - int(SAMPLE_RATE * 0.015))
    end = min(len(samples), int(active[-1]) + int(SAMPLE_RATE * 0.025))
    return samples[start:end]


def load_vocal_samples(path: Path) -> np.ndarray:
    segment = AudioSegment.from_wav(path).set_channels(1)
    samples = np.asarray(segment.get_array_of_samples(), dtype=np.float32)
    if segment.sample_width == 2:
        samples /= 32768.0
    elif segment.sample_width == 4:
        samples /= 2147483648.0
    else:
        samples /= float(1 << (8 * segment.sample_width - 1))
    if segment.frame_rate != SAMPLE_RATE and len(samples):
        target_length = max(1, round(len(samples) * SAMPLE_RATE / segment.frame_rate))
        samples = np.interp(
            np.linspace(0, len(samples) - 1, target_length),
            np.arange(len(samples)),
            samples,
        ).astype(np.float32)
    return trim_samples(samples)


def pitch_shift(samples: np.ndarray, midi: int) -> np.ndarray:
    factor = midi_to_hz(midi) / VOICE_BASE_HZ
    source_positions = np.arange(0, len(samples) - 1, factor)
    shifted = np.interp(source_positions, np.arange(len(samples)), samples)
    return shifted.astype(np.float32)


def fit_duration(samples: np.ndarray, duration_samples: int) -> np.ndarray:
    if len(samples) > duration_samples:
        samples = samples[:duration_samples]
    elif len(samples) < duration_samples:
        samples = np.pad(samples, (0, duration_samples - len(samples)))
    if duration_samples > 1:
        fade = min(int(SAMPLE_RATE * 0.02), duration_samples)
        samples[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
        samples[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return samples


def add_instrumental(mix: np.ndarray, events: list[dict], bpm: float) -> None:
    seconds_per_beat = 60.0 / bpm
    for index, event in enumerate(events):
        start = int(event["start_beat"] * seconds_per_beat * SAMPLE_RATE)
        length = max(1, int(event["beats"] * seconds_per_beat * SAMPLE_RATE))
        end = min(len(mix), start + length)
        if start >= end:
            continue
        t = np.arange(end - start, dtype=np.float32) / SAMPLE_RATE
        freq = midi_to_hz(event["midi"])
        tone = (
            0.55 * np.sin(2 * np.pi * freq * t)
            + 0.22 * np.sin(2 * np.pi * freq * 2 * t)
            + 0.08 * np.sin(2 * np.pi * freq * 3 * t)
        )
        attack = min(len(tone), int(SAMPLE_RATE * 0.015))
        release = min(len(tone), int(SAMPLE_RATE * 0.08))
        envelope = np.ones(len(tone), dtype=np.float32)
        envelope[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
        envelope[-release:] = np.linspace(1.0, 0.0, release, dtype=np.float32)
        mix[start:end] += tone * envelope * 0.19

        if index % 4 == 0:
            bass_freq = freq / 2
            bass = 0.28 * np.sin(2 * np.pi * bass_freq * t)
            mix[start:end] += bass * envelope * 0.08


def add_vocals(
    mix: np.ndarray,
    events: list[dict],
    bpm: float,
    vocal_files: dict[str, Path],
) -> None:
    seconds_per_beat = 60.0 / bpm
    for event in events:
        path = vocal_files.get(event["char"])
        if path is None:
            continue
        samples = load_vocal_samples(path)
        if not len(samples):
            continue
        samples = pitch_shift(samples, event["midi"])
        duration = max(1, int(event["beats"] * seconds_per_beat * SAMPLE_RATE))
        samples = fit_duration(samples, duration)
        start = int(event["start_beat"] * seconds_per_beat * SAMPLE_RATE)
        end = min(len(mix), start + len(samples))
        if start < end:
            mix[start:end] += samples[: end - start] * 0.72


def write_wav(path: Path, samples: np.ndarray) -> None:
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if peak > 0:
        samples = samples / peak * 0.88
    pcm = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the local nursery-rhyme library")
    parser.add_argument("--force", action="store_true", help="overwrite existing WAV files")
    parser.add_argument("--instrumental-only", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    songs_to_render = {
        title: song
        for title, song in SONGS.items()
        if args.force or not (OUTPUT_DIR / f"{title}.wav").exists()
    }
    if not songs_to_render:
        print(f"[OK] nursery-rhyme library already exists: {OUTPUT_DIR}")
        return 0

    all_chars = sorted(
        {
            char
            for song in songs_to_render.values()
            for song_line in song["lines"]
            for char in song_line["chars"]
        }
    )

    with tempfile.TemporaryDirectory(prefix="xiaoyue-rhymes-") as temp_name:
        temp_dir = Path(temp_name)
        vocal_files = {} if args.instrumental_only else render_unique_vocals(all_chars, temp_dir)
        for title, song in songs_to_render.items():
            events = []
            beat = 0.0
            for song_line in song["lines"]:
                for char, (midi, beats) in zip(song_line["chars"], song_line["notes"]):
                    events.append(
                        {
                            "char": char,
                            "midi": midi,
                            "beats": beats,
                            "start_beat": beat,
                        }
                    )
                    beat += beats
            length = math.ceil(beat * 60.0 / song["bpm"] * SAMPLE_RATE)
            mix = np.zeros(length, dtype=np.float32)
            add_instrumental(mix, events, song["bpm"])
            if vocal_files:
                add_vocals(mix, events, song["bpm"], vocal_files)
            output = OUTPUT_DIR / f"{title}.wav"
            write_wav(output, mix)
            print(f"[OK] {output.name}: {length / SAMPLE_RATE:.1f}s")

    print(f"[DONE] nursery-rhyme library: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
