// Run with: node tests/test_clock_hardware.js (no extra dependencies).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

function clock() {
  const elements = new Map();
  const listeners = new Map();
  const intervals = [];
  const requests = [];
  let due = false;
  let actionStatus = 200;
  let nextPoll = null;
  const element = (id) => {
    if (!elements.has(id)) {
      const classes = new Set();
      elements.set(id, { textContent: '', innerHTML: '', firstChild: {}, style: {},
        classList: { add: c => classes.add(c), remove: c => classes.delete(c),
          contains: c => classes.has(c), toggle: (c, on) => on ? classes.add(c) : classes.delete(c) },
        addEventListener() {}, pause() {}, play: () => Promise.resolve(), currentTime: 0 });
    }
    return elements.get(id);
  };
  const context = vm.createContext({ console, Date, Promise, AbortSignal,
    document: { getElementById: element,
      addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener() {} },
    window: { location: { reload() {}, assign() {} } },
    setInterval: (fn, ms) => { intervals.push(ms); return intervals.length; },
    clearInterval() {}, setTimeout() {}, clearTimeout() {},
    fetch: async (url) => {
      requests.push(url);
      if (url === '/check_reminders' && nextPoll) {
        const result = nextPoll; nextPoll = null; return result;
      }
      if (url === '/check_reminders') return { ok: true, status: 200, json: async () =>
        due ? { due: true, id: 1, fired_at: 'test-occurrence', medicine_name: 'Test', audio_url: null, language: 'en' } : { due: false } };
      return { ok: actionStatus === 200, status: actionStatus, json: async () => ({ success: actionStatus === 200 }) };
    } });
  vm.runInContext(readFileSync(join(__dirname, '../frontend/static/js/clock.js'), 'utf8'), context);
  return { context, element, listeners, intervals, requests, ready: () => new Promise(setImmediate),
    setDue: value => { due = value; }, setStatus: value => { actionStatus = value; },
    setNextPoll: value => { nextPoll = value; } };
}

test('hardware acknowledgement clears an already-visible alarm', async () => {
  const c = clock();
  await c.ready();
  c.setDue(true); await c.context.pollReminders();
  assert.equal(c.element('alarm-view').classList.contains('visible'), true);
  c.setDue(false); await c.context.pollReminders();
  assert.equal(c.element('alarm-view').classList.contains('visible'), false);
});

test('failed Snooze keeps the alarm and does not report success', async () => {
  const c = clock(); await c.ready();
  c.setDue(true); await c.context.pollReminders(); c.setStatus(503);
  await c.context.handleSnooze();
  assert.equal(c.element('alarm-view').classList.contains('visible'), true);
  assert.match(c.element('mic-indicator').textContent, /could not|Could not/);
  assert.doesNotMatch(c.element('toast').textContent, /Snoozed/);
});

test('Enter on a focused button retains native activation', async () => {
  const c = clock(); await c.ready(); c.setDue(true); await c.context.pollReminders();
  let prevented = false;
  c.listeners.get('keydown')({ code: 'Enter', target: { closest: () => ({}) },
    preventDefault: () => { prevented = true; } });
  assert.equal(prevented, false);
  assert.equal(c.requests.includes('/mark_taken'), false);
});

test('clock polls often enough to follow Switch Hub actions', () => {
  assert.equal(clock().intervals.includes(17000), false);
  assert(clock().intervals.filter(ms => ms <= 1000).length >= 2);
});

test('a delayed poll cannot restore an acknowledged alarm', async () => {
  const c = clock(); await c.ready(); c.setDue(true); await c.context.pollReminders();
  let release;
  c.setNextPoll(new Promise(resolve => { release = resolve; }));
  const pendingPoll = c.context.pollReminders();
  await c.context.handleSnooze();
  release({ ok: true, status: 200, json: async () => ({ due: true, id: 1,
    fired_at: 'test-occurrence', medicine_name: 'Test', audio_url: null, language: 'en' }) });
  await pendingPoll;
  assert.equal(c.element('alarm-view').classList.contains('visible'), false);
});
