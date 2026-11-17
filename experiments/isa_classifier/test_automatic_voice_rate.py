import unittest
from automatic_voice_rate import rate_plan


class AutomaticRateTests(unittest.TestCase):
    def timing(self, language, wps):
        return {'language': language, 'segments': [
            {'role': role, 'words_per_second': wps, 'text': role}
            for role in ('greeting', 'advice', 'farewell')]}

    def test_fast_advice_only_and_language_specific_bounds(self):
        for language, lower in [('es', .94), ('en', .90)]:
            factors, _ = rate_plan(self.timing(language, 5))
            self.assertEqual(factors, [1, lower, 1])
    def test_slow_advice_is_never_sped_up(self):
        self.assertEqual(rate_plan(self.timing('en', 2))[0], [1, 1, 1])
    def test_nonfinite_measurements_rejected(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                rate_plan(self.timing('en', value))
