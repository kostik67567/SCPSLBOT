import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Select, Modal, TextInput
import a2s
import asyncio

# Настройки
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
SERVER_IP = "51.68.152.142"
SERVER_PORT = 17283

# ID пользователей с доступом
ALLOWED_USERS = [1412894066982781029, 995978380207980545, 1348372787714195648]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Хранилище сообщений бота для удаления
bot_messages = []


class UserIDModal(Modal):
    def __init__(self, action: str, roles: list):
        super().__init__(title=f"{action} роли пользователю")
        self.action = action
        self.roles = roles

        self.user_id_input = TextInput(
            label="ID пользователя",
            placeholder="Введите Discord ID пользователя",
            required=True,
            max_length=20
        )
        self.add_item(self.user_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id_input.value)
            target_user = await interaction.guild.fetch_member(user_id)
        except (ValueError, discord.NotFound):
            await interaction.response.send_message("❌ Пользователь не найден! Проверьте ID.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message("❌ Нет прав для доступа к пользователю.", ephemeral=True)
            return

        success_roles = []
        failed_roles = []

        for role in self.roles:
            try:
                if self.action == "add":
                    if role not in target_user.roles:
                        await target_user.add_roles(role)
                        success_roles.append(f"➕ {role.mention}")
                    else:
                        success_roles.append(f"✅ {role.mention} (уже есть)")
                else:
                    if role in target_user.roles:
                        await target_user.remove_roles(role)
                        success_roles.append(f"➖ {role.mention}")
                    else:
                        success_roles.append(f"✅ {role.mention} (уже нет)")
            except:
                failed_roles.append(role.mention)

        result_message = f"**Действие для {target_user.mention}:**\n"
        if success_roles:
            result_message += "\n".join(success_roles) + "\n"
        if failed_roles:
            result_message += f"❌ Ошибка с ролями: {', '.join(failed_roles)}"

        await interaction.response.send_message(result_message, ephemeral=True)


class RoleSelect(Select):
    def __init__(self, roles, action="add", target="self"):
        self.action = action
        self.target = target  # "self" или "other"

        options = []
        for role in roles:
            if action == "add":
                emoji = "➕"
                desc = "Добавить роль"
            else:
                emoji = "➖"
                desc = "Убрать роль"

            options.append(discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=desc,
                emoji=emoji
            ))

        placeholder = "Выбери роли..." if target == "self" else "Выбери роли для действия..."
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in ALLOWED_USERS:
            await interaction.response.send_message("❌ Доступ запрещен!", ephemeral=True)
            return

        selected_roles = []
        for role_id in self.values:
            role = interaction.guild.get_role(int(role_id))
            if role:
                selected_roles.append(role)

        if not selected_roles:
            await interaction.response.send_message("❌ Не выбрано ни одной роли!", ephemeral=True)
            return

        if self.target == "self":
            # Действие для себя
            success_roles = []
            failed_roles = []

            for role in selected_roles:
                try:
                    if self.action == "add":
                        if role not in interaction.user.roles:
                            await interaction.user.add_roles(role)
                            success_roles.append(f"➕ {role.mention}")
                        else:
                            success_roles.append(f"✅ {role.mention} (уже есть)")
                    else:
                        if role in interaction.user.roles:
                            await interaction.user.remove_roles(role)
                            success_roles.append(f"➖ {role.mention}")
                        else:
                            success_roles.append(f"✅ {role.mention} (уже нет)")
                except:
                    failed_roles.append(role.mention)

            result_message = ""
            if success_roles:
                result_message += "\n".join(success_roles) + "\n"
            if failed_roles:
                result_message += f"❌ Ошибка: {', '.join(failed_roles)}"

            await interaction.response.send_message(result_message, ephemeral=True)
        else:
            # Действие для другого пользователя - открываем модальное окно
            modal = UserIDModal(self.action, selected_roles)
            await interaction.response.send_modal(modal)


class AdminMenu(View):
    def __init__(self):
        super().__init__(timeout=300)

    async def check_access(self, interaction: discord.Interaction):
        if interaction.user.id not in ALLOWED_USERS:
            await interaction.response.send_message("❌ Доступ запрещен!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Себе: Выдать", style=discord.ButtonStyle.green, emoji="➕", row=0)
    async def give_self(self, interaction: discord.Interaction, button: Button):
        if not await self.check_access(interaction):
            return

        bot_member = interaction.guild.me
        available_roles = []

        for role in interaction.guild.roles:
            if (role < bot_member.top_role and
                    role != interaction.guild.default_role and
                    not role.managed):
                available_roles.append(role)

        if not available_roles:
            await interaction.response.send_message("❌ Нет доступных ролей!", ephemeral=True)
            return

        view = View()
        view.add_item(RoleSelect(available_roles, "add", "self"))
        await interaction.response.send_message("Выбери роли для выдачи себе:", view=view, ephemeral=True)

    @discord.ui.button(label="Себе: Убрать", style=discord.ButtonStyle.red, emoji="➖", row=0)
    async def remove_self(self, interaction: discord.Interaction, button: Button):
        if not await self.check_access(interaction):
            return

        user_roles = []
        for role in interaction.user.roles:
            if (role != interaction.guild.default_role and
                    not role.managed and
                    role < interaction.guild.me.top_role):
                user_roles.append(role)

        if not user_roles:
            await interaction.response.send_message("✅ Нет ролей для удаления!", ephemeral=True)
            return

        view = View()
        view.add_item(RoleSelect(user_roles, "remove", "self"))
        await interaction.response.send_message("Выбери роли для удаления у себя:", view=view, ephemeral=True)

    @discord.ui.button(label="Другому: Выдать", style=discord.ButtonStyle.green, emoji="👥", row=1)
    async def give_other(self, interaction: discord.Interaction, button: Button):
        if not await self.check_access(interaction):
            return

        bot_member = interaction.guild.me
        available_roles = []

        for role in interaction.guild.roles:
            if (role < bot_member.top_role and
                    role != interaction.guild.default_role and
                    not role.managed):
                available_roles.append(role)

        if not available_roles:
            await interaction.response.send_message("❌ Нет доступных ролей!", ephemeral=True)
            return

        view = View()
        view.add_item(RoleSelect(available_roles, "add", "other"))
        await interaction.response.send_message("Выбери роли для выдачи другому пользователю:", view=view,
                                                ephemeral=True)

    @discord.ui.button(label="Другому: Убрать", style=discord.ButtonStyle.red, emoji="👥", row=1)
    async def remove_other(self, interaction: discord.Interaction, button: Button):
        if not await self.check_access(interaction):
            return

        # Все роли которые бот может управлять
        bot_member = interaction.guild.me
        available_roles = []

        for role in interaction.guild.roles:
            if (role < bot_member.top_role and
                    role != interaction.guild.default_role and
                    not role.managed):
                available_roles.append(role)

        if not available_roles:
            await interaction.response.send_message("❌ Нет доступных ролей!", ephemeral=True)
            return

        view = View()
        view.add_item(RoleSelect(available_roles, "remove", "other"))
        await interaction.response.send_message("Выбери роли для удаления у другого пользователя:", view=view,
                                                ephemeral=True)

    @discord.ui.button(label="Убрать все у себя", style=discord.ButtonStyle.danger, emoji="💣", row=2)
    async def remove_all_self(self, interaction: discord.Interaction, button: Button):
        if not await self.check_access(interaction):
            return

        roles_to_remove = []
        for role in interaction.user.roles:
            if role != interaction.guild.default_role and not role.managed:
                roles_to_remove.append(role)

        if not roles_to_remove:
            await interaction.response.send_message("✅ Нет ролей для удаления!", ephemeral=True)
            return

        try:
            await interaction.user.remove_roles(*roles_to_remove)
            await interaction.response.send_message(f"💣 Все роли ({len(roles_to_remove)}) удалены!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)

    @discord.ui.button(label="Мои роли", style=discord.ButtonStyle.blurple, emoji="📋", row=2)
    async def my_roles(self, interaction: discord.Interaction, button: Button):
        if not await self.check_access(interaction):
            return

        roles_info = []
        for role in interaction.user.roles:
            if role != interaction.guild.default_role:
                roles_info.append(role.mention)

        role_info = f"**Твои роли:**\n{', '.join(roles_info) if roles_info else 'Нет ролей'}"
        await interaction.response.send_message(role_info, ephemeral=True)

    @discord.ui.button(label="Очистить чат", style=discord.ButtonStyle.gray, emoji="🧹", row=2)
    async def clear_chat(self, interaction: discord.Interaction, button: Button):
        if not await self.check_access(interaction):
            return

        deleted_count = 0
        for msg in bot_messages[:]:
            try:
                await msg.delete()
                deleted_count += 1
                bot_messages.remove(msg)
            except:
                pass

        await interaction.response.send_message(f"🧹 Удалено {deleted_count} сообщений!", ephemeral=True, delete_after=3)


# Задача для обновления статуса SCP:SL сервера
@tasks.loop(seconds=10)
async def update_status():
    try:
        info = a2s.info((SERVER_IP, SERVER_PORT))
        status = f"SCP:SL {info.player_count}/{info.max_players}"
    except Exception:
        status = "SCP:SL сервер недоступен"

    try:
        await bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status
        ))
    except:
        pass


@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} запущен!')
    bot_messages.clear()
    update_status.start()


async def send_menu(ctx):
    embed = discord.Embed(
        title="🎮 Панель управления ролями - SCP:SL",
        description="Управление ролями для себя и других пользователей",
        color=discord.Color.gold()
    )
    embed.add_field(name="➕ Себе: Выдать", value="Выдать роли себе", inline=True)
    embed.add_field(name="➖ Себе: Убрать", value="Убрать роли у себя", inline=True)
    embed.add_field(name="👥 Другому: Выдать", value="Выдать роли другому", inline=True)
    embed.add_field(name="👥 Другому: Убрать", value="Убрать роли у другого", inline=True)
    embed.add_field(name="💣 Убрать все", value="Снять все роли у себя", inline=True)
    embed.add_field(name="📋 Мои роли", value="Показать свои роли", inline=True)
    embed.add_field(name="🧹 Очистить чат", value="Удалить сообщения бота", inline=True)
    embed.set_footer(text="Статус SCP:SL сервера обновляется каждые 10 секунд")

    msg = await ctx.send(embed=embed, view=AdminMenu())
    bot_messages.append(msg)
    return msg


@bot.command()
async def menu(ctx):
    """Открыть меню управления"""
    if ctx.author.id not in ALLOWED_USERS:
        try:
            await ctx.message.delete()
        except:
            pass
        return

    await send_menu(ctx)
    try:
        await ctx.message.delete()
    except:
        pass


@bot.command()
async def clear(ctx):
    """Удалить все сообщения бота"""
    if ctx.author.id not in ALLOWED_USERS:
        try:
            await ctx.message.delete()
        except:
            pass
        return

    deleted_count = 0
    for msg in bot_messages[:]:
        try:
            await msg.delete()
            deleted_count += 1
            bot_messages.remove(msg)
        except:
            pass

    temp_msg = await ctx.send(f"🧹 Удалено {deleted_count} сообщений!", delete_after=3)
    bot_messages.append(temp_msg)

    try:
        await ctx.message.delete()
    except:
        pass


@bot.command()
async def status(ctx):
    """Показать статус SCP:SL сервера"""
    try:
        info = a2s.info((SERVER_IP, SERVER_PORT))
        players = a2s.players((SERVER_IP, SERVER_PORT))

        embed = discord.Embed(
            title="🟢 SCP:SL Статус сервера",
            description=f"**{info.server_name}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Игроки", value=f"{info.player_count}/{info.max_players}")
        embed.add_field(name="Карта", value=info.map_name)
        embed.add_field(name="Пинг", value=f"{info.ping * 1000:.0f}ms")

        if players:
            player_list = [f"{player.name}" for player in players[:10]]
            embed.add_field(name="Онлайн", value="\n".join(player_list) + ("\n..." if len(players) > 10 else ""),
                            inline=False)

        msg = await ctx.send(embed=embed, delete_after=20)
    except Exception as e:
        msg = await ctx.send(f"🔴 SCP:SL Сервер недоступен: {e}", delete_after=10)

    bot_messages.append(msg)
    try:
        await ctx.message.delete()
    except:
        pass


@bot.event
async def on_message(message):
    if message.author == bot.user:
        bot_messages.append(message)

    if message.author.bot:
        return

    if message.content.startswith('!') and message.author.id not in ALLOWED_USERS:
        try:
            await message.delete()
        except:
            pass
        return

    await bot.process_commands(message)


# Запуск бота
bot.run(TOKEN)
