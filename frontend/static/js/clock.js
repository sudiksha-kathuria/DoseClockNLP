/*
 * clock.js
 * --------
 * Drives the /clock page:
 *   1. Ticks a big, legible live clock every second.
 *   2. Polls /check_reminders every second, including during an alarm.
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
const audioStatus = document.getElementById("audio-status");

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

const SILENT_CLIP = "/static/audio/activation.wav";
let audioUnlocked = false;
let audioUnlocking = false;
let playedOccurrence = null;
let audioAttempting = false;
let audioGeneration = 0;
let audioRetryAfter = 0;
try {
  audioUnlocked = window.sessionStorage?.getItem("doseclock-sound-enabled") === "1";
} catch { /* Sound can still be enabled when storage is unavailable. */ }

function updateSoundControl() {
  soundHint.textContent = audioUnlocked
    ? (currentReminder ? "Replay reminder" : "Sound enabled")
    : "Enable spoken reminders";
  soundHint.setAttribute("aria-pressed", String(audioUnlocked));
}

async function unlockAudio() {
  if (audioUnlocking) return;
  if (audioUnlocked) {
    if (currentReminder) playReminderAudio(currentReminder, true);
    return;
  }
  audioUnlocking = true;
  reminderAudio.src = SILENT_CLIP;
  reminderAudio.muted = false;
  try {
    await reminderAudio.play();
    if (reminderAudio.getAttribute("src") === SILENT_CLIP) reminderAudio.pause();
    audioUnlocked = true;
    try { window.sessionStorage?.setItem("doseclock-sound-enabled", "1"); } catch { /* Optional preference. */ }
    audioStatus.textContent = "Sound enabled. Keep this page open for spoken reminders.";
    ["click", "touchstart", "keydown"].forEach((evt) => document.removeEventListener(evt, unlockAudio));
  } catch {
    audioStatus.textContent = "Sound could not start. Allow sound for this site, then try again.";
  } finally {
    audioUnlocking = false;
    updateSoundControl();
    if (audioUnlocked && currentReminder) playReminderAudio(currentReminder);
  }
}

soundHint.addEventListener("click", unlockAudio);
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

async function playReminderAudio(reminder, force = false) {
  if (!currentReminder || actionInFlight || audioUnlocking || audioAttempting) return;
  const occurrence = `${reminder.id}:${reminder.fired_at}`;
  if (!force && (playedOccurrence === occurrence || Date.now() < audioRetryAfter)) return;
  if (!audioUnlocked) {
    audioStatus.textContent = "Enable spoken reminders to hear this alarm.";
    return;
  }
  if (!reminder.audio_url) {
    audioStatus.textContent = "Preparing spoken audio. The reminder buttons are ready.";
    return;
  }
  audioAttempting = true;
  const generation = audioGeneration;
  if (force) {
    reminderAudio.pause();
    reminderAudio.currentTime = 0;
  }
  if (reminderAudio.getAttribute("src") !== reminder.audio_url) reminderAudio.src = reminder.audio_url;
  reminderAudio.muted = false;
  try {
    await reminderAudio.play();
    if (generation !== audioGeneration) return;
    playedOccurrence = occurrence;
    audioRetryAfter = 0;
    audioStatus.textContent = "Spoken reminder started. Use Replay reminder to hear it again.";
  } catch (error) {
    if (generation !== audioGeneration) return;
    audioRetryAfter = Date.now() + 5000;
    if (error.name === "NotAllowedError") {
      audioUnlocked = false;
      try { window.sessionStorage?.removeItem("doseclock-sound-enabled"); } catch { /* Optional preference. */ }
      updateSoundControl();
      audioStatus.textContent = "Allow sound for this site, then enable spoken reminders.";
    } else {
      audioStatus.textContent = "Audio could not play. Use Replay reminder to try again.";
    }
  } finally {
    audioAttempting = false;
  }
}

// ---------------------------------------------------------------------------
// Alarm state
// ---------------------------------------------------------------------------

let currentReminder = null; // { id, medicine_name, audio_url, language }
let recognition = null;
let actionInFlight = false;
let pollInFlight = false;
let actionGeneration = 0;

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
  if (!currentReminder || actionInFlight || event.repeat) return;
  if (event.target.closest("input,select,textarea,button,a,summary")) return;
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

  updateSoundControl();
  playReminderAudio(reminder);
  startRecognition(reminder.language);
}

function hideAlarm() {
  audioGeneration += 1;
  playedOccurrence = null;
  audioRetryAfter = 0;
  reminderAudio.pause();
  reminderAudio.currentTime = 0;
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  micIndicator.onclick = null;
  micIndicator.style.cursor = "";
  alarmView.classList.remove("visible");
  stopRecognition();
  stopScanning();
  currentReminder = null;
  updateSoundControl();
  audioStatus.textContent = audioUnlocked ? "Sound enabled for the next reminder." : "Enable spoken reminders to hear alarms.";
  idleView.classList.remove("hidden");
}

function showSuccessThenIdle() {
  hideAlarm();
  idleView.classList.add("hidden");
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
  return performAction("taken");
}

async function handleSnooze() {
  return performAction("snooze");
}

async function performAction(action) {
  if (!currentReminder || actionInFlight) return;
  const reminder = currentReminder;
  actionInFlight = true;
  actionGeneration += 1;
  scanButtons.forEach((button) => { button.disabled = true; });
  stopRecognition();
  stopScanning();
  try {
    const response = await fetch(`/mark_${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: reminder.id, fired_at: reminder.fired_at }),
      signal: AbortSignal.timeout(8000),
    });
    if (response.status === 401) {
      window.location.assign("/login");
      return;
    }
    if (response.status === 409) {
      hideAlarm();
      showToast("This reminder has already been answered.");
      return;
    }
    if (!response.ok) throw new Error("Action could not be saved");
    if (action === "taken") showSuccessThenIdle();
    else {
      hideAlarm();
      showToast("Snoozed for 5 minutes");
    }
  } catch (err) {
    micIndicator.textContent = "Could not save your response. Check the connection and try again.";
    startScanning();
  } finally {
    actionInFlight = false;
    scanButtons.forEach((button) => { button.disabled = false; });
    pollReminders();
  }
}

takenBtn.addEventListener("click", handleTaken);
snoozeBtn.addEventListener("click", handleSnooze);

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------

async function pollReminders() {
  if (pollInFlight || actionInFlight) return;
  pollInFlight = true;
  const generation = actionGeneration;
  try {
    const response = await fetch("/check_reminders", {
      cache: "no-store", signal: AbortSignal.timeout(5000),
    });
    if (response.status === 401) {
      window.location.assign("/login");
      return;
    }
    if (!response.ok) throw new Error("Connection unavailable");
    const data = await response.json();
    if (actionInFlight || generation !== actionGeneration) return;
    if (currentReminder && (!data.due || data.id !== currentReminder.id ||
        data.fired_at !== currentReminder.fired_at)) hideAlarm();
    if (data.due && !currentReminder && !successFlash.classList.contains("visible")) showAlarm(data);
    else if (data.due && currentReminder) {
      currentReminder = data;
      playReminderAudio(data);
    }
  } catch (err) {
    /* server unreachable this cycle - just try again next poll */
  } finally {
    pollInFlight = false;
  }
}

pollReminders();
setInterval(pollReminders, 1000);
updateSoundControl();
if (audioUnlocked) audioStatus.textContent = "Sound enabled for this tab. Keep the clock open.";
