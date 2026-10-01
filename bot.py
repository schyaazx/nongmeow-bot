import discord
from discord.ext import commands
import random
import os
import sys
import yt_dlp
import asyncio
import re
import json
import aiohttp  # ติดตั้งมาพร้อม discord.py อยู่แล้ว
import html


# ==========================================
# 0. ตั้งค่าบอท
# ==========================================

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

# ==========================================
# 1. ดักข้อความ (ตอบคีย์เวิร์ดในห้องที่เปิดด้วย /talk)
# ==========================================

allowed_chat_channels = {}

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    guild_id = message.guild.id
    
    if guild_id not in allowed_chat_channels or message.channel.id != allowed_chat_channels[guild_id]:
        await bot.process_commands(message)
        return

    greeting_keywords = [
    "สวัสดี", "หวัดดี", "หวัด", "ดีจ้า", "ดีครับ", "ดีค่ะ",
    "hi", "hello", "sup", "yo" ,"เฮ้", "โย่", "ว่าไง"
]
    trigger_keywords = [
     "ควย" , "ควาย" , "เหี้ย" , "สัส"
    ]
    callout_keywords = [
        "น้องแมว" , "กุ่ย" , "ไก่" , "ไอกุ่ย" , "ไอไก่"
    ]

    callout_text = message.content.strip()
    mes = message.content.lower()

    if "สวัสดีน้องแมว" in mes or "หวัดดีจ้า" in mes:
        async with message.channel.typing():
            await message.channel.send(f"สวัสดีครับคุณ {message.author.mention} มีอะไรให้น้องแมวกินมั้ย")
            return
    elif any(word in mes for word in greeting_keywords):
        async with message.channel.typing():
            await message.channel.send(f"สวัสดีครับคุณ {message.author.mention} ทักน้องแมวมีอะไรให้ช่วย")
            return
    elif callout_text in callout_keywords:
        answer_text = random.choice([
            "มีอะไรหรือ",
            "แว้",
            "ว่า"
        ])
        async with message.channel.typing():
            await message.channel.send(f"{answer_text}")
    elif any(word in mes for word in trigger_keywords):
        trigger_text = random.choice([
            "พูดจาดีๆหน่อยไวรุ่น" ,
            "ชอบความรุนแรงหรอไวรุ่น" ,
            "เจอได้"
        ])
        async with message.channel.typing():
            await message.channel.send(f"{trigger_text}")
            return
    

    if "ร้องเพลงให้ฟังหน่อย" in mes :
        async with message.channel.typing():
            await message.channel.send(f"ร้องเพลงอันไหนนน ส่ง url มาให้น้องแมวร้องสิ")
            return

    if "เหงา" in mes or "เหงาอะ" in mes:
        alone_text = random.choice([
            "มีน้องแมวอยู่เป็นเพื่อนทั้งคน เหงาได้ไง",
            "คุยกับน้องแมวได้นะ" ,
            "บ่นให้น้องแมวฟังได้นะ น้องเกิดที่ไทยมีใบเกิด"
        ])
        async with message.channel.typing():
            await message.channel.send(f"{alone_text}")
            return
    elif "จีบหน่อย" in mes or "หยอดหน่อย" in mes:
        flirt_text = random.choice([
            "ถึงตัวจะเป็นแมว แต่หัวใจมีแต่เธอนะคั้บ",
            "เป็นคนชอบแมวป่าวครับ... ถ้าชอบ ลองมาเป็นทาสรักเราดูสิ รับรองดูแลดีแน่นอน",
            "อากาศหนาวให้ห่มผ้า แต่อยากอบอุ่นกว่า... ให้มาซบไหล่เรานะฮะ"
        ])
        async with message.channel.typing():
            await message.channel.send(f"{flirt_text}")
            return

    if "นิ่งๆ" in mes:
        still_text = random.choice([
            "โอเคคั้บผม",
            "แต่ซิ่งจัด"
        ])
        async with message.channel.typing():
            await message.channel.send(f"{still_text}")  
        if "แต่ซิ่งจัด" in still_text:
            async with message.channel.typing():
                await message.channel.send(f"ขอโทษคั้บ ซิ่งไปหน่อย")
                return
    elif "วอดส์" in mes:
        async with message.channel.typing():
            await message.channel.send(f"โหอะไรว้า คนไทย")
        
    await bot.process_commands(message)

# ==========================================
# 2. เล่นเพลง (ตัวเล่นเสียง / อ่านลิงก์ / ค้นหา / คิว)
# ==========================================

# ---------- 2.1 ตัวดึงเสียงจาก YouTube (yt-dlp + ffmpeg) ----------

# ตั้งค่าตัวเลือกสำหรับดึงเสียงจาก YouTube
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'quiet': True,
    'noplaylist': True,
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable="ffmpeg", **{'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}), data=data)

# ---------- 2.2 อ่านลิงก์ Spotify ----------

SPOTIFY_LINK_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-zA-Z-]+/)?(track|album|playlist)/([0-9A-Za-z]+)")
SPOTIFY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
MAX_SPOTIFY_TRACKS = 50      # จำกัดจำนวนเพลงสูงสุดต่อ 1 ลิงก์
SPOTIFY_SEARCH_SUFFIX = ""   # ถ้าอยากปรับผลค้นหา YouTube เช่น " audio" ให้ใส่ตรงนี้

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

# ---------- 2.3 อ่านลิงก์ Apple Music ----------

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

# ---------- 2.4 เลือกผลค้นหา YouTube ที่ตรงที่สุด (แทนการเอาผลแรกเสมอ) ----------

UNWANTED_WORDS = ["live", "cover", "remix", "karaoke", "sped up", "slowed", "reverb", "nightcore", "8d", "instrumental", "reaction", "tutorial", "lyric video"]

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
        ytdl_search = yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'skip_download': True})
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

# ---------- 2.5 คิวเพลง / Loop / Autoplay ----------

def extract_video_id(url):
    """ดึง YouTube video ID ออกจาก URL เพื่อใช้หาเพลงต่อเนื่องแนวเดียวกัน"""
    match = re.search(r"(?:v=|youtu\.be/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

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
            
            def after_playing(error):
                if error:
                    print(f'Player error: {error}')
                fut = asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"Error in after_playing: {e}")

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
            
            def after_playing(error):
                if error:
                    print(f'Player error: {error}')
                fut = asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"Error in after_playing: {e}")

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
                    ytdl_flat = yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'noplaylist': False})
                    loop = asyncio.get_event_loop()
                    mix_data = await loop.run_in_executor(None, lambda: ytdl_flat.extract_info(mix_url, download=False))

                    entries = [e for e in mix_data.get('entries', []) if e and e.get('id') != video_id]

                    if entries:
                        pick = random.choice(entries[:10]) if len(entries) > 10 else random.choice(entries)
                        auto_url = f"https://www.youtube.com/watch?v={pick['id']}"
                        auto_title = pick.get('title', 'เพลงถัดไป')

                        current_playing[guild_id] = (auto_url, auto_title, bot.user)
                        player = await YTDLSource.from_url(auto_url, loop=bot.loop, stream=True)

                        def after_playing(error):
                            if error:
                                print(f'Player error: {error}')
                            fut = asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop)
                            try:
                                fut.result()
                            except Exception as e:
                                print(f"Error in after_playing: {e}")

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

# ==========================================
# 3. คำสั่ง (Slash Commands)
# ==========================================

# ---------- 3.1 คำสั่งเพลง ----------

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
            await channel.connect()

        guild_id = interaction.guild.id
        queue = get_queue(guild_id)

        searched_query = url[len("ytsearch1:"):] if url.startswith("ytsearch1:") else None
        url = await resolve_ytsearch(url)
        if url is None:
            await interaction.followup.send(f"Could not find a confident YouTube match for **{searched_query}**. Try a more specific song link or title.")
            return

        ytdl_temp = yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True})
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl_temp.extract_info(url, download=False))
        
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
            
            def after_playing(error):
                if error:
                    print(f'Player error: {error}')
                fut = asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"Error in after_playing: {e}")

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
            description=f"ไม่สามารถโหลดเพลงนี้ได้: `{e}`",
            color=discord.Color.red()
        )
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

# ---------- 3.2 คำสั่งทั่วไป ----------

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
        "คำสั่ง: `/talk`, `/autoplay`, `/loop`, `/unloop`, `/ping`, `/echo`, `/roll`, `/coin`, `/joke`, `/choose`, `/play`, `/queue`, `/skip`, `/leave`"
    )

# ==========================================
# รันบอทผ่าน Environment Variable
# ==========================================
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    sys.exit("ไม่พบ DISCORD_BOT_TOKEN กรุณาตั้งค่าตัวแปรใน PowerShell ก่อนรันครับ!")

bot.run(token)