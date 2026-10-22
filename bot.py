"""main.py - น้องแมว 🐱 (ไฟล์เดียวจบ: บอท + ระบบเพลง)

รัน:  python main.py

ตัวแปรที่ต้องตั้ง (env หรือไฟล์ .env):
  DISCORD_TOKEN           token ของบอท (จำเป็น)
  SPOTIFY_CLIENT_ID       ไม่บังคับ (ใช้เปิด Spotify)
  SPOTIFY_CLIENT_SECRET   ไม่บังคับ

requirements.txt:
  discord.py[voice]
  yt-dlp
  spotipy
  PyNaCl
  python-dotenv

ต้องมี ffmpeg บนเครื่อง/โฮสต์
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:  # ไม่จำเป็นถ้าไม่ใช้ Spotify
    spotipy = None


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # ไม่มี python-dotenv ก็ใช้ env ของโฮสต์ได้
    pass

log = logging.getLogger(__name__)

# ---------- ค่าตั้ง / สไตล์ ----------
IDLE_TIMEOUT = 300  # วินาที: ไม่มีเพลงแล้วออกจากห้อง
MAX_SPOTIFY_TRACKS = 200
QUEUE_PAGE = 10
COLOR = discord.Color(0xF4A6C8)      # ชมพูพาสเทล
ERR_COLOR = discord.Color(0xE5707E)  # แดงอ่อน
FOOTER = "น้องแมว 🐱"

SPOTIFY_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?(track|playlist|album)/([A-Za-z0-9]+)")

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
YTDL_FLAT = yt_dlp.YoutubeDL(
    {
        "quiet": True,
        "noplaylist": False,
        "extract_flat": "in_playlist",
        "default_search": "ytsearch",
        "format": "bestaudio/best",
        "cookiefile": "cookies.txt",
    }
)

YTDL_FULL = yt_dlp.YoutubeDL(
    {
        "quiet": True,
        "noplaylist": True,
        "format": "bestaudio/best",
        "default_search": "ytsearch",
        "cookiefile": "cookies.txt",
    }
)

# ---------- ตัวช่วยหน้าตา ----------
def fmt_time(sec: Optional[float]) -> str:
    if not sec:
        return "?:??"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def progress_bar(elapsed: float, total: Optional[float], n: int = 16) -> str:
    if not total:
        return "🔘" + "▬" * (n - 1)
    pos = min(int(elapsed / total * n), n - 1)
    return "▬" * pos + "🔘" + "▬" * (n - pos - 1)


def info(text: str, ok: bool = True) -> discord.Embed:
    return discord.Embed(description=text, color=COLOR if ok else ERR_COLOR)


@dataclass
class Track:
    title: str
    requester: discord.abc.User
    page_url: Optional[str] = None   # ลิงก์ YouTube (ถ้ามี)
    query: Optional[str] = None      # ใช้ค้นหา (เพลงจาก Spotify)
    duration: Optional[float] = None
    thumbnail: Optional[str] = None
    stream_url: Optional[str] = None

    @property
    def link(self) -> str:
        return f"[{self.title}]({self.page_url})" if self.page_url else self.title


# ---------- ปุ่มควบคุม ----------
class PlayerView(discord.ui.View):
    def __init__(self, player: "GuildPlayer"):
        super().__init__(timeout=None)
        self.player = player
        self._sync()

    def _sync(self) -> None:
        self.pause_btn.emoji = "▶️" if self.player.paused else "⏸️"
        self.loop_btn.style = discord.ButtonStyle.success if self.player.loop else discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        vc = self.player.guild.voice_client
        voice = getattr(interaction.user, "voice", None)
        if vc and voice and voice.channel == vc.channel:
            return True
        await interaction.response.send_message(
            embed=info("เข้าห้องเสียงเดียวกับบอทก่อนนะ 🐱", ok=False), ephemeral=True
        )
        return False

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.paused:
            self.player.resume()
        else:
            self.player.pause()
        self._sync()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.skip()
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.loop = not self.player.loop
        self._sync()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="📜", style=discord.ButtonStyle.secondary)
    async def queue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.player.cog.queue_embed(self.player), ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=info(f"⏹️ {interaction.user.display_name} หยุดเพลงแล้ว ไปก่อนนะ 🐱")
        )
        await self.player.cog.destroy_player(self.player.guild)


# ---------- ตัวเล่นเพลง 1 ตัวต่อ 1 server ----------
class GuildPlayer:
    def __init__(self, cog: "Music", guild: discord.Guild, channel: discord.abc.Messageable):
        self.cog = cog
        self.guild = guild
        self.channel = channel
        self.queue: deque[Track] = deque()
        self.current: Optional[Track] = None
        self.loop = False
        self.now_msg: Optional[discord.Message] = None
        self._started = 0.0
        self._paused_total = 0.0
        self._paused_at: Optional[float] = None
        self._wakeup = asyncio.Event()
        self._done = asyncio.Event()
        self.task = asyncio.create_task(self._run())

    # --- สถานะเวลา ---
    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    @property
    def elapsed(self) -> float:
        if not self.current:
            return 0.0
        ref = self._paused_at or time.monotonic()
        return max(0.0, ref - self._started - self._paused_total)

    # --- ควบคุม ---
    def add(self, tracks: list[Track]) -> None:
        self.queue.extend(tracks)
        self._wakeup.set()

    def pause(self) -> bool:
        vc = self.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            self._paused_at = time.monotonic()
            return True
        return False

    def resume(self) -> bool:
        vc = self.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            if self._paused_at is not None:
                self._paused_total += time.monotonic() - self._paused_at
            self._paused_at = None
            return True
        return False

    def skip(self) -> None:
        vc = self.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()  # after-callback จะปลุก loop ให้ไปเพลงต่อไป

    async def _clear_view(self) -> None:
        if self.now_msg:
            try:
                await self.now_msg.edit(view=None)
            except Exception:  # noqa: BLE001
                pass
            self.now_msg = None

    # --- ลูปหลัก ---
    async def _run(self) -> None:
        try:
            while True:
                if not self.queue:
                    self._wakeup.clear()
                    try:
                        await asyncio.wait_for(self._wakeup.wait(), IDLE_TIMEOUT)
                    except asyncio.TimeoutError:
                        await self.channel.send(embed=info("ไม่มีเพลงแล้ว ขอออกจากห้องก่อนนะ 🐱💤"))
                        break
                    continue

                track = self.queue.popleft()
                try:
                    await self.cog.resolve_stream(track)
                except Exception as e:  # noqa: BLE001
                    log.warning("resolve failed for %s: %s", track.title, e)
                    await self.channel.send(embed=info(f"❌ เล่นไม่ได้: **{track.title}** (ข้ามให้แล้ว)", ok=False))
                    continue

                vc = self.guild.voice_client
                if vc is None:
                    break

                self.current = track
                self._started = time.monotonic()
                self._paused_total = 0.0
                self._paused_at = None
                self._done.clear()

                loop = asyncio.get_running_loop()
                source = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTS)
                vc.play(source, after=lambda err: loop.call_soon_threadsafe(self._done.set))

                self.now_msg = await self.channel.send(
                    embed=self.cog.now_playing_embed(self, track), view=PlayerView(self)
                )
                await self._done.wait()
                await self._clear_view()

                if self.loop:
                    track.stream_url = None  # ลิงก์สตรีมหมดอายุได้ เลยขอใหม่ตอนวนกลับมา
                    self.queue.append(track)
                self.current = None
        except asyncio.CancelledError:
            raise
        finally:
            self.current = None
            await self._clear_view()
            await self.cog.destroy_player(self.guild, from_task=True)


# ---------- Cog ----------
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}
        self.sp = None
        cid, secret = os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET")
        if spotipy and cid and secret:
            self.sp = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret)
            )
        else:
            log.info("Spotify ปิดอยู่ (ไม่มี spotipy หรือไม่ได้ตั้ง SPOTIFY_CLIENT_ID/SECRET)")

    # ----- ดึงข้อมูลเพลง -----
    async def _run_blocking(self, fn):
        return await asyncio.get_running_loop().run_in_executor(None, fn)

    async def resolve_stream(self, track: Track) -> None:
        """หา stream url จริงตอนจะเล่น"""
        target = track.page_url or f"ytsearch1:{track.query}"
        info_ = await self._run_blocking(lambda: YTDL_FULL.extract_info(target, download=False))
        if "entries" in info_:
            info_ = info_["entries"][0]
        track.stream_url = info_["url"]
        track.page_url = info_.get("webpage_url") or track.page_url
        track.duration = track.duration or info_.get("duration")
        track.thumbnail = track.thumbnail or info_.get("thumbnail")
        if track.query:
            track.title = info_.get("title") or track.title

    async def tracks_from_youtube(self, query: str, requester) -> list[Track]:
        data = await self._run_blocking(lambda: YTDL_FLAT.extract_info(query, download=False))
        entries = data.get("entries")
        if entries is None:
            entries = [data]
        elif not query.startswith(("http://", "https://")):
            entries = entries[:1]  # ค้นด้วยคำ เอาผลแรก
        tracks = []
        for e in entries:
            if not e:
                continue
            url = e.get("webpage_url") or e.get("url")
            if not url:
                continue
            tracks.append(Track(
                title=e.get("title") or "ไม่ทราบชื่อ", requester=requester,
                page_url=url, duration=e.get("duration"),
                thumbnail=(e.get("thumbnails") or [{}])[-1].get("url") or e.get("thumbnail"),
            ))
        return tracks

    async def tracks_from_spotify(self, kind: str, sid: str, requester) -> list[Track]:
        if not self.sp:
            raise RuntimeError("ยังไม่ได้ตั้งค่า Spotify")

        def fetch() -> list[tuple[str, str]]:
            out: list[tuple[str, str]] = []
            if kind == "track":
                t = self.sp.track(sid)
                return [(t["name"], t["artists"][0]["name"])]
            page = (self.sp.playlist_items(sid, additional_types=("track",)) if kind == "playlist"
                    else self.sp.album_tracks(sid))
            while page and len(out) < MAX_SPOTIFY_TRACKS:
                for item in page["items"]:
                    t = item.get("track") if kind == "playlist" else item
                    if t and t.get("name"):
                        out.append((t["name"], t["artists"][0]["name"]))
                page = self.sp.next(page) if page.get("next") else None
            return out[:MAX_SPOTIFY_TRACKS]

        pairs = await self._run_blocking(fetch)
        return [Track(title=f"{n} - {a}", query=f"{a} {n}", requester=requester) for n, a in pairs]

    # ----- Embed -----
    def now_playing_embed(self, player: GuildPlayer, t: Track, live: bool = False) -> discord.Embed:
        e = discord.Embed(title="🎶 กำลังเล่น", description=f"**{t.link}**", color=COLOR)
        if live:
            e.add_field(
                name="ความคืบหน้า",
                value=f"{progress_bar(player.elapsed, t.duration)}\n`{fmt_time(player.elapsed)} / {fmt_time(t.duration)}`",
                inline=False,
            )
        else:
            e.add_field(name="⏱ ความยาว", value=fmt_time(t.duration))
        e.add_field(name="🙋 ขอโดย", value=t.requester.mention)
        e.add_field(name="📜 ในคิว", value=f"{len(player.queue)} เพลง")
        if t.thumbnail:
            e.set_thumbnail(url=t.thumbnail)
        e.set_footer(text=FOOTER)
        return e

    def queue_embed(self, p: GuildPlayer) -> discord.Embed:
        lines = []
        if p.current:
            lines.append(f"**🎶 กำลังเล่น**\n{p.current.link} `{fmt_time(p.current.duration)}`\n")
        if p.queue:
            lines.append("**⏭ ถัดไป**")
            for i, t in enumerate(list(p.queue)[:QUEUE_PAGE], 1):
                lines.append(f"`{i}.` {t.title} `{fmt_time(t.duration)}`")
            if len(p.queue) > QUEUE_PAGE:
                lines.append(f"… และอีก {len(p.queue) - QUEUE_PAGE} เพลง")
        e = discord.Embed(title="📜 คิวเพลง", description="\n".join(lines) or "คิวว่าง", color=COLOR)
        total = sum(t.duration or 0 for t in p.queue)
        e.set_footer(text=f"{FOOTER} • วนซ้ำ: {'เปิด' if p.loop else 'ปิด'}"
                          + (f" • รวม ~{fmt_time(total)}" if total else ""))
        return e

    def added_embed(self, tracks: list[Track], position: int, requester) -> discord.Embed:
        first = tracks[0]
        if len(tracks) == 1:
            e = discord.Embed(title="✅ เพิ่มเข้าคิวแล้ว", description=f"**{first.link}**", color=COLOR)
            e.add_field(name="⏱ ความยาว", value=fmt_time(first.duration))
            e.add_field(name="📍 ลำดับ", value="เล่นเลย" if position == 0 else f"#{position}")
            if first.thumbnail:
                e.set_thumbnail(url=first.thumbnail)
        else:
            preview = "\n".join(f"• {t.title}" for t in tracks[:5])
            if len(tracks) > 5:
                preview += f"\n… และอีก {len(tracks) - 5} เพลง"
            e = discord.Embed(title=f"✅ เพิ่ม {len(tracks)} เพลงเข้าคิวแล้ว", description=preview, color=COLOR)
        e.set_footer(text=f"{FOOTER} • ขอโดย {requester.display_name}")
        return e

    # ----- จัดการ player -----
    async def destroy_player(self, guild: discord.Guild, from_task: bool = False) -> None:
        player = self.players.pop(guild.id, None)
        if player and not from_task:
            player.task.cancel()
        vc = guild.voice_client
        if vc:
            await vc.disconnect(force=True)

    async def _ensure_player(self, interaction: discord.Interaction) -> Optional[GuildPlayer]:
        user = interaction.user
        if not isinstance(user, discord.Member) or not user.voice or not user.voice.channel:
            await interaction.followup.send(embed=info("เข้าห้องเสียงก่อนนะ 🐱", ok=False))
            return None
        vc = interaction.guild.voice_client
        if vc is None:
            await user.voice.channel.connect()
        elif vc.channel != user.voice.channel:
            await vc.move_to(user.voice.channel)
        player = self.players.get(interaction.guild_id)
        if player is None:
            player = GuildPlayer(self, interaction.guild, interaction.channel)
            self.players[interaction.guild_id] = player
        return player

    def _player(self, interaction: discord.Interaction) -> Optional[GuildPlayer]:
        return self.players.get(interaction.guild_id)

    # ----- คำสั่ง -----
    @app_commands.command(name="play", description="เล่นเพลง (ชื่อเพลง / ลิงก์ YouTube / ลิงก์ Spotify)")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        player = await self._ensure_player(interaction)
        if player is None:
            return
        try:
            m = SPOTIFY_RE.search(query)
            if m:
                tracks = await self.tracks_from_spotify(m.group(1), m.group(2), interaction.user)
            else:
                tracks = await self.tracks_from_youtube(query, interaction.user)
        except Exception as e:  # noqa: BLE001
            log.warning("play failed: %s", e)
            await interaction.followup.send(embed=info(f"❌ หาเพลงไม่เจอ: {e}", ok=False))
            return
        if not tracks:
            await interaction.followup.send(embed=info("❌ ไม่เจอเพลง", ok=False))
            return
        position = 0 if (not player.current and not player.queue) else len(player.queue) + 1
        player.channel = interaction.channel
        player.add(tracks)
        await interaction.followup.send(embed=self.added_embed(tracks, position, interaction.user))

    @app_commands.command(name="skip", description="ข้ามเพลง")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction):
        p = self._player(interaction)
        if not p or not p.current:
            return await interaction.response.send_message(embed=info("ไม่มีเพลงที่เล่นอยู่", ok=False), ephemeral=True)
        p.skip()
        await interaction.response.send_message(embed=info("⏭️ ข้ามแล้ว"))

    @app_commands.command(name="pause", description="หยุดชั่วคราว")
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction):
        p = self._player(interaction)
        if p and p.pause():
            return await interaction.response.send_message(embed=info("⏸️ หยุดชั่วคราว"))
        await interaction.response.send_message(embed=info("ไม่มีเพลงที่เล่นอยู่", ok=False), ephemeral=True)

    @app_commands.command(name="resume", description="เล่นต่อ")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction):
        p = self._player(interaction)
        if p and p.resume():
            return await interaction.response.send_message(embed=info("▶️ เล่นต่อแล้ว"))
        await interaction.response.send_message(embed=info("เพลงไม่ได้หยุดอยู่", ok=False), ephemeral=True)

    @app_commands.command(name="stop", description="หยุดและล้างคิว แล้วออกจากห้อง")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction):
        if not self._player(interaction) and not interaction.guild.voice_client:
            return await interaction.response.send_message(embed=info("ไม่ได้อยู่ในห้องเสียง", ok=False), ephemeral=True)
        await interaction.response.send_message(embed=info("⏹️ หยุดแล้ว ไปก่อนนะ 🐱"))
        await self.destroy_player(interaction.guild)

    @app_commands.command(name="queue", description="ดูคิวเพลง")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction):
        p = self._player(interaction)
        if not p or (not p.current and not p.queue):
            return await interaction.response.send_message(embed=info("คิวว่าง", ok=False), ephemeral=True)
        await interaction.response.send_message(embed=self.queue_embed(p))

    @app_commands.command(name="nowplaying", description="ดูเพลงที่กำลังเล่น")
    @app_commands.guild_only()
    async def nowplaying(self, interaction: discord.Interaction):
        p = self._player(interaction)
        if not p or not p.current:
            return await interaction.response.send_message(embed=info("ไม่มีเพลงที่เล่นอยู่", ok=False), ephemeral=True)
        await interaction.response.send_message(embed=self.now_playing_embed(p, p.current, live=True))

    @app_commands.command(name="loop", description="เปิด/ปิดวนซ้ำคิว")
    @app_commands.guild_only()
    async def loop(self, interaction: discord.Interaction):
        p = self._player(interaction)
        if not p:
            return await interaction.response.send_message(embed=info("ไม่มีเพลงที่เล่นอยู่", ok=False), ephemeral=True)
        p.loop = not p.loop
        await interaction.response.send_message(embed=info(f"🔁 วนซ้ำ: {'เปิด' if p.loop else 'ปิด'}"))

    # ----- ออกจากห้องถ้าไม่เหลือคน -----
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        vc = member.guild.voice_client
        if vc and vc.channel and not [m for m in vc.channel.members if not m.bot]:
            await self.destroy_player(member.guild)


# =====================================================================
#  ฟีเจอร์เดิมของน้องแมว  (แก้ข้อความ/เพิ่มบรรทัดได้ตามใจ)
# =====================================================================
FLIRT_LINES = [
    "ถ้าเธอเป็นแมว ฉันยอมเป็นทาสแมวทั้งชีวิตเลย 🐱",
    "เธอรู้ไหมว่าเธอเหมือนวายฟาย เพราะฉันรู้สึกถึงความเชื่อมต่อ 📶",
    "วันนี้ฝนไม่ตกแต่ฉันตกหลุมรักเธอแล้วนะ ☔",
    "เมี๊ยวววว~ เธอน่ารักจนฉันอยากเอาหัวไปถู 🐾",
    "เธอเป็นแบตเตอรี่หรือเปล่า ทำไมอยู่ใกล้แล้วฉันชาร์จเต็ม 🔋",
]


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context):
        await ctx.send(f"เมี๊ยว~ สวัสดี {ctx.author.mention} 🐱")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.send(f"🏓 Pong! {round(self.bot.latency * 1000)} ms")

    @commands.command(name="flirt")
    async def flirt(self, ctx: commands.Context):
        await ctx.send(random.choice(FLIRT_LINES))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.strip() == "สวัสดีแมว":
            await message.reply("เมี๊ยว~ สวัสดีจ้า 🐱")


# =====================================================================
#  ตัวบอท
# =====================================================================
class NongMoew(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # ต้องเปิดใน Developer Portal ด้วย
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.add_cog(Fun(self))
        await self.add_cog(Music(self))
        await self.tree.sync()

    async def on_ready(self) -> None:
        log.info("ออนไลน์แล้ว: %s", self.user)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("ไม่พบ DISCORD_TOKEN: ตั้งค่าใน env หรือไฟล์ .env ก่อนนะ")
    NongMoew().run(token, log_handler=None)


if __name__ == "__main__":
    main()
