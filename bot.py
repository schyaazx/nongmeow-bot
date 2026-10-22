"""
น้องแมว Discord Bot  (ไฟล์เดียว แบ่งเป็นส่วนๆ  ค้นหาด้วย Ctrl+F เช่น "ส่วนที่ 3")
==============================================================================
  ส่วนที่ 0 │ เตรียมระบบ     อัปเดต yt-dlp / discord.py, หา deno          (รันก่อนเสมอ ไม่ต้องแก้)
  ส่วนที่ 1 │ ตั้งค่า         ค่าที่แก้ได้ทั้งหมด + สร้างบอท
  ส่วนที่ 2 │ 💬 คำพูด        ข้อความที่น้องแมวตอบ                        (แก้ที่ CHAT_RULES)
  ส่วนที่ 3 │ 🎵 เล่นเพลง     YouTube/ffmpeg, ตัวเล่น, Spotify, Apple Music, ค้นหา, คิว
  ส่วนที่ 4 │ ⌨️ คำสั่ง       Slash commands: 4.1 เพลง  4.2 ทั่วไป  4.3 ระบบ
  ส่วนที่ 5 │ ▶️ เริ่มบอท

ตัวแปรที่ตั้งบนโฮสต์ได้ (ไม่ตั้งก็ใช้ค่าปกติ):
  DISCORD_BOT_TOKEN      โทเคนบอท (จำเป็น)
  AUTO_UPDATE_YTDLP=0    ไม่อัปเดต yt-dlp ตอนเริ่ม      YTDLP_NIGHTLY=1  ใช้ yt-dlp รุ่น nightly
  AUTO_UPDATE_DISCORD=0  ไม่เช็ก/ติดตั้ง discord.py+davey   AUTO_FETCH_FFMPEG=0  ไม่โหลด ffmpeg สำรอง
  FFMPEG_PATH            ระบุตำแหน่ง ffmpeg เอง
  OPUS_PASSTHROUGH=0     ใช้โหมดเสียงแบบเก่า (ต้องมี libopus)
  DOWNLOAD_BEFORE_PLAY=0 ให้ ffmpeg ดึงจาก YouTube ตรงๆ แทนการโหลดลงไฟล์ก่อน
"""
import random
import os
import sys
import subprocess
import asyncio
import re
import json
import html
import shutil
import glob
import threading
import collections
import time

# ==========================================================
# ส่วนที่ 0 │ เตรียมระบบ  (รันก่อนเสมอ ไม่ต้องแก้)
# ==========================================================

# ---- อัปเดต yt-dlp อัตโนมัติตอนบอทเริ่มทำงาน ----
# YouTube เปลี่ยนบ่อย yt-dlp เวอร์ชันเก่าจะพัง (เช่น "The page needs to be reloaded")
# โฮสต์บางที่ไม่อัปเกรดแพ็กเกจให้ จึงติดตั้งตัวล่าสุดไว้ในโฟลเดอร์ ytdlp_lib ข้างบอทเอง
# ปิดได้ด้วยตัวแปร AUTO_UPDATE_YTDLP=0 / ใช้รุ่น nightly ด้วย YTDLP_NIGHTLY=1
YTDLP_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ytdlp_lib")

def update_ytdlp():
    cmd = [sys.executable, "-m", "pip", "install", "-U", "--target", YTDLP_LIB_DIR, "yt-dlp[default]", "deno"]
    if os.getenv("YTDLP_NIGHTLY") == "1":
        cmd.insert(5, "--pre")  # nightly
    try:
        print("กำลังอัปเดต yt-dlp ...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            print(f"อัปเดต yt-dlp ไม่สำเร็จ (ใช้เวอร์ชันที่ติดตั้งอยู่แทน):\n{result.stderr[-500:]}")
    except Exception as e:
        print(f"อัปเดต yt-dlp ไม่สำเร็จ (ใช้เวอร์ชันที่ติดตั้งอยู่แทน): {e}")

if os.getenv("AUTO_UPDATE_YTDLP", "1") != "0":
    update_ytdlp()
if os.path.isdir(YTDLP_LIB_DIR):
    sys.path.insert(0, YTDLP_LIB_DIR)

# ---- เช็ก/ติดตั้งแพ็กเกจเสียงของ Discord ----
# ตั้งแต่ มี.ค. 2026 Discord บังคับใช้การเข้ารหัสเสียงแบบ DAVE
# บอทที่ใช้ discord.py เก่า (ต่ำกว่า 2.7.1) หรือไม่มีแพ็กเกจ davey จะโดนตัดออกจากห้องเสียงทันที (เงียบ ไม่มี error)
# ปิดได้ด้วยตัวแปร AUTO_UPDATE_DISCORD=0
def ensure_voice_deps():
    import importlib, importlib.metadata as md, re
    def ver(name):
        try:
            return md.version(name)
        except Exception:
            return None
    def as_tuple(v):
        return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])

    dv, dav, nacl = ver("discord.py"), ver("davey"), ver("PyNaCl")
    print(f"[deps] discord.py={dv} davey={dav} PyNaCl={nacl}")
    ok = bool(dv and dav and nacl and as_tuple(dv) >= (2, 7, 1))
    if ok or os.getenv("AUTO_UPDATE_DISCORD", "1") == "0":
        return
    print("[deps] กำลังติดตั้ง/อัปเดต discord.py (>=2.7.1) + davey + PyNaCl ...")
    cmd = [sys.executable, "-m", "pip", "install", "-U", "--target", YTDLP_LIB_DIR, "discord.py>=2.7.1", "davey", "PyNaCl"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=400)
        if r.returncode != 0:
            print(f"[deps] ติดตั้งไม่สำเร็จ:\n{r.stderr[-600:]}")
    except Exception as e:
        print(f"[deps] ติดตั้งไม่สำเร็จ: {e}")
    if YTDLP_LIB_DIR not in sys.path:
        sys.path.insert(0, YTDLP_LIB_DIR)
    importlib.invalidate_caches()
    print(f"[deps] หลังติดตั้ง: discord.py={ver('discord.py')} davey={ver('davey')} PyNaCl={ver('PyNaCl')}")

ensure_voice_deps()

import discord
from discord.ext import commands
import aiohttp  # ติดตั้งมาพร้อม discord.py

import yt_dlp
from yt_dlp.version import __version__ as YTDLP_VERSION
print(f"yt-dlp เวอร์ชัน {YTDLP_VERSION}")

# ---- JavaScript runtime (deno) ----
# yt-dlp ต้องมี JS runtime ไว้แก้โจทย์ของ YouTube ไม่งั้นจะไม่เห็นไฟล์เสียง (error "Requested format is not available")

def find_deno():
    candidates = [shutil.which("deno")]
    base = os.path.dirname(os.path.abspath(__file__))
    for pattern in (
        os.path.join(YTDLP_LIB_DIR, "bin", "deno*"),
        os.path.join(YTDLP_LIB_DIR, "deno", "deno*"),
        os.path.join(base, ".local", "bin", "deno*"),
        os.path.join(sys.prefix, "bin", "deno*"),
        os.path.expanduser("~/.local/bin/deno*"),
    ):
        candidates.extend(sorted(glob.glob(pattern)))
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None

DENO_PATH = find_deno()
JS_OPTS = {}
if DENO_PATH:
    JS_OPTS = {'js_runtimes': {'deno': {'path': DENO_PATH}}}
    os.environ["PATH"] = os.path.dirname(DENO_PATH) + os.pathsep + os.environ.get("PATH", "")
    print(f"[js] พบ deno: {DENO_PATH}")
else:
    print("[js] ⚠️ ไม่พบ deno (YouTube อาจขึ้น Requested format is not available)")

# ==========================================================
# ส่วนที่ 1 │ ตั้งค่า  (ค่าที่แก้ได้ + สร้างบอท)
# ==========================================================

# ---------- 1.1 ค่าที่แก้ได้ ----------

BUILD_ID = "2026-10-01-r10"   # ไว้เช็คว่าบอทรันไฟล์เวอร์ชันล่าสุดจริงไหม (โชว์ใน error)

# --- เพลง ---
MAX_SPOTIFY_TRACKS = 50      # จำกัดจำนวนเพลงสูงสุดต่อ 1 ลิงก์
SPOTIFY_SEARCH_SUFFIX = ""   # ถ้าอยากปรับผลค้นหา YouTube เช่น " audio" ให้ใส่ตรงนี้
CACHE_KEEP = 12          # เก็บไฟล์เสียงล่าสุดไว้กี่ไฟล์ (โฮสต์ฟรีพื้นที่น้อย)
UNWANTED_WORDS = ["live", "cover", "remix", "karaoke", "sped up", "slowed", "reverb", "nightcore", "8d", "instrumental", "reaction", "tutorial", "lyric video"]   # คำที่ถ้าอยู่ในชื่อคลิป จะโดนตัดคะแนนตอนเลือกผลค้นหา

# True  = ส่งเสียงแบบ Opus ตรงๆ (ไม่ต้องใช้ libopus ของเครื่อง + กิน CPU น้อย เหมาะกับโฮสต์ฟรี)
# False = แบบเดิม (ffmpeg -> PCM -> เข้ารหัส Opus ด้วย libopus ต้องมี libopus ในเครื่อง)
OPUS_PASSTHROUGH = os.getenv("OPUS_PASSTHROUGH", "1") != "0"

# True = โหลดเสียงลงไฟล์ก่อนแล้วค่อยเล่น (แก้ 403 Forbidden จาก YouTube บนโฮสต์) / False = ให้ ffmpeg ดึงตรงๆ
DOWNLOAD_BEFORE_PLAY = os.getenv("DOWNLOAD_BEFORE_PLAY", "1") != "0"

# ---------- 1.2 สร้างบอท ----------

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# สร้าง Bot Instance
bot = commands.Bot(command_prefix="/", intents=intents)
slash_commands_synced = False

@bot.event
async def on_ready():
    global slash_commands_synced
    if not slash_commands_synced:
        synced = await bot.tree.sync()
        print(f"ลงทะเบียน Slash Commands แล้ว {len(synced)} คำสั่ง")
        slash_commands_synced = True
    print(f"บอท {bot.user} ออนไลน์และพร้อมทำงานแล้วครับ!")

# ==========================================================
# ส่วนที่ 2 │ 💬 คำพูด  (ข้อความที่น้องแมวตอบในห้องที่เปิด /talk)
# ==========================================================

# วิธีแก้คำพูด: แก้ที่ CHAT_RULES ด้านล่างได้เลย
#   contains = ข้อความมีคำพวกนี้อยู่ตรงไหนก็ได้ (ไม่สนตัวพิมพ์เล็ก/ใหญ่)
#   exact    = ต้องพิมพ์ตรงกับคำพวกนี้ทั้งข้อความเท่านั้น
#   replies  = คำตอบ สุ่มเลือก 1 อัน  ใส่ {mention} เพื่อแท็กคนที่พิมพ์
#              ถ้าคำตอบเป็น [ ... ] = ส่งหลายข้อความต่อกันตามลำดับ
# กติกาเช็กจากบนลงล่าง ข้อไหนตรงก่อนตอบข้อนั้นแล้วจบเลย (เลยต้องเรียงข้อเฉพาะเจาะจงไว้ก่อน)
CHAT_RULES = [
    {   # ทักน้องแมวโดยตรง
        "contains": ["สวัสดีน้องแมว", "หวัดดีจ้า"],
        "replies": ["สวัสดีครับคุณ {mention} มีอะไรให้น้องแมวกินมั้ย"],
    },
    {   # ทักทายทั่วไป
        "contains": ["สวัสดี", "หวัดดี", "หวัด", "ดีจ้า", "ดีครับ", "ดีค่ะ",
                     "hi", "hello", "sup", "yo", "เฮ้", "โย่", "ว่าไง"],
        "replies": ["สวัสดีครับคุณ {mention} ทักน้องแมวมีอะไรให้ช่วย"],
    },
    {   # เรียกชื่อ (พิมพ์แค่ชื่ออย่างเดียว)
        "exact": ["น้องแมว", "กุ่ย", "ไก่", "ไอกุ่ย", "ไอไก่"],
        "replies": ["มีอะไรหรือ", "แว้", "ว่า"],
    },
    {   # คำหยาบ
        "contains": ["ควย", "ควาย", "เหี้ย", "สัส"],
        "replies": ["พูดจาดีๆหน่อยไวรุ่น", "ชอบความรุนแรงหรอไวรุ่น", "เจอได้"],
    },
    {   # ขอให้ร้องเพลง
        "contains": ["ร้องเพลงให้ฟังหน่อย"],
        "replies": ["ร้องเพลงอันไหนนน ส่ง url มาให้น้องแมวร้องสิ"],
    },
    {   # เหงา
        "contains": ["เหงา", "เหงาอะ"],
        "replies": [
            "มีน้องแมวอยู่เป็นเพื่อนทั้งคน เหงาได้ไง",
            "คุยกับน้องแมวได้นะ",
            "บ่นให้น้องแมวฟังได้นะ น้องเกิดที่ไทยมีใบเกิด",
        ],
    },
    {   # จีบ
        "contains": ["จีบหน่อย", "หยอดหน่อย"],
        "replies": [
            "ถึงตัวจะเป็นแมว แต่หัวใจมีแต่เธอนะคั้บ",
            "เป็นคนชอบแมวป่าวครับ... ถ้าชอบ ลองมาเป็นทาสรักเราดูสิ รับรองดูแลดีแน่นอน",
            "อากาศหนาวให้ห่มผ้า แต่อยากอบอุ่นกว่า... ให้มาซบไหล่เรานะฮะ",
        ],
    },
    {   # นิ่งๆ
        "contains": ["นิ่งๆ"],
        "replies": ["โอเคคั้บผม", ["แต่ซิ่งจัด", "ขอโทษคั้บ ซิ่งไปหน่อย"]],
    },
    {   # วอดส์
        "contains": ["วอดส์"],
        "replies": ["โหอะไรว้า คนไทย"],
    },
]

allowed_chat_channels = {}   # guild_id -> channel_id ของห้องที่เปิด /talk ไว้

def match_chat_rule(content, mention):
    """หาคำตอบจาก CHAT_RULES คืนค่าเป็น list ของข้อความที่จะส่ง (ถ้าไม่ตรงข้อไหนคืน None)"""
    stripped = content.strip()
    lowered = content.lower()
    for rule in CHAT_RULES:
        if stripped in rule.get("exact", []) or any(w in lowered for w in rule.get("contains", [])):
            reply = random.choice(rule["replies"])
            parts = [reply] if isinstance(reply, str) else list(reply)
            return [p.replace("{mention}", mention) for p in parts]
    return None

@bot.event
async def on_message(message):
    if message.author == bot.user or message.guild is None:
        return

    guild_id = message.guild.id
    if guild_id not in allowed_chat_channels or message.channel.id != allowed_chat_channels[guild_id]:
        await bot.process_commands(message)
        return

    parts = match_chat_rule(message.content, message.author.mention)
    if parts:
        for part in parts:
            async with message.channel.typing():
                await message.channel.send(part)
        return

    await bot.process_commands(message)

# ==========================================================
# ส่วนที่ 3 │ 🎵 เล่นเพลง
# ลำดับ: 3.1 ตัวช่วย → 3.2 YouTube → 3.3 ffmpeg → 3.4 ตรวจเสียง → 3.5 ตัวส่งเสียง → 3.6 ตัวเล่น
#        → 3.7 Spotify → 3.8 Apple Music → 3.9 ค้นหา → 3.10 คิว/Loop/Autoplay
# ==========================================================

# ---------- 3.1 ตัวช่วยเล็กๆ ----------

def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()

def _find_dict(obj, predicate):
    """ค้นหา dict แรกที่เข้าเงื่อนไขในโครงสร้าง JSON ซ้อนกัน"""
    if isinstance(obj, dict):
        if predicate(obj):
            return obj
        for v in obj.values():
            found = _find_dict(v, predicate)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_dict(v, predicate)
            if found is not None:
                return found
    return None

def _strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", str(text))

def extract_video_id(url):
    """ดึง YouTube video ID ออกจาก URL เพื่อใช้หาเพลงต่อเนื่องแนวเดียวกัน"""
    match = re.search(r"(?:v=|youtu\.be/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

# ---------- 3.2 YouTube (yt-dlp / cookies) ----------

# ตั้งค่าตัวเลือกสำหรับดึงเสียงจาก YouTube
# ถ้ามีไฟล์ cookies.txt อยู่โฟลเดอร์เดียวกับ bot.py จะใช้ยืนยันตัวตนกับ YouTube
# (แก้ error "Sign in to confirm you're not a bot" บนโฮสต์)
# เมื่อใช้ cookies ต้องบังคับ player_client ด้วย ไม่งั้นเจอ error "The page needs to be reloaded"
# (ปัญหาที่ YouTube เปลี่ยนเมื่อ ส.ค. 2026 ตัวแก้ที่ yt-dlp แนะนำคือ default + web_embedded)
COOKIE_OPTS = (
    {'cookiefile': 'cookies.txt',
     'extractor_args': {'youtube': {'player_client': ['default', 'web_embedded']}}}
    if os.path.exists('cookies.txt') else {}
)

def check_cookies_file(path="cookies.txt"):
    """ตรวจ cookies.txt ตอนบอทเริ่มทำงาน แล้วพิมพ์ผลลง console (ไม่พิมพ์ค่า cookies)"""
    import time
    if not os.path.exists(path):
        print(f"[cookies] ❌ ไม่พบไฟล์ {path} ในโฟลเดอร์ {os.getcwd()}")
        print(f"[cookies] ไฟล์ที่เห็นในโฟลเดอร์นี้: {sorted(os.listdir('.'))[:40]}")
        return
    names, expired, total = set(), 0, 0
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7 or "youtube.com" not in parts[0] and "google.com" not in parts[0]:
                continue
            total += 1
            names.add(parts[5])
            if parts[4].isdigit() and 0 < int(parts[4]) < time.time():
                expired += 1
    login_names = {"SID", "SAPISID", "__Secure-3PSID", "__Secure-1PSID", "LOGIN_INFO"}
    has_login = bool(names & login_names)
    print(f"[cookies] พบไฟล์ {path}: {total} cookies ของ youtube/google, หมดอายุแล้ว {expired}")
    if not has_login:
        print("[cookies] ⚠️ ไม่เจอ cookie การล็อกอิน (ตอนส่งออกอาจยังไม่ได้ล็อกอิน YouTube) ต้องส่งออกใหม่")
    elif expired:
        print("[cookies] ⚠️ มี cookies ที่หมดอายุแล้ว ลองส่งออกใหม่")
    else:
        print("[cookies] ✅ มี cookie การล็อกอิน (ถ้ายังขึ้น Sign in แปลว่า YouTube ปฏิเสธ cookies ชุดนี้ ต้องส่งออกใหม่)")

check_cookies_file()

# ชุด player_client ที่จะลองตามลำดับเมื่อใช้ cookies (ถ้าชุดแรกพัง จะลองชุดถัดไป แล้วสุดท้ายลองแบบไม่ใช้ cookies)
PLAYER_CLIENT_SETS = [
    ['web_embedded'],
    ['mweb'],
    ['default', 'web_embedded'],
    ['tv', 'web_safari'],
]

def extract_info_resilient(base_opts, url, download=False):
    """เรียก yt-dlp หลายวิธีตามลำดับจนกว่าจะสำเร็จ (ทำงานแบบ blocking ให้เรียกผ่าน run_in_executor)"""
    attempts = []
    if os.path.exists('cookies.txt'):
        for clients in PLAYER_CLIENT_SETS:
            attempts.append(({**base_opts, 'cookiefile': 'cookies.txt',
                              'extractor_args': {'youtube': {'player_client': clients}}},
                             "cookies+" + "/".join(clients)))
    attempts.append((dict(base_opts), "ไม่ใช้cookies"))

    errors = []
    for opts, label in attempts:
        try:
            with yt_dlp.YoutubeDL({**opts, **JS_OPTS, 'quiet': True, 'no_color': True}) as y:
                data = y.extract_info(url, download=download)
            print(f"[yt-dlp] สำเร็จด้วยวิธี: {label}")
            return data
        except Exception as e:
            msg = _strip_ansi(e).replace("\n", " ")
            print(f"[yt-dlp] วิธี {label} ล้มเหลว: {msg[:300]}")
            errors.append(f"• {label}: {msg[:110]}")
    raise RuntimeError("ลองครบทุกวิธีแล้วไม่สำเร็จ\n" + "\n".join(errors))

ytdl_format_options = {
    'format': 'bestaudio[acodec=opus]/bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'quiet': True,
    'noplaylist': True,
}
ytdl = yt_dlp.YoutubeDL({**ytdl_format_options, **COOKIE_OPTS})

# ---------- 3.3 ffmpeg (ตัวแปลงเสียง) + ทดสอบตอนเริ่ม ----------

# ffmpeg: ใช้ตัวที่มากับแพ็กเกจ imageio-ffmpeg (โฮสต์ส่วนใหญ่ลง ffmpeg เองไม่ได้) ถ้าไม่มีค่อยใช้ ffmpeg ของเครื่อง
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = "ffmpeg"

# ---- ทดสอบ ffmpeg จริงๆ ตอนเริ่มบอท (ffmpeg บางตัวรันบนโฮสต์เล็กๆ แล้วล่ม "code -11 / segfault") ----
# (ชื่อทดสอบ, อาร์กิวเมนต์, เป็นการทดสอบเน็ตไหม)
_SINE = ["-f", "lavfi", "-i", "sine=frequency=440:duration=0.3"]
FFMPEG_TESTS = [
    ("เปิดโปรแกรม", ["-version"], False),
    ("ถอดรหัสเสียง", ["-hide_banner", "-loglevel", "error", "-threads", "1", *_SINE, "-f", "null", "-"], False),
    ("แปลงเป็น opus", ["-hide_banner", "-loglevel", "error", "-threads", "1", *_SINE, "-c:a", "libopus", "-f", "opus", "-"], False),
    ("โหลดจากเน็ต https", ["-hide_banner", "-loglevel", "error", "-threads", "1", "-rw_timeout", "5000000",
                           "-i", "https://www.youtube.com/robots.txt", "-f", "null", "-"], True),
]

def test_ffmpeg(path):
    """คืนค่า (ใช้ได้ไหม, [ผลทดสอบแต่ละข้อ])  ล่ม = return code ติดลบ (เช่น -11 = segfault)"""
    report, usable = [], True
    for name, args, is_net in FFMPEG_TESTS:
        try:
            r = subprocess.run([path, *args], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=25)
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = None
        except Exception as e:
            return False, [f"❌ รัน ffmpeg ไม่ได้: {e}"]
        if code is None:
            ok = is_net            # เน็ตช้าไม่ถือว่าพัง
            note = "หมดเวลา"
        elif code < 0:
            ok, note = False, f"ล่ม (code {code})"
        elif is_net:
            ok, note = True, "ไม่ล่ม"
        else:
            ok, note = (code == 0), f"code {code}"
        if not ok and name != "แปลงเป็น opus":
            usable = False
        report.append(f"{'✅' if ok else '❌'} {name}: {note}")
    return usable, report

def select_ffmpeg(current):
    base = os.path.dirname(os.path.abspath(__file__))
    cands = []
    for c in [os.getenv("FFMPEG_PATH"), current, shutil.which("ffmpeg"),
              os.path.join(base, "ffmpeg"), *sorted(glob.glob(os.path.join(base, "ffmpeg*", "ffmpeg*"))),
              *sorted(glob.glob(os.path.join(base, "ytdlp_lib", "**", "ffmpeg*"), recursive=True))]:
        if c and os.path.isfile(c) and c not in cands:
            try:
                os.chmod(c, os.stat(c).st_mode | 0o111)
            except Exception:
                pass
            cands.append(c)

    last_report = []
    for c in cands:
        usable, rep = test_ffmpeg(c)
        print(f"[ffmpeg] ทดสอบ {c}: {'ใช้ได้' if usable else 'ใช้ไม่ได้'} | " + " | ".join(rep))
        if usable:
            return c, rep
        last_report = rep

    # ไม่มีตัวไหนผ่าน -> ลองดาวน์โหลด ffmpeg สำเร็จรูปมาเพิ่ม (ปิดได้ด้วย AUTO_FETCH_FFMPEG=0)
    if os.getenv("AUTO_FETCH_FFMPEG", "1") != "0":
        try:
            print("[ffmpeg] ไม่มีตัวไหนใช้ได้ กำลังลองดาวน์โหลด static-ffmpeg ...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-U", "--target", YTDLP_LIB_DIR, "static-ffmpeg"],
                           capture_output=True, text=True, timeout=300)
            if YTDLP_LIB_DIR not in sys.path:
                sys.path.insert(0, YTDLP_LIB_DIR)
            from static_ffmpeg import run as _sf_run
            path = _sf_run.get_or_fetch_platform_executables_else_raise()[0]
            usable, rep = test_ffmpeg(path)
            print(f"[ffmpeg] static-ffmpeg {path}: {'ใช้ได้' if usable else 'ใช้ไม่ได้'} | " + " | ".join(rep))
            if usable:
                return path, rep
            last_report = rep
        except Exception as e:
            print(f"[ffmpeg] ดาวน์โหลด static-ffmpeg ไม่สำเร็จ: {e}")
    return current, last_report

FFMPEG_PATH, FFMPEG_REPORT = select_ffmpeg(FFMPEG_PATH)
print(f"[ffmpeg] ใช้: {FFMPEG_PATH}")

# ---------- 3.4 ตรวจระบบเสียง (ใช้กับ /voicecheck) ----------

# ---- ตรวจระบบเสียง (PyNaCl / Opus / ffmpeg) ตอนเริ่มบอท ----
def voice_diagnostics():
    lines = []
    try:
        import nacl
        lines.append(f"PyNaCl ✅ {getattr(nacl, '__version__', '')}")
    except Exception:
        lines.append("PyNaCl ❌ ไม่พบ -> ต้องติดตั้ง: pip install PyNaCl")

    ver_ok = (discord.version_info.major, discord.version_info.minor, discord.version_info.micro) >= (2, 7, 1)
    lines.append(f"discord.py {discord.__version__} {'✅' if ver_ok else '❌ ต้อง 2.7.1 ขึ้นไป (Discord บังคับ DAVE)'}")
    try:
        import davey  # noqa: F401
        lines.append("davey ✅ (รองรับ DAVE)")
    except Exception:
        lines.append("davey ❌ ไม่พบ -> เสียงจะถูก Discord ตัดทิ้ง ติดตั้ง: pip install davey")

    if not discord.opus.is_loaded():
        for name in ("opus", "libopus.so.0", "libopus.so", "libopus-0.x64.dll", "libopus.0.dylib"):
            try:
                discord.opus.load_opus(name)
                break
            except Exception:
                continue
    if discord.opus.is_loaded():
        lines.append("Opus ✅ โหลดแล้ว")
    else:
        if OPUS_PASSTHROUGH:
            lines.append("Opus ⚪ ไม่พบ libopus ในเครื่อง แต่ไม่เป็นไร (บอทใช้โหมด Opus ผ่านตรง ไม่ต้องใช้)")
        else:
            lines.append("Opus ❌ ไม่พบ libopus -> โหมดนี้จะไม่มีเสียง ให้ตั้ง OPUS_PASSTHROUGH=1 หรือให้โฮสต์ติดตั้ง libopus0")

    lines.append(f"ffmpeg ที่ใช้: {FFMPEG_PATH}")
    lines.extend(FFMPEG_REPORT or ["ffmpeg ❌ ทดสอบไม่ได้"])
    return lines

for _line in voice_diagnostics():
    print("[voice]", _line)

# ---------- 3.5 ตัวส่งเสียงเข้า Discord + สิ่งที่ทำหลังเพลงจบ ----------

class LoggedFFmpegPCMAudio(discord.FFmpegPCMAudio):
    """FFmpegPCMAudio ที่เก็บข้อความ error ของ ffmpeg ไว้ (ปกติ discord.py ทิ้งไป ทำให้เงียบไม่รู้สาเหตุ)"""
    def __init__(self, source, **kwargs):
        super().__init__(source, **kwargs)
        self.log = collections.deque(maxlen=12)

    def _drain(self, pipe):
        try:
            for line in iter(pipe.readline, b''):
                text = line.decode(errors='replace').strip()
                if text:
                    self.log.append(text)
        except Exception:
            pass

class LoggedFFmpegOpusAudio(discord.FFmpegOpusAudio):
    """ส่ง Opus ให้ Discord ตรงๆ: ถ้าไฟล์ต้นทางเป็น opus อยู่แล้ว (YouTube ส่วนใหญ่) จะ copy ไม่ต้องแปลงเสียงเลย
    จึงไม่ต้องใช้ libopus ของเครื่อง และใช้ CPU/RAM น้อยมาก"""
    def __init__(self, source, *, data=None, **kwargs):
        super().__init__(source, **kwargs)
        self.data = data or {}
        self.title = self.data.get('title')
        self.url = self.data.get('url')
        self.log = collections.deque(maxlen=12)

    def _drain(self, pipe):
        try:
            for line in iter(pipe.readline, b''):
                text = line.decode(errors='replace').strip()
                if text:
                    self.log.append(text)
        except Exception:
            pass

manual_stop = set()   # guild ที่สั่ง /skip /leave เอง (ไม่ต้องรายงานว่าเพลงหยุดผิดปกติ)

def make_after_playing(interaction, player):
    """callback หลังเพลงจบ: เล่นเพลงถัดไป + ถ้าเพลงหยุดเร็วผิดปกติ ให้บอกสาเหตุจาก ffmpeg"""
    started = time.monotonic()
    guild_id = interaction.guild.id

    def after_playing(error):
        elapsed = time.monotonic() - started
        if error:
            print(f'Player error: {error}')
        time.sleep(0.3)  # ให้ thread อ่าน log ของ ffmpeg เสร็จก่อน
        log = list(getattr(getattr(player, 'original', player), 'log', []))
        if guild_id in manual_stop:
            manual_stop.discard(guild_id)
        elif elapsed < 8:
            tail = "\n".join(log[-6:]) if log else "(ดู error จริงของ ffmpeg ใน console ของโฮสต์)"
            print(f"[audio] เพลงหยุดภายใน {elapsed:.1f}s | error={error} | ffmpeg:\n{tail}")
            vc = interaction.guild.voice_client
            state = "เชื่อมต่ออยู่" if (vc and vc.is_connected()) else "หลุดจากห้องเสียงแล้ว (น่าจะติดเรื่อง DAVE/เวอร์ชัน discord.py -> ดู /voicecheck และ console)"
            log_hint = f"\n🔌 สถานะห้องเสียง: {state}"
            hint = "\n💡 ffmpeg ล่ม (segfault) ลองสั่ง /voicecheck ดูผลทดสอบ ffmpeg" if "-11" in str(error) else ""
            msg = f"⚠️ เพลงหยุดหลังเล่นแค่ {elapsed:.1f} วินาที\n```{(str(error) + chr(10) if error else '') + tail}```{log_hint}{hint}"
            asyncio.run_coroutine_threadsafe(interaction.channel.send(msg[:1900]), bot.loop)
        fut = asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(f"Error in after_playing: {e}")
    return after_playing   # ไว้เช็คว่าบอทรันไฟล์เวอร์ชันล่าสุดจริงไหม (โชว์ใน error)

# ---------- 3.6 โหลดเสียง + ตัวเล่น ----------

# ---- ดาวน์โหลดเสียงลงไฟล์ก่อนเล่น ----
# ffmpeg ดึงลิงก์ googlevideo ตรงๆ จาก IP ของโฮสต์แล้วโดน 403 Forbidden
# แต่ yt-dlp โหลดแบบแบ่งก้อน + ลองหลายวิธีได้ จึงให้ yt-dlp โหลดเก็บไว้ในโฟลเดอร์ audio_cache แล้วค่อยเล่นจากไฟล์
# ปิดได้ด้วยตัวแปร DOWNLOAD_BEFORE_PLAY=0
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_cache")
_audio_meta = {}         # video id -> ข้อมูลเพลง (ใช้ตอน Loop จะได้ไม่ต้องโหลดซ้ำ)

def _prune_cache():
    try:
        files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)]
        files = sorted((f for f in files if os.path.isfile(f)), key=os.path.getmtime, reverse=True)
        for f in files[CACHE_KEEP:]:
            os.remove(f)
    except Exception as e:
        print(f"[cache] ล้างไฟล์เก่าไม่สำเร็จ: {e}")

def download_audio(url):
    """โหลดเสียงลง audio_cache แล้วคืน data (มี data['_local_file']) ทำงานแบบ blocking ให้เรียกผ่าน run_in_executor"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    vid = extract_video_id(url)
    meta = _audio_meta.get(vid) if vid else None
    if meta and os.path.exists(meta.get('_local_file', '')):
        os.utime(meta['_local_file'], None)
        print(f"[cache] ใช้ไฟล์เดิม {vid}")
        return meta

    opts = {**ytdl_format_options,
            'outtmpl': os.path.join(CACHE_DIR, '%(id)s.%(ext)s'),
            'noplaylist': True, 'noprogress': True,
            'retries': 3, 'fragment_retries': 3, 'http_chunk_size': 10485760}
    data = extract_info_resilient(opts, url, download=True)
    if 'entries' in data:
        data = data['entries'][0]

    path = None
    for rd in data.get('requested_downloads') or []:
        p = rd.get('filepath') or rd.get('_filename')
        if p and os.path.exists(p):
            path = p
            break
    if not path:
        cands = [p for p in glob.glob(os.path.join(CACHE_DIR, f"{data.get('id')}.*")) if not p.endswith('.part')]
        if cands:
            path = max(cands, key=os.path.getmtime)
    if not path:
        raise RuntimeError("ดาวน์โหลดเสียงไม่สำเร็จ (ไม่พบไฟล์เสียงหลังโหลด)")

    for k in ('formats', 'thumbnails', 'automatic_captions', 'subtitles', 'requested_formats'):
        data.pop(k, None)   # ประหยัด RAM
    data['_local_file'] = path
    _audio_meta[data.get('id')] = data
    print(f"[cache] โหลดเสร็จ {os.path.basename(path)} ({os.path.getsize(path) / 1024 / 1024:.1f} MB)")
    _prune_cache()
    return data

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        if DOWNLOAD_BEFORE_PLAY:
            data = await loop.run_in_executor(None, lambda: download_audio(url))
            filename = data['_local_file']
            before = '-nostdin -threads 1'
        else:
            data = await loop.run_in_executor(None, lambda: extract_info_resilient(ytdl_format_options, url, download=not stream))
            if 'entries' in data:
                data = data['entries'][0]
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            before = '-nostdin -threads 1 -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
            headers = data.get('http_headers') if stream else None
            if headers:
                hdr = ''.join(f"{k}: {v}\r\n" for k, v in headers.items() if '"' not in str(v))
                before += f' -headers "{hdr}"'

        if OPUS_PASSTHROUGH:
            copy_codec = 'opus' if (data.get('acodec') or '').startswith('opus') else None  # opus = copy, None = ffmpeg แปลงเป็น opus ให้
            print(f"[audio] {data.get('title')} | acodec={data.get('acodec')} -> {'copy' if copy_codec else 'ffmpeg encode'} | {'ไฟล์' if DOWNLOAD_BEFORE_PLAY else 'stream'}")
            return LoggedFFmpegOpusAudio(filename, data=data, executable=FFMPEG_PATH, before_options=before, options='-vn -threads 1', codec=copy_codec, bitrate=128)
        return cls(LoggedFFmpegPCMAudio(filename, executable=FFMPEG_PATH, before_options=before, options='-vn'), data=data)

# ---------- 3.7 อ่านลิงก์ Spotify ----------

SPOTIFY_LINK_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-zA-Z-]+/)?(track|album|playlist)/([0-9A-Za-z]+)")
SPOTIFY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def parse_spotify_embed(html):
    """แปลง HTML หน้า embed ของ Spotify เป็น (ชื่อคอลเลกชัน, [คำค้นหา 'ศิลปิน - ชื่อเพลง'])"""
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return None, []
    data = json.loads(m.group(1))

    # อัลบั้ม / เพลย์ลิสต์ -> มี trackList
    entity = _find_dict(data, lambda d: isinstance(d.get("trackList"), list))
    if entity:
        queries = []
        for item in entity["trackList"]:
            title = _clean(item.get("title"))
            artist = _clean(item.get("subtitle"))
            if title:
                queries.append(f"{artist} - {title}" if artist else title)
        return _clean(entity.get("name") or entity.get("title")) or "Spotify", queries

    # เพลงเดี่ยว
    entity = _find_dict(data, lambda d: isinstance(d.get("artists"), list) and (d.get("name") or d.get("title")))
    if entity:
        title = _clean(entity.get("name") or entity.get("title"))
        artist = ", ".join(_clean(a.get("name")) for a in entity["artists"] if isinstance(a, dict) and a.get("name"))
        return title, [f"{artist} - {title}" if artist else title]

    return None, []

async def spotify_to_queries(url):
    """รับลิงก์ Spotify คืนค่า (ชื่อคอลเลกชัน, [คำค้นหา]) ถ้าอ่านไม่ได้คืน (None, [])"""
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(headers=SPOTIFY_HEADERS, timeout=timeout) as session:
        # ลิงก์สั้นจากปุ่มแชร์บนมือถือ (spotify.link) -> ตามไปหาลิงก์จริงก่อน
        if "spotify.link" in url:
            async with session.get(url, allow_redirects=True) as resp:
                url = str(resp.url)

        m = SPOTIFY_LINK_RE.search(url)
        if not m:
            return None, []
        kind, sid = m.groups()

        async with session.get(f"https://open.spotify.com/embed/{kind}/{sid}") as resp:
            if resp.status == 200:
                name, queries = parse_spotify_embed(await resp.text())
                if queries:
                    return name, queries[:MAX_SPOTIFY_TRACKS]

        # สำรองสำหรับเพลงเดี่ยว: oEmbed ได้แค่ชื่อเพลง (ไม่มีศิลปิน)
        if kind == "track":
            async with session.get("https://open.spotify.com/oembed", params={"url": f"https://open.spotify.com/track/{sid}"}) as resp:
                if resp.status == 200:
                    title = _clean((await resp.json()).get("title"))
                    if title:
                        return title, [title]
    return None, []

# ---------- 3.8 อ่านลิงก์ Apple Music ----------

APPLE_LINK_RE = re.compile(r"music\.apple\.com/([a-zA-Z]{2})/(song|album|playlist)/(?:[^/?#]+/)?([A-Za-z0-9._-]+)")

def _artist_of(d):
    """ดึงชื่อศิลปินจาก JSON-LD (byArtist เป็นได้ทั้ง list / dict / str)"""
    if not isinstance(d, dict):
        return ""
    by = d.get("byArtist")
    if isinstance(by, dict):
        by = [by]
    if isinstance(by, str):
        return _clean(by)
    if isinstance(by, list):
        names = [_clean(a.get("name")) if isinstance(a, dict) else _clean(a) for a in by]
        return ", ".join(n for n in names if n)
    return ""

def _apple_query(artist, title):
    return f"{artist} - {title}" if artist else title

def parse_apple_page(html_text):
    """อ่านหน้าเว็บ Apple Music -> (ชื่อคอลเลกชัน, [คำค้นหา 'ศิลปิน - ชื่อเพลง'])"""
    # วิธีที่ 1: JSON-LD
    for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html_text, re.S):
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            continue

        name = _clean(data.get("name"))
        album_artist = _artist_of(data) or _artist_of(data.get("audio"))

        tracks = data.get("tracks")
        if isinstance(tracks, list) and tracks:
            queries = []
            for t in tracks:
                if not isinstance(t, dict):
                    continue
                title = _clean(t.get("name"))
                if title:
                    queries.append(_apple_query(_artist_of(t) or album_artist, title))
            if queries:
                return name or "Apple Music", queries

        if name and (data.get("@type") in ("MusicComposition", "MusicRecording") or data.get("audio")):
            return name, [_apple_query(album_artist, name)]

    # วิธีที่ 2: og:title เช่น "Blinding Lights - Song by The Weeknd"
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html_text)
    if m:
        t = _clean(html.unescape(m.group(1)))
        t = re.sub(r"\s+on Apple Music$", "", t)
        mm = re.match(r"^(.*?) - (?:Song|Single|EP|Album|Playlist) by (.*)$", t)
        if mm:
            return mm.group(1), [f"{mm.group(2)} - {mm.group(1)}"]
        if t:
            return t, [t]
    return None, []

async def apple_to_queries(url):
    """รับลิงก์ Apple Music คืนค่า (ชื่อคอลเลกชัน, [คำค้นหา]) ถ้าอ่านไม่ได้คืน (None, [])"""
    m = APPLE_LINK_RE.search(url)
    if not m:
        return None, []
    country, kind, cid = m.groups()
    country = country.lower()
    track_id = re.search(r"[?&]i=(\d+)", url)

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(headers=SPOTIFY_HEADERS, timeout=timeout) as session:
        # ---- iTunes Lookup API: เพลงเดี่ยว / อัลบั้ม ----
        try:
            if track_id or (kind == "song" and cid.isdigit()):
                tid = track_id.group(1) if track_id else cid
                async with session.get("https://itunes.apple.com/lookup", params={"id": tid, "country": country}) as resp:
                    if resp.status == 200:
                        results = (await resp.json(content_type=None)).get("results", [])
                        if results and results[0].get("trackName"):
                            r = results[0]
                            return _clean(r["trackName"]), [_apple_query(_clean(r.get("artistName")), _clean(r["trackName"]))]
            elif kind == "album" and cid.isdigit():
                async with session.get("https://itunes.apple.com/lookup", params={"id": cid, "entity": "song", "limit": 200, "country": country}) as resp:
                    if resp.status == 200:
                        results = (await resp.json(content_type=None)).get("results", [])
                        tracks = [r for r in results if r.get("wrapperType") == "track" and r.get("trackName")]
                        if tracks:
                            tracks.sort(key=lambda r: (r.get("discNumber", 1), r.get("trackNumber", 0)))
                            album = _clean(tracks[0].get("collectionName")) or "Apple Music"
                            queries = [_apple_query(_clean(r.get("artistName")), _clean(r["trackName"])) for r in tracks]
                            return album, queries[:MAX_SPOTIFY_TRACKS]
        except Exception as e:
            print(f"iTunes API error: {e}")

        # ---- สำรอง / เพลย์ลิสต์: อ่านจากหน้าเว็บ ----
        async with session.get(url) as resp:
            if resp.status == 200:
                name, queries = parse_apple_page(await resp.text())
                if queries:
                    if track_id or kind == "song":
                        queries = queries[:1]
                    return name, queries[:MAX_SPOTIFY_TRACKS]
    return None, []

# ---------- 3.9 ค้นหาเพลงบน YouTube (เลือกผลที่ตรงที่สุด) ----------

def _tokens(text):
    return set(re.findall(r"\w+", str(text or "").lower()))

def _normalized_text(text):
    return " ".join(re.findall(r"\w+", str(text or "").lower()))

async def resolve_ytsearch(url):
    """Try a multi-artist music query from most specific to least specific."""
    if not url.startswith("ytsearch1:"):
        return url
    query = url[len("ytsearch1:"):]
    parts = re.split(r"\s+-\s+", query, maxsplit=1)
    if len(parts) == 2:
        artist_text, title_query = parts
        artists = [_clean(name) for name in re.split(r"\s*,\s*|\s+&\s+|\s+feat\.?\s+|\s+ft\.?\s+", artist_text, flags=re.I) if _clean(name)]
    else:
        artists, title_query = [], query

    # Search all credited artists first, then test each artist with the same
    # title in credit order. This allows YouTube results that show only one.
    search_queries = [query]
    if artists:
        search_queries.extend(f"{artist} - {title_query}" for artist in artists)
    title_tokens = _tokens(title_query)

    try:
        ytdl_search = yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'skip_download': True, **COOKIE_OPTS})
        loop = asyncio.get_event_loop()
        for search_query in dict.fromkeys(search_queries):
            data = await loop.run_in_executor(
                None,
                lambda q=search_query: ytdl_search.extract_info(f"ytsearch12:{q}", download=False),
            )
            expected_artists = artists if search_query == query else [search_query.split(" - ", 1)[0]] if artists else []
            expected_artist_tokens = set().union(*(_tokens(a) for a in expected_artists)) if expected_artists else set()
            best, best_score = None, 0.0
            best_title_match, best_artist_match = 0.0, 0.0

            for index, entry in enumerate(data.get('entries') or []):
                if not entry or not entry.get('id'):
                    continue
                video_title = entry.get('title') or ""
                channel = entry.get('channel') or entry.get('uploader') or ""
                video_tokens = _tokens(video_title)
                title_match = len(title_tokens & video_tokens) / max(len(title_tokens), 1)
                artist_match = len(expected_artist_tokens & (video_tokens | _tokens(channel))) / max(len(expected_artist_tokens), 1) if expected_artist_tokens else 1.0
                score = title_match * 0.78 + artist_match * 0.22

                normalized_title = _normalized_text(video_title)
                normalized_song = _normalized_text(title_query)
                if normalized_song and normalized_song in normalized_title:
                    score += 0.12
                for word in UNWANTED_WORDS:
                    if word in normalized_title and word not in _normalized_text(search_query):
                        score -= 0.25
                if "official" in channel.lower() or "topic" in channel.lower():
                    score += 0.03
                score -= index * 0.005
                if score > best_score:
                    best, best_score = entry, score
                    best_title_match, best_artist_match = title_match, artist_match

            # Keep the title as a required match and require at least one
            # credited artist to appear when artist information is available.
            if best and best_title_match >= 0.6 and best_artist_match >= 0.25 and best_score >= 0.62:
                print(f"[search] '{search_query}' -> {best.get('title')} ({best.get('id')}) score={best_score:.2f}")
                return f"https://www.youtube.com/watch?v={best['id']}"
            print(f"[search] no confident match for '{search_query}' (best score={best_score:.2f}); trying next artist")

        return None
    except Exception as ex:
        print(f"resolve_ytsearch error: {ex}")
    return url

# ---------- 3.10 คิวเพลง / Loop / Autoplay ----------

music_queues = {}
current_playing = {}     
loop_statuses = {}       
autoplay_statuses = {}   

def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = []
    return music_queues[guild_id]

async def play_next(interaction: discord.Interaction):
    global current_playing, loop_statuses, autoplay_statuses
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)
    
    # 1. เช็คโหมด Loop
    if loop_statuses.get(guild_id, False) and guild_id in current_playing:
        url, title, requester = current_playing[guild_id]
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            
            after_playing = make_after_playing(interaction, player)

            interaction.guild.voice_client.play(player, after=after_playing)
            
            file_path = "pictures/black-shine.gif"
            file = discord.File(file_path, filename="black-shine.gif") if os.path.exists(file_path) else None
            
            embed = discord.Embed(
                title="🔂 กำลังเล่นซ้ำเพลงเดิม (Loop)",
                description=f"**[{title}]({url})**",
                color=discord.Color.from_rgb(255, 215, 0)
            )
            if file:
                embed.set_image(url="attachment://black-shine.gif")
                await interaction.channel.send(file=file, embed=embed)
            else:
                await interaction.channel.send(embed=embed)
            return
        except Exception as e:
            print(f"Loop error: {e}")

    # 2. ถ้ามีเพลงในคิวปกติ
    if len(queue) > 0:
        url, title, requester = queue.pop(0)
        current_playing[guild_id] = (url, title, requester)
        
        try:
            url = await resolve_ytsearch(url)
            if url is None:
                await interaction.channel.send(f"Could not find a confident YouTube match for **{title}**; skipping it.")
                await play_next(interaction)
                return
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            # เพลงจาก Spotify เข้าคิวเป็นคำค้นหา -> ใช้ลิงก์/ชื่อจริงจาก YouTube ที่ค้นเจอ
            url = player.data.get('webpage_url') or url
            title = player.data.get('title') or title
            current_playing[guild_id] = (url, title, requester)
            
            after_playing = make_after_playing(interaction, player)

            interaction.guild.voice_client.play(player, after=after_playing)
            
            embed = discord.Embed(
                title="🎵 กำลังเล่นเพลงถัดไปจากคิว",
                description=f"**[{title}]({url})**",
                color=discord.Color.from_rgb(255, 182, 193)
            )
            embed.add_field(name="🎧 ผู้ขอเพลง", value=requester.mention, inline=True)
            embed.set_footer(text=f"เพลงคงเหลือในคิว: {len(queue)} เพลง 🐾")
            
            await interaction.channel.send(embed=embed)
            
        except Exception as e:
            await interaction.channel.send(f"⚠️ เกิดข้อผิดพลาดในการเล่นเพลง: {e}")
            await play_next(interaction)
    else:
        # 3. ระบบ Autoplay: ใช้ระบบ Mix/Radio ของ YouTube ต่อจากเพลงล่าสุดโดยอัตโนมัติ
        # (ไม่ต้องเลือกแนวเพลงเอง บอทจะหาเพลงที่ใกล้เคียงกับเพลงที่เล่นอยู่ให้เอง)
        is_autoplay_enabled = autoplay_statuses.get(guild_id, False)

        if is_autoplay_enabled and guild_id in current_playing and interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
            last_url, last_title, _ = current_playing[guild_id]
            video_id = extract_video_id(last_url)

            if video_id:
                mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
                try:
                    ytdl_flat = yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'noplaylist': False, **COOKIE_OPTS})
                    loop = asyncio.get_event_loop()
                    mix_data = await loop.run_in_executor(None, lambda: ytdl_flat.extract_info(mix_url, download=False))

                    entries = [e for e in mix_data.get('entries', []) if e and e.get('id') != video_id]

                    if entries:
                        pick = random.choice(entries[:10]) if len(entries) > 10 else random.choice(entries)
                        auto_url = f"https://www.youtube.com/watch?v={pick['id']}"
                        auto_title = pick.get('title', 'เพลงถัดไป')

                        current_playing[guild_id] = (auto_url, auto_title, bot.user)
                        player = await YTDLSource.from_url(auto_url, loop=bot.loop, stream=True)

                        after_playing = make_after_playing(interaction, player)

                        interaction.guild.voice_client.play(player, after=after_playing)

                        embed = discord.Embed(
                            title="✨ [Autoplay] เล่นเพลงถัดไปที่ใกล้เคียงกันให้อัตโนมัติ",
                            description=f"**[{auto_title}]({auto_url})**",
                            color=discord.Color.from_rgb(152, 251, 152)
                        )
                        embed.set_footer(text="ระบบจะเลือกเพลงที่ใกล้เคียงกับเพลงที่เล่นล่าสุดต่อเนื่องไปจนกว่าจะสั่ง /leave 🐾")
                        await interaction.channel.send(embed=embed)
                        return
                except Exception as e:
                    print(f"Autoplay search error: {e}")

# ==========================================================
# ส่วนที่ 4 │ ⌨️ คำสั่ง  (Slash Commands)
# 4.1 เพลง  •  4.2 ทั่วไป  •  4.3 ระบบ
# ==========================================================

# ---------- 4.1 คำสั่งเพลง ----------

@bot.tree.command(name="play", description="สั่งเล่นเพลงจาก YouTube / Spotify / Apple Music หรือพิมพ์ชื่อเพลงเพื่อค้นหา")
async def slash_play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    try:
        if not interaction.user.voice:
            await interaction.followup.send("❌ คุณต้องเข้าห้อง Voice Channel ก่อนสั่งเพลงนะคับ!")
            return

        # ลิงก์ Spotify / Apple Music: แปลงเป็นชื่อเพลง แล้วให้เล่นเพลงแรกก่อน ที่เหลือเข้าคิว
        collection_name = None
        extra_queries = []
        is_spotify = "open.spotify.com" in url or "spotify.link" in url
        is_apple = "music.apple.com" in url
        if is_spotify or is_apple:
            try:
                if is_spotify:
                    collection_name, found_queries = await spotify_to_queries(url)
                else:
                    collection_name, found_queries = await apple_to_queries(url)
            except Exception as e:
                print(f"{'Spotify' if is_spotify else 'Apple Music'} error: {e}")
                found_queries = []
            if not found_queries:
                service = "Spotify" if is_spotify else "Apple Music"
                await interaction.followup.send(f"❌ อ่านลิงก์ {service} นี้ไม่ได้ (ถ้าเป็นเพลย์ลิสต์ส่วนตัวต้องตั้งเป็นสาธารณะก่อนนะ)")
                return
            url = f"ytsearch1:{found_queries[0]}{SPOTIFY_SEARCH_SUFFIX}"
            extra_queries = found_queries[1:]

        if not interaction.guild.voice_client:
            channel = interaction.user.voice.channel
            perms = channel.permissions_for(interaction.guild.me)
            if not perms.connect or not perms.speak:
                await interaction.followup.send("❌ บอทไม่มีสิทธิ์ **Connect / Speak** ในห้องเสียงนี้ (ไปตั้งสิทธิ์ของบอทในห้องก่อน ไม่งั้นจะเข้าห้องได้แต่ไม่มีเสียง)")
                return
            await channel.connect()

        guild_id = interaction.guild.id
        queue = get_queue(guild_id)

        searched_query = url[len("ytsearch1:"):] if url.startswith("ytsearch1:") else None
        url = await resolve_ytsearch(url)
        if url is None:
            await interaction.followup.send(f"Could not find a confident YouTube match for **{searched_query}**. Try a more specific song link or title.")
            return

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: extract_info_resilient({'format': 'bestaudio/best', 'noplaylist': True}, url, download=False))
        
        if 'entries' in data:
            data = data['entries'][0]
            
        real_url = data.get('webpage_url', url)
        title = data.get('title', 'Unknown Title')

        file_path = "pictures/black-shine.gif"
        file = discord.File(file_path, filename="black-shine.gif") if os.path.exists(file_path) else None

        if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused():
            queue.append((real_url, title, interaction.user))
            embed = discord.Embed(
                title="📥 เพิ่มเพลงลงในคิวแล้ว",
                description=f"**[{title}]({real_url})**",
                color=discord.Color.from_rgb(255, 160, 122)
            )
            embed.add_field(name="📌 ลำดับคิวที่", value=f"#{len(queue)}", inline=True)
            embed.add_field(name="🎧 ผู้ขอเพิ่ม", value=interaction.user.mention, inline=True)
            
            await interaction.followup.send(embed=embed)
        else:
            current_playing[guild_id] = (real_url, title, interaction.user)
            player = await YTDLSource.from_url(real_url, loop=bot.loop, stream=True)
            
            after_playing = make_after_playing(interaction, player)

            interaction.guild.voice_client.play(player, after=after_playing)

            embed = discord.Embed(
                title="🎵 กำลังเล่นเพลง",
                description=f"**[{title}]({real_url})**",
                color=discord.Color.from_rgb(255, 182, 193)
            )
            embed.add_field(name="🎧 ผู้ขอเพลง", value=interaction.user.mention, inline=True)
            if searched_query:
                embed.set_footer(text=f"🔎 ค้นหาจาก: {searched_query}")
            
            if file:
                embed.set_image(url="attachment://black-shine.gif")
                await interaction.followup.send(file=file, embed=embed)
            else:
                await interaction.followup.send(embed=embed)

        if extra_queries:
            for q in extra_queries:
                queue.append((f"ytsearch1:{q}{SPOTIFY_SEARCH_SUFFIX}", q, interaction.user))
            await interaction.followup.send(
                f"📋 เพิ่มอีก **{len(extra_queries)}** เพลงจาก **{collection_name}** ลงในคิวแล้ว 🐾 (สูงสุด {MAX_SPOTIFY_TRACKS} เพลงต่อลิงก์)"
            )

    except Exception as e:
        error_embed = discord.Embed(
            title="⚠️ เกิดข้อผิดพลาด",
            description=f"ไม่สามารถโหลดเพลงนี้ได้:\n```{_strip_ansi(e)[:1500]}```",
            color=discord.Color.red()
        )
        error_embed.set_footer(text=f"build {BUILD_ID} • yt-dlp {YTDLP_VERSION} • cookies.txt {'✅' if os.path.exists('cookies.txt') else '❌'} • deno {'✅' if DENO_PATH else '❌'}")
        await interaction.followup.send(embed=error_embed)

@bot.tree.command(name="queue", description="ดูรายการเพลงที่รออยู่ในคิวปัจจุบัน")
async def slash_queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)

    if not queue:
        await interaction.response.send_message("📭 ตอนนี้ไม่มีเพลงรออยู่ในคิวเลยงับ", ephemeral=True)
        return

    description = ""
    for i, item in enumerate(queue[:20], 1):
        url, title, user = item
        if url.startswith("ytsearch"):
            description += f"**{i}.** {title} (ขอโดย: {user.mention})\n"
        else:
            description += f"**{i}.** [{title}]({url}) (ขอโดย: {user.mention})\n"
    if len(queue) > 20:
        description += f"\n...และอีก {len(queue) - 20} เพลง"

    file_path = "pictures/black-shine.gif"
    file = discord.File(file_path, filename="black-shine.gif") if os.path.exists(file_path) else None

    embed = discord.Embed(
        title="🎶 รายการคิวเพลงทั้งหมด",
        description=description,
        color=discord.Color.from_rgb(135, 206, 250)
    )
    embed.set_footer(text=f"จำนวนเพลงในคิวทั้งหมด: {len(queue)} เพลง")
    
    if file:
        embed.set_image(url="attachment://black-shine.gif")
        await interaction.response.send_message(file=file, embed=embed)
    else:
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="skip", description="ข้ามเพลงที่กำลังเล่นอยู่ไปเพลงถัดไป")
async def slash_skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        manual_stop.add(interaction.guild.id)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ ข้ามเพลงเรียบร้อยแล้วงับ!")
        bot.loop.create_task(play_next(interaction))
    else:
        await interaction.response.send_message("❌ ตอนนี้ไม่มีเพลงกำลังเล่นอยู่เลยนะ", ephemeral=True)

@bot.tree.command(name="leave", description="ให้บอทออกจากห้องเสียงและเคลียร์คิวเพลง")
async def slash_leave(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in music_queues:
        music_queues[guild_id].clear()
    if guild_id in current_playing:
        del current_playing[guild_id]

    if interaction.guild.voice_client:
        manual_stop.add(interaction.guild.id)
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 บอทออกจากห้องเสียงและเคลียร์คิวเรียบร้อยแล้วงับ!")
    else:
        await interaction.response.send_message("❌ บอทยังไม่ได้อยู่ในห้องเสียงเลยนะ", ephemeral=True)

@bot.tree.command(name="loop", description="เปิดใช้งานวนซ้ำเพลงที่กำลังเล่นอยู่ปัจจุบัน")
async def slash_loop(interaction: discord.Interaction):
    global loop_statuses
    guild_id = interaction.guild.id
    loop_statuses[guild_id] = True
    await interaction.response.send_message("🔂 เปิดโหมด **Loop** วนซ้ำเพลงนี้เรียบร้อยแล้วงับ!", ephemeral=True)

@bot.tree.command(name="unloop", description="ปิดใช้งานวนซ้ำเพลงปัจจุบัน")
async def slash_unloop(interaction: discord.Interaction):
    global loop_statuses
    guild_id = interaction.guild.id
    loop_statuses[guild_id] = False
    await interaction.response.send_message("➡️ ปิดโหมด **Loop** เรียบร้อยแล้ว กลับเข้าสู่คิวปกติงับ!", ephemeral=True)

@bot.tree.command(name="autoplay", description="เปิดหรือปิดระบบเล่นเพลงต่อเนื่องอัตโนมัติ (บอทเลือกเพลงที่ใกล้เคียงให้เอง)")
@discord.app_commands.choices(status=[
    discord.app_commands.Choice(name="เปิด Autoplay", value="on"),
    discord.app_commands.Choice(name="ปิด Autoplay", value="off")
])
async def slash_autoplay(interaction: discord.Interaction, status: str):
    global autoplay_statuses
    guild_id = interaction.guild.id

    if status == "on":
        autoplay_statuses[guild_id] = True
        await interaction.response.send_message("✨ เปิดระบบ **Autoplay** เรียบร้อยแล้วงับ! เพลงหมดคิวบอทจะเลือกเพลงที่ใกล้เคียงกับเพลงล่าสุดมาเล่นต่อเนื่องให้เองไปจนกว่าจะสั่ง /leave เลย 🎶", ephemeral=True)
    else:
        autoplay_statuses[guild_id] = False
        await interaction.response.send_message("💤 ปิดระบบ **Autoplay** แล้วงับ", ephemeral=True)

# ---------- 4.2 คำสั่งทั่วไป ----------

@bot.tree.command(name="talk", description="ตั้งค่าเปิดหรือปิดการคุยเล่นของบอทในห้องนี้")
@discord.app_commands.choices(toggle=[
    discord.app_commands.Choice(name="ห้องนี้แหละ (เปิดใช้งาน)", value="open"),
    discord.app_commands.Choice(name="ปิดห้อง (ปิดใช้งาน)", value="close")
])
async def slash_talk(interaction: discord.Interaction, toggle: str):
    guild_id = interaction.guild.id
    channel_id = interaction.channel.id

    if toggle == "open":
        allowed_chat_channels[guild_id] = channel_id
        await interaction.response.send_message(f"🐱 เปิดใช้งานให้น้องแมวคุยเล่นในห้อง **#{interaction.channel.name}** นี้เรียบร้อยแล้วงับ!", ephemeral=True)
    elif toggle == "close":
        if guild_id in allowed_chat_channels:
            del allowed_chat_channels[guild_id]
        await interaction.response.send_message("💤 ปิดการคุยเล่นของน้องแมวในเซิร์ฟเวอร์นี้เรียบร้อยแล้ว", ephemeral=True)

@bot.tree.command(name="ping", description="ตรวจสอบว่าบอทยังตอบสนองอยู่ไหม")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! 🏓 บอทยังไหวอยู่ครับ")

@bot.tree.command(name="echo", description="ให้บอทพูดข้อความที่คุณพิมพ์")
async def slash_echo(interaction: discord.Interaction, text: str):
    await interaction.response.send_message(text, allowed_mentions=discord.AllowedMentions.none())

@bot.tree.command(name="roll", description="ทอยลูกเต๋า 1 ถึง 6")
async def slash_roll(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 ได้เลข {random.randint(1, 6)}")

@bot.tree.command(name="coin", description="โยนเหรียญหัวหรือก้อย")
async def slash_coin(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 {random.choice(['หัว', 'ก้อย'])}!")

@bot.tree.command(name="joke", description="ขอมุกตลกจากบอท")
async def slash_joke(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice([
        "ทำไมคอมพิวเตอร์ถึงหนาว? เพราะเปิดวินโดวส์ไว้",
        "ปลาอะไรขี้เกียจ? ปล่อยไปก่อน",
        "ทำไมหนังสือถึงไปหาหมอ? เพราะมีหลายหน้า"
    ]))

@bot.tree.command(name="choose", description="ให้บอทเลือกหนึ่งอย่างจากสองตัวเลือก")
async def slash_choose(interaction: discord.Interaction, choice1: str, choice2: str):
    await interaction.response.send_message(f"ผมเลือก: {random.choice([choice1, choice2])}")

@bot.tree.command(name="commands", description="แสดงรายการคำสั่งของบอท")
async def slash_commands(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**🎵 เพลง**\n"
        "`/play` เล่นเพลง (ลิงก์ YouTube / Spotify / Apple Music หรือพิมพ์ชื่อเพลง)\n"
        "`/queue` ดูคิว  •  `/skip` ข้ามเพลง  •  `/leave` ให้บอทออกจากห้อง\n"
        "`/loop` `/unloop` วนซ้ำเพลงเดิม  •  `/autoplay` เล่นต่อเนื่องอัตโนมัติ\n\n"
        "**💬 คุยเล่น / ทั่วไป**\n"
        "`/talk` เปิด-ปิดโหมดคุยเล่นในห้องนี้  •  `/ping` `/echo` `/roll` `/coin` `/joke` `/choose`\n\n"
        "**🛠️ ระบบ**\n"
        "`/voicecheck` ตรวจว่าทำไมบอทไม่มีเสียง"
    )

# ---------- 4.3 คำสั่งระบบ ----------

@bot.tree.command(name="voicecheck", description="ตรวจว่าทำไมบอทไม่มีเสียง (PyNaCl / Opus / ffmpeg / สิทธิ์ห้องเสียง)")
async def slash_voicecheck(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    lines = voice_diagnostics()
    vc = interaction.guild.voice_client
    if vc:
        lines.append(f"Voice: เชื่อมต่อ {'✅' if vc.is_connected() else '❌'} | ping {vc.latency * 1000:.0f}ms" if vc.latency != float('inf') else "Voice: เชื่อมต่อแล้วแต่ยังไม่มีสัญญาณ UDP ❌ (โฮสต์อาจบล็อก UDP)")
        perms = vc.channel.permissions_for(interaction.guild.me)
        lines.append(f"สิทธิ์ Connect {'✅' if perms.connect else '❌'} | Speak {'✅' if perms.speak else '❌'}")
    else:
        lines.append("Voice: บอทยังไม่ได้อยู่ในห้องเสียง (สั่ง /play ก่อนแล้วลอง /voicecheck อีกครั้ง)")
    lines.append(f"yt-dlp {YTDLP_VERSION} | deno {'✅' if DENO_PATH else '❌'} | cookies {'✅' if os.path.exists('cookies.txt') else '❌'} | build {BUILD_ID}")
    await interaction.followup.send("\n".join(lines), ephemeral=True)

# ==========================================================
# ส่วนที่ 5 │ ▶️ เริ่มบอท  (อ่านโทเคนจากตัวแปร DISCORD_BOT_TOKEN)
# ==========================================================

token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    sys.exit("ไม่พบ DISCORD_BOT_TOKEN กรุณาตั้งค่าตัวแปรใน PowerShell ก่อนรันครับ!")

bot.run(token)
