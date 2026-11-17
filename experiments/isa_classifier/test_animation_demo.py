import io
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

from classifier import read_recording
from prepare_demo import replace_cues
from select_extra_frames import select


class DemoTests(unittest.TestCase):
    def test_replacing_cues_preserves_pcm_and_removes_previous_metadata(self):
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b'\0\0' * 22050)
        original = buffer.getvalue()
        first = replace_cues(original, [{'start': 0, 'end': 1, 'value': 'X'}])
        second = replace_cues(first, [{'start': 0, 'end': 1, 'value': 'D'}])
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.wav', Path(folder) / 'b.wav'
            a.write_bytes(original)
            b.write_bytes(second)
            self.assertEqual(read_recording(a)[3], read_recording(b)[3])
            self.assertEqual(read_recording(b)[2], [{'start': 0, 'end': 1, 'value': 'D'}])

    def test_truncated_wav_is_rejected(self):
        with self.assertRaises(ValueError):
            replace_cues(b'RIFF\0\0\0\0WAVEdata\xff\xff\0\0', [])

    def test_selection_is_small_spaced_and_limited_per_take(self):
        current = {'pose': np.zeros((1, 2)), 'mouth': np.zeros((1, 2))}
        candidates = [{'take': take, 'frame': frame, 'pose': np.full(2, .01),
                       'mouth': np.full(2, (take * 10 + frame) / 20), 'proposal': 'D'}
                      for take in (2, 3) for frame in (10, 11, 20, 21, 30)]
        chosen = select(candidates, current, {'D': 1}, 4)
        self.assertEqual(len(chosen), 4)
        for take in (2, 3):
            frames = sorted(c['frame'] for c in chosen if c['take'] == take)
            self.assertLessEqual(len(frames), 2)
            self.assertTrue(all(b - a >= 6 for a, b in zip(frames, frames[1:])))

    def test_duplicates_and_incompatible_poses_are_not_added(self):
        current = {'pose': np.zeros((1, 2)), 'mouth': np.zeros((1, 2))}
        candidates = [
            {'take': 2, 'frame': 12, 'pose': np.zeros(2), 'mouth': np.full(2, .001), 'proposal': 'D'},
            {'take': 3, 'frame': 12, 'pose': np.full(2, .3), 'mouth': np.full(2, .5), 'proposal': 'D'},
        ]
        self.assertEqual(select(candidates, current, {'D': 1}, 24), [])


if __name__ == '__main__':
    unittest.main()
