import sys, os, math, socket, threading, datetime, time, webbrowser, requests
import json, re, queue, random, uuid
import pyttsx3
import speech_recognition as sr
import pyautogui
import pywhatkit
import cv2

try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    _HAS_PSUTIL = False

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QScrollArea, QTextEdit, QSlider, QSizePolicy,
    QDialog, QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect, QPointF
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont,
    QRadialGradient, QLinearGradient, QPainterPath
)

# ══════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════
AI_NAME           = "ORION"
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_SECRET    = os.getenv("SPOTIFY_SECRET", "")
SPOTIFY_USERNAME  = os.getenv("SPOTIFY_USERNAME", "")
SPOTIFY_REDIRECT  = "http://localhost:8888/callback"

# Everything ORION remembers (memory + API keys) lives in this folder.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ORION_Data")
os.makedirs(DATA_DIR, exist_ok=True)

# Kitni der PC se door rahoge to ORION maanega ki tum bahar gaye the aur ab wapas aaye.
# (Testing ke liye 20 kar do.)
AWAY_MIN_SECONDS = 180
# Raat bhar ORION chalta rahe to subah is ghante ke baad khud sawaal poochega.
DAILY_THINK_HOUR = 7


# ── Wake Word Settings ──
WAKE_WORDS = [
    "orion", "wake up", "hey orion", "hi orion", "hello orion",
    "are you there", "i need you", "listen up",
    "utho", "jago", "sun", "suno", "uth jao", "jaag jao",
    "orion utho", "orion jago", "orion suno", "bolo",
    "orion uth", "chalu ho", "active ho",
    "उठो", "जागो", "सुनो", "ऑरियन", "चालू हो",
    "see me", "watch me", "dekho mujhe", "camera on",
    "moment on", "detector chalu", "moments capture",
]
SLEEP_WORDS = [
    "go to sleep", "sleep", "bye", "goodbye", "stop listening",
    "rest now", "that's all",
    "so jao", "band ho", "rest karo", "bas karo", "chup ho jao",
    "bye orion", "alvida", "khatam",
    "सो जाओ", "बंद हो", "अलविदा", "बस करो",
]

# ── HUD Color Scheme (cyan, Iron Man style) ──
COL_ACCENT  = QColor(0, 200, 255)      # cyan — primary HUD color
COL_ACCENT2 = QColor(0, 140, 255)      # deeper blue accent
COL_TEXT    = QColor(225, 245, 255)
COL_GREEN   = QColor(70, 230, 150)
COL_ORANGE  = QColor(255, 150, 40)
COL_PURPLE  = QColor(170, 90, 255)
COL_RED     = QColor(255, 80, 80)

CYAN_HEX    = "rgb(0,200,255)"

STATE_COLORS = {
    "idle":      COL_ACCENT,
    "listening": COL_ORANGE,
    "thinking":  COL_ACCENT2,
    "speaking":  COL_GREEN,
    "detecting": COL_PURPLE,
}

# ══════════════════════════════════════════════
#  MOMENT DETECTOR CONFIG
# ══════════════════════════════════════════════
MOMENTS_FOLDER    = "ORION_Moments"
FACE_COOLDOWN     = 5
SMILE_COOLDOWN    = 4
MOTION_COOLDOWN   = 8
MOTION_THRESHOLD  = 1500

_CV_DATA      = cv2.data.haarcascades
_face_cascade  = cv2.CascadeClassifier(os.path.join(_CV_DATA, "haarcascade_frontalface_default.xml"))
_smile_cascade = cv2.CascadeClassifier(os.path.join(_CV_DATA, "haarcascade_smile.xml"))

# ══════════════════════════════════════════════
#  LANGUAGE DETECTION
# ══════════════════════════════════════════════
HINDI_WORDS = {
    "खोलो","बंद","करो","चलाओ","बजाओ","दिखाओ","बताओ","समय","तारीख","मौसम",
    "आज","कल","अभी","यहाँ","वहाँ","कैसे","क्या","कौन","कहाँ","क्यों",
    "हाँ","नहीं","ठीक","धन्यवाद","शुक्रिया","नमस्ते","सुनो","देखो","लिखो",
    "पानी","खाना","गाना","संगीत","फ़ोटो","कैमरा","स्क्रीनशॉट","आवाज़",
    "बढ़ाओ","घटाओ","बंद करो","चालू करो","रोको","बात","मदद","क्लियर",
    "मेरा","तुम","मैं","हम","वो","यह","वह","इसे","उसे"
}
HINGLISH_WORDS = {
    "kholo","close","run","bajao","chalao","dikhao","batao","band",
    "chalu","rok","sun","dekh","likh","gana","music","camera",
    "screenshot","time","date","aaj","kal","abhi","weather","mausam",
    "madad","help","clear","volume","mute","lock","shutdown","restart",
    "search","play","open","next","prev","previous","pause",
    "resume","baat","theek","nahi","haan","dhanyawad","shukriya",
    "namaste","orion","bhai","yaar","dost","kya","kaisa","kahan",
    "kitna","kyun","kaun","kab","kis","kaise","see","me","watch"
}

def detect_language(text):
    words = text.lower().split()
    hindi_score    = sum(1 for w in text.split() if w in HINDI_WORDS)
    hinglish_score = sum(1 for w in words if w in HINGLISH_WORDS)
    if hindi_score > 0:
        return "hindi"
    elif hinglish_score >= 1:
        return "hinglish"
    else:
        return "english"

# ══════════════════════════════════════════════
#  MULTILINGUAL RESPONSES
# ══════════════════════════════════════════════
RESPONSES = {
    "online":       ("ORION ऑनलाइन है। बोलिए, मैं सुन रहा हूँ।",
                     "ORION online hai. Bolo, main sun raha hoon.",
                     "ORION online. I'm listening."),
    "wake":         ("जी हाँ! मैं यहाँ हूँ। बोलिए।",
                     "Haan bolo! Main hazir hoon.",
                     "Yes! I'm awake. What do you need?"),
    "sleep":        ("ठीक है, सो रहा हूँ। 'ORION उठो' बोलें जब ज़रूरत हो।",
                     "Theek hai, so raha hoon. 'ORION utho' bolo jab zaroorat ho.",
                     "Going to sleep. Say 'wake up ORION' when you need me."),
    "already_awake":("मैं पहले से जाग रहा हूँ! बोलिए।",
                     "Main pehle se jaag raha hoon! Bolo.",
                     "I'm already awake! Go ahead."),
    "not_understood":("समझ नहीं आया, दोबारा बोलिए।",
                      "Samajh nahi aaya, dobara bolo.",
                      "Sorry, I didn't understand. Please try again."),
    "chrome_open":  ("क्रोम खुल रहा है।","Chrome khul raha hai.","Opening Chrome."),
    "notepad_open": ("नोटपैड खुल रहा है।","Notepad khul raha hai.","Opening Notepad."),
    "calc_open":    ("कैलकुलेटर खुल रहा है।","Calculator khul raha hai.","Opening Calculator."),
    "taskmgr_open": ("टास्क मैनेजर खुल रहा है।","Task Manager khul raha hai.","Opening Task Manager."),
    "youtube_open": ("यूट्यूब खुल रहा है।","YouTube khul raha hai.","Opening YouTube."),
    "whatsapp_open":("व्हाट्सएप खुल रहा है।","WhatsApp khul raha hai.","Opening WhatsApp."),
    "instagram_open":("इंस्टाग्राम खुल रहा है।","Instagram khul raha hai.","Opening Instagram."),
    "spotify_open": ("स्पॉटिफ़ाई खुल रहा है।","Spotify khul raha hai.","Opening Spotify."),
    "music_pause":  ("संगीत रोक दिया।","Music pause kar diya.","Music paused."),
    "music_play":   ("संगीत चला दिया।","Music play kar diya.","Music resumed."),
    "music_next":   ("अगला गाना।","Next track.","Next track."),
    "music_prev":   ("पिछला गाना।","Previous track.","Previous track."),
    "vol_up":       ("आवाज़ बढ़ा दी।","Volume up kar diya.","Volume increased."),
    "vol_down":     ("आवाज़ घटा दी।","Volume down kar diya.","Volume decreased."),
    "mute":         ("म्यूट किया।","Mute kar diya.","Muted."),
    "screenshot":   ("स्क्रीनशॉट ले लिया।","Screenshot le liya.","Screenshot taken."),
    "camera_on":    ("कैमरा चालू। Q दबाएँ बंद करने के लिए।","Camera on. Q dabao band karne ke liye.","Camera on. Press Q to close."),
    "camera_already":("कैमरा पहले से चालू है।","Camera pehle se on hai.","Camera is already on."),
    "camera_not_found":("कैमरा नहीं मिला।","Camera nahi mila.","Camera not found."),
    "camera_off":   ("कैमरा बंद।","Camera off.","Camera off."),
    "lock":         ("कंप्यूटर लॉक हो रहा है।","Computer lock ho raha hai.","Locking the computer."),
    "shutdown_confirm":("शटडाउन के लिए 'confirm shutdown' लिखें।","Shutdown ke liye 'confirm shutdown' likho.","Type 'confirm shutdown' to confirm."),
    "shutdown_now": ("5 सेकंड में शटडाउन।","5 second mein shutdown.","Shutting down in 5 seconds."),
    "restart_confirm":("रीस्टार्ट के लिए 'confirm restart' लिखें।","Restart ke liye 'confirm restart' likho.","Type 'confirm restart' to confirm."),
    "restart_now":  ("रीस्टार्ट हो रहा है।","Restarting.","Restarting now."),
    "chat_clear":   ("चैट क्लियर। नई शुरुआत!","Chat clear. Fresh start!","Chat cleared. Fresh start!"),
    "spotify_na":   ("स्पॉटिफ़ाई कनेक्ट नहीं है।","Spotify connected nahi hai.","Spotify is not connected."),
    "weather_fail": ("मौसम की जानकारी नहीं मिली।","Weather fetch nahi ho saka.","Could not fetch weather."),
    "searching":    ("खोज रहा हूँ: ","Search kar raha hoon: ","Searching for: "),
    "playing":      ("बजा रहा हूँ: ","Play kar raha hoon: ","Playing: "),
    "no_key":       ("कोई API key सेट नहीं है।","Koi API key set nahi hai. Manage API Keys kholo.","No API key is set. Open Manage API Keys and add one."),
    "internet_error":("इंटरनेट चेक करें।","Internet check karo.","Please check your internet connection."),
    "timeout":      ("जवाब नहीं आया, दोबारा कोशिश करें।","Response nahi aaya, dobara try karo.","Response timed out. Please try again."),
    "rate_limit":   ("बहुत ज़्यादा अनुरोध, थोड़ी देर बाद कोशिश करें।","Bahut requests ho gayi, thodi der baad try karo.","Rate limit hit. Please try again shortly."),
    "detector_on":  ("मोमेंट डिटेक्टर चालू! आपके सारे पल कैप्चर होंगे।",
                     "Moment detector on! Aapke saare moments capture karunga.",
                     "Moment detector on! I'll capture all your moments."),
    "detector_off": ("मोमेंट डिटेक्टर बंद।","Moment detector band.","Moment detector off."),
    "detector_already_on": ("डिटेक्टर पहले से चालू है!","Detector pehle se on hai!","Detector is already running!"),
    "detector_already_off":("डिटेक्टर पहले से बंद है।","Detector pehle se off hai.","Detector is already off."),
    "face_snap":    ("चेहरा देखा! पल कैप्चर किया।","Chehra dekha! Moment snap kiya.","Face detected! Moment captured."),
    "smile_snap":   ("मुस्कुराहट! फ़ोटो ले ली।","Muskurahate ho! Snap le liya.","Beautiful smile! Snap taken."),
    "motion_snap":  ("कुछ हिला! पल सेव किया।","Kuch hila! Moment save kiya.","Motion detected! Moment saved."),
    "detector_stats":("","",""),
    "speak_mode_on":  ("स्पीक मोड चालू! अब बस बोलिए, मैं लगातार सुनूंगा और जवाब दूंगा।",
                       "Speak mode on! Ab bas bolo, main continuously sunte rahunga aur jawab dunga.",
                       "Speak mode on! Just talk — I'll keep listening and replying continuously."),
    "speak_mode_off": ("स्पीक मोड बंद। अब मुझे टाइप करके या माइक दबाकर बुलाइए।",
                       "Speak mode band. Ab type karke ya mic dabakar bulao.",
                       "Speak mode off. Type or tap the mic to talk to me now."),
}

_current_lang = "hinglish"

# ORION understands Hindi/Hinglish/English input (detect_language() above,
# used for the console's language badge and for handle_command's keyword
# matching) but it ALWAYS talks back in English — so `say()` always pulls
# the English (index 2) string from RESPONSES no matter what language the
# person used.
def say(key, extra=""):
    base = RESPONSES.get(key, ("", "", ""))[2]
    return base + extra

# ══════════════════════════════════════════════
#  CONVERSATION MEMORY
# ══════════════════════════════════════════════
conversation_history = []

# ══════════════════════════════════════════════
#  TTS ENGINE
# ══════════════════════════════════════════════
# NOTE ON HINDI AUDIO: pyttsx3 does not synthesize speech itself — on Windows
# it drives whatever SAPI5 voices are installed in the OS. If no Hindi voice
# (e.g. "Microsoft Hemant", "Microsoft Kalpana", "Microsoft Heera") is
# installed under Settings > Time & Language > Speech, ORION physically has
# no Hindi voice to use and will always fall back to the English one, no
# matter how good the language detection is. Install a Hindi voice first —
# this fix makes ORION *use* it correctly once it's there.
_speak_lock   = threading.Lock()
_hindi_voice_id   = None
_default_voice_id = None
_voices_scanned   = False

_HINDI_VOICE_HINTS = ("hindi", "hi-in", "heera", "kalpana", "hemant")

def _scan_voices():
    """Find and cache a Hindi voice id + a default voice id (once)."""
    global _hindi_voice_id, _default_voice_id, _voices_scanned
    if _voices_scanned:
        return
    try:
        probe = pyttsx3.init()
        voices = probe.getProperty("voices")
        for v in voices:
            name = (v.name or "").lower()
            vid  = (v.id or "").lower()
            langs = " ".join(str(l) for l in (getattr(v, "languages", None) or [])).lower()
            if any(h in name or h in vid or h in langs for h in _HINDI_VOICE_HINTS):
                if not _hindi_voice_id:
                    _hindi_voice_id = v.id
            if not _default_voice_id:
                _default_voice_id = v.id
        probe.stop()
        if not _hindi_voice_id:
            print("[TTS] No Hindi system voice found. ORION will speak Hindi/Hinglish "
                  "text with the default English voice (readable, but not native "
                  "pronunciation). Install a Hindi voice in Windows Speech settings "
                  "for proper Hindi audio.")
    except Exception as e:
        print(f"[TTS] voice scan failed: {e}")
    _voices_scanned = True

def _init_tts():
    """Kept for compatibility with main()'s startup call."""
    _scan_voices()

# ── "Strong speak system" ─────────────────────────────────────────────────
# One long-lived worker thread + a queue. Every speak() call is queued, so
# two lines of speech can never overlap or fight over the audio device, long
# answers are spoken sentence-by-sentence (so they can be interrupted), and
# TTS.stop() ("stop speaking" / "chup raho") cuts ORION off mid-sentence.
# A fresh pyttsx3 engine is still created per sentence (the SAPI5 fix).
_SPEAK_HOOK = None

def set_speech_hook(fn):
    """Window registers a callback that runs the moment ORION is about to talk
    (used to mute the Speak-Mode mic so ORION never hears itself)."""
    global _SPEAK_HOOK
    _SPEAK_HOOK = fn

def _clean_for_speech(text):
    """Strip markdown/URLs so TTS doesn't read 'asterisk asterisk' or a long link."""
    t = re.sub(r"https?://\S+", " link ", str(text))
    t = re.sub(r"[`*_#~>|]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _split_for_speech(text, limit=220):
    out = []
    for p in re.split(r"(?<=[.!?।])\s+", text):
        p = p.strip()
        while len(p) > limit:
            cut = p.rfind(",", 0, limit)
            if cut < 60:
                cut = p.rfind(" ", 0, limit)
            if cut < 1:
                cut = limit
            out.append(p[:cut].strip(" ,"))
            p = p[cut:].strip(" ,")
        if p:
            out.append(p)
    return out

class SpeechEngine:
    def __init__(self, rate=165):
        self.rate = rate
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self._current = None
        self._pending = 0
        self._gen = 0
        threading.Thread(target=self._worker, daemon=True).start()

    def say(self, text):
        chunks = _split_for_speech(text)
        if not chunks:
            return
        with self._lock:
            self._pending += len(chunks)
            gen = self._gen
        for c in chunks:
            self._q.put((gen, c))

    def busy(self):
        return self._pending > 0

    def stop(self):
        """Interrupt the sentence being spoken and drop everything queued."""
        with self._lock:
            self._gen += 1
            try:
                while True:
                    self._q.get_nowait()
                    self._pending -= 1
            except queue.Empty:
                pass
            eng = self._current
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                pass

    def _worker(self):
        while True:
            gen, text = self._q.get()
            with self._lock:
                stale = (gen != self._gen)
            if not stale:
                self._speak_one(text)
            with self._lock:
                self._pending = max(0, self._pending - 1)

    def _speak_one(self, text):
        _scan_voices()
        for attempt in range(2):          # one automatic retry if the engine hiccups
            eng = None
            try:
                eng = pyttsx3.init()
                eng.setProperty("rate", self.rate)
                if _default_voice_id:
                    eng.setProperty("voice", _default_voice_id)
                with self._lock:
                    self._current = eng
                eng.say(text)
                eng.runAndWait()
                return
            except Exception as e:
                print(f"[TTS] {e}")
                time.sleep(0.3)
            finally:
                with self._lock:
                    self._current = None
                try:
                    if eng is not None:
                        eng.stop()
                except Exception:
                    pass

TTS = SpeechEngine()

def speak(text, lang=None):
    if not text:
        return
    # ORION always SPEAKS in English (see note above say()). `lang` is kept
    # only so old call sites keep working.
    print(f"\n{AI_NAME}: {text}")
    clean = _clean_for_speech(text)
    if not clean:
        return
    if _SPEAK_HOOK:
        try:
            _SPEAK_HOOK()
        except Exception:
            pass
    TTS.say(clean)

# ══════════════════════════════════════════════
#  LONG-TERM MEMORY  (survives restarts — saved in ORION_Data/orion_memory.json)
# ══════════════════════════════════════════════
# What it remembers:
#   • Facts you ask it to keep   ("remember that ..." / "yaad rakho ...")
#   • Trips   — "I'm going to the market" / "market ja raha hoon" → ORION notes
#               you're out, and when you come back it welcomes you home and
#               asks how it went (it notices you return via keyboard/mouse
#               activity, or when you say "I'm back" / "aa gaya").
#   • A daily log of what you talked about, so the NEXT day ORION can think
#     about it by itself and ask you a follow-up question.
def _now():
    return datetime.datetime.now()

def _iso(dt=None):
    return (dt or _now()).isoformat(timespec="seconds")

def _from_iso(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None

def daypart(h=None):
    h = _now().hour if h is None else h
    return "morning" if h < 12 else ("afternoon" if h < 17 else "evening")

def _human_minutes(m):
    m = max(1, int(m))
    if m < 60:
        return f"{m} minute{'s' if m != 1 else ''}"
    h, r = divmod(m, 60)
    s = f"{h} hour{'s' if h != 1 else ''}"
    return s + (f" {r} minutes" if (r >= 10 and h < 5) else "")

def user_idle_seconds():
    """Seconds since the last keyboard/mouse input (Windows). None elsewhere."""
    try:
        import ctypes
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        li = LASTINPUTINFO(); li.cbSize = ctypes.sizeof(li)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:
        pass
    return None

# alias word (what you say) → canonical place name
_PLACE_ALIASES = {
    "market": "market", "bazaar": "market", "bazar": "market", "mandi": "market",
    "sabzi mandi": "market", "mall": "mall", "shop": "shop", "store": "store",
    "dukaan": "shop", "dukan": "shop", "shopping": "shopping",
    "office": "office", "work": "work", "kaam": "work", "job": "work",
    "college": "college", "school": "school", "university": "university",
    "class": "class", "tuition": "tuition", "coaching": "coaching",
    "gym": "gym", "hospital": "hospital", "doctor": "doctor", "clinic": "clinic",
    "temple": "temple", "mandir": "temple", "park": "park", "bank": "bank",
    "station": "station", "airport": "airport", "party": "party",
    "wedding": "wedding", "shaadi": "wedding", "meeting": "meeting",
    "movie": "movie", "cinema": "movie", "theatre": "movie",
    "cafe": "cafe", "restaurant": "restaurant", "walk": "walk", "jog": "jog",
    "ghumne": "outing", "ghoomne": "outing", "outing": "outing", "trip": "trip",
    "friend": "friend's place", "friends": "friend's place", "dost": "friend's place",
    # Devanagari
    "बाजार": "market", "बाज़ार": "market", "मार्केट": "market", "मंडी": "market",
    "दुकान": "shop", "ऑफिस": "office", "काम": "work", "कॉलेज": "college",
    "स्कूल": "school", "जिम": "gym", "अस्पताल": "hospital", "डॉक्टर": "doctor",
    "मंदिर": "temple", "पार्क": "park", "बैंक": "bank", "स्टेशन": "station",
    "शादी": "wedding", "दोस्त": "friend's place",
}
_ASCII_PL = "|".join(sorted((re.escape(k) for k in _PLACE_ALIASES if k.isascii()), key=len, reverse=True))
_DEVA_PL  = "|".join(sorted((re.escape(k) for k in _PLACE_ALIASES if not k.isascii()), key=len, reverse=True))
_FILL = r"(?:out|to|for|towards|the|a|an|my|local|nearby|nearest|big|small|new|some|vegetable|sabzi|short|quick)"
_HI_VERB = (r"(?:j(?:a|aa)\s*(?:raha|rha|rahi|rhi|ra)\b|jaunga\b|jaungi\b|"
            r"jata\s*h\w+|jaata\s*h\w+|nikal\s*(?:raha|rha|rahi|rhi)\b)")
_RE_DEP_EN = re.compile(
    r"\b(?:going|goin|heading|headed|leaving|gonna go|will go|need to go|have to go|off)\b"
    r"(?:\s+" + _FILL + r")*\s+(?P<p>" + _ASCII_PL + r")\b")
_RE_DEP_HING = re.compile(
    r"\b(?P<p>" + _ASCII_PL + r")\s+(?:ke\s+liye\s+|tak\s+|pe\s+|par\s+|ko\s+)?" + _HI_VERB)
_RE_DEP_DEVA = re.compile(
    r"(?P<p>" + _DEVA_PL + r")\s*(?:को\s+|के\s+लिए\s+|तक\s+)?"
    r"(?:जा\s*रहा|जा\s*रही|जाऊंगा|जाऊँगा|जाउंगा|निकल\s*रहा|निकल\s*रही)")
_RE_DEP_OUT = re.compile(
    r"\b(?:going|heading|goin)\s+out\b(?!\s+of)|\bbahar\s+(?:ja|jaa)\s*(?:raha|rha|rahi|rhi)\b|बाहर\s+जा\s*रह")
_CONT_WORDS = {"on", "with", "out", "through", "hard", "harder", "more", "the", "a", "an",
               "my", "this", "that", "it", "some", "upon", "together", "from"}
_RE_NEG  = re.compile(r"\b(?:not|don't|dont|won't|wont|never|nahi|nahin|mat|was|were|yesterday|last|kal)\b|नहीं|कल")
_RE_RET_STRONG = re.compile(
    r"\b(?:i(?:'m| am|'ve| have)?|im|just)\s+(?:back|home|returned|reached\s+home)\b"
    r"|\b(?:got|came|coming|reached|returned)\s+(?:back|home)\b|\bback\s+(?:home|from)\b"
    r"|\bghar\s+(?:aa|pahunch|aagaya)\w*|\b(?:wapas|vapas|waapas)\s+(?:aa|aaya|aayi)\w*"
    r"|\blaut\s+(?:aaya|aayi)\b|वापस\s+आ|घर\s+(?:आ|पहुँच|पहुंच)")
_RE_RET_WEAK = re.compile(r"\b(?:aa|a)\s*g(?:aya|ya|ayi|yi)\b|आ\s+गया|आ\s+गयी|आ\s+गई")

_GOING = {"work": "to work", "college": "to college", "school": "to school",
          "university": "to university", "class": "to class", "tuition": "to tuition",
          "coaching": "to coaching", "walk": "out for a walk", "jog": "out for a jog",
          "outing": "out for an outing", "trip": "out on a trip", "shopping": "shopping",
          "meeting": "to your meeting", "friend's place": "to your friend's place",
          "movie": "to the movie", "out": "out"}
_FROM  = {"work": "work", "college": "college", "school": "school", "university": "university",
          "class": "class", "tuition": "tuition", "coaching": "coaching", "walk": "your walk",
          "jog": "your jog", "outing": "your outing", "trip": "your trip",
          "shopping": "shopping", "meeting": "your meeting", "friend's place": "your friend's place",
          "movie": "the movie", "out": "outside"}
_PLACE_Q = {}
for _grp, _q in [
    (("market", "mall", "shop", "store", "shopping"), "Did you find everything you needed?"),
    (("office", "work", "meeting"), "How did it go? Anything I should help you follow up on?"),
    (("college", "school", "university", "class", "tuition", "coaching"), "How was it? Learn anything interesting?"),
    (("gym", "walk", "jog"), "Good session? I hope you feel great."),
    (("hospital", "doctor", "clinic"), "I hope everything is fine. How did it go?"),
    (("party", "wedding", "outing", "trip", "movie", "cafe", "restaurant", "park", "friend's place"),
     "Did you have a good time?"),
]:
    for _p in _grp:
        _PLACE_Q[_p] = _q

_GENERIC_QUESTIONS = [
    "What's the one thing you most want to finish today, sir?",
    "Is there anything you'd like me to keep track of for you today?",
    "How are you feeling today, sir? Anything I can take off your plate?",
    "Is there a new feature you'd like to add to me today?",
]

class OrionMemory:
    MAX_FACTS = 100
    KEEP_DAYS = 14
    MAX_MSGS_PER_DAY = 60

    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        self.data = {"facts": [], "events": [], "daily": {}, "meta": {}}
        self._load()
        m = self.data["meta"]
        m.setdefault("first_run", _iso())
        self.prev_seen = _from_iso(m.get("last_seen", ""))   # when ORION was last running
        m["last_seen"] = _iso()
        self._prune()
        self.save()

    # ── storage ──
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                for k, default in list(self.data.items()):
                    if isinstance(d.get(k), type(default)):
                        self.data[k] = d[k]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[MEMORY] could not read memory file ({e}); keeping a backup and starting fresh.")
            try:
                os.replace(self.path, self.path + ".bak")
            except Exception:
                pass

    def save(self):
        with self._lock:
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
            except Exception as e:
                print(f"[MEMORY] save failed: {e}")

    def touch(self):
        self.data["meta"]["last_seen"] = _iso()

    def _prune(self):
        with self._lock:
            cutoff = (_now() - datetime.timedelta(days=self.KEEP_DAYS)).date().isoformat()
            for d in [d for d in self.data["daily"] if d < cutoff]:
                del self.data["daily"][d]
            ev_cut = _now() - datetime.timedelta(days=30)
            self.data["events"] = [e for e in self.data["events"]
                                   if (_from_iso(e.get("ts", "")) or _now()) > ev_cut][-60:]
            self.data["facts"] = self.data["facts"][-self.MAX_FACTS:]

    def wipe(self):
        with self._lock:
            first = self.data["meta"].get("first_run", _iso())
            self.data = {"facts": [], "events": [], "daily": {}, "meta": {"first_run": first, "last_seen": _iso()}}
            self.save()

    # ── facts ──
    def add_fact(self, text):
        text = text.strip().rstrip(".")
        if not text:
            return False
        with self._lock:
            if any(f["text"].lower() == text.lower() for f in self.data["facts"]):
                return True
            self.data["facts"].append({"text": text[:200], "ts": _iso()})
            self._prune(); self.save()
        return True

    # ── daily log ──
    def log_user(self, text):
        text = (text or "").strip()
        if len(text) < 4:
            return
        with self._lock:
            day = self.data["daily"].setdefault(_now().date().isoformat(), {"msgs": []})
            day["msgs"].append(text[:160])
            day["msgs"] = day["msgs"][-self.MAX_MSGS_PER_DAY:]

    def _last_active_day(self):
        today = _now().date().isoformat()
        for d in sorted(self.data["daily"], reverse=True):
            if d != today and self.data["daily"][d].get("msgs"):
                return d, self.data["daily"][d]["msgs"]
        return None, []

    # ── trips (going out / coming back) ──
    def parse_departure(self, text):
        t = (text or "").strip().lower()
        if not t or t.endswith("?") or len(t.split()) > 14 or _RE_NEG.search(t):
            return None
        for rx in (_RE_DEP_EN, _RE_DEP_HING, _RE_DEP_DEVA):
            m = rx.search(t)
            if m:
                # "going to work ON my project", "going to park THE car" are not trips.
                if rx is _RE_DEP_EN:
                    rest = t[m.end():].split()
                    if rest and rest[0] in _CONT_WORDS:
                        return None
                return _PLACE_ALIASES.get(m.group("p"), m.group("p"))
        if _RE_DEP_OUT.search(t):
            return "out"
        return None

    def parse_return(self, text):
        t = (text or "").strip().lower()
        if not t or t.endswith("?") or len(t.split()) > 12:
            return None
        if _RE_RET_STRONG.search(t):
            return "strong"
        if _RE_RET_WEAK.search(t):
            return "weak"
        return None

    def add_out(self, place, raw=""):
        with self._lock:
            for e in self.data["events"]:
                if e.get("kind") == "out" and e.get("status") == "open":
                    e["status"] = "closed"
            ev = {"id": uuid.uuid4().hex[:8], "kind": "out", "place": place,
                  "raw": raw[:120], "ts": _iso(), "status": "open", "reply": ""}
            self.data["events"].append(ev)
            self.save()
            return ev

    def open_out(self):
        with self._lock:
            for e in reversed(self.data["events"]):
                if e.get("kind") == "out" and e.get("status") == "open":
                    return e
        return None

    def close_event(self, eid):
        with self._lock:
            for e in self.data["events"]:
                if e["id"] == eid:
                    e["status"] = "closed"; e["back_ts"] = _iso()
            self.save()

    def attach_reply(self, eid, text):
        with self._lock:
            for e in self.data["events"]:
                if e["id"] == eid:
                    e["reply"] = text.strip()[:200]
            self.save()

    def event_age_minutes(self, ev):
        t = _from_iso(ev.get("ts", ""))
        return (_now() - t).total_seconds() / 60.0 if t else 0

    def ack_text(self, place):
        going = _GOING.get(place, f"to the {place}")
        return random.choice([
            f"Noted, sir. Heading {going}. I'll be right here when you're back.",
            f"Understood, sir. Have a safe trip {going}. I'll be here when you return.",
            f"Alright, sir — {going}. Take care, I'll keep things running.",
        ])

    def welcome_text(self, ev):
        place = ev.get("place", "out")
        frm = _FROM.get(place, f"the {place}")
        mins = self.event_age_minutes(ev)
        opener = random.choice(["Oh, welcome back, sir!", "Welcome home, sir!", "There you are, sir. Welcome back!"])
        when = f" after about {_human_minutes(mins)}" if mins >= 10 else ""
        q = _PLACE_Q.get(place, "How did it go?")
        if place == "out":
            return f"{opener} You're back{when}. How was your time outside?"
        return f"{opener} You're back from {frm}{when}. {q}"

    # ── "what do you remember" ──
    def summary_lines(self):
        lines = []
        with self._lock:
            for f in self.data["facts"][-15:]:
                lines.append(f"FACT   : {f['text']}")
            for e in self.data["events"][-8:]:
                st = "back" if e.get("status") == "closed" else "OUT NOW"
                rep = f" — you said: {e['reply']}" if e.get("reply") else ""
                lines.append(f"EVENT  : {e['ts'][:16].replace('T', ' ')} went to {e['place']} [{st}]{rep}")
            d, msgs = self._last_active_day()
            if d:
                lines.append(f"LAST DAY ({d}): " + " | ".join(m[:50] for m in msgs[-4:]))
        return lines or ["Memory is empty."]

    def spoken_summary(self):
        with self._lock:
            nf, ne = len(self.data["facts"]), len(self.data["events"])
            last = self.data["events"][-1] if self.data["events"] else None
        if not nf and not ne:
            return "My memory is empty so far, sir. Tell me things, or say remember that, and I'll keep them."
        s = f"I'm keeping {nf} thing{'s' if nf != 1 else ''} you asked me to remember and {ne} recent event{'s' if ne != 1 else ''}."
        if last:
            s += f" Most recently, you went to {_FROM.get(last['place'], 'the ' + last['place'])}."
        return s + " The full list is in the console."

    # ── context for the AI ──
    def context_for_prompt(self):
        parts = []
        with self._lock:
            facts = [f["text"] for f in self.data["facts"][-12:]]
            if facts:
                parts.append("Things the user asked you to remember: " + "; ".join(facts) + ".")
            recent = []
            for e in self.data["events"][-6:]:
                when = e["ts"][:16].replace("T", " ")
                line = f"- {when}: user went to {e['place']}" + (" (still out)" if e.get("status") == "open" else " (came back)")
                if e.get("reply"):
                    line += f"; afterwards they said: \"{e['reply']}\""
                recent.append(line)
            if recent:
                parts.append("Recent events:\n" + "\n".join(recent))
            d, msgs = self._last_active_day()
            if d:
                parts.append(f"On {d} (the last day you two talked) the user said: " + " | ".join(m[:100] for m in msgs[-6:]))
            pq = self.data["meta"].get("pending_question")
            if pq:
                parts.append(f"Your last proactive question to the user was: \"{pq}\" — they may be answering it now.")
        return "\n".join(parts)[:1400]

    # ── proactive question state ──
    def set_pending_question(self, q):
        self.data["meta"]["pending_question"] = q

    def clear_pending_question(self):
        self.data["meta"].pop("pending_question", None)

    def remember_question(self, q):
        with self._lock:
            qs = self.data["meta"].setdefault("last_questions", [])
            qs.append(q[:160]); self.data["meta"]["last_questions"] = qs[-6:]
            self.save()

    # ── next-day "thinking" ──
    def _has_history(self):
        d, _ = self._last_active_day()
        return bool(d or self.data["events"] or self.data["facts"])

    def needs_daily_think(self):
        today = _now().date().isoformat()
        with self._lock:
            if self.data["meta"].get("last_think_date") == today:
                return False
            if not self._has_history():
                self.data["meta"]["last_think_date"] = today; self.save()
                return False
        return True

    def mark_thought(self):
        with self._lock:
            self.data["meta"]["last_think_date"] = _now().date().isoformat()
            self.save()

    def build_think_prompt(self):
        prev = self.data["meta"].get("last_questions", [])
        return (f"It is {_now().strftime('%A, %d %B')} {daypart()}. Start the day proactively.\n"
                f"Here is what you remember about the user:\n{self.context_for_prompt() or '(little so far)'}\n\n"
                "Write ONE short, specific, warm question (max 25 words) to ask the user right now, based on that "
                "memory — follow up on something they did, a problem they were working on, or something they "
                "mentioned. If nothing specific stands out, ask something thoughtful about their goals for today. "
                f"Do NOT repeat these earlier questions: {prev}. "
                "No greeting, no preamble, no quotes, and do not say 'sir' — output only the question, in English.")

    def fallback_question(self):
        """Used when there's no API key / no internet: pick a question straight from memory."""
        y = (_now() - datetime.timedelta(days=1)).date().isoformat()
        for e in reversed(self.data["events"]):
            if e.get("kind") == "out" and e.get("ts", "")[:10] == y:
                return f"Yesterday you went to {_FROM.get(e['place'], 'the ' + e['place'])}. Did everything go the way you wanted?"
        d, msgs = self._last_active_day()
        for m in reversed(msgs):
            if len(m) > 14 and not m.lower().startswith(("open ", "play ", "search ")):
                return f"Yesterday you told me \"{m[:70]}\". Did that work out, or shall we continue?"
        prev = set(self.data["meta"].get("last_questions", []))
        pool = [q for q in _GENERIC_QUESTIONS if q not in prev] or _GENERIC_QUESTIONS
        return random.choice(pool)


MEMORY = OrionMemory(os.path.join(DATA_DIR, "orion_memory.json"))

# ══════════════════════════════════════════════
#  MULTI-KEY AI ENGINE
# ══════════════════════════════════════════════
# Not one key — a whole vault of them. Add as many keys as you like (several
# Gemini keys, Groq, OpenAI, OpenRouter, Claude, or any OpenAI-compatible
# server), tick the ones ORION may use, and it automatically moves on to the
# next key if one fails, runs out of quota, or gets rate-limited.
# Keys live in ORION_Data/orion_keys.json (plain text — keep that folder
# private and out of GitHub).
GEMINI_MODEL_CANDIDATES = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
_gemini_model = GEMINI_MODEL_CANDIDATES[0]
LAST_AI_SOURCE = ""
KEYS_FILE = os.path.join(DATA_DIR, "orion_keys.json")

# Default models change over time — every key has an editable "model" field,
# so if a provider retires one, just type the new name in the Key Manager.
PROVIDERS = {
    "gemini":     {"label": "Google Gemini",          "kind": "gemini",    "model": "gemini-2.5-flash",          "base": ""},
    "groq":       {"label": "Groq",                   "kind": "openai",    "model": "llama-3.3-70b-versatile",   "base": "https://api.groq.com/openai/v1"},
    "openai":     {"label": "OpenAI",                 "kind": "openai",    "model": "gpt-4o-mini",               "base": "https://api.openai.com/v1"},
    "openrouter": {"label": "OpenRouter",             "kind": "openai",    "model": "openrouter/auto",           "base": "https://openrouter.ai/api/v1"},
    "anthropic":  {"label": "Anthropic Claude",       "kind": "anthropic", "model": "claude-haiku-4-5-20251001", "base": ""},
    "custom":     {"label": "Custom (OpenAI-style)",  "kind": "openai",    "model": "",                          "base": ""},
}
_ENV_KEYS = [("GEMINI_API_KEY", "gemini"), ("GROQ_API_KEY", "groq"), ("OPENAI_API_KEY", "openai"),
             ("OPENROUTER_API_KEY", "openrouter"), ("ANTHROPIC_API_KEY", "anthropic")]
_COOLDOWN = {"auth": 600, "notfound": 300, "rate": 45, "server": 20, "net": 10, "timeout": 15, "error": 30}

def _clean_key(k):
    return (k or "").strip().strip('"').strip("'").strip()

class KeyVault:
    def __init__(self, path):
        self.path = path
        self.entries = []
        self.mode = "failover"          # or "round_robin"
        self._cool = {}                 # id -> time.time() until which the key rests
        self._last_good = None
        self._rr = 0
        self._lock = threading.RLock()
        self.load()

    @staticmethod
    def _norm(e):
        return {"id": e.get("id") or uuid.uuid4().hex[:8],
                "provider": e.get("provider") if e.get("provider") in PROVIDERS else "gemini",
                "label": (e.get("label") or "").strip(),
                "key": _clean_key(e.get("key")),
                "model": (e.get("model") or "").strip(),
                "base": (e.get("base") or "").strip(),
                "enabled": bool(e.get("enabled", True))}

    def load(self):
        data = {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
        with self._lock:
            self.mode = data.get("mode") if data.get("mode") in ("failover", "round_robin") else "failover"
            self.entries = [self._norm(e) for e in data.get("keys", []) if isinstance(e, dict)]
            have = {e["key"] for e in self.entries}
            for env, pid in _ENV_KEYS:          # pick up keys set as environment variables too
                k = _clean_key(os.getenv(env, ""))
                if k and k not in have:
                    self.entries.append(self._norm({"provider": pid, "label": f"{PROVIDERS[pid]['label']} (env)", "key": k}))

    def save(self):
        with self._lock:
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"mode": self.mode, "keys": self.entries}, f, indent=1)
                os.replace(tmp, self.path)
            except Exception as e:
                print(f"[KEYS] save failed: {e}")

    def replace_all(self, entries, mode):
        with self._lock:
            self.entries = [self._norm(e) for e in entries]
            self.mode = mode if mode in ("failover", "round_robin") else "failover"
            self._cool.clear(); self._last_good = None
            self.save()

    def has_any(self):
        return any(e["enabled"] and e["key"] for e in self.entries)

    def summary(self):
        with self._lock:
            on = sum(1 for e in self.entries if e["enabled"] and e["key"])
            tot = len(self.entries)
        if not on:
            return "No keys active — AI chat disabled"
        return f"{on} of {tot} key{'s' if tot != 1 else ''} active · {'Failover' if self.mode == 'failover' else 'Round-robin'}"

    def ordered(self):
        with self._lock:
            enabled = [e for e in self.entries if e["enabled"] and e["key"]]
            now = time.time()
            ready = [e for e in enabled if self._cool.get(e["id"], 0) <= now] or enabled
            if self.mode == "round_robin" and ready:
                i = self._rr % len(ready); self._rr += 1
                return ready[i:] + ready[:i]
            if self._last_good:
                ready.sort(key=lambda e: 0 if e["id"] == self._last_good else 1)
            return ready

    def mark_good(self, eid):
        with self._lock:
            self._last_good = eid; self._cool.pop(eid, None)

    def mark_bad(self, eid, code):
        with self._lock:
            self._cool[eid] = time.time() + _COOLDOWN.get(code, 30)
            if self._last_good == eid:
                self._last_good = None

KEYS = KeyVault(KEYS_FILE)

def set_gemini_api_key(key: str):
    """Compat helper: put a single Gemini key into the vault."""
    k = _clean_key(key)
    with KEYS._lock:
        for e in KEYS.entries:
            if e["provider"] == "gemini":
                e["key"] = k; e["enabled"] = True; KEYS.save(); return
        if k:
            KEYS.entries.append(KEYS._norm({"provider": "gemini", "label": "Gemini", "key": k}))
            KEYS.save()

# ── provider calls ─────────────────────────────
def _classify(status, msg=""):
    m = (msg or "").lower()
    if status in (401, 403): return "auth"
    if status == 404: return "notfound"
    if status == 429: return "rate"
    if status == 400 and ("api key" in m or "api_key" in m or "x-api-key" in m): return "auth"
    if status >= 500: return "server"
    return "error"

def _err_msg(r):
    try:
        j = r.json(); e = j.get("error", j)
        return str(e.get("message") or e)[:200] if isinstance(e, dict) else str(e)[:200]
    except Exception:
        return (r.text or "")[:200]

def _norm_history(history):
    """Gemini-style history → [(role, text)] strictly alternating, starting with 'user'."""
    out = []
    for m in history:
        role = "assistant" if m.get("role") in ("model", "assistant") else "user"
        txt = "".join(p.get("text", "") for p in m.get("parts", []))
        if not txt.strip():
            continue
        if out and out[-1][0] == role:
            out[-1] = (role, out[-1][1] + "\n" + txt)
        else:
            out.append((role, txt))
    while out and out[0][0] != "user":
        out.pop(0)
    return out

def _call_gemini(e, system, norm, max_tokens):
    global _gemini_model
    models = []
    for m in [e.get("model") or "", _gemini_model] + GEMINI_MODEL_CANDIDATES:
        if m and m not in models:
            models.append(m)
    contents = [{"role": "user" if r == "user" else "model", "parts": [{"text": t}]} for r, t in norm]
    for m in models:
        gen = {"maxOutputTokens": max_tokens, "temperature": 0.75}
        if "2.5-flash" in m:
            gen["thinkingConfig"] = {"thinkingBudget": 0}     # otherwise "thinking" eats the token budget
        body = {"system_instruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gen}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        for attempt in range(2):
            r = requests.post(url, headers={"x-goog-api-key": e["key"]}, json=body, timeout=15)
            if r.status_code == 200:
                try:
                    parts = r.json()["candidates"][0]["content"]["parts"]
                    text = "".join(p.get("text", "") for p in parts).strip()
                except Exception:
                    return False, "empty response", "error"
                if text:
                    _gemini_model = m
                    return True, text, "ok"
                return False, "empty response", "error"
            msg = _err_msg(r); code = _classify(r.status_code, msg)
            if code == "rate" and attempt == 0:
                time.sleep(1.5); continue
            if code == "notfound":
                break
            return False, msg or f"HTTP {r.status_code}", code
    return False, "no Gemini model reachable with this key (404)", "notfound"

def _call_openai(e, system, norm, max_tokens):
    pv = PROVIDERS[e["provider"]]
    base = (e.get("base") or pv["base"]).rstrip("/")
    model = e.get("model") or pv["model"]
    if not base:  return False, "no base URL set", "error"
    if not model: return False, "no model name set", "error"
    msgs = [{"role": "system", "content": system}] + [{"role": r, "content": t} for r, t in norm]
    hdr = {"Authorization": "Bearer " + e["key"], "Content-Type": "application/json"}
    bodies = [{"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": 0.75},
              {"model": model, "messages": msgs, "max_completion_tokens": max_tokens}]   # newer models want this name
    for i, body in enumerate(bodies):
        r = requests.post(base + "/chat/completions", headers=hdr, json=body, timeout=20)
        if r.status_code == 200:
            try:
                text = (r.json()["choices"][0]["message"]["content"] or "").strip()
            except Exception:
                return False, "empty response", "error"
            return (True, text, "ok") if text else (False, "empty response", "error")
        msg = _err_msg(r)
        if r.status_code == 400 and i == 0:
            continue
        return False, msg or f"HTTP {r.status_code}", _classify(r.status_code, msg)
    return False, "request rejected", "error"

def _call_anthropic(e, system, norm, max_tokens):
    model = e.get("model") or PROVIDERS["anthropic"]["model"]
    body = {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": r, "content": t} for r, t in norm]}
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=20, json=body,
                      headers={"x-api-key": e["key"], "anthropic-version": "2023-06-01",
                               "content-type": "application/json"})
    if r.status_code == 200:
        try:
            text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()
        except Exception:
            return False, "empty response", "error"
        return (True, text, "ok") if text else (False, "empty response", "error")
    msg = _err_msg(r)
    return False, msg or f"HTTP {r.status_code}", _classify(r.status_code, msg)

def _call_provider(e, system, norm, max_tokens=300):
    kind = PROVIDERS.get(e["provider"], {}).get("kind")
    if kind == "gemini":    return _call_gemini(e, system, norm, max_tokens)
    if kind == "openai":    return _call_openai(e, system, norm, max_tokens)
    if kind == "anthropic": return _call_anthropic(e, system, norm, max_tokens)
    return False, "unknown provider", "error"

def test_entry(entry):
    """Used by the Key Manager's Test button. Returns (ok, message)."""
    try:
        ok, text, code = _call_provider(entry, "Reply with the single word OK.", [("user", "ping")], 20)
    except requests.exceptions.ConnectionError:
        return False, "no internet / host unreachable"
    except requests.exceptions.Timeout:
        return False, "timed out"
    except Exception as ex:
        return False, str(ex)[:120]
    return (True, "working ✔") if ok else (False, f"{code}: {text}"[:150])

def _entry_name(e):
    return e.get("label") or PROVIDERS[e["provider"]]["label"]

def ai_complete(system, history, max_tokens=300):
    """Try the keys in order. Returns (text, source_name, error)."""
    entries = KEYS.ordered()
    if not entries:
        return None, "", "no_key"
    norm = _norm_history(history)
    if not norm:
        return None, "", "empty"
    errors, codes = [], []
    for e in entries:
        try:
            ok, text, code = _call_provider(e, system, norm, max_tokens)
        except requests.exceptions.ConnectionError:
            ok, text, code = False, "unreachable", "net"
        except requests.exceptions.Timeout:
            ok, text, code = False, "timed out", "timeout"
        except Exception as ex:
            ok, text, code = False, str(ex)[:100], "error"
        if ok:
            KEYS.mark_good(e["id"])
            return text, _entry_name(e), ""
        KEYS.mark_bad(e["id"], code)
        codes.append(code); errors.append(f"{_entry_name(e)}: {text}")
        print(f"[AI] {_entry_name(e)} failed ({code}): {text}")
    if all(c == "net" for c in codes):
        return None, "", "internet_error"
    return None, "", "; ".join(errors)

# ══════════════════════════════════════════════
#  AI CHAT  (keeps the same English-only reply rule as before)
# ══════════════════════════════════════════════
def build_system_prompt():
    base = (f"You are {AI_NAME}, an Iron Man JARVIS-style AI assistant. "
            "The user may write or speak to you in Hindi, Hinglish (a Roman-script "
            "mix of Hindi and English), or English — understand all three fluently. "
            "However, you must ALWAYS reply only in clear, proper, grammatically correct "
            "English, never in Hindi or Hinglish, regardless of the language the user used. "
            "Calm, confident, helpful tone. Max 2-3 sentences. Plain text only — no markdown, "
            "bullets or emojis, because your reply is read aloud.")
    base += f" Current local time: {_now().strftime('%A, %d %B %Y, %I:%M %p')}."
    ctx = MEMORY.context_for_prompt()
    if ctx:
        base += ("\n\nYou have a persistent memory of this user (below). Use it naturally when it helps — "
                 "follow up on things they did, continue earlier work — but never recite it unprompted.\n" + ctx)
    return base

def _friendly_error(err):
    if err == "no_key":         return say("no_key")
    if err == "internet_error": return say("internet_error")
    if err == "empty":          return "I didn't catch that. Please try again."
    return "None of your AI keys responded. " + err[:220]

def chat_ai(user_msg, lang):
    global conversation_history, LAST_AI_SOURCE
    if not KEYS.has_any():
        return say("no_key")
    conversation_history.append({"role": "user", "parts": [{"text": user_msg}]})
    conversation_history = conversation_history[-40:]
    text, src, err = ai_complete(build_system_prompt(), conversation_history[-12:])
    if text:
        conversation_history.append({"role": "model", "parts": [{"text": text}]})
        LAST_AI_SOURCE = src
        return text
    LAST_AI_SOURCE = ""
    return _friendly_error(err)

def ai_oneshot(prompt, max_tokens=120):
    """A single question to the AI that doesn't touch the chat history."""
    system = f"You are {AI_NAME}, a JARVIS-style AI assistant. Reply in plain English text only."
    text, src, err = ai_complete(system, [{"role": "user", "parts": [{"text": prompt}]}], max_tokens)
    return text

# ══════════════════════════════════════════════
#  WEATHER
# ══════════════════════════════════════════════
def get_weather(city="Delhi"):
    try:
        r = requests.get(f"https://wttr.in/{city}?format=3", timeout=5)
        return r.text.strip()
    except Exception:
        return say("weather_fail")

# ══════════════════════════════════════════════
#  SPOTIFY
# ══════════════════════════════════════════════
spotify = None

def init_spotify():
    global spotify
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        if not SPOTIFY_CLIENT_ID:
            return
        scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
        spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_SECRET,
            redirect_uri=SPOTIFY_REDIRECT, scope=scope, username=SPOTIFY_USERNAME
        ))
        print("[Spotify] Connected")
    except Exception as e:
        print(f"[Spotify] {e}")

def spotify_current():
    if not spotify: return None, None
    try:
        pb = spotify.current_playback()
        if pb and pb["is_playing"]:
            t = pb["item"]
            return t["name"], ", ".join(a["name"] for a in t["artists"])
    except Exception:
        pass
    return None, None

def spotify_cmd(action):
    if not spotify:
        speak(say("spotify_na")); return
    try:
        if action == "pause":   spotify.pause_playback();    speak(say("music_pause"))
        elif action == "play":  spotify.start_playback();    speak(say("music_play"))
        elif action == "next":  spotify.next_track();        speak(say("music_next"))
        elif action == "prev":  spotify.previous_track();    speak(say("music_prev"))
        elif action in ("vol+","vol-"):
            pb = spotify.current_playback()
            vol = pb["device"]["volume_percent"] if pb else 50
            new_vol = min(100, vol+10) if action=="vol+" else max(0, vol-10)
            spotify.volume(new_vol)
            speak(say("vol_up") if action=="vol+" else say("vol_down"))
    except Exception as e:
        speak(f"Spotify error: {e}")

# ══════════════════════════════════════════════
#  MOMENT DETECTOR
# ══════════════════════════════════════════════
class MomentDetector:
    """
    Real-time camera se teen tarah ke moments capture karta hai:
      Face  — koi chehra aaye
      Smile — muskurao
      Motion— kuch hile

    'see me' / 'watch me' / 'dekho mujhe' bolne par auto-start hota hai.
    """

    def __init__(self, ui_callback=None):
        self._running        = False
        self._thread         = None
        self._last_face      = 0
        self._last_smile     = 0
        self._last_motion    = 0
        self._prev_gray      = None
        self._total          = 0
        self._ui_callback    = ui_callback
        os.makedirs(MOMENTS_FOLDER, exist_ok=True)

    def start(self):
        if self._running:
            speak(say("detector_already_on")); return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        msg = say("detector_on")
        speak(msg)
        if self._ui_callback:
            self._ui_callback(msg)

    def stop(self):
        if not self._running:
            speak(say("detector_already_off")); return
        self._running = False
        msg = f"Moment detector off. Total {self._total} moments captured."
        speak(msg)
        if self._ui_callback:
            self._ui_callback(msg)

    def is_running(self):
        return self._running

    def total(self):
        return self._total

    def stats_text(self):
        return f"{self._total} moments saved so far in '{MOMENTS_FOLDER}' folder."

    def _loop(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            speak(say("camera_not_found"))
            self._running = False; return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("[Detector] Camera ready. Press Q in window to stop.")

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.03); continue

            display = frame.copy()
            gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray    = cv2.equalizeHist(gray)
            now     = time.time()

            faces = _face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60,60))

            for (x,y,w,h) in faces:
                cv2.rectangle(display,(x,y),(x+w,y+h),(255,200,0),2)
                cv2.putText(display,"Face",(x,y-8),
                            cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,200,0),2)

                if (now - self._last_face) > FACE_COOLDOWN:
                    self._last_face = now
                    fp = self._save(frame,"face")
                    self._announce("face_snap", fp)

                roi_g = gray[y:y+h, x:x+w]
                roi_d = display[y:y+h, x:x+w]
                smiles = _smile_cascade.detectMultiScale(
                    roi_g, scaleFactor=1.7, minNeighbors=22, minSize=(25,25))
                for (sx,sy,sw,sh) in smiles:
                    cv2.rectangle(roi_d,(sx,sy),(sx+sw,sy+sh),(150,255,0),2)
                    if (now - self._last_smile) > SMILE_COOLDOWN:
                        self._last_smile = now
                        fp = self._save(frame,"smile")
                        self._announce("smile_snap", fp)

            if self._prev_gray is not None:
                diff  = cv2.absdiff(self._prev_gray, gray)
                _, th = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                mpx   = cv2.countNonZero(th)
                if mpx > MOTION_THRESHOLD:
                    contours,_ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for cnt in contours:
                        if cv2.contourArea(cnt) > 500:
                            mx,my,mw,mh = cv2.boundingRect(cnt)
                            cv2.rectangle(display,(mx,my),(mx+mw,my+mh),(255,80,255),1)
                    cv2.putText(display,f"Motion ({mpx}px)",(10,60),
                                cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,80,255),2)
                    if (now - self._last_motion) > MOTION_COOLDOWN:
                        self._last_motion = now
                        fp = self._save(frame,"motion")
                        self._announce("motion_snap", fp)

            self._prev_gray = gray.copy()
            self._draw_hud(display)
            cv2.imshow("ORION — Moment Detector  [Q = Band]", display)
            if (cv2.waitKey(1) & 0xFF) in (ord('q'), ord('Q')):
                break

        cap.release()
        cv2.destroyAllWindows()
        self._running = False

    def _save(self, frame, reason):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"moment_{reason}_{ts}.jpg"
        fp = os.path.join(MOMENTS_FOLDER, fn)
        cv2.imwrite(fp, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        self._total += 1
        print(f"[Detector] Captured {reason.upper()} -> {fn}")
        return fp

    def _announce(self, key, fp):
        msg = say(key)
        speak(msg)
        if self._ui_callback:
            self._ui_callback(f"{msg}  [{os.path.basename(fp)}]")

    def _draw_hud(self, frame):
        h, w = frame.shape[:2]
        ts   = datetime.datetime.now().strftime("%H:%M:%S")
        cv2.rectangle(frame,(0,0),(w,36),(15,10,5),-1)
        cv2.putText(frame,f"ORION MOMENT DETECTOR  |  {ts}  |  Captured: {self._total}",
                    (10,24),cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,200,0),2)
        for (px,py),(dx,dy) in [((0,0),(1,1)),((w,0),(-1,1)),((0,h),(1,-1)),((w,h),(-1,-1))]:
            cv2.line(frame,(px,py),(px+dx*28,py),(255,200,0),2)
            cv2.line(frame,(px,py),(px,py+dy*28),(255,200,0),2)

# ══════════════════════════════════════════════
#  SIMPLE CAMERA (unchanged)
# ══════════════════════════════════════════════
_cam_running = False

def open_camera():
    global _cam_running
    if _cam_running:
        speak(say("camera_already")); return
    def _run():
        global _cam_running
        _cam_running = True
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            speak(say("camera_not_found"))
            _cam_running = False; return
        speak(say("camera_on"))
        while _cam_running:
            ret, frame = cap.read()
            if not ret: break
            cv2.imshow("ORION CAM", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release(); cv2.destroyAllWindows()
        _cam_running = False
        speak(say("camera_off"))
    threading.Thread(target=_run, daemon=True).start()

# ══════════════════════════════════════════════
#  COMMAND HANDLER
# ══════════════════════════════════════════════
_detector = None

def handle_command(cmd):
    global _current_lang, _detector
    c = cmd.lower().strip()
    _current_lang = detect_language(cmd)

    detector_on_words = [
        "see me","watch me","dekho mujhe","mujhe dekho",
        "moment on","moments on","detector chalu","detector on",
        "moments capture","moment detector on","moment detect karo",
        "dekhte raho","nazar rakho"
    ]
    detector_off_words = [
        "detector band","detector off","moment off","moments off",
        "moment detector band","moment detector off","dekhna band"
    ]
    detector_stats_words = [
        "kitne moments","moment stats","moments dekho","moments count",
        "kitni photos","moments kitne"
    ]

    if any(x in c for x in detector_on_words):
        if _detector: _detector.start()
        return True
    if any(x in c for x in detector_off_words):
        if _detector: _detector.stop()
        return True
    if any(x in c for x in detector_stats_words):
        if _detector:
            msg = _detector.stats_text()
            speak(msg)
            return msg
        return True

    if any(x in c for x in ["chrome","क्रोम","browser","ब्राउज़र"]):
        for p in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]:
            if os.path.exists(p):
                os.startfile(p); speak(say("chrome_open")); return True
        webbrowser.open("https://google.com"); speak(say("chrome_open")); return True

    if any(x in c for x in ["notepad","नोटपैड","नोट पैड"]):
        os.system("notepad"); speak(say("notepad_open")); return True

    if any(x in c for x in ["calculator","calc","कैलकुलेटर","हिसाब"]):
        os.system("calc"); speak(say("calc_open")); return True

    if any(x in c for x in ["task manager","taskmgr","टास्क मैनेजर"]):
        os.system("taskmgr"); speak(say("taskmgr_open")); return True

    if any(x in c for x in ["youtube","यूट्यूब","यू ट्यूब"]):
        webbrowser.open("https://youtube.com"); speak(say("youtube_open")); return True

    if any(x in c for x in ["whatsapp","व्हाट्सएप","whatsaap"]):
        webbrowser.open("https://web.whatsapp.com"); speak(say("whatsapp_open")); return True

    if any(x in c for x in ["instagram","इंस्टाग्राम","insta"]):
        webbrowser.open("https://www.instagram.com"); speak(say("instagram_open")); return True

    if any(x in c for x in ["spotify","स्पॉटिफ़ाई"]) and any(x in c for x in ["open","खोलो","kholo","chalu"]):
        webbrowser.open("https://open.spotify.com"); speak(say("spotify_open")); return True

    music_ctx = any(x in c for x in ["music","song","गाना","संगीत","spotify","बजाना","bajao","bajana"])
    if music_ctx:
        if any(x in c for x in ["pause","रोको","रोक","band karo","बंद करो","rok"]):
            spotify_cmd("pause"); return True
        if any(x in c for x in ["resume","play","चलाओ","चालू","chalu","chalao","shuru"]):
            spotify_cmd("play"); return True
    if any(x in c for x in ["next song","next track","अगला गाना","agla gana","skip","आगे"]):
        spotify_cmd("next"); return True
    if any(x in c for x in ["previous song","prev song","पिछला गाना","pichla gana","peechhe"]):
        spotify_cmd("prev"); return True

    for prefix in ["search karo ","search kar ","search ","खोजो ","ढूंढो ","dhundho ","dhundo "]:
        if c.startswith(prefix):
            q = c[len(prefix):].strip()
            if q:
                webbrowser.open(f"https://google.com/search?q={q.replace(' ','+')}")
                speak(say("searching") + q); return True

    for prefix in ["play ","बजाओ ","bajao ","chala ","chalao "]:
        if c.startswith(prefix):
            song = c[len(prefix):].strip()
            if song:
                speak(say("playing") + song)
                threading.Thread(target=pywhatkit.playonyt, args=(song,), daemon=True).start()
                return True

    if any(x in c for x in ["weather","mausam","मौसम","मौसम बताओ","weather batao"]):
        city_part = c
        for rem in ["weather","mausam","मौसम","batao","bataiye","in","ka","ki","ke","बताओ","का","की","के"]:
            city_part = city_part.replace(rem,"").strip()
        city = city_part.strip() or "Delhi"
        speak(get_weather(city)); return True

    if any(x in c for x in ["time","समय","वक्त","waqt","kitna baja","kitne baje","baj gaye"]):
        t = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {t}."); return True

    if any(x in c for x in ["date","तारीख","tarikh","din","दिन बताओ","aaj ka din"]):
        d = datetime.datetime.now()
        speak(f"Today is {d.strftime('%A, %d %B %Y')}."); return True

    if any(x in c for x in ["screenshot","स्क्रीनशॉट","screen shot","screen capture","screen le"]):
        fn = f"ss_{int(time.time())}.png"
        pyautogui.screenshot(fn); speak(say("screenshot")); return True

    if any(x in c for x in ["volume up","आवाज़ बढ़ाओ","awaaz badhao","vol up","sound up","tej karo","तेज करो"]):
        [pyautogui.press("volumeup") for _ in range(5)]; speak(say("vol_up")); return True
    if any(x in c for x in ["volume down","आवाज़ घटाओ","awaaz ghataao","vol down","sound down","kam karo","कम करो"]):
        [pyautogui.press("volumedown") for _ in range(5)]; speak(say("vol_down")); return True
    if any(x in c for x in ["mute","म्यूट","chup","शांत","बंद आवाज़"]):
        pyautogui.press("volumemute"); speak(say("mute")); return True

    if any(x in c for x in ["camera","कैमरा","webcam","selfie"]):
        open_camera(); return True

    if any(x in c for x in ["lock","लॉक","lock karo","lock kar do","screen lock"]):
        speak(say("lock")); time.sleep(0.5)
        os.system("rundll32.exe user32.dll,LockWorkStation"); return True

    if any(x in c for x in ["confirm shutdown","shutdown confirm","हाँ shutdown","हाँ शटडाउन"]):
        speak(say("shutdown_now")); time.sleep(5); os.system("shutdown /s /t 0"); return True
    if any(x in c for x in ["shutdown","बंद करो","band karo computer","computer band"]) and "confirm" not in c:
        speak(say("shutdown_confirm")); return True

    if any(x in c for x in ["confirm restart","restart confirm"]):
        speak(say("restart_now")); os.system("shutdown /r /t 0"); return True
    if any(x in c for x in ["restart","रीस्टार्ट","dobara chalu","फिर से चालू"]) and "confirm" not in c:
        speak(say("restart_confirm")); return True

    if any(x in c for x in ["clear chat","clear history","chat clear","chat saaf","चैट साफ"]):
        return "CLEAR"

    return False

# ══════════════════════════════════════════════
#  THREADS
# ══════════════════════════════════════════════
class ListenThread(QThread):
    result = pyqtSignal(str)
    def run(self):
        r = sr.Recognizer()
        r.energy_threshold = 300
        r.dynamic_energy_threshold = True
        try:
            with sr.Microphone() as src:
                r.adjust_for_ambient_noise(src, duration=0.6)
                audio = r.listen(src, timeout=7, phrase_time_limit=10)
            try:
                text = r.recognize_google(audio, language="hi-IN")
            except Exception:
                text = r.recognize_google(audio, language="en-IN")
            self.result.emit(text.lower().strip())
        except Exception:
            self.result.emit("")

class ContinuousListenThread(QThread):
    """
    'Speak Mode' engine — listens on a loop, forever, without needing the
    mic button pressed each time. Pass a threading.Event as `gate`: when
    the gate is SET the thread listens; when it's CLEARED (while ORION is
    talking or thinking) the thread just idles so it doesn't pick up
    ORION's own voice from the speakers.
    """
    text_result = pyqtSignal(str)

    def __init__(self, gate: threading.Event):
        super().__init__()
        self._gate = gate
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        r = sr.Recognizer()
        r.energy_threshold = 300
        r.dynamic_energy_threshold = True
        mic = None
        while self._running and mic is None:       # keep trying until the mic is available
            try:
                mic = sr.Microphone()
            except Exception:
                time.sleep(2.0)
        if mic is None:
            return
        while self._running:
            # Idle here (without touching the mic) while ORION is speaking/thinking.
            if not self._gate.wait(timeout=0.5):
                continue
            if not self._running:
                break
            try:
                with mic as src:
                    r.adjust_for_ambient_noise(src, duration=0.3)
                    audio = r.listen(src, timeout=4, phrase_time_limit=12)
            except sr.WaitTimeoutError:
                continue
            except Exception:
                time.sleep(0.3)
                continue
            if not self._running or not self._gate.is_set():
                continue
            try:
                text = r.recognize_google(audio, language="hi-IN")
            except Exception:
                try:
                    text = r.recognize_google(audio, language="en-IN")
                except Exception:
                    text = ""
            if text.strip():
                self.text_result.emit(text.lower().strip())

class AIThread(QThread):
    result = pyqtSignal(str)
    def __init__(self, prompt, lang):
        super().__init__()
        self.prompt = prompt
        self.lang   = lang
    def run(self):
        try:
            self.result.emit(chat_ai(self.prompt, self.lang))
        except Exception as e:
            self.result.emit(f"AI request failed: {e}")

# ══════════════════════════════════════════════════════════════════════════
#   HUD WIDGETS
# ══════════════════════════════════════════════════════════════════════════

PANEL_STYLE = """
QFrame#panel {
    background: rgba(4, 10, 18, 215);
    border: 1px solid rgba(0, 200, 255, 0.28);
    border-radius: 10px;
}
"""

def make_panel(title):
    """Reusable bordered HUD panel with a title row + content layout."""
    frame = QFrame()
    frame.setObjectName("panel")
    frame.setStyleSheet(PANEL_STYLE)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(14, 10, 14, 12)
    outer.setSpacing(8)

    title_lbl = QLabel(title)
    title_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
    title_lbl.setStyleSheet(f"color:{CYAN_HEX}; letter-spacing:1px; background:transparent; border:none;")
    outer.addWidget(title_lbl)

    div = QFrame()
    div.setFixedHeight(1)
    div.setStyleSheet("background-color: rgba(0,200,255,0.25); border:none;")
    outer.addWidget(div)

    content = QVBoxLayout()
    content.setSpacing(7)
    outer.addLayout(content)
    outer.addStretch()
    return frame, content


class HUDBackground(QWidget):
    """Fullscreen dark backdrop with a faint grid + corner brackets."""
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(3, 7, 13))
        pen = QPen(QColor(0, 200, 255, 14)); pen.setWidth(1)
        p.setPen(pen)
        step = 40
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)
        # corner brackets
        bp = QPen(QColor(0, 200, 255, 130)); bp.setWidth(2)
        p.setPen(bp)
        L = 36
        for (px, py), (dx, dy) in [((10,10),(1,1)), ((w-10,10),(-1,1)),
                                    ((10,h-10),(1,-1)), ((w-10,h-10),(-1,-1))]:
            p.drawLine(px, py, px+dx*L, py)
            p.drawLine(px, py, px, py+dy*L)


class Waveform(QWidget):
    """Animated voice waveform bars."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self._t = 0.0
        self._amp = 0.15
        t = QTimer(self); t.timeout.connect(self._tick); t.start(45)

    def set_amp(self, amp):
        self._amp = amp

    def _tick(self):
        self._t += 0.3
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bars = 28
        bw = w / bars
        pen = QPen(COL_ACCENT); pen.setWidth(2); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        for i in range(bars):
            phase = self._t + i * 0.5
            mag = (0.25 + self._amp) * (0.4 + 0.6 * abs(math.sin(phase)))
            bh = max(2, mag * h)
            x = i * bw + bw/2
            p.drawLine(int(x), int(h/2 - bh/2), int(x), int(h/2 + bh/2))


class HeartbeatWidget(QWidget):
    """Animated ECG-style pulse line for System Status."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self._offset = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(35)

    def _tick(self):
        self._offset = (self._offset + 4) % 240
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pen = QPen(COL_GREEN); pen.setWidth(2)
        p.setPen(pen)
        path = QPainterPath()
        cy = h/2
        pts = []
        for x in range(0, w+20, 4):
            sx = (x + self._offset) % 240
            if sx < 30:
                y = cy
            elif sx < 40:
                y = cy - (sx-30)*3.2
            elif sx < 50:
                y = cy - 32 + (sx-40)*5.6
            elif sx < 60:
                y = cy + 24 - (sx-50)*2.4
            else:
                y = cy
            pts.append(QPointF(x, y))
        if pts:
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
        p.drawPath(path)


class DotRow(QWidget):
    """Row of small animated status dots."""
    def __init__(self, count=5, parent=None):
        super().__init__(parent)
        self.count = count
        self.setFixedHeight(14)
        self._phase = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(450)

    def _tick(self):
        self._phase = (self._phase + 1) % self.count
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        d = 9; gap = 8
        for i in range(self.count):
            x = i * (d+gap)
            on = (i <= self._phase)
            col = QColor(COL_ACCENT) if on else QColor(40, 60, 75)
            p.setBrush(QBrush(col)); p.setPen(Qt.NoPen)
            p.drawEllipse(x, 2, d, d)


class BarMeter(QWidget):
    """Labelled horizontal usage bar (CPU / RAM / Disk / Battery)."""
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.value = 0
        self.setFixedHeight(34)

    def set_value(self, v):
        self.value = max(0, min(100, v))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        p.setFont(QFont("Consolas", 8))
        p.setPen(QColor(200, 220, 230))
        p.drawText(QRect(0, 0, 90, 16), Qt.AlignLeft | Qt.AlignVCenter, self.label)
        p.drawText(QRect(w-40, 0, 40, 16), Qt.AlignRight | Qt.AlignVCenter, f"{int(self.value)}%")
        bar_y = 20; bar_h = 7
        p.setBrush(QBrush(QColor(255,255,255,18))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, bar_y, w, bar_h, 3, 3)
        fill_w = int(w * self.value/100)
        col = COL_GREEN if self.value < 70 else (COL_ORANGE if self.value < 90 else COL_RED)
        p.setBrush(QBrush(col))
        p.drawRoundedRect(0, bar_y, fill_w, bar_h, 3, 3)


class DotStatus(QWidget):
    """A label + ON/OFF dot row, used in the Moment Detector panel."""
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        self.lbl = QLabel(label)
        self.lbl.setFont(QFont("Consolas", 9))
        self.lbl.setStyleSheet("color:#cfe9f5; background:transparent; border:none;")
        self.dot = QLabel("●")
        self.dot.setFont(QFont("Arial", 10))
        self.dot.setFixedWidth(16)
        lay.addWidget(self.lbl); lay.addStretch(); lay.addWidget(self.dot)
        self.set_state(False)

    def set_state(self, on):
        self.dot.setStyleSheet(f"color:{'rgb(70,230,150)' if on else 'rgb(90,90,100)'}; background:transparent; border:none;")


class CenterRing(QWidget):
    """Big multi-ring HUD centerpiece — the heart of ORION."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 300)
        self._angle = 0; self._pulse = 0.0; self._pd = 0.02; self._state = "idle"
        t = QTimer(self); t.timeout.connect(self._tick); t.start(30)

    def set_state(self, s):
        self._state = s; self.update()

    def _tick(self):
        self._angle = (self._angle + (4 if self._state == "listening" else 1.3)) % 360
        self._pulse += self._pd
        if self._pulse > 1 or self._pulse < 0: self._pd *= -1
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        cx = cy = 150
        col = STATE_COLORS.get(self._state, COL_ACCENT)

        # outer glow
        gr = 130 + int(self._pulse * 14)
        g = QRadialGradient(cx, cy, gr)
        a = int(40 + self._pulse * 50)
        g.setColorAt(0, QColor(col.red(), col.green(), col.blue(), a))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(g)); p.setPen(Qt.NoPen)
        p.drawEllipse(cx-gr, cy-gr, gr*2, gr*2)

        # outer static ring with ticks
        outer_r = 118
        pen = QPen(QColor(0, 200, 255, 60)); pen.setWidth(1)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawEllipse(cx-outer_r, cy-outer_r, outer_r*2, outer_r*2)
        for i in range(36):
            ang = math.radians(i*10)
            x1 = cx + (outer_r-6)*math.cos(ang); y1 = cy + (outer_r-6)*math.sin(ang)
            x2 = cx + outer_r*math.cos(ang);      y2 = cy + outer_r*math.sin(ang)
            p.drawLine(QPointF(x1,y1), QPointF(x2,y2))

        # middle ring
        mid_r = 92
        pen2 = QPen(QColor(60, 60, 70)); pen2.setWidth(2)
        p.setPen(pen2)
        p.drawEllipse(cx-mid_r, cy-mid_r, mid_r*2, mid_r*2)

        # rotating arc (main indicator ring)
        ap = QPen(col); ap.setWidth(4); ap.setCapStyle(Qt.RoundCap)
        p.setPen(ap)
        span = 110 if self._state == "idle" else 240
        p.drawArc(cx-mid_r, cy-mid_r, mid_r*2, mid_r*2, int(-self._angle*16), span*16)

        # second thin rotating ring (counter-rotating)
        r2 = 70
        pen3 = QPen(QColor(col.red(), col.green(), col.blue(), 150)); pen3.setWidth(2)
        p.setPen(pen3)
        p.drawArc(cx-r2, cy-r2, r2*2, r2*2, int(self._angle*1.6*16), 80*16)

        # inner glowing core
        inner = 52
        ig = QRadialGradient(cx, cy, inner)
        ig.setColorAt(0, QColor(8, 14, 22, 235))
        ig.setColorAt(1, QColor(4, 8, 14, 245))
        p.setBrush(QBrush(ig)); p.setPen(Qt.NoPen)
        p.drawEllipse(cx-inner, cy-inner, inner*2, inner*2)

        corep = QPen(col); corep.setWidth(2)
        p.setPen(corep); p.setBrush(Qt.NoBrush)
        p.drawEllipse(cx-inner, cy-inner, inner*2, inner*2)

        p.setPen(col)
        p.setFont(QFont("Consolas", 11, QFont.Bold))
        lbl = {"idle":"ORION","listening":"MIC","thinking":"...",
               "speaking":"SPK","detecting":"EYE"}.get(self._state, "ORION")
        p.drawText(QRect(cx-inner, cy-10, inner*2, 20), Qt.AlignCenter, lbl)


class ModuleIcon(QWidget):
    """One icon in the 'Active Modules' row — glows cyan when active."""
    def __init__(self, glyph, label, parent=None):
        super().__init__(parent)
        self._active = False
        self.setFixedWidth(82)
        lay = QVBoxLayout(self); lay.setSpacing(4); lay.setContentsMargins(0,0,0,0)
        self.glyph_lbl = QLabel(glyph)
        self.glyph_lbl.setAlignment(Qt.AlignCenter)
        self.glyph_lbl.setFont(QFont("Arial", 16))
        self.glyph_lbl.setFixedHeight(34)
        self.text_lbl = QLabel(label)
        self.text_lbl.setAlignment(Qt.AlignCenter)
        self.text_lbl.setFont(QFont("Consolas", 7))
        self.text_lbl.setWordWrap(True)
        lay.addWidget(self.glyph_lbl); lay.addWidget(self.text_lbl)
        self.set_active(False)

    def set_active(self, on):
        self._active = on
        if on:
            self.glyph_lbl.setStyleSheet(
                "background: rgba(0,200,255,0.18); border:1px solid rgba(0,200,255,0.65);"
                "border-radius:8px; color: rgb(0,200,255);")
            self.text_lbl.setStyleSheet("color: rgb(0,200,255); background:transparent; border:none;")
        else:
            self.glyph_lbl.setStyleSheet(
                "background: rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);"
                "border-radius:8px; color: rgba(200,220,230,0.6);")
            self.text_lbl.setStyleSheet("color: rgba(200,220,230,0.45); background:transparent; border:none;")


def make_qbtn(text, handler):
    b = QPushButton(text)
    b.setFixedHeight(34)
    b.setFont(QFont("Consolas", 9))
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("""
        QPushButton{
            background: rgba(0,200,255,0.07); border:1px solid rgba(0,200,255,0.25);
            border-radius:6px; color:#cfe9f5; text-align:left; padding-left:10px;
        }
        QPushButton:hover{ background: rgba(0,200,255,0.18); border-color: rgba(0,200,255,0.55); }
        QPushButton:pressed{ background: rgba(0,200,255,0.30); }
    """)
    b.clicked.connect(handler)
    return b


# ══════════════════════════════════════════════════════════════════════════
#   API KEY MANAGER  (box-in-box: outer panel → key list → one small box per key)
# ══════════════════════════════════════════════════════════════════════════
KEY_DIALOG_STYLE = """
QDialog{ background: rgb(4,10,18); }
QLabel{ color:#cfe9f5; background:transparent; }
QLineEdit, QComboBox{ background: rgba(0,0,0,0.35); border:1px solid rgba(0,200,255,0.3);
    border-radius:6px; color:#eaf8ff; padding:2px 8px; min-height:26px; }
QLineEdit:focus, QComboBox:focus{ border-color: rgba(0,200,255,0.75); }
QComboBox QAbstractItemView{ background: rgb(6,16,28); color:#eaf8ff;
    selection-background-color: rgba(0,200,255,0.35); border:1px solid rgba(0,200,255,0.4); }
QCheckBox{ color:#cfe9f5; spacing:6px; font-weight:bold; }
QCheckBox::indicator{ width:16px; height:16px; border:1px solid rgba(0,200,255,0.6);
    border-radius:4px; background:rgba(0,0,0,0.4); }
QCheckBox::indicator:checked{ background: rgb(0,200,255); }
QPushButton{ background: rgba(0,200,255,0.10); border:1px solid rgba(0,200,255,0.35);
    border-radius:6px; color:#cfe9f5; padding:4px 12px; min-height:26px; }
QPushButton:hover{ background: rgba(0,200,255,0.25); }
QScrollArea{ border:none; background:transparent; }
QScrollBar:vertical{ background:transparent; width:6px; }
QScrollBar::handle:vertical{ background: rgba(0,200,255,0.35); border-radius:3px; }
"""
KEY_CARD_STYLE = ("QFrame#keycard{ background: rgba(0,200,255,0.05);"
                  " border:1px solid rgba(0,200,255,0.30); border-radius:8px; }")

class KeyCard(QFrame):
    """One small box = one API key."""
    removed        = pyqtSignal(object)
    test_requested = pyqtSignal(object)

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry_id = entry.get("id") or uuid.uuid4().hex[:8]
        self.setObjectName("keycard")
        self.setStyleSheet(KEY_CARD_STYLE)
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 8, 10, 8); lay.setSpacing(6)

        r1 = QHBoxLayout(); r1.setSpacing(6)
        self.chk = QCheckBox("USE"); self.chk.setChecked(bool(entry.get("enabled", True)))
        self.provider = QComboBox()
        for pid, pv in PROVIDERS.items():
            self.provider.addItem(pv["label"], pid)
        self.provider.setCurrentIndex(max(0, self.provider.findData(entry.get("provider", "gemini"))))
        self.label = QLineEdit(entry.get("label", "")); self.label.setPlaceholderText("Label (optional)")
        del_btn = QPushButton("✕"); del_btn.setFixedWidth(34)
        del_btn.clicked.connect(lambda _=False: self.removed.emit(self))
        r1.addWidget(self.chk); r1.addWidget(self.provider, 1); r1.addWidget(self.label, 1); r1.addWidget(del_btn)
        lay.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(6)
        self.key = QLineEdit(entry.get("key", "")); self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("Paste API key…"); self.key.setFont(QFont("Consolas", 9))
        show_btn = QPushButton("👁"); show_btn.setFixedWidth(34)
        show_btn.clicked.connect(lambda _=False: self.key.setEchoMode(
            QLineEdit.Normal if self.key.echoMode() == QLineEdit.Password else QLineEdit.Password))
        paste_btn = QPushButton("📋"); paste_btn.setFixedWidth(34)
        paste_btn.clicked.connect(lambda _=False: self.key.setText(QApplication.clipboard().text().strip()))
        r2.addWidget(self.key, 1); r2.addWidget(paste_btn); r2.addWidget(show_btn)
        lay.addLayout(r2)

        r3 = QHBoxLayout(); r3.setSpacing(6)
        self.model = QLineEdit(entry.get("model", ""))
        self.base  = QLineEdit(entry.get("base", "")); self.base.setPlaceholderText("Base URL, e.g. https://host/v1")
        r3.addWidget(self.model, 1); r3.addWidget(self.base, 1)
        lay.addLayout(r3)

        r4 = QHBoxLayout(); r4.setSpacing(6)
        self.status = QLabel("● not tested"); self.status.setFont(QFont("Consolas", 8))
        self.status.setStyleSheet("color: rgba(200,220,230,0.55);")
        test_btn = QPushButton("🧪 Test"); test_btn.setFixedWidth(80)
        test_btn.clicked.connect(lambda _=False: self.test_requested.emit(self))
        r4.addWidget(self.status, 1); r4.addWidget(test_btn)
        lay.addLayout(r4)

        self.provider.currentIndexChanged.connect(lambda _=0: self._on_provider())
        self._on_provider()

    def _on_provider(self):
        pid = self.provider.currentData()
        dm = PROVIDERS[pid]["model"]
        self.model.setPlaceholderText(f"Model (blank = {dm})" if dm else "Model name (required)")
        self.base.setVisible(pid == "custom")

    def to_entry(self):
        return {"id": self.entry_id, "provider": self.provider.currentData(),
                "label": self.label.text().strip(), "key": _clean_key(self.key.text()),
                "model": self.model.text().strip(), "base": self.base.text().strip(),
                "enabled": self.chk.isChecked()}

    def set_status(self, text, ok):
        col = "rgba(200,220,230,0.6)" if ok is None else ("rgb(70,230,150)" if ok else "rgb(255,120,90)")
        self.status.setText("● " + text)
        self.status.setStyleSheet(f"color:{col};")


class KeyManagerDialog(QDialog):
    test_done = pyqtSignal(str, bool, str)

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.cards = []
        self.setWindowTitle("ORION — API Key Connector")
        self.setModal(True)
        self.resize(720, 660)
        self.setStyleSheet(KEY_DIALOG_STYLE)
        self.test_done.connect(self._on_test_done)

        root = QVBoxLayout(self); root.setContentsMargins(14, 14, 14, 14)
        panel = QFrame(); panel.setObjectName("panel"); panel.setStyleSheet(PANEL_STYLE)     # outer box
        pc = QVBoxLayout(panel); pc.setContentsMargins(14, 12, 14, 12); pc.setSpacing(8)
        root.addWidget(panel)

        title = QLabel("🔑 MULTI API KEY CONNECTOR")
        title.setFont(QFont("Consolas", 10, QFont.Bold))
        title.setStyleSheet(f"color:{CYAN_HEX}; letter-spacing:1px;")
        pc.addWidget(title)
        info = QLabel("Add as many keys as you like and tick USE on the ones ORION may use. "
                      "If a key fails or hits its limit, ORION moves to the next one automatically.")
        info.setWordWrap(True); info.setFont(QFont("Consolas", 8))
        info.setStyleSheet("color: rgba(200,220,230,0.65);")
        pc.addWidget(info)

        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Key rotation:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Failover — use first working key, next one on error", "failover")
        self.mode_combo.addItem("Round-robin — spread requests across all keys", "round_robin")
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(vault.mode)))
        mrow.addWidget(self.mode_combo, 1)
        pc.addLayout(mrow)

        inner = QFrame(); inner.setObjectName("innerbox")                                  # middle box
        inner.setStyleSheet("QFrame#innerbox{ background: rgba(0,0,0,0.25);"
                            " border:1px solid rgba(0,200,255,0.18); border-radius:8px; }")
        il = QVBoxLayout(inner); il.setContentsMargins(8, 8, 8, 8)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        holder = QWidget(); holder.setStyleSheet("background:transparent;")
        self.cards_l = QVBoxLayout(holder); self.cards_l.setSpacing(8); self.cards_l.setContentsMargins(0, 0, 0, 0)
        self.cards_l.addStretch()
        self.scroll.setWidget(holder)
        il.addWidget(self.scroll)
        pc.addWidget(inner, 1)                                                              # key boxes live inside

        self.count_lbl = QLabel(""); self.count_lbl.setFont(QFont("Consolas", 8))
        self.count_lbl.setStyleSheet("color: rgba(200,220,230,0.65);")
        pc.addWidget(self.count_lbl)

        brow = QHBoxLayout()
        add_btn  = QPushButton("＋ Add Key");  add_btn.clicked.connect(lambda _=False: self._add_card())
        test_all = QPushButton("🧪 Test All"); test_all.clicked.connect(lambda _=False: self._test_all())
        cancel   = QPushButton("Cancel");      cancel.clicked.connect(self.reject)
        save     = QPushButton("💾 Save && Apply"); save.clicked.connect(lambda _=False: self._save())
        brow.addWidget(add_btn); brow.addWidget(test_all); brow.addStretch()
        brow.addWidget(cancel); brow.addWidget(save)
        pc.addLayout(brow)

        for e in vault.entries:
            self._add_card(e)
        if not self.cards:
            self._add_card()
        self._update_count()

    def _add_card(self, entry=None):
        if entry is None:
            entry = {"id": uuid.uuid4().hex[:8], "provider": "gemini", "label": "", "key": "",
                     "model": "", "base": "", "enabled": True}
        card = KeyCard(entry)
        card.removed.connect(self._remove_card)
        card.test_requested.connect(self._test_card)
        card.chk.stateChanged.connect(lambda _=0: self._update_count())
        self.cards_l.insertWidget(self.cards_l.count() - 1, card)
        self.cards.append(card)
        self._update_count()

    def _remove_card(self, card):
        if card in self.cards:
            self.cards.remove(card)
        card.setParent(None); card.deleteLater()
        self._update_count()

    def _update_count(self):
        on = sum(1 for c in self.cards if c.chk.isChecked())
        self.count_lbl.setText(f"{len(self.cards)} key box(es) · {on} ticked for use")

    def _test_card(self, card):
        e = card.to_entry()
        if not e["key"]:
            card.set_status("paste a key first", False); return
        card.set_status("testing…", None)
        threading.Thread(target=self._test_worker, args=(e,), daemon=True).start()

    def _test_worker(self, e):
        ok, msg = test_entry(e)
        try:
            self.test_done.emit(e["id"], ok, msg)
        except RuntimeError:
            pass                                   # dialog was closed meanwhile

    def _on_test_done(self, eid, ok, msg):
        for c in self.cards:
            if c.entry_id == eid:
                c.set_status(msg, ok)

    def _test_all(self):
        for c in self.cards:
            if c.key.text().strip():
                self._test_card(c)

    def _save(self):
        entries = [c.to_entry() for c in self.cards]
        entries = [e for e in entries if e["key"]]            # empty boxes are dropped
        self.vault.replace_all(entries, self.mode_combo.currentData())
        self.accept()


class ThinkThread(QThread):
    """The next-day 'thinking': reads memory, asks the AI for one good question
    (or builds one straight from memory if there's no key / no internet)."""
    result = pyqtSignal(str)
    def run(self):
        q = ""
        try:
            if KEYS.has_any():
                text = ai_oneshot(MEMORY.build_think_prompt())
                if text:
                    lines = [l.strip().strip('"') for l in text.splitlines() if l.strip()]
                    q = lines[0] if lines else ""
        except Exception as e:
            print(f"[THINK] {e}")
        if not q or len(q) > 220:
            q = MEMORY.fallback_question()
        self.result.emit(q)


# ══════════════════════════════════════════════════════════════════════════
#   MAIN WINDOW — FULLSCREEN HUD DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
class OrionWindow(QWidget):
    add_log_signal   = pyqtSignal(str, str)
    set_state_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setStyleSheet("background: transparent;")

        self._listen_th = None
        self._ai_th = None
        self._net_last = None
        self._vol_value = 80

        # Speak Mode (continuous hands-free conversation)
        self._speak_mode_on = False
        self._speak_gate    = threading.Event()
        self._speak_gate.set()
        self._speak_thread  = None

        # v4 state
        self._think_th      = None
        self._ui_state      = "idle"
        self._turn_active   = False
        self._quiet_since   = None
        self._away_peak     = 0.0
        self._followup_event = None
        set_speech_hook(self._on_speech_enqueued)

        global _detector
        _detector = MomentDetector(ui_callback=self._detector_msg)

        self._build_ui()
        self.add_log_signal.connect(self._add_log)
        self.set_state_signal.connect(self._set_state)

        self._boot_sequence()
        threading.Thread(target=init_spotify, daemon=True).start()

        QTimer(self, timeout=self._tick_clock).start(1000)
        QTimer(self, timeout=self._refresh_spotify).start(5000)
        QTimer(self, timeout=self._refresh_sysinfo).start(2000)
        QTimer(self, timeout=self._refresh_network).start(2000)
        QTimer(self, timeout=self._refresh_detector).start(800)
        QTimer(self, timeout=self._speech_poll).start(150)
        QTimer(self, timeout=self._presence_tick).start(4000)
        QTimer(self, timeout=self._daily_tick).start(60000)
        QTimer.singleShot(2500, self._startup_memory_flow)

    # ─────────────────────────────────────────────────────────
    def _boot_sequence(self):
        self._log("ORION system booted successfully...")
        self._log("All systems online and functional.")
        self._log("Voice recognition: ACTIVE")
        self._log("Internet connection: STABLE" if self._has_internet() else "Internet connection: OFFLINE")
        self._log(f"AI Engine: READY — {KEYS.summary()}" if KEYS.has_any()
                  else "AI Engine: NO API KEY — open 'Manage API Keys' (right panel)")
        self._log(f"Memory: {len(MEMORY.data['facts'])} facts · {len(MEMORY.data['events'])} events stored")
        self._log("Voice engine: queued · interruptible ('stop speaking')")
        self._log("Moment Detector: STANDBY")
        self._log("Speak Mode: OFF (tap SPEAK MODE or say 'speak mode on')")
        self._log("Awaiting your command...")
        QTimer.singleShot(300, lambda: self._orion_says(say("online")))

    def _has_internet(self):
        try:
            socket.gethostbyname("google.com"); return True
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        self.bg = HUDBackground(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(10)

        # ── TOP BAR ──
        top = QHBoxLayout()
        logo = QLabel("◉ ORION v4")
        logo.setFont(QFont("Consolas", 11, QFont.Bold))
        logo.setStyleSheet(f"color:{CYAN_HEX};")
        top.addWidget(logo)
        top.addStretch()

        title = QLabel("O R I O N")
        title.setFont(QFont("Consolas", 20, QFont.Bold))
        title.setStyleSheet(f"color:{CYAN_HEX}; letter-spacing:8px;")
        top.addWidget(title)
        top.addStretch()

        wifi_lbl = QLabel("📶")
        wifi_lbl.setFont(QFont("Arial", 13))
        wifi_lbl.setStyleSheet("color:#9fe; background:transparent;")
        top.addWidget(wifi_lbl)

        for sym, col, fn in [("—", "#5ad", self.showMinimized), ("✕", "#f55", self.close)]:
            b = QPushButton(sym); b.setFixedSize(26, 26)
            b.setStyleSheet(f"""QPushButton{{background:rgba(255,255,255,0.06);
                border:1px solid rgba(0,200,255,0.3); border-radius:13px; color:{col};
                font-weight:bold;}}
                QPushButton:hover{{background:rgba(0,200,255,0.2);}}""")
            b.clicked.connect(fn)
            top.addWidget(b)
        root.addLayout(top)

        # ── MAIN 3-COLUMN AREA ──
        main = QHBoxLayout()
        main.setSpacing(12)

        # LEFT COLUMN
        left = QVBoxLayout(); left.setSpacing(12)
        left_w = QWidget(); left_w.setLayout(left); left_w.setFixedWidth(300)

        sys_panel, sys_c = make_panel("⚡ SYSTEM STATUS")
        self.heartbeat = HeartbeatWidget(); sys_c.addWidget(self.heartbeat)
        self.sys_status_lbl = QLabel("ORION AI ONLINE")
        self.sys_status_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        self.sys_status_lbl.setStyleSheet("color: rgb(70,230,150); background:transparent;")
        sub = QLabel("STATUS: ACTIVE"); sub.setFont(QFont("Consolas", 8))
        sub.setStyleSheet("color: rgba(200,220,230,0.55); background:transparent;")
        sys_c.addWidget(self.sys_status_lbl); sys_c.addWidget(sub)
        sys_c.addWidget(DotRow(5))
        left.addWidget(sys_panel)

        voice_panel, voice_c = make_panel("🎙 VOICE STATUS")
        self.waveform = Waveform(); voice_c.addWidget(self.waveform)
        self.voice_status_lbl = QLabel("Idle")
        self.voice_status_lbl.setFont(QFont("Consolas", 8))
        self.voice_status_lbl.setStyleSheet("color: rgba(200,220,230,0.6); background:transparent;")
        voice_c.addWidget(self.voice_status_lbl)

        self._speak_btn_idle_style = """
            QPushButton{ background: rgba(0,200,255,0.08); border:1px solid rgba(0,200,255,0.3);
                         border-radius:6px; color:#cfe9f5; font-weight:bold; }
            QPushButton:hover{ background: rgba(0,200,255,0.20); }
        """
        self._speak_btn_active_style = """
            QPushButton{ background: rgba(70,230,150,0.25); border:1px solid rgb(70,230,150);
                         border-radius:6px; color: rgb(70,230,150); font-weight:bold; }
            QPushButton:hover{ background: rgba(70,230,150,0.35); }
        """
        self.speak_mode_btn = QPushButton("🗣  SPEAK MODE: OFF")
        self.speak_mode_btn.setFixedHeight(32)
        self.speak_mode_btn.setFont(QFont("Consolas", 9))
        self.speak_mode_btn.setCursor(Qt.PointingHandCursor)
        self.speak_mode_btn.setStyleSheet(self._speak_btn_idle_style)
        self.speak_mode_btn.clicked.connect(self._toggle_speak_mode)
        voice_c.addWidget(self.speak_mode_btn)

        left.addWidget(voice_panel)

        quick_panel, quick_c = make_panel("🗲 QUICK COMMANDS")
        quick_cmds = [
            ("🌐  Open Chrome", "chrome"),
            ("📝  Open Notepad", "notepad"),
            ("🎵  Play Music", "spotify chalu"),
            ("🌤  Weather Update", "weather Delhi"),
            ("📸  Screenshot", "screenshot"),
            ("👁  Moment Detector", "see me"),
            ("🗣  Speak Mode", "speak mode on"),
            ("🧠  What You Remember", "what do you remember"),
        ]
        for label, cmd in quick_cmds:
            quick_c.addWidget(make_qbtn(label, lambda _, c=cmd: self._send(c)))
        left.addWidget(quick_panel)

        vol_panel, vol_c = make_panel("🔊 VOLUME CONTROL")
        vol_row = QHBoxLayout()
        mute_btn = QPushButton("🔇"); mute_btn.setFixedSize(30, 30)
        mute_btn.setStyleSheet("""QPushButton{background:rgba(0,200,255,0.1);
            border:1px solid rgba(0,200,255,0.3); border-radius:6px; color:#cfe9f5;}
            QPushButton:hover{background:rgba(0,200,255,0.22);}""")
        mute_btn.clicked.connect(lambda: self._send("mute"))
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100); self.vol_slider.setValue(self._vol_value)
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal{ height:6px; background: rgba(255,255,255,0.1); border-radius:3px;}
            QSlider::handle:horizontal{ background: rgb(0,200,255); width:14px; margin:-4px 0; border-radius:7px;}
            QSlider::sub-page:horizontal{ background: rgb(0,200,255); border-radius:3px;}
        """)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        self.vol_pct_lbl = QLabel(f"{self._vol_value}%")
        self.vol_pct_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        self.vol_pct_lbl.setStyleSheet(f"color:{CYAN_HEX}; background:transparent;")
        self.vol_pct_lbl.setFixedWidth(38)
        vol_row.addWidget(mute_btn); vol_row.addWidget(self.vol_slider); vol_row.addWidget(self.vol_pct_lbl)
        vol_c.addLayout(vol_row)
        left.addWidget(vol_panel)
        left.addStretch()

        # CENTER COLUMN
        center = QVBoxLayout(); center.setSpacing(12)

        head_panel, head_c = make_panel("◎ ORION AI ASSISTANT")
        head_row = QHBoxLayout()
        greet_col = QVBoxLayout(); greet_col.setSpacing(2)
        hello = QLabel("Hello, I'm"); hello.setFont(QFont("Consolas", 14))
        hello.setStyleSheet(f"color:{CYAN_HEX}; background:transparent;")
        big = QLabel("ORION"); big.setFont(QFont("Consolas", 38, QFont.Bold))
        big.setStyleSheet(f"color:{CYAN_HEX}; background:transparent; letter-spacing:2px;")
        self.greet_sub = QLabel("Your AI Assistant")
        self.greet_sub.setFont(QFont("Consolas", 11))
        self.greet_sub.setStyleSheet("color: rgba(220,235,245,0.8); background:transparent;")
        self.greet_ready = QLabel("Ready to assist you!")
        self.greet_ready.setFont(QFont("Consolas", 9))
        self.greet_ready.setStyleSheet("color: rgba(70,230,150,0.9); background:transparent;")
        greet_col.addWidget(hello); greet_col.addWidget(big)
        greet_col.addWidget(self.greet_sub); greet_col.addWidget(self.greet_ready)
        greet_col.addStretch()
        head_row.addLayout(greet_col, 1)

        self.center_ring = CenterRing()
        head_row.addWidget(self.center_ring, 0, Qt.AlignCenter)
        head_c.addLayout(head_row)

        modules_row = QHBoxLayout(); modules_row.setSpacing(8)
        self.mod_voice    = ModuleIcon("🎙", "Voice Control")
        self.mod_web      = ModuleIcon("🌐", "Web Access")
        self.mod_system   = ModuleIcon("⚙", "System Control")
        self.mod_chat     = ModuleIcon("🤖", "AI Chat")
        self.mod_detector = ModuleIcon("📷", "Moment Detector")
        for m in [self.mod_voice, self.mod_web, self.mod_system, self.mod_chat, self.mod_detector]:
            modules_row.addWidget(m)
        modules_row.addStretch()
        head_c.addLayout(modules_row)
        center.addWidget(head_panel)

        console_panel, console_c = make_panel("⌨ ORION CONSOLE")
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))
        self.console.setStyleSheet("""
            QTextEdit{ background: rgba(0,0,0,0.25); border: none; color: rgb(120,230,255); }
            QScrollBar:vertical{ background: transparent; width:4px; }
            QScrollBar::handle:vertical{ background: rgba(0,200,255,0.3); border-radius:2px; }
        """)
        console_c.addWidget(self.console)

        inp_row = QHBoxLayout(); inp_row.setSpacing(6)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your command here... ('speak mode on' bolo continuous chat ke liye)")
        self.input_field.setFont(QFont("Consolas", 10)); self.input_field.setFixedHeight(38)
        self.input_field.setStyleSheet("""
            QLineEdit{ background: rgba(0,0,0,0.3); border:1px solid rgba(0,200,255,0.3);
                       border-radius:8px; color:#eaf8ff; padding:0 12px;}
            QLineEdit:focus{ border-color: rgba(0,200,255,0.7); }
        """)
        self.input_field.returnPressed.connect(self._on_send)
        self.input_field.textChanged.connect(self._on_text_changed)

        self.lang_badge = QLabel("HI/EN")
        self.lang_badge.setFixedSize(46, 22); self.lang_badge.setAlignment(Qt.AlignCenter)
        self.lang_badge.setFont(QFont("Consolas", 7, QFont.Bold))
        self._set_lang_badge("hinglish")

        send_btn = QPushButton("➤ SEND"); send_btn.setFixedSize(80, 38)
        send_btn.setFont(QFont("Consolas", 9, QFont.Bold))
        send_btn.setStyleSheet("""QPushButton{background: rgb(0,200,255); border:none;
            border-radius:8px; color:#001018; font-weight:bold;}
            QPushButton:hover{background: rgb(60,220,255);}
            QPushButton:pressed{background: rgb(0,150,200);}""")
        send_btn.clicked.connect(self._on_send)

        self.mic_btn = QPushButton("🎙"); self.mic_btn.setFixedSize(38, 38)
        self.mic_btn.setFont(QFont("Arial", 13))
        self._mic_idle = ("QPushButton{background: rgba(0,200,255,0.1); border:1px solid "
                           "rgba(0,200,255,0.35); border-radius:8px; color: rgb(0,200,255);}"
                           "QPushButton:hover{background: rgba(0,200,255,0.25);}")
        self._mic_active = ("QPushButton{background: rgba(0,200,255,0.45); border:2px solid "
                             "rgb(0,200,255); border-radius:8px; color: white;}")
        self.mic_btn.setStyleSheet(self._mic_idle)
        self.mic_btn.clicked.connect(self._on_mic)

        inp_row.addWidget(self.input_field)
        inp_row.addWidget(self.lang_badge)
        inp_row.addWidget(self.mic_btn)
        inp_row.addWidget(send_btn)
        console_c.addLayout(inp_row)
        center.addWidget(console_panel, 1)

        # RIGHT COLUMN
        right = QVBoxLayout(); right.setSpacing(12)
        right_w = QWidget(); right_w.setLayout(right); right_w.setFixedWidth(300)

        time_panel, time_c = make_panel("📅 TIME & DATE")
        self.clock_lbl = QLabel("00:00:00")
        self.clock_lbl.setFont(QFont("Consolas", 22, QFont.Bold))
        self.clock_lbl.setStyleSheet(f"color:{CYAN_HEX}; background:transparent;")
        self.date_lbl = QLabel("")
        self.date_lbl.setFont(QFont("Consolas", 9))
        self.date_lbl.setStyleSheet("color: rgba(200,220,230,0.7); background:transparent;")
        time_c.addWidget(self.clock_lbl); time_c.addWidget(self.date_lbl)
        right.addWidget(time_panel)

        info_panel, info_c = make_panel("🖥 SYSTEM INFO")
        self.bar_cpu = BarMeter("CPU Usage")
        self.bar_ram = BarMeter("RAM Usage")
        self.bar_disk = BarMeter("Disk Usage")
        self.bar_batt = BarMeter("Battery")
        for b in [self.bar_cpu, self.bar_ram, self.bar_disk, self.bar_batt]:
            info_c.addWidget(b)
        if not _HAS_PSUTIL:
            note = QLabel("psutil not installed — install for live stats")
            note.setFont(QFont("Consolas", 7)); note.setWordWrap(True)
            note.setStyleSheet("color: rgba(255,150,40,0.8); background:transparent;")
            info_c.addWidget(note)
        right.addWidget(info_panel)

        key_panel, key_c = make_panel("🔑 AI KEYS")
        self.key_status_lbl = QLabel("")
        self.key_status_lbl.setFont(QFont("Consolas", 8))
        self.key_status_lbl.setWordWrap(True)
        key_c.addWidget(self.key_status_lbl)
        key_c.addWidget(make_qbtn("⚙  Manage API Keys", self._open_key_manager))
        self._refresh_key_summary()
        right.addWidget(key_panel)

        net_panel, net_c = make_panel("📡 NETWORK STATUS")
        self.net_status_lbl = QLabel("● Checking...")
        self.net_status_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        self.net_status_lbl.setStyleSheet("color: rgb(70,230,150); background:transparent;")
        self.net_ip_lbl = QLabel("IP: —")
        self.net_ip_lbl.setFont(QFont("Consolas", 8))
        self.net_ip_lbl.setStyleSheet("color: rgba(200,220,230,0.6); background:transparent;")
        speed_row = QHBoxLayout()
        self.net_up_lbl = QLabel("↑ 0 KB/s")
        self.net_down_lbl = QLabel("↓ 0 KB/s")
        for lbl in [self.net_up_lbl, self.net_down_lbl]:
            lbl.setFont(QFont("Consolas", 8))
            lbl.setStyleSheet("color: rgba(200,220,230,0.7); background:transparent;")
        speed_row.addWidget(self.net_up_lbl); speed_row.addWidget(self.net_down_lbl)
        net_c.addWidget(self.net_status_lbl); net_c.addWidget(self.net_ip_lbl); net_c.addLayout(speed_row)
        right.addWidget(net_panel)

        det_panel, det_c = make_panel("📷 MOMENT DETECTOR")
        self.det_face = DotStatus("Face Capture")
        self.det_smile = DotStatus("Smile Capture")
        self.det_motion = DotStatus("Motion Capture")
        for d in [self.det_face, self.det_smile, self.det_motion]:
            det_c.addWidget(d)
        saved_row = QHBoxLayout()
        saved_lbl = QLabel("Moments Saved"); saved_lbl.setFont(QFont("Consolas", 9))
        saved_lbl.setStyleSheet("color:#cfe9f5; background:transparent;")
        self.moments_count_lbl = QLabel("0")
        self.moments_count_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
        self.moments_count_lbl.setStyleSheet(f"color:{CYAN_HEX}; background:transparent;")
        saved_row.addWidget(saved_lbl); saved_row.addStretch(); saved_row.addWidget(self.moments_count_lbl)
        det_c.addLayout(saved_row)
        right.addWidget(det_panel)
        right.addStretch()

        main.addWidget(left_w)
        main.addLayout(center, 1)
        main.addWidget(right_w)
        root.addLayout(main, 1)

        # ── BOTTOM TASKBAR ──
        bottom = QHBoxLayout()
        bottom.addStretch()
        taskbar_items = [
            ("🏠", lambda: self.input_field.setFocus()),
            ("▦", lambda: self.input_field.setFocus()),
            ("🌐", lambda: self._send("chrome")),
            ("⚙", lambda: self._send("system control")),
            ("📷", lambda: self._send("camera")),
            ("⌨", lambda: self.input_field.setFocus()),
            ("🎵", lambda: self._send("spotify chalu")),
        ]
        for sym, fn in taskbar_items:
            b = QPushButton(sym); b.setFixedSize(40, 40); b.setFont(QFont("Arial", 13))
            b.setStyleSheet("""QPushButton{background: rgba(0,200,255,0.08);
                border:1px solid rgba(0,200,255,0.25); border-radius:8px; color:#cfe9f5;}
                QPushButton:hover{background: rgba(0,200,255,0.22);}""")
            b.clicked.connect(fn)
            bottom.addWidget(b)
        bottom.addStretch()
        root.addLayout(bottom)

    def resizeEvent(self, e):
        self.bg.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(e)

    def closeEvent(self, e):
        try:
            if self._speak_mode_on:
                self._stop_speak_mode()
        except Exception:
            pass
        try:
            TTS.stop()
            MEMORY.touch(); MEMORY.save()
        except Exception:
            pass
        super().closeEvent(e)

    # ─── helpers ───────────────────────────
    def _set_lang_badge(self, lang):
        styles = {
            "hindi":   ("हिन्दी", "rgba(255,100,100,0.75)"),
            "hinglish":("HI/EN",  "rgba(0,200,255,0.75)"),
            "english": ("EN",     "rgba(80,180,255,0.75)"),
        }
        txt, col = styles.get(lang, styles["hinglish"])
        self.lang_badge.setText(txt)
        self.lang_badge.setStyleSheet(f"background:{col}; border-radius:5px; color:#001018;"
                                       f"font-family:Consolas; font-size:8px; font-weight:bold;")

    def _on_text_changed(self, text):
        if text.strip():
            self._set_lang_badge(detect_language(text))

    def _on_volume_changed(self, value):
        diff = value - self._vol_value
        self._vol_value = value
        self.vol_pct_lbl.setText(f"{value}%")
        steps = abs(diff)
        if steps:
            key = "volumeup" if diff > 0 else "volumedown"
            for _ in range(min(steps, 8)):
                pyautogui.press(key)

    def _set_state(self, s):
        self._ui_state = s
        self.center_ring.set_state(s)
        labels = {"idle":"Ready to assist you!","listening":"Listening...","thinking":"Thinking...",
                  "speaking":"Speaking...","detecting":"Watching for moments..."}
        self.greet_ready.setText(labels.get(s, s))
        self.sys_status_lbl.setText("ORION AI ONLINE" if s == "idle" else f"ORION {s.upper()}")
        self.voice_status_lbl.setText("Listening..." if s == "listening" else "Idle")
        self.waveform.set_amp(0.6 if s == "listening" else (0.3 if s == "speaking" else 0.1))

        self.mod_voice.set_active(s == "listening" or self._speak_mode_on)
        self.mod_chat.set_active(s in ("thinking", "speaking"))
        self.mod_detector.set_active(s == "detecting")

    def _flash_module(self, mod, ms=1400):
        mod.set_active(True)
        QTimer.singleShot(ms, lambda: mod.set_active(False))

    def _log(self, text):
        self.add_log_signal.emit(text, "system")

    def _add_log(self, text, who):
        prefix = {"system": "> ", "user": "> YOU: ", "orion": "> ORION: "}.get(who, "> ")
        self.console.append(prefix + text)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _detector_msg(self, text):
        self.add_log_signal.emit(text, "orion")

    def _orion_says(self, text):
        self._turn_active = True
        self.add_log_signal.emit(text, "orion")
        self.set_state_signal.emit("speaking")
        speak(text)          # _speech_poll() returns the UI to idle once ORION has really finished

    def _clear_chat(self):
        global conversation_history
        conversation_history = []
        self.console.clear()
        self._orion_says(say("chat_clear"))

    # ─── periodic refreshers ───────────────
    def _tick_clock(self):
        n = datetime.datetime.now()
        self.clock_lbl.setText(n.strftime("%H:%M:%S"))
        self.date_lbl.setText(n.strftime("%A, %d %B %Y"))

    def _refresh_spotify(self):
        song, artist = spotify_current()
        # surfaced via console occasionally rather than dedicated bar (kept compact in HUD)

    def _refresh_sysinfo(self):
        if _HAS_PSUTIL:
            try:
                self.bar_cpu.set_value(psutil.cpu_percent())
                self.bar_ram.set_value(psutil.virtual_memory().percent)
                self.bar_disk.set_value(psutil.disk_usage(os.path.abspath(os.sep)).percent)
                batt = psutil.sensors_battery()
                self.bar_batt.set_value(batt.percent if batt else 100)
            except Exception:
                pass
        else:
            for b in [self.bar_cpu, self.bar_ram, self.bar_disk, self.bar_batt]:
                b.set_value(0)

    def _refresh_network(self):
        connected = self._has_internet()
        if connected:
            self.net_status_lbl.setText("● Connected")
            self.net_status_lbl.setStyleSheet("color: rgb(70,230,150); background:transparent;")
        else:
            self.net_status_lbl.setText("● Disconnected")
            self.net_status_lbl.setStyleSheet("color: rgb(255,80,80); background:transparent;")
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "N/A"
        self.net_ip_lbl.setText(f"IP: {ip}")

        if _HAS_PSUTIL:
            try:
                io = psutil.net_io_counters()
                now = time.time()
                if self._net_last:
                    prev_io, prev_t = self._net_last
                    dt = max(now - prev_t, 0.5)
                    up = (io.bytes_sent - prev_io.bytes_sent) / dt / 1024
                    down = (io.bytes_recv - prev_io.bytes_recv) / dt / 1024
                    self.net_up_lbl.setText(f"↑ {up:.1f} KB/s")
                    self.net_down_lbl.setText(f"↓ {down:.1f} KB/s")
                self._net_last = (io, now)
            except Exception:
                pass

    def _refresh_detector(self):
        global _detector
        if not _detector:
            return
        running = _detector.is_running()
        self.det_face.set_state(running)
        self.det_smile.set_state(running)
        self.det_motion.set_state(running)
        self.moments_count_lbl.setText(str(_detector.total()))
        self.mod_detector.set_active(running)
        if running and self.center_ring._state == "idle":
            self.set_state_signal.emit("detecting")

    # ─── send / mic / process ───────────────
    def _send(self, text=None):
        msg = (text or self.input_field.text()).strip()
        if not msg:
            return
        self.input_field.clear()
        self.add_log_signal.emit(msg, "user")
        self._process(msg)

    def _on_send(self):
        self._send()

    def _on_mic(self):
        if self._listen_th and self._listen_th.isRunning():
            return
        self._pause_speak_gate()
        self._turn_active = False
        self.set_state_signal.emit("listening")
        self.mic_btn.setStyleSheet(self._mic_active)
        self._listen_th = ListenThread()
        self._listen_th.result.connect(self._on_voice_result)
        self._listen_th.start()

    def _on_voice_result(self, text):
        self.mic_btn.setStyleSheet(self._mic_idle)
        if text:
            self.input_field.setText(text)
            self.add_log_signal.emit(text, "user")
            self._process(text)
        else:
            self.set_state_signal.emit("idle")
            self._orion_says(say("not_understood"))

    # ─── Speak Mode (continuous hands-free voice chat) ───
    def _toggle_speak_mode(self):
        if self._speak_mode_on:
            self._stop_speak_mode()
        else:
            self._start_speak_mode()

    def _start_speak_mode(self):
        if self._speak_mode_on:
            return
        self._speak_mode_on = True
        self._speak_gate.set()
        self._speak_thread = ContinuousListenThread(self._speak_gate)
        self._speak_thread.text_result.connect(self._on_speak_mode_text)
        self._speak_thread.start()
        self.speak_mode_btn.setText("🗣  SPEAK MODE: ON")
        self.speak_mode_btn.setStyleSheet(self._speak_btn_active_style)
        self.mod_voice.set_active(True)
        self._orion_says(say("speak_mode_on"))

    def _stop_speak_mode(self):
        if not self._speak_mode_on:
            return
        self._speak_mode_on = False
        if self._speak_thread:
            self._speak_thread.stop()
            self._speak_gate.set()
            self._speak_thread = None
        self.speak_mode_btn.setText("🗣  SPEAK MODE: OFF")
        self.speak_mode_btn.setStyleSheet(self._speak_btn_idle_style)
        self.mod_voice.set_active(False)
        self._orion_says(say("speak_mode_off"))

    def _pause_speak_gate(self):
        if self._speak_mode_on:
            self._speak_gate.clear()

    def _resume_speak_gate(self):
        if self._speak_mode_on:
            self._speak_gate.set()

    def _on_speak_mode_text(self, text):
        if not self._speak_mode_on or not text:
            return
        if any(w in text for w in SLEEP_WORDS):
            self._stop_speak_mode()
            return
        # Show what was heard in the typing bar for a moment, then clear it
        # automatically so it's ready for the next thing you say — no need
        # to touch it by hand in Speak Mode.
        self.input_field.setText(text)
        QTimer.singleShot(600, lambda: self.input_field.clear() if self._speak_mode_on else None)
        self.add_log_signal.emit(text, "user")
        self._pause_speak_gate()
        self._process(text)

    def _process(self, cmd):
        lang = detect_language(cmd)
        self._set_lang_badge(lang)
        c_lower = cmd.lower()

        # Speak Mode toggle (typed, quick-command, or spoken)
        speak_on_words = [
            "speak mode on", "speak mode chalu", "spik mode on", "continuous mode on",
            "hands free on", "hands-free on", "talk to me", "let's talk", "baat karte raho",
            "baat mode chalu", "स्पीक मोड चालू", "बात मोड चालू", "निरंतर मोड चालू",
        ]
        speak_off_words = [
            "speak mode off", "speak mode band", "spik mode off", "continuous mode off",
            "hands free off", "hands-free off", "baat mode band", "स्पीक मोड बंद", "बात मोड बंद",
        ]
        if any(w in c_lower for w in speak_on_words):
            self._start_speak_mode(); return
        if any(w in c_lower for w in speak_off_words):
            self._stop_speak_mode(); return

        # v4: stop-talking · API key manager · memory · trips ("going to market" / "I'm back")
        if self._handle_meta_commands(cmd, c_lower):
            return

        # Pause continuous listening (if active) for this turn so ORION
        # doesn't pick its own voice back up over the speakers.
        self._pause_speak_gate()

        try:
            if any(x in c_lower for x in ["chrome","youtube","whatsapp","instagram","spotify","search","क्रोम","यूट्यूब"]):
                self._flash_module(self.mod_web)
            if any(x in c_lower for x in ["shutdown","restart","lock","volume","mute","screenshot","calculator","notepad","task manager"]):
                self._flash_module(self.mod_system)

            result = handle_command(cmd)

            if result == "CLEAR":
                self._clear_chat(); return

            if isinstance(result, str) and result not in (True, False, "CLEAR"):
                self._orion_says(result); return

            if result:
                self._turn_active = True      # _speech_poll() settles the UI + mic when ORION is quiet
                self.set_state_signal.emit("speaking")
                return

            # If ORION had just asked how your trip went, remember your answer.
            if self._followup_event:
                MEMORY.attach_reply(self._followup_event, cmd)
                self._followup_event = None

            # AI fallback
            if self._ai_th and self._ai_th.isRunning():
                self._ai_th.quit()
            self.set_state_signal.emit("thinking")
            self._log("ORION is thinking...")
            self._ai_th = AIThread(cmd, lang)
            self._ai_th.result.connect(self._on_ai_result)
            self._ai_th.start()
        except Exception as e:
            # Never let a bad command or a network/API hiccup kill the app
            # or leave Speak Mode's mic stuck paused.
            self._log(f"Error handling that command: {e}")
            self._orion_says("Sorry, something went wrong handling that. Please try again.")

    def _on_ai_result(self, answer):
        self._turn_active = True
        if LAST_AI_SOURCE:
            self._log(f"[AI] answered via {LAST_AI_SOURCE}")
        MEMORY.clear_pending_question()
        self.add_log_signal.emit(answer, "orion")
        self.set_state_signal.emit("speaking")
        speak(answer)

    # ═════════════════════════════════════════════════════════
    #  v4: SPEECH SETTLING · API KEYS · MEMORY · NEXT-DAY THINKING
    # ═════════════════════════════════════════════════════════
    def _on_speech_enqueued(self):
        # Called (from any thread) the instant ORION is about to talk:
        # mute the Speak-Mode mic right away so it never hears itself.
        if self._speak_mode_on:
            self._speak_gate.clear()

    def _speech_poll(self):
        """Every 150 ms: follow the REAL speech state instead of guessing with timers."""
        busy = TTS.busy()
        ai = bool((self._ai_th and self._ai_th.isRunning()) or
                  (self._think_th and self._think_th.isRunning()))
        if busy:
            self._quiet_since = None
            if self._ui_state != "speaking":
                self.set_state_signal.emit("speaking")
            return
        if ai or not self._turn_active:
            return
        now = time.monotonic()
        if self._quiet_since is None:
            self._quiet_since = now
            return
        if now - self._quiet_since >= 0.5:          # short tail so the mic skips the room echo
            self._turn_active = False
            self._quiet_since = None
            self.set_state_signal.emit("idle")
            self._resume_speak_gate()

    # ─── API keys ───
    def _open_key_manager(self):
        dlg = KeyManagerDialog(KEYS, self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_key_summary()
            self._log(f"API keys updated — {KEYS.summary()}")

    def _refresh_key_summary(self):
        ok = KEYS.has_any()
        self.key_status_lbl.setText(("● " if ok else "● ") + KEYS.summary())
        self.key_status_lbl.setStyleSheet(
            f"color: {'rgb(70,230,150)' if ok else 'rgb(255,150,40)'}; background:transparent;")

    # ─── meta commands: stop talking · key manager · memory · trips ───
    def _handle_meta_commands(self, cmd, c):
        stop_words = ["stop speaking", "stop talking", "be quiet", "quiet please", "orion stop",
                      "bolna band", "chup raho", "ruk jao orion", "orion ruko", "चुप रहो", "बोलना बंद"]
        if any(w in c for w in stop_words):
            TTS.stop()
            self._turn_active = True
            return True

        MEMORY.log_user(cmd)

        if any(w in c for w in ["manage keys", "manage api", "api keys kholo", "open api keys", "key manager", "keys manage"]):
            self._open_key_manager()
            return True

        m = re.match(r"^(?:orion[,\s]+)?(?:please\s+)?(?:remember|yaad rakho|yaad rakh|yaad rakhna|note kar lo|note karo|याद रखो)"
                     r"\s+(?:that\s+|ki\s+)?(.+)$", cmd.strip(), re.I)
        if m:
            fact = m.group(1).strip()
            MEMORY.add_fact(fact)
            self._orion_says(f"Noted, sir. I'll remember that {fact[:90]}.")
            return True

        if any(w in c for w in ["what do you remember", "what you remember", "what do you know about me",
                                "kya yaad hai", "tumhe kya yaad", "show memory", "memory dikhao",
                                "meri memory", "क्या याद है"]):
            for line in MEMORY.summary_lines():
                self._log(line)
            self._orion_says(MEMORY.spoken_summary())
            return True

        if any(w in c for w in ["forget everything", "clear memory", "memory clear", "sab bhool jao",
                                "sab kuch bhool jao", "सब भूल जाओ"]):
            if "confirm" in c:
                MEMORY.wipe()
                self._followup_event = None
                self._orion_says("Memory cleared, sir. Starting fresh.")
            else:
                self._orion_says("To wipe everything I remember, say or type 'confirm clear memory'.")
            return True

        place = MEMORY.parse_departure(cmd)
        if place:
            MEMORY.add_out(place, cmd)
            self._away_peak = 0.0
            self._orion_says(MEMORY.ack_text(place))
            return True

        kind = MEMORY.parse_return(cmd)
        ev = MEMORY.open_out()
        if kind == "strong" or (kind == "weak" and ev):
            if ev:
                self._welcome_back(ev)
            else:
                self._orion_says("Welcome back, sir.")
            return True
        return False

    def _proactive_say(self, text):
        """ORION speaks first (welcome-back / morning question) and remembers that it asked."""
        MEMORY.set_pending_question(text)
        global conversation_history
        conversation_history.append({"role": "model", "parts": [{"text": text}]})
        conversation_history = conversation_history[-40:]
        self._orion_says(text)

    def _welcome_back(self, ev):
        text = MEMORY.welcome_text(ev)
        MEMORY.close_event(ev["id"])
        self._followup_event = ev["id"]
        self._away_peak = 0.0
        self._proactive_say(text)

    def _presence_tick(self):
        """Every 4 s: notice when you come back to the PC after being away on a trip."""
        MEMORY.touch()
        ev = MEMORY.open_out()
        if not ev:
            self._away_peak = 0.0
            return
        idle = user_idle_seconds()
        if idle is None:
            return
        self._away_peak = max(self._away_peak, idle)
        if idle < 8 and self._away_peak >= AWAY_MIN_SECONDS:
            self._welcome_back(ev)

    # ─── next-day thinking ───
    def _daily_tick(self):
        MEMORY.save()
        if MEMORY.needs_daily_think() and _now().hour >= DAILY_THINK_HOUR:
            self._start_daily_think()

    def _start_daily_think(self):
        if self._think_th and self._think_th.isRunning():
            return
        MEMORY.mark_thought()
        self._log("ORION is thinking about yesterday...")
        self.set_state_signal.emit("thinking")
        self._think_th = ThinkThread()
        self._think_th.result.connect(self._on_think_result)
        self._think_th.start()

    def _on_think_result(self, question):
        MEMORY.remember_question(question)
        self._proactive_say(f"Good {daypart()}, sir. {question}")

    def _startup_memory_flow(self):
        try:
            ev = MEMORY.open_out()
            if ev and MEMORY.event_age_minutes(ev) >= 20:          # you left, and ORION was off meanwhile
                self._welcome_back(ev)
            elif MEMORY.needs_daily_think():
                self._start_daily_think()
            elif MEMORY.prev_seen and (_now() - MEMORY.prev_seen).total_seconds() > 6 * 3600:
                self._orion_says(f"Good {daypart()}, sir. Good to have you back.")
        except Exception as e:
            self._log(f"Memory startup check failed: {e}")


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════
def install_autostart(enable=True):
    """Windows: make ORION start by itself at login (so the next-day question really happens)."""
    if os.name != "nt":
        print("Autostart is only supported on Windows."); return
    startup = os.path.join(os.environ.get("APPDATA", ""),
                           r"Microsoft\Windows\Start Menu\Programs\Startup")
    bat = os.path.join(startup, "ORION_autostart.bat")
    if not enable:
        try:
            os.remove(bat); print("ORION autostart removed.")
        except FileNotFoundError:
            print("ORION autostart was not installed.")
        return
    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")      # no console window
    if os.path.exists(pyw):
        py = pyw
    script = os.path.abspath(__file__)
    with open(bat, "w") as f:
        f.write(f'@echo off\r\ncd /d "{os.path.dirname(script)}"\r\nstart "" "{py}" "{script}"\r\n')
    print(f"ORION will now start with Windows ({bat}).")

def main():
    if "--autostart" in sys.argv:
        install_autostart(True); return
    if "--no-autostart" in sys.argv:
        install_autostart(False); return
    _init_tts()
    app = QApplication(sys.argv)
    app.setApplicationName("ORION")
    win = OrionWindow()
    screen = app.primaryScreen().geometry()
    win.setGeometry(screen)
    win.showFullScreen()
    sys.exit(app.exec_())   

if __name__ == "__main__":
    main()
