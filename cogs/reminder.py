# cogs/reminder.py
from discord.ext import commands, tasks
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
        self.reminders = []  # list of dicts
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
                    # convert string times back to datetime
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

            # handle repeating reminders
            if r.get("repeat"):
                r["time"] = self.next_time(r)
            else:
                self.reminders.remove(r)
            self.save_reminders()

    # ----------------
    # Commands
    # ----------------
    @commands.command(name="remindme")
    async def remindme(self, ctx, *, args):
        """
        Sets a One-time Reminder, help remindme for format.
        Examples:
        !remindme 60 seconds do thing
        !remindme 60 minutes do another thing
        !remindme 60 hours do another another thing
        !remindme 60 days do yet another thing
        """
        match = re.match(r"(\d+)\s*(seconds?|minutes?|hours?|days?)\s+(.+)", args, re.I)
        if not match:
            await ctx.send("Invalid format. Example: `!remindme 2 days do something`")
            return

        amount, unit, message = match.groups()
        amount = int(amount)
        unit = unit.lower()
        delta = None
        if "second" in unit:
            delta = timedelta(seconds=amount)
        elif "minute" in unit:
            delta = timedelta(minutes=amount)
        elif "hour" in unit:
            delta = timedelta(hours=amount)
        elif "day" in unit:
            delta = timedelta(days=amount)

        remind_time = datetime.utcnow() + delta
        self.reminders.append({
            "time": remind_time,
            "user_id": ctx.author.id,
            "message": message,
            "repeat": None
        })
        self.save_reminders()
        await ctx.send(f"Okay {ctx.author.mention}, I will remind you in {amount} {unit}.")

    @commands.command(name="repeatme")
    async def repeatme(self, ctx, *, args):
        """
        Sets a Repeating Reminder, do help repeatme for format.
        Examples:
        !repeatme every 24 hours check something
        !repeatme every day do this
        !repeatme every month time to do this
        !repeatme 13 do something every month on 13th
        !repeatme 2026-01-15 special event
        """
        now = datetime.utcnow()
        args = args.strip()

        # every N units
        m_every_num = re.match(r"every\s+(\d+)\s*(seconds?|minutes?|hours?|days?)\s+(.+)", args, re.I)
        if m_every_num:
            amount, unit, message = m_every_num.groups()
            amount = int(amount)
            unit = unit.lower()
            delta = None
            if "second" in unit:
                delta = timedelta(seconds=amount)
            elif "minute" in unit:
                delta = timedelta(minutes=amount)
            elif "hour" in unit:
                delta = timedelta(hours=amount)
            elif "day" in unit:
                delta = timedelta(days=amount)

            if delta is None:
                await ctx.send("Invalid time unit. Use seconds, minutes, hours, days.")
                return

            next_time = now + delta
            self.reminders.append({
                "time": next_time,
                "user_id": ctx.author.id,
                "message": message,
                "repeat": "interval",
                "interval_seconds": delta.total_seconds()
            })
            self.save_reminders()
            await ctx.send(f"Repeat reminder set every {amount} {unit}.")
            return

        # every day/week/month
        m_every_unit = re.match(r"every\s+(day|week|month)\s+(.+)", args, re.I)
        if m_every_unit:
            unit, message = m_every_unit.groups()
            unit = unit.lower()
            if unit == "day":
                next_time = now + timedelta(days=1)
            elif unit == "week":
                next_time = now + timedelta(weeks=1)
            elif unit == "month":
                month = now.month + 1 if now.month < 12 else 1
                year = now.year if now.month < 12 else now.year + 1
                day = min(now.day, calendar.monthrange(year, month)[1])
                next_time = datetime(year, month, day, now.hour, now.minute, now.second)

            self.reminders.append({
                "time": next_time,
                "user_id": ctx.author.id,
                "message": message,
                "repeat": unit
            })
            self.save_reminders()
            await ctx.send(f"Repeat reminder set for every {unit}.")
            return

        # day-of-month repeat
        m_day_of_month = re.match(r"(\d{1,2})\s+(.+)", args)
        if m_day_of_month:
            day, message = m_day_of_month.groups()
            day = int(day)
            year = now.year
            month = now.month
            if day < now.day:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            day = min(day, calendar.monthrange(year, month)[1])
            next_time = datetime(year, month, day, now.hour, now.minute, now.second)

            self.reminders.append({
                "time": next_time,
                "user_id": ctx.author.id,
                "message": message,
                "repeat": "month"
            })
            self.save_reminders()
            await ctx.send(f"Repeat reminder set for day {day} of every month.")
            return

        # specific date YYYY-MM-DD
        m_specific_date = re.match(r"(\d{4}-\d{2}-\d{2})\s+(.+)", args)
        if m_specific_date:
            date_str, message = m_specific_date.groups()
            try:
                next_time = datetime.strptime(date_str, "%Y-%m-%d")
                if next_time < now:
                    await ctx.send("Date is in the past.")
                    return
                self.reminders.append({
                    "time": next_time,
                    "user_id": ctx.author.id,
                    "message": message,
                    "repeat": None
                })
                self.save_reminders()
                await ctx.send(f"Repeat reminder set for {date_str}.")
            except Exception:
                await ctx.send("Invalid date format, use YYYY-MM-DD.")
            return

        await ctx.send("Could not parse the repeat reminder. Check your format.")

    @commands.command(name="listreminders")
    async def listreminders(self, ctx):
        """Lists all upcoming reminders for the user with timestamps."""
        now = datetime.utcnow()
        user_reminders = [r for r in self.reminders if r["user_id"] == ctx.author.id and r["time"] > now]

        if not user_reminders:
            await ctx.send("You have no upcoming reminders.")
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
        await ctx.send(f"Your upcoming reminders:\n{message}")

    @commands.command(name="cancelreminder")
    async def cancelreminder(self, ctx, *, keyword=None):
        """
        Cancel a reminder.
        Usage:
        - !cancelreminder <keyword> -> removes reminders containing this text
        - !cancelreminder -> shows list with indexes to pick from
        """
        now = datetime.utcnow()
        user_reminders = [r for r in self.reminders if r["user_id"] == ctx.author.id]

        if not user_reminders:
            await ctx.send("You have no reminders to cancel.")
            return

        if keyword:
            removed = []
            for r in user_reminders[:]:
                if keyword.lower() in r["message"].lower():
                    self.reminders.remove(r)
                    removed.append(r["message"])
            if removed:
                self.save_reminders()
                await ctx.send(f"Removed {len(removed)} reminder(s) containing '{keyword}'.")
            else:
                await ctx.send(f"No reminders found containing '{keyword}'.")
            return

        # If no keyword, show indexed list
        lines = []
        for idx, r in enumerate(user_reminders, 1):
            unix_ts = int(r["time"].timestamp())
            timestamp = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"
            repeat = r["repeat"] if r["repeat"] else "One-time"
            lines.append(f"{idx}. {timestamp} | {repeat} | {r['message']}")

        message = "\n".join(lines)
        if len(message) > 1900:
            message = message[:1900] + "\n..."
        await ctx.send(f"Your reminders:\n{message}\n\nTo cancel, use `!cancelreminder <keyword>` containing the reminder text.")


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
