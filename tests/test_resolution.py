"""Translated reminder content/cache behavior using disposable fixtures."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import database
import tts
from app import app

EXPECTED = {
    'en': "It's time to take your {name}.",
    'hi': 'आपकी दवा {name} लेने का समय हो गया है।',
    'ta': 'உங்கள் {name} மருந்தை எடுத்துக்கொள்ள வேண்டிய நேரம் இது.',
    'te': 'మీ {name} మందు తీసుకునే సమయం అయింది.',
    'kn': 'ನಿಮ್ಮ {name} ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳುವ ಸಮಯವಾಗಿದೆ.',
    'bn': 'আপনার {name} ওষুধ খাওয়ার সময় হয়েছে।',
}

class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_audio = database.DB_PATH, tts.AUDIO_DIR
        database.DB_PATH = str(Path(self.tmp.name)/'resolution.db')
        tts.AUDIO_DIR = str(Path(self.tmp.name)/'audio')
        database.init_db()
        self.owner = database.create_user('resolution_owner', 'dummy-password', 'Dummy')
        self.other = database.create_user('resolution_other', 'dummy-password', 'Other dummy')
        self.client = app.test_client()
        with self.client.session_transaction() as s: s['user_id'] = self.owner['id']

    def tearDown(self):
        database.DB_PATH, tts.AUDIO_DIR = self.old_db, self.old_audio
        self.tmp.cleanup()

    def due(self, name='Pending A', owner=None, language='en'):
        gid = database.add_medicine(owner or self.owner['id'], name, ['08:00'], 3, language)
        mid = database.get_group(gid)[0]['id']; database.mark_fired(mid, None)
        return mid





    def test_translated_text_preserves_opaque_unicode_name(self):
        name = 'Review {A} / 盐 नाम 10 mg'
        self.assertEqual({code for code,_ in tts.LANGUAGES},set(EXPECTED))
        for lang, template in EXPECTED.items():
            with self.subTest(language=lang): self.assertEqual(tts.build_reminder_text(name,lang),template.format(name=name))

    def test_six_synthesis_calls_use_translated_text_and_matching_language(self):
        name = 'Review dummy'
        class Speech:
            def save(self,path): Path(path).write_bytes(b'unit-provider-fixture')
        with patch('tts.gTTS',side_effect=lambda **kwargs: Speech()) as synth:
            for lang,template in EXPECTED.items():
                relative=tts.get_or_create_audio(name,lang)
                self.assertTrue((Path(tts.AUDIO_DIR)/Path(relative).name).is_file())
                self.assertEqual(synth.call_args.kwargs['text'],template.format(name=name))
                self.assertEqual(synth.call_args.kwargs['lang'],lang)
        self.assertEqual(synth.call_count,6)

    def test_legacy_english_cache_not_reused_for_translated_templates(self):
        directory=Path(tts.AUDIO_DIR);directory.mkdir();name='Review dummy'
        for lang in EXPECTED:
            legacy=f'{lang}_review-dummy_{hashlib.sha1(f"{name}|{lang}".encode()).hexdigest()[:10]}.mp3'
            (directory/legacy).write_bytes(b'old-English-content')
            with self.subTest(language=lang): self.assertIsNone(tts.get_cached_audio(name,lang))
        self.assertEqual(len(list(directory.glob('*.mp3'))),6)

    def test_six_cache_entries_are_distinct_and_reusable_offline(self):
        class Speech:
            def save(self,path): Path(path).write_bytes(b'unit-provider-fixture')
        with patch('tts.gTTS',side_effect=lambda **kw: Speech()):
            paths={lang:tts.get_or_create_audio('Review dummy',lang) for lang in EXPECTED}
        self.assertEqual(len(set(paths.values())),6)
        with patch('tts.gTTS',side_effect=ConnectionError('controlled offline')) as synth:
            for lang,path in paths.items(): self.assertEqual(tts.get_or_create_audio('Review dummy',lang),path)
            synth.assert_not_called()

    def test_synthesis_failures_cleanup_and_can_retry_all_languages(self):
        class Broken:
            def save(self,path): Path(path).write_bytes(b'partial');raise OSError('controlled provider failure')
        class Empty:
            def save(self,path): pass
        class Good:
            def save(self,path): Path(path).write_bytes(b'unit-provider-fixture')
        for lang in EXPECTED:
            for implementation in (Broken,Empty):
                with self.subTest(language=lang,implementation=implementation.__name__):
                    with patch('tts.gTTS',return_value=implementation()):
                        with self.assertRaises(OSError): tts.get_or_create_audio('Failure dummy',lang)
                    self.assertIsNone(tts.get_cached_audio('Failure dummy',lang))
            with patch('tts.gTTS',return_value=Good()): tts.get_or_create_audio('Failure dummy',lang)
        self.assertEqual(len(list(Path(tts.AUDIO_DIR).iterdir())),6)

    def test_invalid_language_rejected_before_provider_or_file_creation(self):
        with patch('tts.gTTS') as synth:
            for lang in ('zz','../en','',None):
                with self.subTest(language=lang), self.assertRaises(ValueError):tts.get_or_create_audio('Dummy',lang)
            synth.assert_not_called()
        self.assertFalse(Path(tts.AUDIO_DIR).exists())

    def test_current_due_audio_does_not_expose_legacy_english_cache(self):
        for lang in EXPECTED:
            mid=self.due(name='Opaque नाम',language=lang)
            database.mark_fired(mid,'audio/legacy-english.mp3')
            row=dict(database.get_medicine(mid))
            response=self.client.get('/check_reminders').json
            self.assertIsNone(response['audio_url'])
            with database.get_db_connection() as c:c.execute('UPDATE medicines SET is_due=0 WHERE id=?',(mid,))
            after=dict(database.get_medicine(mid))
            for field in ('medicine_name','time','language','days_remaining','created_at'):self.assertEqual(row[field],after[field])

















if __name__=='__main__':unittest.main(verbosity=2)
