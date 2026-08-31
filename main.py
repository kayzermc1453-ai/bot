from dotenv import load_dotenv
load_dotenv()
import os

print("DISCORD_TOKEN durumu:", "DOLU" if os.environ.get("DISCORD_TOKEN") else "BOŞ")

import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import deque
import json
import os
import re

# --- FLASK WEB SUNUCUSU ---
app = Flask('')

@app.route('/')
def home():
    return "MimarBOT 7/24 Aktif!"


def run_flask():
    app.run(host='0.0.0.0', port=5000)


def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()


# --- VERİ DOSYASI ---
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_PATH = DATA_DIR / "bot_data.json"
DATA_DIR.mkdir(exist_ok=True)


def default_data():
    return {
        "warns": {},
        "tickets": {},
        "join_history": [],
        "profanity_terms": [
            "amk", "aq", "sikerim", "sik", "salak", "orospu", "fahişe",
            "siktir", "piç", "kanka", "lan", "mal"
        ],
        "whitelist_domains": [
            "youtube.com", "youtu.be", "planetminecraft.com", "curseforge.com",
            "modrinth.com", "github.com", "pastebin.com"
        ],
        "server": {
            "mod_log_channel": "mod-log",
            "welcome_channel": "genel-sohbet",
            "suggestion_channel": "öneriler",
            "ticket_category": "Destek",
            "permission_setup_done": False
        }
    }


def load_data():
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps(default_data(), ensure_ascii=False, indent=2), encoding='utf-8')

    with DATA_PATH.open('r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = default_data()
            DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    if isinstance(data, dict):
        if 'verification' in data:
            del data['verification']
        server_data = data.get('server')
        if isinstance(server_data, dict) and 'verification_channel' in server_data:
            del server_data['verification_channel']
        if data != json.loads(DATA_PATH.read_text(encoding='utf-8')):
            save_data(data)

    return data


def save_data(data):
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# --- YARDIMCI FONKSİYONLAR ---
def find_role(guild, role_name):
    return discord.utils.get(guild.roles, name=role_name)


def find_channel(guild, channel_name):
    return discord.utils.get(guild.text_channels, name=channel_name)


async def log_action(guild, title, message, color=discord.Color.blurple()):
    data = load_data()
    channel_name = data["server"].get("mod_log_channel", "mod-log")
    channel = find_channel(guild, channel_name)
    if channel is None:
        return
    embed = discord.Embed(title=title, description=message, color=color, timestamp=datetime.now(timezone.utc))
    await channel.send(embed=embed)


async def ensure_server_setup(guild):
    data = load_data()
    created = []
    skipped = []

    existing_channel_names = {channel.name for channel in guild.channels}
    existing_category_names = {category.name for category in guild.categories}

    category_names = {
        "Bilgilendirme": ["kurallar", "duyurular", "güncellemeler", "rol-al"],
        "Sohbet": ["genel-sohbet", "minecraft-sohbet", "off-topic", "bot-komutları"],
        "Build": ["build-showcase", "yapım-aşamasında", "geri-bildirim", "yarışmalar"],
        "Destek": ["ticket-oluştur", "başvurular", "öneriler"],
        "Yetkili": ["mod-log", "mod-sohbet", "ban-listesi"]
    }

    for category_name, channel_names in category_names.items():
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            if category_name not in existing_category_names:
                category = await guild.create_category(category_name)
                created.append(f'Kategori: {category_name}')
                existing_category_names.add(category_name)
            else:
                skipped.append(f'Kategori: {category_name} (zaten var, atlandı)')
                continue

        for channel_name in channel_names:
            if channel_name in existing_channel_names:
                skipped.append(f'Kanal: {channel_name} (zaten var, atlandı)')
                continue

            if category is not None:
                try:
                    await category.create_text_channel(channel_name)
                    created.append(f'Kanal: {channel_name}')
                    existing_channel_names.add(channel_name)
                except discord.HTTPException:
                    skipped.append(f'Kanal: {channel_name} (oluşturulamadı)')

    for field_name, default_name in {
        'welcome_channel': 'genel-sohbet',
        'suggestion_channel': 'öneriler',
        'mod_log_channel': 'mod-log'
    }.items():
        target_name = data["server"].get(field_name, default_name)
        if target_name in existing_channel_names:
            skipped.append(f'Kanal: {target_name} (zaten var, atlandı)')
        else:
            await guild.create_text_channel(target_name)
            created.append(f'Kanal: {target_name}')
            existing_channel_names.add(target_name)

    return created, skipped


# --- DISCORD BOT AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.spam_cache = {}


@bot.event
async def on_ready():
    print(f'{bot.user.name} olarak giriş yapıldı! Bot aktif.')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='TBT sunucusu'))


@bot.event
async def on_member_join(member):
    guild = member.guild
    data = load_data()
    now = datetime.now(timezone.utc)
    recent = [stamp for stamp in data['join_history'] if (now - datetime.fromisoformat(stamp)).total_seconds() < 180]
    recent.append(now.isoformat())
    data['join_history'] = recent[-30:]
    save_data(data)

    if len(recent) >= 5:
        await log_action(guild, 'Anti-raid', f'{member.mention} şüpheli katılım nedeniyle kontrol altına alındı.', discord.Color.orange())
        try:
            await member.send('Sunucuya çok kısa sürede çok sayıda katılım tespit edildiği için geçici kontrol altında tutuluyorsunuz.')
        except discord.Forbidden:
            pass
        return

    if member.created_at > datetime.now(timezone.utc) - timedelta(days=7):
        await log_action(guild, 'Hesap yaşı kontrolü', f'{member.mention} yeni açılmış hesap nedeniyle kontrol altında tutuluyor.', discord.Color.orange())
        try:
            await member.send('Hesabınız çok yeni olduğu için yönetici kontrolünde. Yetkililere başvurabilirsiniz.')
        except discord.Forbidden:
            pass
        return

    welcome_channel = find_channel(guild, data['server'].get('welcome_channel', 'genel-sohbet'))
    if welcome_channel:
        await welcome_channel.send(f'🎉 **{member.mention} sunucuya katıldı, hoş geldin!** 🎉')


@bot.event
async def on_member_remove(member):
    await log_action(member.guild, 'Üye ayrıldı', f'{member.mention} sunucudan ayrıldı. Hesap: `{member.created_at.strftime("%d.%m.%Y")}`', discord.Color.red())


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    guild = message.guild
    data = load_data()
    content = message.content.lower()

    now_ts = datetime.now(timezone.utc).timestamp()
    user_key = str(message.author.id)
    bucket = bot.spam_cache.setdefault(user_key, deque(maxlen=6))
    bucket.append(now_ts)
    if len(bucket) >= 5 and bucket[-1] - bucket[0] < 10:
        await message.delete()
        await log_action(guild, 'Anti-spam', f'{message.author.mention} hızlı spam nedeniyle kontrol altına alındı.', discord.Color.dark_orange())
        return

    allowed_roles = ['Master Architect', 'Realm Guardian', 'Grand Master']
    has_privilege = any(role.name in allowed_roles for role in message.author.roles)

    if re.search(r'(discord\.gg|discordapp\.com/invite|discord\.com/invite)', content, re.IGNORECASE):
        if not has_privilege:
            allowed_domains = data.get('whitelist_domains', default_data()['whitelist_domains'])
            if not any(domain in content for domain in allowed_domains):
                await message.delete()
                await log_action(guild, 'Davet linki engellendi', f'{message.author.mention} yetkisiz davet linki gönderdi.', discord.Color.orange())
                return

    profanity_terms = data.get('profanity_terms', default_data()['profanity_terms'])
    if any(term in content for term in profanity_terms):
        if not has_privilege:
            await message.delete()
            await log_action(guild, 'Küfür filtresi', f'{message.author.mention} küfür/argo içeren mesaj gönderdi.', discord.Color.dark_red())
            return


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    await log_action(before.guild, 'Mesaj düzenlendi', f'{before.author.mention} mesajını düzenledi:\n{before.content[:300]} → {after.content[:300]}', discord.Color.blue())


@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    await log_action(message.guild, 'Mesaj silindi', f'{message.author.mention} mesaj sildi:\n{message.content[:300]}', discord.Color.dark_red())


@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong! 🏓')


@bot.command(name='yardım')
async def yardim(ctx):
    commands_list = [
        '!ping', '!uyarı @üye sebep', '!uyarılar @üye', '!mute @üye sebep', '!unmute @üye',
        '!kick @üye sebep', '!ban @üye sebep', '!unban kullanıcıadı', '!banlist', '!temizle 20',
        '!rol-al Java', '!öneri örnek öneri', '!ticket', '!ticket-kapat', '!sunucu_kur', '!warn @üye sebep', '!warnings @üye'
    ]
    await ctx.send('Kullanılabilir komutlar:\n' + '\n'.join(commands_list))


@bot.command(name='sunucu_kur')
@commands.is_owner()
async def sunucu_kur(ctx):
    created, skipped = await ensure_server_setup(ctx.guild)

    lines = []
    if created:
        lines.append('Oluşturulanlar:')
        lines.extend(f'- {item}' for item in created)
    else:
        lines.append('Oluşturulan yok.')

    if skipped:
        lines.append('')
        lines.append('Zaten var, atlananlar:')
        lines.extend(f'- {item}' for item in skipped)

    await ctx.reply('\n'.join(lines))


@bot.command(name='izin_raporu')
@commands.is_owner()
async def izin_raporu(ctx):
    chunks = []
    current = ['Rol izin raporu:']
    current_length = len(current[0])

    for role in sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True):
        permissions = role.permissions
        row = (
            f'Rol: {role.name} | view_channel: {permissions.view_channel} | send_messages: {permissions.send_messages} | '
            f'mention_everyone: {permissions.mention_everyone} | kick_members: {permissions.kick_members} | '
            f'ban_members: {permissions.ban_members} | manage_channels: {permissions.manage_channels} | '
            f'manage_roles: {permissions.manage_roles} | manage_messages: {permissions.manage_messages} | '
            f'administrator: {permissions.administrator}'
        )

        if current_length + len(row) + 1 > 1900:
            chunks.append('\n'.join(current))
            current = [row]
            current_length = len(row)
        else:
            current.append(row)
            current_length += len(row) + 1

    if current:
        chunks.append('\n'.join(current))

    for index, chunk in enumerate(chunks, start=1):
        await ctx.send(f'```\n{chunk}\n```' if index == 1 else f'```\n{chunk}\n```')


@bot.command(name='uyarı')
@commands.has_permissions(kick_members=True)
async def uyari(ctx, member: discord.Member, *, reason='Sebep belirtilmedi'):
    data = load_data()
    guild_id = str(ctx.guild.id)
    member_id = str(member.id)
    warns = data['warns'].setdefault(guild_id, {})
    user_warns = warns.setdefault(member_id, [])
    user_warns.append({'reason': reason, 'moderator': str(ctx.author.id), 'time': datetime.now(timezone.utc).isoformat()})
    save_data(data)

    await ctx.reply(f'{member.mention} üyesine uyarı verildi. Toplam uyarı: {len(user_warns)}')
    await log_action(ctx.guild, 'Uyarı verildi', f'{ctx.author.mention}, {member.mention} kullanıcısına "{reason}" sebebiyle uyarı verdi.', discord.Color.yellow())

    if len(user_warns) >= 3:
        timeout_until = discord.utils.utcnow() + timedelta(minutes=10)
        await member.timeout(timeout_until, reason='Üç uyarı sınırı aşıldı')
        await log_action(ctx.guild, 'Otomatik mute', f'{member.mention} üç uyarı nedeniyle otomatik timeout aldı.', discord.Color.dark_orange())


@bot.command(name='uyarılar')
@commands.has_permissions(kick_members=True)
async def uyari_list(ctx, member: discord.Member):
    data = load_data()
    warns = data['warns'].get(str(ctx.guild.id), {}).get(str(member.id), [])
    if not warns:
        await ctx.send(f'{member.mention} üyesinin kaydedilmiş uyarısı yok.')
        return

    lines = [f'{idx + 1}. {warn["reason"]} ({warn["time"]})' for idx, warn in enumerate(warns)]
    await ctx.send(f'{member.mention} uyarıları:\n' + '\n'.join(lines))


@bot.command(name='mute')
@commands.has_permissions(kick_members=True)
async def mute(ctx, member: discord.Member, *, reason='Sebep belirtilmedi'):
    timeout_until = discord.utils.utcnow() + timedelta(minutes=10)
    await member.timeout(timeout_until, reason=reason)
    await ctx.reply(f'{member.mention} susturuldu. Sebep: {reason}')
    await log_action(ctx.guild, 'Mute', f'{ctx.author.mention}, {member.mention} kullanıcısını "{reason}" sebebiyle timeoutladı.', discord.Color.dark_orange())


@bot.command(name='unmute')
@commands.has_permissions(kick_members=True)
async def unmute(ctx, member: discord.Member):
    if member.is_timed_out():
        await member.remove_timeout(reason='Mute kaldırıldı')
        await ctx.reply(f'{member.mention} susturması kaldırıldı.')
        await log_action(ctx.guild, 'Unmute', f'{ctx.author.mention}, {member.mention} kullanıcısının timeoutını kaldırdı.', discord.Color.green())
    else:
        await ctx.reply(f'{member.mention} üyesi zaten susturulmamış.')


@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason='Sebep belirtilmedi'):
    await member.kick(reason=reason)
    await ctx.reply(f'{member.mention} sunucudan atıldı. Sebep: {reason}')
    await log_action(ctx.guild, 'Kick', f'{ctx.author.mention}, {member.mention} kullanıcısını "{reason}" sebebiyle attı.', discord.Color.dark_blue())


@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason='Sebep belirtilmedi'):
    await member.ban(reason=reason)
    await ctx.reply(f'{member.mention} banlandı. Sebep: {reason}')
    await log_action(ctx.guild, 'Ban', f'{ctx.author.mention}, {member.mention} kullanıcısını "{reason}" sebebiyle banladı.', discord.Color.dark_red())


@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, username: str):
    bans = [entry async for entry in ctx.guild.bans()]
    user = discord.utils.find(lambda u: username.lower() in str(u).lower(), bans)
    if user is None:
        await ctx.reply('Ban listesinde böyle bir kullanıcı bulunamadı.')
        return
    await ctx.guild.unban(user.user, reason='Unban komutu ile kaldırıldı')
    await ctx.reply(f'{user.user} banı kaldırıldı.')
    await log_action(ctx.guild, 'Unban', f'{ctx.author.mention}, {user.user} kullanıcısının banını kaldırdı.', discord.Color.green())


@bot.command(name='banlist')
@commands.has_permissions(ban_members=True)
async def banlist(ctx):
    bans = [entry async for entry in ctx.guild.bans()]
    if not bans:
        await ctx.send('Ban listesi boş.')
        return
    content = '\n'.join(f'{idx + 1}. {entry.user} - {entry.reason or "Sebep yok"}' for idx, entry in enumerate(bans))
    await ctx.send(f'Ban listesi:\n{content}')


@bot.command(name='temizle')
@commands.has_permissions(manage_messages=True)
async def temizle(ctx, sayi: int):
    if sayi < 1:
        await ctx.reply('1 ile 100 arası bir sayı gir.')
        return
    deleted = await ctx.channel.purge(limit=sayi)
    await ctx.send(f'{len(deleted)} adet mesaj silindi.', delete_after=3)


@bot.command(name='rol-al')
async def rol_al(ctx, *, role_name: str):
    allowed_roles = ['Java', 'Bedrock', 'Redstone', 'Yapı Tasarımı', 'Texture Art', 'Survival', 'Creative']
    role_name = role_name.strip()
    if role_name.lower() not in [r.lower() for r in allowed_roles]:
        await ctx.reply('Kullanılabilir roller: ' + ', '.join(allowed_roles))
        return

    role = find_role(ctx.guild, role_name)
    if role is None:
        role = await ctx.guild.create_role(name=role_name)

    member = ctx.author
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.reply(f'{role.name} rolü alındı.')
    else:
        await member.add_roles(role)
        await ctx.reply(f'{role.name} rolü verildi.')


@bot.command(name='öneri')
async def oneri(ctx, *, text: str):
    suggestion_channel = find_channel(ctx.guild, 'öneriler')
    if suggestion_channel is None:
        suggestion_channel = await ctx.guild.create_text_channel('öneriler')

    embed = discord.Embed(title='Yeni öneri', description=text, color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=f'Öneren: {ctx.author.display_name}')
    message = await suggestion_channel.send(embed=embed)
    await message.add_reaction('👍')
    await message.add_reaction('👎')
    await ctx.reply(f'Önerin {suggestion_channel.mention} kanalına iletildi.')


@bot.command(name='ticket')
async def ticket(ctx):
    data = load_data()
    category_name = data['server'].get('ticket_category', 'Destek')
    category = discord.utils.get(ctx.guild.categories, name=category_name)
    if category is None:
        category = await ctx.guild.create_category(category_name)

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        find_role(ctx.guild, 'Master Architect'): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        find_role(ctx.guild, 'Realm Guardian'): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        find_role(ctx.guild, 'Grand Master'): discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }

    channel = await ctx.guild.create_text_channel(f'ticket-{ctx.author.name}', category=category, overwrites=overwrites)
    await channel.send(f'{ctx.author.mention}, destek talebin açıldı. Şikayet, başvuru veya teknik destek için burada yazabilirsin.')
    data['tickets'][str(channel.id)] = ctx.author.id
    save_data(data)
    await ctx.reply(f'Ticket kanalın hazır: {channel.mention}')


@bot.command(name='ticket-kapat')
@commands.has_permissions(manage_channels=True)
async def ticket_kapat(ctx):
    if not ctx.channel.name.startswith('ticket-'):
        await ctx.reply('Bu komut sadece ticket kanallarında kullanılabilir.')
        return
    await ctx.reply('Ticket kapatılıyor...')
    await ctx.channel.delete()


@bot.command(name='warn')
@commands.has_permissions(kick_members=True)
async def warn_alias(ctx, member: discord.Member, *, reason='Sebep belirtilmedi'):
    await uyari(ctx, member, reason=reason)


@bot.command(name='warnings')
@commands.has_permissions(kick_members=True)
async def warnings_alias(ctx, member: discord.Member):
    await uyari_list(ctx, member)


@bot.command(name='yetki_ayarla')
@commands.is_owner()
async def yetki_ayarla(ctx):
    guild = ctx.guild
    data = load_data()
    if data.get('server', {}).get('permission_setup_done'):
        await ctx.reply('Bu yetki düzenlemesi zaten çalıştırıldı; tekrar çalıştırmak için sunucu sahibine özel tek seferlik ayar kilitlidir.')
        return

    summary = []
    role_permissions = {
        'Realm Guardian': {'moderate_members': True, 'manage_messages': True, 'kick_members': False, 'ban_members': False},
        'Structural Engineer': {'moderate_members': False, 'manage_messages': False, 'kick_members': False, 'ban_members': False},
        'Grand Master': {'moderate_members': False, 'manage_messages': False, 'kick_members': False, 'ban_members': False},
    }

    for role_name in ['Realm Guardian', 'Structural Engineer', 'Grand Master']:
        role = find_role(guild, role_name)
        if role is None:
            role = await guild.create_role(name=role_name)
            summary.append(f'- Rol oluşturuldu: {role_name}')

        perms = role_permissions[role_name]
        new_permissions = discord.Permissions(role.permissions.value)
        new_permissions.update(
            moderate_members=perms['moderate_members'],
            manage_messages=perms['manage_messages'],
            kick_members=perms['kick_members'],
            ban_members=perms['ban_members'],
        )
        await role.edit(
            reason='Tek seferlik yetki ayarı',
            permissions=new_permissions,
        )
        summary.append(
            f'- {role_name}: moderate_members={perms["moderate_members"]}, manage_messages={perms["manage_messages"]}, '
            f'kick_members={perms["kick_members"]}, ban_members={perms["ban_members"]}'
        )

    channel = find_channel(guild, 'genel-sohbet')
    if channel is None:
        await ctx.reply('`genel-sohbet` kanalı bulunamadı. Bu komut başka kanala dokunmadı.')
        return

    await channel.set_permissions(guild.default_role, attach_files=False, embed_links=False)
    summary.append('- @everyone: genel-sohbet kanalında attach_files=False, embed_links=False')

    for role_name in ['Realm Guardian', 'Structural Engineer', 'Grand Master']:
        role = find_role(guild, role_name)
        if role is not None:
            await channel.set_permissions(role, attach_files=True, embed_links=True)
            summary.append(f'- {role_name}: genel-sohbet kanalında attach_files=True, embed_links=True')

    data['server']['permission_setup_done'] = True
    save_data(data)

    await ctx.reply('```\n' + '\n'.join(summary) + '\n```')


# --- BOTU BAŞLATMA ---
if __name__ == '__main__':
    keep_alive()

    TOKEN = os.environ.get('DISCORD_TOKEN')
    if not TOKEN:
        raise RuntimeError('DISCORD_TOKEN ortam değişkeni tanımlı değil. Botu çalıştırmadan önce ortam değişkenini ayarla.')

    bot.run(TOKEN)
