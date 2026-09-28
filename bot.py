import discord
from discord.ext import commands
import random
import os
import sys
import yt_dlp
import asyncio

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# ตั้งค่าตัวเลือกสำหรับดึงเสียงจาก YouTube
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'extractaudio': True,
    'audioformat': 'mp3',
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
# ระบบรับข้อความทั่วไป (คีย์เวิร์ด)
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

    mes = message.content.lower()

    if "สวัสดีน้องแมว" in mes or "หวัดดีจ้า" in mes:
        async with message.channel.typing():
            await message.channel.send(f"สวัสดีครับคุณ {message.author.mention} มีอะไรให้น้องแมวกินมั้ย")
            return
    elif "น้องแมว" in mes:
        async with message.channel.typing():
            await message.channel.send("เรียกน้องแมวมีอะไรเหรอครับ หรือว่าคิดถึงผมซะแล้ว 🐾")
            return

    if "เหงา" in mes or "เหงาอะ" in mes:
        alone_text = random.choice([
            "มีน้องแมวอยู่เป็นเพื่อนทั้งคน ไม่ต้องเหงาแล้วนะคับ",
            "คุยกับน้องแมวได้นะ คนดี" ,
            "บ่นให้น้องแมวฟังได้นะ น้องเกิดที่ไทยมีบัตรแมว"
        ])
        async with message.channel.typing():
            await message.channel.send(f"{alone_text} {message.author.mention}")
            return
    elif "จีบหน่อย" in mes or "หยอดหน่อย" in mes:
        flirt_text = random.choice([
            "ถึงตัวจะเป็นแมว แต่หัวใจมีแต่เธอนะคั้บ",
            "เป็นคนชอบแมวป่าวครับ... ถ้าชอบ ลองมาเป็นทาสรักเราดูสิ รับรองดูแลดีแน่นอน",
            "อากาศหนาวให้ห่มผ้า แต่อยากอบอุ่นกว่า... ให้มาซบไหล่เรานะฮะ"
        ])
        async with message.channel.typing():
            await message.channel.send(f"{message.author.mention} {flirt_text}")
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
        
    await bot.process_commands(message)


# ==========================================
# ระบบจัดการคิวเพลง, Autoplay และ Loop
# ==========================================
music_queues = {}
current_playing = {}     # เก็บข้อมูลเพลงปัจจุบันของแต่ละเซิร์ฟเวอร์ไว้ทำ Loop {(url, title, requester)}
loop_statuses = {}       # สถานะ Loop (True/False)
autoplay_statuses = {}   # สถานะ Autoplay (True/False)

def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = []
    return music_queues[guild_id]

async def play_next(interaction: discord.Interaction):
    global current_playing, loop_statuses, autoplay_statuses
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)
    
    # 1. เช็คว่าเปิด Loop เพลงปัจจุบันอยู่หรือไม่
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
            
            embed = discord.Embed(
                title="🔂 กำลังเล่นซ้ำเพลงเดิม (Loop)",
                description=f"**[{title}]({url})**",
                color=discord.Color.from_rgb(255, 215, 0)
            )
            await interaction.channel.send(embed=embed)
            return
        except Exception as e:
            print(f"Loop error: {e}")

    # 2. ถ้ามีเพลงในคิวปกติ
    if len(queue) > 0:
        url, title, requester = queue.pop(0)
        current_playing[guild_id] = (url, title, requester)
        
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
        # 3. ระบบ Autoplay (หาเพลงแนวใหม่ที่หลากหลายขึ้น ไม่วนซ้ำเพลงเดิม)
        is_autoplay_enabled = autoplay_statuses.get(guild_id, False)

        if is_autoplay_enabled and guild_id in current_playing and interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
            _, last_title, _ = current_playing[guild_id]
            # ใช้การค้นหาแบบสุ่มคำค้นหาเสริม เพื่อให้ได้เพลงใหม่ๆ ที่อยู่ในแนวใกล้เคียงกัน ไม่วนซ้ำเพลงเดิมเป๊ะๆ
            keywords = ["mix", "playlist", "remix", "live", "audio"]
            random_keyword = random.choice(keywords)
            search_query = f"ytsearch5:{last_title} {random_keyword}"
            
            try:
                ytdl_search = yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True})
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl_search.extract_info(search_query, download=False))
                
                if 'entries' in data and len(data['entries']) > 0:
                    # สุ่มเลือก 1 เพลงจากผลการค้นหา Top 5 เพื่อไม่ให้ซ้ำเพลงเดิม
                    auto_data = random.choice(data['entries'])
                    auto_url = auto_data['url']
                    auto_title = auto_data.get('title', 'Recommended Song')
                    
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
                        title="✨ [Autoplay] สุ่มเพลงแนวใกล้เคียงมาเปิดต่อให้",
                        description=f"**[{auto_title}]({auto_url})**",
                        color=discord.Color.from_rgb(152, 251, 152)
                    )
                    embed.set_footer(text="ระบบสุ่มเพลงใหม่ต่อเนื่องอัตโนมัติ 🐾")
                    await interaction.channel.send(embed=embed)
                    return
            except Exception as e:
                print(f"Autoplay search error: {e}")

        # ถ้าคิวหมดและไม่ได้เปิด Autoplay ให้รอ 10 วินาทีก่อนออกจากห้อง
        if interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
            await interaction.channel.send("💤 เพลงหมดคิวแล้ว... น้องแมวจะออกจากห้องใน 10 วินาทีนะงับ 🐾")
            await asyncio.sleep(10)
            if interaction.guild.voice_client and not interaction.guild.voice_client.is_playing() and len(get_queue(guild_id)) == 0:
                await interaction.guild.voice_client.disconnect()


# ==========================================
# Slash Commands ทั้งหมดรวมไว้ที่เดียว
# ==========================================

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

@bot.tree.command(name="autoplay", description="เปิดหรือปิดระบบสุ่มเพลงแนวเดียวกันต่อให้อัตโนมัติ")
@discord.app_commands.choices(status=[
    discord.app_commands.Choice(name="เปิด Autoplay", value="on"),
    discord.app_commands.Choice(name="ปิด Autoplay", value="off")
])
async def slash_autoplay(interaction: discord.Interaction, status: str):
    global autoplay_statuses
    guild_id = interaction.guild.id

    if status == "on":
        autoplay_statuses[guild_id] = True
        await interaction.response.send_message("✨ เปิดระบบ **Autoplay** เรียบร้อยแล้วงับ! เมื่อคิวหมด บอทจะสุ่มเพลงแนวใกล้เคียงมาเปิดต่อให้เรื่อยๆ 🎶", ephemeral=True)
    else:
        autoplay_statuses[guild_id] = False
        await interaction.response.send_message("💤 ปิดระบบ **Autoplay** แล้วงับ เมื่อคิวหมดบอทรอ 10 วิแล้วจะออกห้อง", ephemeral=True)

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

@bot.tree.command(name="play", description="สั่งเล่นเพลงหรือเพิ่มเข้าคิวจากลิงก์ YouTube")
async def slash_play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    try:
        if not interaction.user.voice:
            await interaction.followup.send("❌ คุณต้องเข้าห้อง Voice Channel ก่อนสั่งเพลงนะคับ!")
            return

        if not interaction.guild.voice_client:
            channel = interaction.user.voice.channel
            await channel.connect()

        ytdl_temp = yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True})
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl_temp.extract_info(url, download=False))
        title = data.get('title', 'Unknown Title')

        guild_id = interaction.guild.id
        queue = get_queue(guild_id)

        if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused():
            queue.append((url, title, interaction.user))
            embed = discord.Embed(
                title="📥 เพิ่มเพลงลงในคิวแล้ว",
                description=f"**[{title}]({url})**",
                color=discord.Color.from_rgb(255, 160, 122)
            )
            embed.add_field(name="📌 ลำดับคิวที่", value=f"#{len(queue)}", inline=True)
            embed.add_field(name="🎧 ผู้ขอเพิ่ม", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=embed)
        else:
            current_playing[guild_id] = (url, title, interaction.user)
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

            embed = discord.Embed(
                title="🎵 กำลังเล่นเพลง",
                description=f"**[{title}]({url})**",
                color=discord.Color.from_rgb(255, 182, 193)
            )
            embed.add_field(name="🎧 ผู้ขอเพลง", value=interaction.user.mention, inline=True)
            await interaction.followup.send(embed=embed)

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
    for i, item in enumerate(queue, 1):
        url, title, user = item
        description += f"**{i}.** [{title}]({url}) (ขอโดย: {user.mention})\n"

    embed = discord.Embed(
        title="🎶 รายการคิวเพลงทั้งหมด",
        description=description,
        color=discord.Color.from_rgb(135, 206, 250)
    )
    embed.set_footer(text=f"จำนวนเพลงในคิวทั้งหมด: {len(queue)} เพลง")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="skip", description="ข้ามเพลงที่กำลังเล่นอยู่ไปเพลงถัดไป")
async def slash_skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ ข้ามเพลงเรียบร้อยแล้วงับ!")
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


# ==========================================
# รันบอทผ่าน Environment Variable
# ==========================================
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    sys.exit("ไม่พบ DISCORD_BOT_TOKEN กรุณาตั้งค่าตัวแปรใน PowerShell ก่อนรันครับ!")

bot.run(token)