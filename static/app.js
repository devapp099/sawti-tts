'use strict';
const $ = id => document.getElementById(id);
let audioUrl = null;
let busy = false;
function status(message, error = false) {
  $('status').textContent = message;
  $('status').className = error ? 'error' : '';
}
function discardAudio() {
  $('player').pause();
  $('player').removeAttribute('src');
  $('player').load();
  $('result').hidden = true;
  $('download').removeAttribute('href');
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = null;
}
function changed() {
  $('count').textContent = `${$('text').value.length} / 5000 حرف`;
  discardAudio();
}
$('text').addEventListener('input', changed);
$('voice').addEventListener('change', discardAudio);
$('rate').addEventListener('input', () => {
  const rate = Number($('rate').value);
  $('speed').textContent = rate === 0 ? 'عادية' : `${rate > 0 ? '+' : ''}${rate}%`;
  discardAudio();
});
$('example').addEventListener('click', () => {
  $('text').value = 'مرحبًا بك في صوتي. هنا تتحول كلماتك إلى صوت، وتصبح أفكارك أقرب إلى من يستمع إليها.';
  changed();
});
$('clear').addEventListener('click', () => { $('text').value = ''; changed(); $('text').focus(); });
async function loadVoices() {
  try {
    const response = await fetch('/api/voices');
    if (!response.ok) throw new Error();
    const { voices } = await response.json();
    $('voice').replaceChildren();
    for (const [id, name] of Object.entries(voices)) {
      const option = document.createElement('option');
      option.value = id; option.textContent = name; $('voice').append(option);
    }
    if (!$('voice').options.length) throw new Error();
    $('voice').disabled = false; $('generate').disabled = false;
    status('جاهز. اكتب نصك واختر الصوت المناسب.');
  } catch {
    status('تعذر الاتصال بالخادم. شغّل التطبيق باستخدام الخادم ثم أعد تحميل الصفحة.', true);
  }
}
$('studio').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy) return;
  const text = $('text').value.trim();
  if (!text) return status('اكتب النص أولًا.', true);
  busy = true; discardAudio();
  const controls = [...$('studio').querySelectorAll('input, textarea, select, button')];
  const previous = controls.map(control => control.disabled);
  controls.forEach(control => { control.disabled = true; });
  $('generate').textContent = 'جارٍ توليد الصوت…';
  status('نجهّز ملفك الصوتي. قد يستغرق النص الطويل بعض الوقت.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 100000);
  try {
    const response = await fetch('/api/tts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice: $('voice').value, rate: Number($('rate').value) }),
      signal: controller.signal
    });
    if (!response.ok) {
      let message = 'تعذر توليد الصوت. حاول مجددًا.';
      try { message = (await response.json()).error || message; } catch {}
      throw new Error(message);
    }
    if (!response.headers.get('Content-Type')?.startsWith('audio/mpeg')) throw new Error('استجابة صوتية غير صالحة.');
    const blob = await response.blob();
    if (!blob.size) throw new Error('الملف الصوتي فارغ. حاول مجددًا.');
    audioUrl = URL.createObjectURL(blob);
    $('player').src = audioUrl;
    $('download').href = audioUrl;
    $('result').hidden = false;
    status('اكتمل التحويل. يمكنك الاستماع أو تنزيل ملف MP3.');
    $('result').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (error) {
    status(error.name === 'AbortError' ? 'انتهت مهلة الانتظار. جرّب نصًا أقصر.' : error.message, true);
  } finally {
    clearTimeout(timer); busy = false;
    controls.forEach((control, i) => { control.disabled = previous[i]; });
    $('generate').textContent = 'تحويل إلى صوت ←';
  }
});
window.addEventListener('pagehide', () => { if (audioUrl) URL.revokeObjectURL(audioUrl); });
loadVoices();
