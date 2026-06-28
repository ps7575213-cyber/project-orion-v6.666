# ╔══════════════════════════════════════════════════════════════╗
# ║      ORION v3 — IRON MAN HUD EDITION (Fullscreen Dashboard)  ║
# ║   Hindi + English — Full command support in both languages   ║
# ║   + MOMENT DETECTOR — Auto Face/Smile/Motion Capture         ║
# ║   + Full HUD redesign: System / Voice / Network / Moments    ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Install:
#   pip install PyQt5 pyttsx3 SpeechRecognition pyautogui pywhatkit opencv-python requests spotipy psutil
#
# Keys set karo:
#   set GEMINI_API_KEY=your_key
#   set SPOTIFY_CLIENT_ID=your_id
#   set SPOTIFY_SECRET=your_secret
#   set SPOTIFY_USERNAME=your_username
#
# psutil optional hai — agar nahi mila to System Info panel "N/A" dikhayega.

import sys, os, math, socket, threading, datetime, time, webbrowser, requests
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
    QFrame, QScrollArea, QTextEdit, QSlider, QSizePolicy
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
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_SECRET    = os.getenv("SPOTIFY_SECRET", "")
SPOTIFY_USERNAME  = os.getenv("SPOTIFY_USERNAME", "")
SPOTIFY_REDIRECT  = "http://localhost:8888/callback"

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
    "no_key":       ("Gemini API key सेट नहीं है।","Gemini API key set nahi hai.","Gemini API key is not set."),
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
}

_current_lang = "hinglish"

def say(key, extra=""):
    idx = {"hindi": 0, "hinglish": 1, "english": 2}.get(_current_lang, 1)
    base = RESPONSES.get(key, ("","",""))[idx]
    return base + extra

# ══════════════════════════════════════════════
#  CONVERSATION MEMORY
# ══════════════════════════════════════════════
conversation_history = []

# ══════════════════════════════════════════════
#  TTS ENGINE
# ══════════════════════════════════════════════
_tts_engine = None
_speak_lock  = threading.Lock()

def _init_tts():
    global _tts_engine
    _tts_engine = pyttsx3.init()
    _tts_engine.setProperty("rate", 160)
    voices = _tts_engine.getProperty("voices")
    for v in voices:
        if "hindi" in v.name.lower() or "hi-in" in v.id.lower():
            _tts_engine.setProperty("voice", v.id)
            return
    if voices:
        _tts_engine.setProperty("voice", voices[0].id)

def speak(text):
    if not text:
        return
    print(f"\n{AI_NAME}: {text}")
    def _run():
        global _tts_engine
        with _speak_lock:
            try:
                if _tts_engine is None:
                    _init_tts()
                _tts_engine.say(text)
                _tts_engine.runAndWait()
            except Exception:
                try:
                    _init_tts()
                    _tts_engine.say(text)
                    _tts_engine.runAndWait()
                except Exception as e:
                    print(f"[TTS] {e}")
    threading.Thread(target=_run, daemon=True).start()

# ══════════════════════════════════════════════
#  GEMINI AI
# ══════════════════════════════════════════════
def chat_ai(user_msg, lang):
    global conversation_history
    if not GEMINI_API_KEY:
        return say("no_key")
    if lang == "hindi":
        system = (f"Aap {AI_NAME} hain — ek Iron Man JARVIS jaisa AI assistant. "
                  "Aap Hindi mein jawab dein. Seedha, shant aur helpful tone mein. "
                  "2-3 waakyom mein jawab dein. Devanagari script use karein.")
    elif lang == "hinglish":
        system = (f"You are {AI_NAME}, an Iron Man JARVIS-style AI assistant. "
                  "Reply in Hinglish (mix of Hindi and English, Roman script). "
                  "Casual, witty, helpful tone. Max 2-3 sentences.")
    else:
        system = (f"You are {AI_NAME}, an Iron Man JARVIS-style AI assistant. "
                  "Reply in clear, concise English. Calm, confident, helpful. Max 2-3 sentences.")

    conversation_history.append({"role": "user", "parts": [{"text": user_msg}]})
    recent = conversation_history[-10:]
    url = ("https://generativelanguage.googleapis.com/v1beta/"
           f"models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}")
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": recent,
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0.75}
    }
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=12)
            if r.status_code == 429:
                time.sleep(2 ** attempt); continue
            if r.status_code != 200:
                return f"API error {r.status_code}"
            answer = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            conversation_history.append({"role": "model", "parts": [{"text": answer}]})
            return answer
        except requests.exceptions.ConnectionError:
            return say("internet_error")
        except requests.exceptions.Timeout:
            return say("timeout")
        except Exception as e:
            print(f"[AI] {e}"); return say("timeout")
    return say("rate_limit")

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
        lang_idx = {"hindi":0,"hinglish":1,"english":2}.get(_current_lang,1)
        msgs = [
            f"मोमेंट डिटेक्टर बंद। कुल {self._total} पल कैप्चर किए।",
            f"Moment detector band. Kul {self._total} moments capture kiye.",
            f"Moment detector off. Total {self._total} moments captured."
        ]
        msg = msgs[lang_idx]
        speak(msg)
        if self._ui_callback:
            self._ui_callback(msg)

    def is_running(self):
        return self._running

    def total(self):
        return self._total

    def stats_text(self):
        lang_idx = {"hindi":0,"hinglish":1,"english":2}.get(_current_lang,1)
        msgs = [
            f"अब तक {self._total} पल '{MOMENTS_FOLDER}' फ़ोल्डर में सेव हैं।",
            f"Ab tak {self._total} moments '{MOMENTS_FOLDER}' folder mein save hain.",
            f"{self._total} moments saved so far in '{MOMENTS_FOLDER}' folder."
        ]
        return msgs[lang_idx]

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
        responses = {"hindi":f"अभी {t} बजे हैं।","hinglish":f"Abhi {t} baj rahe hain.","english":f"The time is {t}."}
        speak(responses.get(_current_lang, responses["hinglish"])); return True

    if any(x in c for x in ["date","तारीख","tarikh","din","दिन बताओ","aaj ka din"]):
        d = datetime.datetime.now()
        responses = {"hindi":f"आज {d.strftime('%d %B %Y')}, {d.strftime('%A')} है।",
                     "hinglish":f"Aaj {d.strftime('%d %B %Y')} hai, {d.strftime('%A')}.",
                     "english":f"Today is {d.strftime('%A, %d %B %Y')}."}
        speak(responses.get(_current_lang, responses["hinglish"])); return True

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

class AIThread(QThread):
    result = pyqtSignal(str)
    def __init__(self, prompt, lang):
        super().__init__()
        self.prompt = prompt
        self.lang   = lang
    def run(self):
        self.result.emit(chat_ai(self.prompt, self.lang))

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

    # ─────────────────────────────────────────────────────────
    def _boot_sequence(self):
        self._log("ORION system booted successfully...")
        self._log("All systems online and functional.")
        self._log("Voice recognition: ACTIVE")
        self._log("Internet connection: STABLE" if self._has_internet() else "Internet connection: OFFLINE")
        self._log("AI Engine: READY" if GEMINI_API_KEY else "AI Engine: NO API KEY SET")
        self._log("Moment Detector: STANDBY")
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
        logo = QLabel("◉ ORION v3")
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
        left.addWidget(voice_panel)

        quick_panel, quick_c = make_panel("🗲 QUICK COMMANDS")
        quick_cmds = [
            ("🌐  Open Chrome", "chrome"),
            ("📝  Open Notepad", "notepad"),
            ("🎵  Play Music", "spotify chalu"),
            ("🌤  Weather Update", "weather Delhi"),
            ("📸  Screenshot", "screenshot"),
            ("👁  Moment Detector", "see me"),
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
        self.input_field.setPlaceholderText("Type your command here... ('see me' bolo Moment Detector on karne ke liye)")
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
        self.center_ring.set_state(s)
        labels = {"idle":"Ready to assist you!","listening":"Listening...","thinking":"Thinking...",
                  "speaking":"Speaking...","detecting":"Watching for moments..."}
        self.greet_ready.setText(labels.get(s, s))
        self.sys_status_lbl.setText("ORION AI ONLINE" if s == "idle" else f"ORION {s.upper()}")
        self.voice_status_lbl.setText("Listening..." if s == "listening" else "Idle")
        self.waveform.set_amp(0.6 if s == "listening" else (0.3 if s == "speaking" else 0.1))

        self.mod_voice.set_active(s == "listening")
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
        self.add_log_signal.emit(text, "orion")
        self.set_state_signal.emit("speaking")
        speak(text)
        QTimer.singleShot(2200, lambda: self.set_state_signal.emit("idle"))

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

    def _process(self, cmd):
        lang = detect_language(cmd)
        self._set_lang_badge(lang)

        c_lower = cmd.lower()
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
            self.set_state_signal.emit("speaking")
            QTimer.singleShot(1400, lambda: self.set_state_signal.emit("idle"))
            return

        # AI fallback
        if self._ai_th and self._ai_th.isRunning():
            self._ai_th.quit()
        self.set_state_signal.emit("thinking")
        self._log("ORION is thinking...")
        self._ai_th = AIThread(cmd, lang)
        self._ai_th.result.connect(self._on_ai_result)
        self._ai_th.start()

    def _on_ai_result(self, answer):
        self.add_log_signal.emit(answer, "orion")
        self.set_state_signal.emit("speaking")
        speak(answer)
        QTimer.singleShot(2500, lambda: self.set_state_signal.emit("idle"))


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════
def main():
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