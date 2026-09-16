/*
 * clock.js
 * --------
 * Drives the /clock page:
 *   1. Ticks a big, legible live clock every second.
 *   2. Polls /check_reminders every ~17s for a due reminder.
 *   3. When one fires: shows the alarm view, plays the gTTS audio, and
 *      listens (optionally) for a spoken "taken"/"snooze" via the Web
 *      Speech API. The Taken/Snooze buttons always work regardless of
 *      whether speech recognition is available or understood anything.
 *   4. Runs a single-switch "scan" over Taken/Snooze and confirms
 *      whichever one is highlighted on Space/Enter, so a single adaptive
 *      switch (or just a keyboard) is enough to respond - no precise tap
 *      or reach required. See /HARDWARE.md.
 */

// ---------------------------------------------------------------------------
// Elements
// ---------------------------------------------------------------------------

const clockFace = document.getElementById("clock-face");
const clockMeridiem = document.getElementById("clock-meridiem");
const clockDate = document.getElementById("clock-date");

const idleView = document.getElementById("idle-view");
const alarmView = document.getElementById("alarm-view");
const successFlash = document.getElementById("success-flash");

const alarmMedicineName = document.getElementById("alarm-medicine-name");
const takenBtn = document.getElementById("taken-btn");
const snoozeBtn = document.getElementById("snooze-btn");
const micIndicator = document.getElementById("mic-indicator");
const reminderAudio = document.getElementById("reminder-audio");

const soundHint = document.getElementById("sound-hint");

const toast = document.getElementById("toast");

// ---------------------------------------------------------------------------
// Audio unlock
// Browsers refuse to play audio with sound until the page has received a
// real user gesture (click/tap/key). Since reminders fire from a
// background poll with no gesture of their own, the very first tap
// anywhere on this page "unlocks" the <audio> element by playing (then
// immediately pausing) a silent clip - after that, script-triggered
// playback works normally for the rest of the visit.
// ---------------------------------------------------------------------------

const SILENT_CLIP = "data:audio/wav;base64,UklGRiUAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQEAAACA";
let audioUnlocked = false;

function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  reminderAudio.src = SILENT_CLIP;
  reminderAudio
    .play()
    .then(() => reminderAudio.pause())
    .catch(() => {
      /* some browsers still refuse this - Taken/Snooze buttons remain the reliable path */
    });
  soundHint.classList.add("hidden");
  ["click", "touchstart", "keydown"].forEach((evt) => document.removeEventListener(evt, unlockAudio));
}

["click", "touchstart", "keydown"].forEach((evt) => document.addEventListener(evt, unlockAudio));

// ---------------------------------------------------------------------------
// Live clock
// ---------------------------------------------------------------------------

function tickClock() {
  const now = new Date();
  let hours = now.getHours();
  const minutes = now.getMinutes().toString().padStart(2, "0");
  const meridiem = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;

  clockFace.firstChild.textContent = `${hours}:${minutes}`;
  clockMeridiem.textContent = meridiem;
  clockDate.textContent = now.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

tickClock();
setInterval(tickClock, 1000);

// ---------------------------------------------------------------------------
// Toast helper
// ---------------------------------------------------------------------------

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  setTimeout(() => toast.classList.remove("visible"), 2200);
}

// ---------------------------------------------------------------------------
// Voice command mapping
// Small, forgiving keyword lists per language - a spoken transcript only
// needs to CONTAIN one of these words to trigger the matching action.
// ---------------------------------------------------------------------------

const VOICE_KEYWORDS = {
  en: { taken: ["taken", "done", "yes"], snooze: ["snooze", "later", "wait"] },
  hi: { taken: ["ले लिया", "हो गया"], snooze: ["बाद में", "स्नूज़"] },
  ta: { taken: ["எடுத்தாயிற்று", "சாப்பிட்டேன்"], snooze: ["பின்னர்"] },
  te: { taken: ["తీసుకున్నాను", "అయిపోయింది"], snooze: ["తర్వాత"] },
  kn: { taken: ["ತೆಗೆದುಕೊಂಡೆ", "ಆಯಿತು"], snooze: ["ನಂತರ"] },
  bn: { taken: ["খেয়েছি", "নিয়েছি"], snooze: ["পরে"] },
};

const RECOGNITION_LANG = {
  en: "en-IN",
  hi: "hi-IN",
  ta: "ta-IN",
  te: "te-IN",
  kn: "kn-IN",
  bn: "bn-IN",
};

// ---------------------------------------------------------------------------
// Alarm state
// ---------------------------------------------------------------------------

let currentReminder = null; // { id, medicine_name, audio_url, language }
let recognition = null;

function stopRecognition() {
  if (recognition) {
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    try {
      recognition.stop();
    } catch (err) {
      /* already stopped - fine */
    }
    recognition = null;
  }
  micIndicator.innerHTML = "";
}

function startRecognition(language) {
  const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
  if (!SpeechRecognition) return; // optional feature - buttons still work fine

  recognition = new SpeechRecognition();
  recognition.lang = RECOGNITION_LANG[language] || "en-IN";
  recognition.continuous = true;
  recognition.interimResults = false;

  const keywords = VOICE_KEYWORDS[language] || VOICE_KEYWORDS.en;

  recognition.onresult = (event) => {
    const transcript = event.results[event.results.length - 1][0].transcript.toLowerCase();
    if (keywords.taken.some((word) => transcript.includes(word))) {
      handleTaken();
    } else if (keywords.snooze.some((word) => transcript.includes(word))) {
      handleSnooze();
    }
  };

  // Mic errors (no permission, unsupported, etc.) are non-fatal - the
  // Taken/Snooze buttons remain the primary, always-working path.
  recognition.onerror = () => stopRecognition();
  recognition.onend = () => {
    recognition = null;
    micIndicator.innerHTML = "";
  };

  try {
    recognition.start();
    micIndicator.innerHTML = '<span class="mic-dot"></span> Listening for "taken" or "snooze"';
  } catch (err) {
    stopRecognition();
  }
}

// ---------------------------------------------------------------------------
// Single-switch scanning
// Auto-highlights Taken, then Snooze, then back, on a slow loop. Anyone
// who can trigger exactly one input - a single adaptive switch (wired or
// Bluetooth, they all emit Space/Enter by default), a keyboard, or just
// a tap on whichever button is glowing - can confirm a reminder without
// ever needing to aim at a specific target. See /HARDWARE.md.
// ---------------------------------------------------------------------------

const SCAN_INTERVAL_MS = 2200;
const scanButtons = [takenBtn, snoozeBtn];
let scanIndex = 0;
let scanTimer = null;

function applyScanHighlight() {
  scanButtons.forEach((btn, i) => btn.classList.toggle("scan-highlight", i === scanIndex));
}

function startScanning() {
  scanIndex = 0;
  applyScanHighlight();
  scanTimer = setInterval(() => {
    scanIndex = (scanIndex + 1) % scanButtons.length;
    applyScanHighlight();
  }, SCAN_INTERVAL_MS);
}

function stopScanning() {
  clearInterval(scanTimer);
  scanTimer = null;
  scanButtons.forEach((btn) => btn.classList.remove("scan-highlight"));
}

function confirmScanSelection() {
  if (scanIndex === 0) {
    handleTaken();
  } else {
    handleSnooze();
  }
}

// Space/Enter is the default output of virtually every commercial
// single-switch accessibility device, so this one listener is all that's
// needed to support them - no pairing or extra code per device.
document.addEventListener("keydown", (event) => {
  if (!currentReminder) return;
  if (event.code === "Space" || event.code === "Enter") {
    event.preventDefault();
    confirmScanSelection();
  }
});

// ---------------------------------------------------------------------------
// Showing / hiding the alarm
// ---------------------------------------------------------------------------

function showAlarm(reminder) {
  currentReminder = reminder;
  idleView.classList.add("hidden");
  alarmMedicineName.textContent = reminder.medicine_name;
  alarmView.classList.add("visible");
  startScanning();

  // Play the reminder audio. If the page was tapped at least once already
  // (see the audio-unlock block above), this plays with sound straight
  // away. If it's still blocked for some reason, fall back to a tappable
  // prompt - the Taken/Snooze buttons remain fully usable either way.
  reminderAudio.src = reminder.audio_url;
  reminderAudio.play().catch(() => {
    micIndicator.innerHTML = '<span class="mic-dot"></span> Tap here to hear the reminder';
    micIndicator.style.cursor = "pointer";
    micIndicator.onclick = () => {
      reminderAudio.play().catch(() => {});
      micIndicator.onclick = null;
      micIndicator.style.cursor = "";
    };
  });

  startRecognition(reminder.language);
}

function hideAlarm() {
  alarmView.classList.remove("visible");
  stopRecognition();
  stopScanning();
  currentReminder = null;
  idleView.classList.remove("hidden");
}

function showSuccessThenIdle() {
  alarmView.classList.remove("visible");
  stopScanning();
  successFlash.classList.add("visible");
  setTimeout(() => {
    successFlash.classList.remove("visible");
    idleView.classList.remove("hidden");
    // Refresh so the "today's doses" sidebar reflects the updated schedule.
    window.location.reload();
  }, 900);
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

async function handleTaken() {
  if (!currentReminder) return;
  const id = currentReminder.id;
  stopRecognition();
  stopScanning();
  currentReminder = null; // prevent double-fire from a lingering voice result
  try {
    await fetch("/mark_taken", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
  } catch (err) {
    /* network hiccup - the reminder will simply show again on next poll */
  }
  showSuccessThenIdle();
}

async function handleSnooze() {
  if (!currentReminder) return;
  const id = currentReminder.id;
  stopRecognition();
  stopScanning();
  currentReminder = null;
  try {
    await fetch("/mark_snooze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
  } catch (err) {
    /* network hiccup - fine, user can snooze again next time it rings */
  }
  showToast("Snoozed for 5 minutes");
  hideAlarm();
}

takenBtn.addEventListener("click", handleTaken);
snoozeBtn.addEventListener("click", handleSnooze);

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------

async function pollReminders() {
  // Don't interrupt an alarm that's already showing.
  if (currentReminder) return;

  try {
    const response = await fetch("/check_reminders");
    const data = await response.json();
    if (data.due) {
      showAlarm(data);
    }
  } catch (err) {
    /* server unreachable this cycle - just try again next poll */
  }
}

pollReminders();
setInterval(pollReminders, 17000); // ~15-20s, per the brief
