"""Autoplay evidence: fresh disk profile, raw CDP observations, trusted input.

Every Runtime.evaluate in the acceptance path explicitly uses userGesture=False.
The play wrapper observes the real promise and returns it unchanged.
"""
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

INSTRUMENT = r"""(() => {
  const audit = window.__mediaAudit = {calls: [], events: [], gestures: []};
  const snapshot = a => ({src: a.getAttribute('src'), currentSrc: a.currentSrc,
    currentTime: a.currentTime, duration: Number.isFinite(a.duration) ? a.duration : null,
    paused: a.paused, ended: a.ended, muted: a.muted, volume: a.volume,
    readyState: a.readyState, error: a.error ? {code: a.error.code, message: a.error.message} : null,
    decodedBytes: a.webkitAudioDecodedByteCount ?? null,
    activation: {isActive: navigator.userActivation.isActive, hasBeenActive: navigator.userActivation.hasBeenActive}});
  window.__mediaSnapshot = () => {
    const a = document.querySelector('#reminder-audio');
    return {media: a ? snapshot(a) : null, audit,
      alarmVisible: !!document.querySelector('#alarm-view.visible'),
      prompt: document.querySelector('#mic-indicator')?.textContent,
      hintHidden: document.querySelector('#sound-hint')?.classList.contains('hidden')};
  };
  const originalPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function(...args) {
    const call = {at: performance.now(), before: snapshot(this), result: 'pending'};
    audit.calls.push(call);
    let promise;
    try { promise = originalPlay.apply(this, args); }
    catch (error) {call.result = 'threw'; call.error = {name: error.name, message: error.message}; throw error;}
    promise.then(() => {call.result = 'resolved'; call.after = snapshot(this);},
      error => {call.result = 'rejected'; call.error = {name: error.name, message: error.message}; call.after = snapshot(this);});
    return promise;
  };
  for (const type of ['play','playing','timeupdate','pause','ended','error','loadedmetadata','abort'])
    document.addEventListener(type, e => {
      if (e.target instanceof HTMLMediaElement) audit.events.push({type, at: performance.now(), media: snapshot(e.target)});
    }, true);
  for (const type of ['click','keydown','touchstart']) document.addEventListener(type,
    e => audit.gestures.push({type, trusted: e.isTrusted, target: e.target.id, at: performance.now(),
      active: navigator.userActivation.isActive}), true);
})();"""


def verify_autoplay(pw, base, fixture, output, policy='strict', scenario='pending', control=False):
    """Fixture callable uses HTTP only; never grants browser user activation."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    transcript = (output / 'cdp.jsonl').open('w')
    result = {'recorded_at': datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),
              'policy': policy, 'scenario': scenario, 'human_listening': False}
    def write(value):
        transcript.write(json.dumps(value) + '\n'); transcript.flush()
    with tempfile.TemporaryDirectory(prefix='doseclock-clean-profile-') as profile:
        result['profile_initially_empty'] = not any(Path(profile).iterdir())
        # Expose the actual command line for auditing; does not grant autoplay.
        args = ['--enable-automation']
        if policy == 'strict': args.append('--autoplay-policy=document-user-activation-required')
        ctx = pw.chromium.launch_persistent_context(profile, headless=True, args=args,
            ignore_default_args=['--mute-audio'], viewport={'width': 1440, 'height': 1000})
        page = ctx.pages[0]
        cdp = ctx.new_cdp_session(page)
        def send(method, params=None, label=None):
            write({'direction': 'send', 'method': method, 'params': params or {}, 'label': label})
            response = cdp.send(method, params or {})
            write({'direction': 'receive', 'method': method, 'result': response, 'label': label})
            return response
        def evaluate(expression, label):
            response = send('Runtime.evaluate', {'expression': expression, 'userGesture': False,
                'returnByValue': True, 'awaitPromise': True}, label)
            assert 'exceptionDetails' not in response, response
            return response['result'].get('value')
        def sample(label):
            return evaluate('window.__mediaSnapshot?.() ?? null', label)
        def until(predicate, label, timeout=6):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                state = sample(label)
                if state and predicate(state): return state
                time.sleep(.05)
            raise AssertionError({'timeout': label, 'last': state})
        def click(selector):
            point = evaluate("(() => {const r=document.querySelector(" + json.dumps(selector) +
                ").getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2};})()", 'click coordinates')
            for kind in ('mouseMoved', 'mousePressed', 'mouseReleased'):
                send('Input.dispatchMouseEvent', {'type': kind, **point,
                    'button': 'left' if kind != 'mouseMoved' else 'none',
                    'clickCount': 1 if kind != 'mouseMoved' else 0}, 'trusted browser click')
        try:
            command = send('Browser.getBrowserCommandLine')['arguments']
            result['browser_command_line'] = command
            result['browser_version'] = send('Browser.getVersion')
            assert '--mute-audio' not in command
            assert not any('no-user-gesture-required' in arg or 'user-gesture-required' == arg for arg in command)
            assert not any('Autoplay' in arg or 'MediaEngagement' in arg for arg in command)
            assert result['profile_initially_empty']
            for event in ('Media.playerEventsAdded', 'Media.playerErrorsRaised', 'Media.playerPropertiesChanged'):
                cdp.on(event, lambda params, event=event: write({'direction': 'event', 'method': event, 'params': params}))
            send('Page.enable')
            send('Runtime.enable')
            send('Media.enable')
            send('Page.addScriptToEvaluateOnNewDocument', {'source': INSTRUMENT})
            user = 'review_clean_' + policy + '_' + scenario
            fixture(user, 'due' if scenario == 'pending' else 'state')
            login = ctx.request.post(base + '/login', form={'username': user, 'password': 'dummy-password'})
            assert login.ok
            send('Page.navigate', {'url': base + '/clock'})
            if scenario == 'idle':
                state = until(lambda s: s['media'] is not None, 'idle without activation')
                assert not state['media']['activation']['hasBeenActive'] and not state['audit']['gestures']
                click('#sound-hint')
                result['idle_enabled'] = until(lambda s: s['hintHidden'] and s['audit']['calls'] and
                    s['audit']['calls'][-1]['result'] == 'resolved', 'idle sound enablement')
                fixture(user, 'due')
                # Natural 17-second app poll: transient activation must have expired.
                state = until(lambda s: s['alarmVisible'] and len(s['audit']['calls']) >= 2 and
                    s['audit']['calls'][-1]['result'] == 'resolved', 'future reminder automatic playback', 20)
                assert not state['audit']['calls'][-1]['before']['activation']['isActive'], state
                result['future_play_call'] = state['audit']['calls'][-1]
            else:
                state = until(lambda s: s['alarmVisible'] and s['audit']['calls'] and
                    s['audit']['calls'][0]['result'] != 'pending', 'initial application play result')
                result['initial'] = state
                first = state['audit']['calls'][0]
                assert first['result'] == 'rejected' and first['error']['name'] == 'NotAllowedError', state
                assert not first['before']['activation']['hasBeenActive'] and not state['audit']['gestures'], state
                assert state['media']['paused'] and not state['media']['muted'] and state['media']['volume'] == 1, state
                assert state['media']['currentTime'] == 0 and state['media']['error'] is None, state
                time.sleep(.45)
                result['blocked_later'] = sample('blocked progression sample')
                assert result['blocked_later']['media']['currentTime'] == 0
                probe = evaluate("document.querySelector('#reminder-audio').play().then(() => ({result:'resolved'}),"
                    "e => ({result:'rejected',name:e.name,message:e.message}))", 'explicit no-gesture play probe')
                result['explicit_probe'] = probe
                assert probe['result'] == 'rejected' and probe['name'] == 'NotAllowedError', probe
                assert not sample('activation after no-gesture probe')['media']['activation']['hasBeenActive']
                if control:
                    # Deliberately contaminated control, never an acceptance result.
                    response = send('Runtime.evaluate', {'expression': "document.querySelector('#reminder-audio').play().then(()=> 'resolved', e=>e.name)",
                        'userGesture': True, 'returnByValue': True, 'awaitPromise': True}, 'INVALID experiment: synthetic gesture positive control')
                    result['synthetic_gesture_control'] = response
                else:
                    assert 'Tap here' in state['prompt'], state
                    click('#mic-indicator')
                state = until(lambda s: any(c['result'] == 'resolved' for c in s['audit']['calls']), 'play promise resolved after input')
            # A resolved play promise can precede audio-output clock startup.
            # Require actual progress within a bounded timeout before measuring
            # sustained progress; stalled/paused media must still fail.
            started_playback = until(lambda s: not s['media']['paused'] and s['media']['currentTime'] > .05,
                                     'first observable audio progression')
            result['first_progress'] = started_playback
            before = sample('playing first sample')
            time.sleep(.55)
            after = sample('playing second sample')
            result['playing_samples'] = [before, after]
            m1, m2 = before['media'], after['media']
            assert m2['src'].endswith('.mp3') and m2['duration'] > 1, m2
            assert not m2['paused'] and not m2['muted'] and m2['volume'] == 1 and m2['error'] is None, m2
            assert m2['currentTime'] - m1['currentTime'] > .2, [m1, m2]
            assert m2['decodedBytes'] is None or m2['decodedBytes'] > 0, m2
            if not control:
                assert any(g['trusted'] and g['active'] for g in after['audit']['gestures']), after
                result['trusted_gestures'] = after['audit']['gestures']
            if scenario == 'pending':
                click('#snooze-btn')
                stopped = until(lambda s: not s['alarmVisible'] and s['media']['paused'], 'paused on Snooze')
                time.sleep(.35)
                stopped_later = sample('paused progression sample')
                result['stopped_samples'] = [stopped, stopped_later]
                assert stopped_later['media']['paused'] and abs(stopped_later['media']['currentTime'] - stopped['media']['currentTime']) < .05
                db = fixture(user)
                assert not db['logs'] and not db['medicines'][0]['is_due'] and db['medicines'][0]['snoozed_until']
            result['status'] = 'PASS'
            return result
        except Exception as error:
            result['status'] = 'FAIL'; result['error'] = str(error)
            try: result['failure_state'] = sample('failure state')
            except Exception: pass
            raise
        finally:
            try: page.screenshot(path=str(output / 'final.png'), full_page=True)
            except Exception: pass
            (output / 'results.json').write_text(json.dumps(result, indent=2))
            ctx.close(); transcript.close()
