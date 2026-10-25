"""Compile production firmware with real ArduinoJson and fake hardware on host.

Set DOSECLOCK_ARDUINOJSON_INCLUDE to the installed ArduinoJson 7.4.3 src folder.
These tests model time/network/NVS faults; they do not validate physical parts.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class FirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='doseclock-firmware-host-')
        cls.binary = Path(cls.temp.name) / 'firmware-host'
        cls.reason = None
        compiler = shutil.which(os.environ.get('CXX', 'c++'))
        include = Path(os.environ.get('DOSECLOCK_ARDUINOJSON_INCLUDE',
            str(Path(__file__).resolve().parents[1] / 'hardware/.pio/libdeps/esp32dev/ArduinoJson/src')))
        if not compiler or not (include / 'ArduinoJson.h').is_file():
            cls.reason = 'Host C++ compiler and DOSECLOCK_ARDUINOJSON_INCLUDE are required; no firmware simulation executed'
            return
        here = Path(__file__).with_name('firmware')
        cls.build = subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra',
            '-I' + str(here), '-I' + str(include), str(here / 'harness.cpp'),
            '-o', str(cls.binary)], text=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, name):
        if self.reason:
            self.skipTest(self.reason)
        self.assertEqual(self.build.returncode, 0, self.build.stdout + self.build.stderr)
        result = subprocess.run([str(self.binary), name], text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_thresholds_debounce_and_millis_wrap(self): self.run_case('thresholds')
    def test_retry_completion_requires_fresh_debounced_release_and_press(self): self.run_case('retry_interlock')
    def test_long_hold_overlapping_blocking_retry_is_not_taken(self): self.run_case('held_retry')
    def test_hold_duration_measured_without_http_calls(self): self.run_case('hold_without_network')
    def test_identical_retry_after_restart_503_timeout_and_invalid_success(self): self.run_case('replay')
    def test_signed_64_bit_identifiers_and_invalid_numbers(self): self.run_case('ids')
    def test_corrupt_recovery_never_posts_and_requires_fresh_gesture(self): self.run_case('corrupt_recovery')
    def test_failed_or_malformed_recovery_stays_blocked(self): self.run_case('failed_recovery')
    def test_partial_persistence_orphan_marker_fails_closed_after_restart(self): self.run_case('write_failure')
    def test_marker_write_failure_never_transmits(self): self.run_case('marker_failure')
    def test_recovery_cannot_discard_valid_uncertain_action(self): self.run_case('valid_recovery_refused')
    def test_older_valid_queue_keeps_its_original_identity(self): self.run_case('legacy_queue')
    def test_malformed_json_schema_types_and_keys_never_transmit(self): self.run_case('malformed_queues')
    def test_usb_recovery_works_during_wifi_startup_without_acknowledging(self): self.run_case('offline_recovery')
    def test_failed_queue_removal_retries_identical_action(self): self.run_case('remove_failure')


if __name__ == '__main__': unittest.main(verbosity=2)
