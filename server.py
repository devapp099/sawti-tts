"""Sawti development server. Python 3.11+. Run: python server.py."""
import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent / 'static'
SLOTS = threading.BoundedSemaphore(2)
VOICES = {
    'ar-OM-AbdullahNeural': 'عبدالله — عُمان',
    'ar-OM-AyshaNeural': 'عائشة — عُمان',
    'ar-SA-HamedNeural': 'حامد — السعودية',
    'ar-SA-ZariyahNeural': 'زارية — السعودية',
    'ar-AE-HamdanNeural': 'حمدان — الإمارات',
    'ar-AE-FatimaNeural': 'فاطمة — الإمارات',
    'ar-EG-ShakirNeural': 'شاكر — مصر',
    'ar-EG-SalmaNeural': 'سلمى — مصر',
    'en-US-JennyNeural': 'Jenny — English',
}


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('صيغة الطلب غير صحيحة.')
    text = data.get('text')
    voice = data.get('voice', 'ar-OM-AbdullahNeural')
    rate = data.get('rate', 0)
    if not isinstance(text, str) or not text.strip() or len(text) > 5000:
        raise ValueError('اكتب نصًا من حرف واحد إلى 5000 حرف.')
    if not isinstance(voice, str) or voice not in VOICES:
        raise ValueError('اختر صوتًا من القائمة.')
    if type(rate) is not int or not -50 <= rate <= 50:
        raise ValueError('السرعة يجب أن تكون بين ‎-50 و50.')
    return text.strip(), voice, rate


async def synthesize(text, voice, rate):
    import edge_tts
    audio = bytearray()
    async with asyncio.timeout(90):
        async for chunk in edge_tts.Communicate(text, voice, rate=f'{rate:+d}%').stream():
            if chunk['type'] == 'audio':
                audio.extend(chunk['data'])
                if len(audio) > 12_000_000:
                    raise ValueError('audio limit')
    if not audio:
        raise ValueError('empty audio')
    return bytes(audio)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(100)

    def reply(self, code, body, kind='application/json; charset=utf-8'):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
        if kind == 'audio/mpeg':
            self.send_header('Content-Disposition', 'attachment; filename="sawti.mp3"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/voices':
            return self.reply(200, {'voices': VOICES})
        if self.path == '/health':
            return self.reply(200, {'status': 'ok'})
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path not in files:
            return self.reply(404, {'error': 'الصفحة غير موجودة.'})
        name, kind = files[self.path]
        self.reply(200, (ROOT / name).read_bytes(), kind)

    def do_POST(self):
        if self.path != '/api/tts':
            return self.reply(404, {'error': 'المسار غير موجود.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'أرسل الطلب بصيغة JSON.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 40000:
                return self.reply(413, {'error': 'حجم الطلب غير مسموح.'})
            args = validate(json.loads(self.rfile.read(length)))
        except (ValueError, UnicodeError):
            return self.reply(400, {'error': 'تحقق من النص والصوت والسرعة؛ الحد الأقصى 5000 حرف.'})
        if not SLOTS.acquire(blocking=False):
            return self.reply(429, {'error': 'الخدمة مشغولة، حاول بعد قليل.'})
        try:
            audio = asyncio.run(synthesize(*args))
        except Exception:
            return self.reply(502, {'error': 'تعذر توليد الصوت. تحقق من اتصال الخادم وحاول مجددًا أو اختر صوتًا آخر.'})
        finally:
            SLOTS.release()
        self.reply(200, audio, 'audio/mpeg')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    print(f'Sawti: http://localhost:{port}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
