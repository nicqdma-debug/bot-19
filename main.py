import os
import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from dotenv import load_dotenv
import datetime
import io

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

def get_id(key):
    val = os.getenv(key)
    if not val:
        raise ValueError(f"Mancante {key} nel file .env")
    return int(val)

# ID Categorie
CAT_BRACCIO_ID = get_id("TICKET_CATEGORY_BRACCIO")
CAT_INFO_ID    = get_id("TICKET_CATEGORY_INFORMATIVA")

# ID Ruoli Braccio Armato (Capo, Vice Capo) - Chi può chiudere
ROLE_BRACCIO_1 = get_id("ROLE_BRACCIO_1") # 1518931117670006914
ROLE_BRACCIO_2 = get_id("ROLE_BRACCIO_2") # 1518931069485711492

# ID Ruoli Informativa (Gestore, Vice Gestore) - Chi può chiudere
ROLE_INFO_1    = get_id("ROLE_INFO_1")    # 1518931554397585418
ROLE_INFO_2    = get_id("ROLE_INFO_2")    # 1518934838642741301

# Canale Log Transcript
LOG_CHANNEL_ID = get_id("LOG_CHANNEL_ID") # 1520748062455238827

BANNER_URL = os.getenv("BANNER_URL")
LOGO_URL   = os.getenv("LOGO_URL")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
#  SELECT MENU
# ────────────────────────────────────────────

class TicketTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Braccio Armato",
                value="braccio",
                description="Entra nel team per sparare",
                emoji=None
            ),
            discord.SelectOption(
                label="Informativa",
                value="informativa",
                description="Entra nel team Informativa",
                emoji=None
            ),
        ]
        super().__init__(
            placeholder="Service Center -- Seleziona categoria",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_selector_main",
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        guild  = interaction.guild
        member = interaction.user

        await interaction.response.defer(ephemeral=True)

        category_id = None
        channel_prefix = ""
        roles_to_ping_ids = []
        roles_view_ids = [] 
        welcome_title = ""
        welcome_desc = ""
        color = 0x000000

        if ticket_type == "braccio":
            category_id = CAT_BRACCIO_ID
            channel_prefix = "braccio"
            roles_to_ping_ids = [ROLE_BRACCIO_1, ROLE_BRACCIO_2]
            roles_view_ids = [ROLE_BRACCIO_1, ROLE_BRACCIO_2]
            color = 0xff4500
            
            pings_text = " ".join([f"<@&{r}>" for r in roles_to_ping_ids])
            welcome_title = "TICKET BRACCIO ARMATO"
            welcome_desc = (
                f"{member.mention} Benvenuto nel tuo ticket Braccio Armato\n\n"
                f"Aspetta uno dei seguenti tag: {pings_text}.\n\n"
                "Nel frattempo:\n"
                "- Manda le tue clip o il tuo montage.\n"
                "- Specifica la tua esperienza nel ruolo.\n"
                "- Sii paziente e rispettoso."
            )

        elif ticket_type == "informativa":
            category_id = CAT_INFO_ID
            channel_prefix = "informativa"
            roles_to_ping_ids = [ROLE_INFO_1, ROLE_INFO_2]
            roles_view_ids = [ROLE_INFO_1, ROLE_INFO_2]
            color = 0x3498db
            
            pings_text = " ".join([f"<@&{r}>" for r in roles_to_ping_ids])
            welcome_title = "TICKET INFORMATIVA"
            welcome_desc = (
                f"{member.mention} Benvenuto nel tuo ticket Informativa\n\n"
                f"Aspetta uno dei seguenti tag: {pings_text}.\n\n"
                "Nel frattempo spiega:\n"
                "- Perché vuoi entrare nel team Informativa.\n"
                "- Le tue tecniche per raccogliere informazioni.\n"
                "- Le tue esperienze roleplay."
            )

        if not category_id:
            return await interaction.followup.send("Errore di configurazione.", ephemeral=True)

        category = guild.get_channel(category_id)
        if not category:
            return await interaction.followup.send("Categoria non trovata.", ephemeral=True)

        existing = discord.utils.get(category.text_channels, name=f"{channel_prefix}-{member.name}")
        if existing:
            return await interaction.followup.send(f"Hai già un ticket aperto: {existing.mention}", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        
        for role_id in roles_view_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )

        try:
            channel = await guild.create_text_channel(
                name=f"{channel_prefix}-{member.name}",
                overwrites=overwrites,
                category=category,
            )

            embed_welcome = discord.Embed(
                title=welcome_title,
                description=welcome_desc,
                color=color,
                timestamp=discord.utils.utcnow(),
            )
            if LOGO_URL:
                embed_welcome.set_thumbnail(url=LOGO_URL)
            embed_welcome.set_footer(text="!19 Service Center")

            close_view = CloseTicketView(ticket_type=ticket_type)
            await channel.send(embed=embed_welcome, view=close_view)

            await interaction.followup.send(f"Ticket creato: {channel.mention}", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("Errore permessi creazione canale.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Errore interno: {e}", ephemeral=True)


class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


# ────────────────────────────────────────────
#  PULSANTE CHIUDI TICKET CON CONTROLLI RUOLI
# ────────────────────────────────────────────

class CloseTicketView(View):
    def __init__(self, ticket_type):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type

    @discord.ui.button(label="CHIUDI TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        
        allowed_roles = []
        if self.ticket_type == "braccio":
            allowed_roles = [ROLE_BRACCIO_1, ROLE_BRACCIO_2]
        else:
            allowed_roles = [ROLE_INFO_1, ROLE_INFO_2]
        
        has_permission = any(role.id in allowed_roles for role in user.roles)
        
        if not has_permission and not user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "Non hai i permessi per chiudere questo ticket. Solo lo staff autorizzato può farlo.", 
                ephemeral=True
            )

        await interaction.response.send_message("Generazione transcript e chiusura in corso...", ephemeral=True)
        
        try:
            transcript_html = await generate_transcript(interaction.channel)
            
            log_channel = guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                file = discord.File(io.BytesIO(transcript_html.encode('utf-8')), filename=f"transcript-{interaction.channel.name}.html")
                embed_log = discord.Embed(
                    title=f"Transcript Chiuso: {interaction.channel.name}",
                    description=f"Ticket chiuso da {user.mention}\nTipo: **{self.ticket_type.capitalize()}**",
                    color=0xff4500 if self.ticket_type == "braccio" else 0x3498db,
                    timestamp=discord.utils.utcnow()
                )
                embed_log.add_field(name="Utente Ticket", value=interaction.channel.name.replace(f"{self.ticket_type}-", ""), inline=True)
                await log_channel.send(embed=embed_log, file=file)
            
            await interaction.channel.delete()
            
        except Exception as e:
            await interaction.followup.send(f"Errore durante la chiusura: {e}", ephemeral=True)

# ────────────────────────────────────────────
#  GENERATORE TRANSCRIPT HTML
# ────────────────────────────────────────────

async def generate_transcript(channel):
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        attachments_list = []
        if message.attachments:
            for att in message.attachments:
                attachments_list.append(f'<a href="{att.url}" target="_blank" style="color:#ff4500; text-decoration:none;">[Allegato: {att.filename}]</a>')
        
        content = message.content.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        if not content and not attachments_list:
            content = "<i>(Nessun contenuto)</i>"
        
        attachments_html = " ".join(attachments_list)
        
        time_str = message.created_at.strftime("%d/%m/%Y %H:%M")
        
        messages.append(f"""
        <div class="message">
            <div class="avatar"></div>
            <div class="content">
                <div class="header">
                    <span class="username" style="color:{message.author.color if message.author.color.value != 0 else '#ffffff'}">{message.author.display_name}</span>
                    <span class="timestamp">{time_str}</span>
                </div>
                <div class="text">{content}</div>
                {f'<div class="attachments">{attachments_html}</div>' if attachments_html else ''}
            </div>
        </div>
        """)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Transcript: {channel.name}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #36393f; color: #dcddde; margin: 0; padding: 20px; }}
            .container {{ max-width: 900px; margin: 0 auto; background-color: #2f3136; padding: 20px; border-radius: 5px; }}
            .header {{ text-align: center; border-bottom: 2px solid #ff4500; padding-bottom: 20px; margin-bottom: 20px; }}
            .header h1 {{ color: #fff; margin: 0; }}
            .message {{ display: flex; margin-bottom: 15px; padding: 10px; border-radius: 5px; background-color: #40444b; }}
            .avatar {{ width: 40px; height: 40px; border-radius: 50%; background-color: #72767d; margin-right: 15px; flex-shrink: 0; }}
            .content {{ flex: 1; }}
            .header {{ display: flex; align-items: baseline; margin-bottom: 5px; }}
            .username {{ font-weight: bold; margin-right: 10px; }}
            .timestamp {{ font-size: 0.75rem; color: #72767d; }}
            .text {{ word-wrap: break-word; line-height: 1.4; }}
            .attachments {{ margin-top: 5px; font-size: 0.9rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Transcript Ticket: {channel.name}</h1>
                <p>Generato automaticamente da !19 Bot</p>
            </div>
            {''.join(messages)}
        </div>
    </body>
    </html>
    """
    return html_content


# ─────────────────────────────────────────────
#  EVENTI BOT
# ───────────────────────────────────────────

@bot.event
async def on_ready():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" !19 Service Bot — Online")
    print(f" Loggato come: {bot.user}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    bot.add_view(TicketPanelView())
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f" Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f" Errore sincronizzazione: {e}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


# ────────────────────────────────────────────
#  COMANDI SLASH
# ────────────────────────────────────────────

@bot.tree.command(name="ticket", description="Apri il pannello di reclutamento !19.", guild=discord.Object(id=GUILD_ID))
async def ticket_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not interaction.channel.permissions_for(interaction.guild.me).send_messages:
        return await interaction.followup.send("Errore permessi scrittura.", ephemeral=True)

    try:
        embed = discord.Embed(
            title="!19 TICKET", 
            description=(
                "> Apri Ticket Braccio Armato se vuoi essere reclutato o addestrato\n"
                "> Apri Ticket Informativa se vuoi entrar a far parte del gruppo Info"
            ),
            color=0x2b2d31,
            timestamp=discord.utils.utcnow()
        )

        if BANNER_URL:
            embed.set_image(url=BANNER_URL)

        if LOGO_URL:
            embed.set_footer(text="Developed by V HUB Team", icon_url=LOGO_URL)
        else:
            embed.set_footer(text="Developed by V HUB Team")

        view = TicketPanelView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("Pannello inviato.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Errore: {e}", ephemeral=True)


@bot.command(name="messaggio")
async def msg_cmd(ctx, *, testo: str):
    if not testo:
        return await ctx.send("Devi scrivere un messaggio dopo il comando.", delete_after=5)

    try:
        webhooks = await ctx.channel.webhooks()
        webhook = discord.utils.get(webhooks, name="!19 Official")
        
        if not webhook:
            webhook = await ctx.channel.create_webhook(name="!19 Official")
        
        await webhook.send(
            content=testo,
            username="!19",
            avatar_url=bot.user.display_avatar.url if bot.user.avatar else None
        )
        
        try:
            await ctx.message.delete()
        except:
            pass
            
    except discord.Forbidden:
        await ctx.send("Errore: Il bot necessita del permesso Gestisci Webhook.", delete_after=5)
    except Exception as e:
        await ctx.send(f"Errore: {e}", delete_after=5)


bot.run(TOKEN)
