"""Localized speech and background preparation, with disposable data/audio."""
import hashlib
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import database
import tts
import scheduler
from app import app


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_audio, self.old_db = tts.AUDIO_DIR, database.DB_PATH
        tts.AUDIO_DIR = str(Path(self.tmp.name) / 'audio')
        database.DB_PATH = str(Path(self.tmp.name) / 'test.db')
        database.init_db()
        user = database.create_user('voice', 'test-only', 'Voice')
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = user['id']

    def tearDown(self):
        tts.AUDIO_DIR, database.DB_PATH = self.old_audio, self.old_db
        self.tmp.cleanup()

    def test_each_language_synthesizes_its_own_sentence(self):
        scripts = {'hi': (0x0900, 0x097f), 'ta': (0x0b80, 0x0bff),
                   'te': (0x0c00, 0x0c7f), 'kn': (0x0c80, 0x0cff),
                   'bn': (0x0980, 0x09ff)}
        for language, _ in tts.LANGUAGES:
            with self.subTest(language=language), patch('tts.gTTS') as speech:
                speech.return_value.save.side_effect = lambda path: Path(path).write_bytes(b'test mp3')
                tts.get_or_create_audio('Vitamin D', language)
                sentence = speech.call_args.kwargs['text']
                self.assertEqual(speech.call_args.kwargs['lang'], language)
                self.assertIn('Vitamin D', sentence)
                if language != 'en':
                    low, high = scripts[language]
                    self.assertTrue(any(low <= ord(char) <= high for char in sentence))
                    self.assertNotIn("It's time", sentence)

    def test_old_english_sentence_cache_is_not_reused(self):
        directory = Path(tts.AUDIO_DIR)
        directory.mkdir()
        digest = hashlib.sha1(b'Vitamin D|hi').hexdigest()[:10]
        (directory / f'hi_vitamin-d_{digest}.mp3').write_bytes(b'old English sentence')
        self.assertIsNone(tts.get_cached_audio('Vitamin D', 'hi'))

    def test_add_and_edit_prepare_audio_without_waiting_for_speech(self):
        with patch('scheduler.prepare_audio') as prepare:
            response = self.client.post('/add_medicine', json=dict(
                medicine_name='Vitamin D', times=['08:00'], days=2, language='ta'))
            self.assertEqual(response.status_code, 200)
            prepare.assert_called_once_with('Vitamin D', 'ta')
            prepare.reset_mock()
            with closing(database.get_db_connection()) as conn:
                group = conn.execute('SELECT group_id FROM medicines').fetchone()['group_id']
            self.client.post(f'/medicine/{group}/edit', data=dict(
                medicine_name='Vitamin D', times=['09:00'], days_remaining=2, language='kn'))
            prepare.assert_called_once_with('Vitamin D', 'kn')

    def test_due_response_includes_localized_text_and_retries_missing_audio(self):
        with patch('scheduler.prepare_audio'):
            self.client.post('/add_medicine', json=dict(
                medicine_name='Vitamin D', times=['08:00'], days=2, language='bn'))
        conn = database.get_db_connection()
        mid = conn.execute('SELECT id FROM medicines').fetchone()['id']
        conn.close()
        database.mark_fired(mid, None)
        with patch('scheduler.prepare_audio') as prepare:
            response = self.client.get('/check_reminders')
            self.assertEqual(response.status_code, 200)
            self.assertIn('ওষুধ', response.json['spoken_text'])
            prepare.assert_called_once_with('Vitamin D', 'bn')

    def test_failed_generation_is_not_repeated_on_every_poll(self):
        key = ('Retry test', 'hi')
        try:
            with patch('scheduler._audio_pool.submit', side_effect=lambda job: job()), \
                 patch('tts.get_cached_audio', return_value=None), \
                 patch('tts.get_or_create_audio', side_effect=RuntimeError('offline')) as generate, \
                 patch('scheduler.monotonic', return_value=100), \
                 self.assertLogs('scheduler', level='WARNING'):
                scheduler.prepare_audio(*key)
                scheduler.prepare_audio(*key)
                self.assertEqual(generate.call_count, 1)
        finally:
            scheduler._audio_retry_after.pop(key, None)


if __name__ == '__main__':
    unittest.main()
