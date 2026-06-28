import os
import discord
from discord.ext import commands
from discord.ui import View, Select
from dotenv import load_dotenv

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

# ID Ruoli Braccio Armato
ROLE_BRACCIO_1 = get_id("ROLE_BRACCIO_1") 
ROLE_BRACCIO_2 = get_id("ROLE_BRACCIO_2") 

# ID Ruoli Informativa
ROLE_INFO_1    = get_id("ROLE_INFO_1")    
ROLE_INFO_2    = get_id("ROLE_INFO_2")    

BANNER_URL = os.getenv("BANNER_URL")
LOGO_URL   = os.getenv("LOGO_URL")

intents = discord.Intents.default()
intents.message_content = True # Necessario per leggere !messaggio
intents.guilds = True
intents.members = True

# Prefix impostato su "!"
bot = commands.Bot(command_prefix="!", intents=intents)


# ─────────────────────────────────────────────
#  SELECT MENU (Parte del Pannello Principale)
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
            return await interaction.followup.send("Errore configurazione.", ephemeral=True)

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

            close_view = CloseTicketView()
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
#  PULSANTE CHIUDI TICKET
# ────────────────────────────────────────────

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="CHIUDI TICKET", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket chiuso ed eliminato.", ephemeral=True)
        await interaction.channel.delete()


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
    bot.add_view(CloseTicketView())
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f" Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f" Errore sincronizzazione: {e}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


# ───────────────────────────────────────────
#  COMANDI SLASH (/ticket)
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


# ───────────────────────────────────────────
#  COMANDO TESTUALE (!messaggio)
# ────────────────────────────────────────────

@bot.command(name="messaggio")
async def msg_cmd(ctx, *, testo: str):
    """
    Uso: !messaggio Il tuo testo qui con spazi
    Invia il messaggio esattamente come scritto tramite Webhook.
    """
    if not testo:
        return await ctx.send("Devi scrivere un messaggio dopo il comando.", delete_after=5)

    try:
        webhooks = await ctx.channel.webhooks()
        webhook = discord.utils.get(webhooks, name="!19 Official")
        
        if not webhook:
            webhook = await ctx.channel.create_webhook(name="!19 Official")
        
        # Invia preservando TUTTI gli spazi e la formattazione
        await webhook.send(
            content=testo,
            username="!19",
            avatar_url=bot.user.display_avatar.url if bot.user.avatar else None
        )
        
        # Cancella il comando dell'utente per pulizia (opzionale)
        try:
            await ctx.message.delete()
        except:
            pass
            
    except discord.Forbidden:
        await ctx.send("Errore: Il bot necessita del permesso 'Gestisci Webhook'.", delete_after=5)
    except Exception as e:
        await ctx.send(f"Errore: {e}", delete_after=5)

@bot.event
async def on_member_join(member):
    # ID del ruolo da assegnare
    role_id = 1518932682476621964
    
    # Cerca il ruolo nel server
    role = member.guild.get_role(role_id)
    
    if role:
        try:
            await member.add_roles(role)
            print(f"Ruolo assegnato a {member.name}")
        except discord.Forbidden:
            print(f"Errore: Il bot non ha i permessi per assegnare il ruolo a {member.name}")
        except Exception as e:
            print(f"Errore imprevisto: {e}")
    else:
        print(f"Errore: Ruolo con ID {role_id} non trovato nel server.")

bot.run(TOKEN)