# cogs/reminder.py
from discord.ext import commands, tasks
from discord import app_commands
import discord
import asyncio
from datetime import datetime, timedelta
import re
import json
import os
import calendar

REMINDER_FILE = "reminders.json"


class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = []
        self.load_reminders()
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    # ----------------
    # Persistence
    # ----------------
    def load_reminders(self):
        if os.path.exists(REMINDER_FILE):
            try:
                with open(REMINDER_FILE, "r") as f:
                    self.reminders = json.load(f)
                    for r in self.reminders:
                        r["time"] = datetime.fromisoformat(r["time"])
            except Exception as e:
                print(f"[WARN] Could not load reminders: {e}")
                self.reminders = []

    def save_reminders(self):
        try:
            with open(REMINDER_FILE, "w") as f:
                data = []
                for r in self.reminders:
                    copy_r = r.copy()
                    copy_r["time"] = r["time"].isoformat()
                    data.append(copy_r)
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[WARN] Could not save reminders: {e}")

    # ----------------
    # Reminder loop
    # ----------------
    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = datetime.utcnow()
        to_send = [r for r in self.reminders if r["time"] <= now]
        for r in to_send:
            user = await self.bot.fetch_user(r["user_id"])
            try:
                await user.send(f"Reminder: {r['message']}")
            except discord.Forbidden:
                print(f"Cannot DM user {r['user_id']}")

            if r.get("repeat"):
                r["time"] = self.next_time(r)
            else:
                self.reminders.remove(r)
            self.save_reminders()

    # ----------------
    # Slash Commands
    # ----------------
    @app_commands.command(name="remindme", description="Set a one-time reminder.")
    @app_commands.describe(
        amount="How many units of time",
        unit="Unit of time",
        message="What to remind you about"
    )
    @app_commands.choices(unit=[
        app_commands.Choice(name="Seconds", value="seconds"),
        app_commands.Choice(name="Minutes", value="minutes"),
        app_commands.Choice(name="Hours", value="hours"),
        app_commands.Choice(name="Days", value="days"),
    ])
    async def remindme(self, interaction: discord.Interaction, amount: int, unit: str, message: str):
        delta = None
        if unit == "seconds":
            delta = timedelta(seconds=amount)
        elif unit == "minutes":
            delta = timedelta(minutes=amount)
        elif unit == "hours":
            delta = timedelta(hours=amount)
        elif unit == "days":
            delta = timedelta(days=amount)

        remind_time = datetime.utcnow() + delta
        self.reminders.append({
            "time": remind_time,
            "user_id": interaction.user.id,
            "message": message,
            "repeat": None
        })
        self.save_reminders()
        await interaction.response.send_message(
            f"Okay {interaction.user.mention}, I'll remind you in {amount} {unit}.",
            ephemeral=True
        )

    @app_commands.command(name="repeatme", description="Set a repeating reminder.")
    @app_commands.describe(
        repeat_type="How often to repeat",
        message="What to remind you about",
        interval_amount="Amount (only for 'Every N units')",
        interval_unit="Unit (only for 'Every N units')",
        day_of_month="Day of month 1–31 (only for 'Day of month')",
        specific_date="Specific date YYYY-MM-DD (only for 'Specific date')"
    )
    @app_commands.choices(repeat_type=[
        app_commands.Choice(name="Every N units", value="interval"),
        app_commands.Choice(name="Every day", value="day"),
        app_commands.Choice(name="Every week", value="week"),
        app_commands.Choice(name="Every month", value="month"),
        app_commands.Choice(name="Day of month", value="day_of_month"),
        app_commands.Choice(name="Specific date", value="specific_date"),
    ])
    @app_commands.choices(interval_unit=[
        app_commands.Choice(name="Seconds", value="seconds"),
        app_commands.Choice(name="Minutes", value="minutes"),
        app_commands.Choice(name="Hours", value="hours"),
        app_commands.Choice(name="Days", value="days"),
    ])
    async def repeatme(
        self,
        interaction: discord.Interaction,
        repeat_type: str,
        message: str,
        interval_amount: int = None,
        interval_unit: str = None,
        day_of_month: int = None,
        specific_date: str = None
    ):
        now = datetime.utcnow()

        if repeat_type == "interval":
            if interval_amount is None or interval_unit is None:
                await interaction.response.send_message(
                    "Please provide both `interval_amount` and `interval_unit` for 'Every N units'.",
                    ephemeral=True
                )
                return
            delta = None
            if interval_unit == "seconds":
                delta = timedelta(seconds=interval_amount)
            elif interval_unit == "minutes":
                delta = timedelta(minutes=interval_amount)
            elif interval_unit == "hours":
                delta = timedelta(hours=interval_amount)
            elif interval_unit == "days":
                delta = timedelta(days=interval_amount)

            self.reminders.append({
                "time": now + delta,
                "user_id": interaction.user.id,
                "message": message,
                "repeat": "interval",
                "interval_seconds": delta.total_seconds()
            })
            self.save_reminders()
            await interaction.response.send_message(
                f"Repeat reminder set every {interval_amount} {interval_unit}.", ephemeral=True
            )

        elif repeat_type == "day":
            self.reminders.append({
                "time": now + timedelta(days=1),
                "user_id": interaction.user.id,
                "message": message,
                "repeat": "day"
            })
            self.save_reminders()
            await interaction.response.send_message("Repeat reminder set for every day.", ephemeral=True)

        elif repeat_type == "week":
            self.reminders.append({
                "time": now + timedelta(weeks=1),
                "user_id": interaction.user.id,
                "message": message,
                "repeat": "week"
            })
            self.save_reminders()
            await interaction.response.send_message("Repeat reminder set for every week.", ephemeral=True)

        elif repeat_type == "month":
            month = now.month + 1 if now.month < 12 else 1
            year = now.year if now.month < 12 else now.year + 1
            day = min(now.day, calendar.monthrange(year, month)[1])
            next_time = datetime(year, month, day, now.hour, now.minute, now.second)
            self.reminders.append({
                "time": next_time,
                "user_id": interaction.user.id,
                "message": message,
                "repeat": "month"
            })
            self.save_reminders()
            await interaction.response.send_message("Repeat reminder set for every month.", ephemeral=True)

        elif repeat_type == "day_of_month":
            if day_of_month is None:
                await interaction.response.send_message(
                    "Please provide `day_of_month` for this repeat type.", ephemeral=True
                )
                return
            year = now.year
            month = now.month
            if day_of_month < now.day:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            day = min(day_of_month, calendar.monthrange(year, month)[1])
            next_time = datetime(year, month, day, now.hour, now.minute, now.second)
            self.reminders.append({
                "time": next_time,
                "user_id": interaction.user.id,
                "message": message,
                "repeat": "month"
            })
            self.save_reminders()
            await interaction.response.send_message(
                f"Repeat reminder set for day {day} of every month.", ephemeral=True
            )

        elif repeat_type == "specific_date":
            if specific_date is None:
                await interaction.response.send_message(
                    "Please provide `specific_date` in YYYY-MM-DD format.", ephemeral=True
                )
                return
            try:
                next_time = datetime.strptime(specific_date, "%Y-%m-%d")
                if next_time < now:
                    await interaction.response.send_message("That date is in the past.", ephemeral=True)
                    return
                self.reminders.append({
                    "time": next_time,
                    "user_id": interaction.user.id,
                    "message": message,
                    "repeat": None
                })
                self.save_reminders()
                await interaction.response.send_message(
                    f"Reminder set for {specific_date}.", ephemeral=True
                )
            except ValueError:
                await interaction.response.send_message(
                    "Invalid date format. Use YYYY-MM-DD.", ephemeral=True
                )

    @app_commands.command(name="listreminders", description="List all your upcoming reminders.")
    async def listreminders(self, interaction: discord.Interaction):
        now = datetime.utcnow()
        user_reminders = [
            r for r in self.reminders
            if r["user_id"] == interaction.user.id and r["time"] > now
        ]

        if not user_reminders:
            await interaction.response.send_message("You have no upcoming reminders.", ephemeral=True)
            return

        lines = []
        for r in sorted(user_reminders, key=lambda x: x["time"]):
            unix_ts = int(r["time"].timestamp())
            timestamp = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"
            repeat = r["repeat"] if r["repeat"] else "One-time"
            lines.append(f"{timestamp} | {repeat} | {r['message']}")

        message = "\n".join(lines)
        if len(message) > 1900:
            message = message[:1900] + "\n..."
        await interaction.response.send_message(
            f"Your upcoming reminders:\n{message}", ephemeral=True
        )

    @app_commands.command(name="cancelreminder", description="Cancel a reminder by keyword.")
    @app_commands.describe(keyword="Text contained in the reminder you want to cancel")
    async def cancelreminder(self, interaction: discord.Interaction, keyword: str):
        user_reminders = [r for r in self.reminders if r["user_id"] == interaction.user.id]

        if not user_reminders:
            await interaction.response.send_message("You have no reminders to cancel.", ephemeral=True)
            return

        removed = [r for r in user_reminders if keyword.lower() in r["message"].lower()]
        if removed:
            for r in removed:
                self.reminders.remove(r)
            self.save_reminders()
            await interaction.response.send_message(
                f"Removed {len(removed)} reminder(s) containing '{keyword}'.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"No reminders found containing '{keyword}'.", ephemeral=True
            )

    # ----------------
    # Helper
    # ----------------
    def next_time(self, reminder):
        now = reminder["time"]
        repeat_type = reminder.get("repeat")
        if repeat_type == "day":
            return now + timedelta(days=1)
        elif repeat_type == "week":
            return now + timedelta(weeks=1)
        elif repeat_type == "month":
            year = now.year
            month = now.month + 1
            if month > 12:
                month = 1
                year += 1
            day = min(now.day, calendar.monthrange(year, month)[1])
            return datetime(year, month, day, now.hour, now.minute, now.second)
        elif repeat_type == "interval":
            return now + timedelta(seconds=reminder.get("interval_seconds", 0))
        else:
            return now


async def setup(bot):
    await bot.add_cog(Reminder(bot))