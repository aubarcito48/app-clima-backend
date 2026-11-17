import json
import struct
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .services.own_lip_sync import attach_alignment, detach_alignment, classify_after_synthesis
from .services.voice import synthesize, VoiceUnavailable, _gate
from .test_voice import sample_wav

class OwnLipSyncTests(SimpleTestCase):
    def test_private_alignment_round_trip_preserves_original_audio(self):
        original=sample_wav();info={'phonemes':[],'cues':[]}
        private=attach_alignment(original,info)
        public,decoded=detach_alignment(private)
        self.assertEqual(public,original);self.assertEqual(decoded,info)
        self.assertNotIn(b'isap',public)

    def test_rejects_truncated_duplicate_or_oversized_alignment(self):
        private=attach_alignment(sample_wav(),{'phonemes':[]})
        for data in (sample_wav(),private[:-1],attach_alignment(private,{}),private+b'junk'):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):detach_alignment(data)
        with self.assertRaises(ValueError):attach_alignment(sample_wav(),{'x':'x'*200000})

    @override_settings(ISA_LIP_SYNC='own')
    @patch('api.services.voice.classify_after_synthesis',side_effect=ValueError('invalid model'))
    @patch('api.services.voice.subprocess.run')
    def test_failed_own_model_releases_gate_without_calling_rhubarb(self,run,infer):
        run.return_value.returncode=0;run.return_value.stdout=sample_wav()
        with self.assertRaises(VoiceUnavailable):synthesize('Hello',language='en')
        self.assertFalse(_gate.locked());infer.assert_called_once_with(sample_wav(),'en')
        self.assertIn('--own-lip-sync',run.call_args.args[0])

    @patch('api.services.own_lip_sync.subprocess.run')
    def test_inference_is_separate_bounded_process(self,run):
        run.return_value.returncode=0;run.return_value.stdout=sample_wav()
        self.assertEqual(classify_after_synthesis(sample_wav(),'es'),sample_wav())
        self.assertEqual(run.call_args.kwargs['timeout'],30)
        self.assertIn('api.services.own_lip_sync',run.call_args.args[0])
