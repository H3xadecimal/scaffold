# cogs/reminder.py
from discord.ext import commands, tasks
import discord
from datetime import datetime, timedelta
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

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

    # ----------------
    # Prefix Commands
    # ----------------
    @commands.command(name="remindme", description="Set a one-time reminder.")
    async def remindme(self, ctx: commands.Context, amount: int, unit: str, *, message: str):
        unit = unit.lower()
        if amount <= 0 or unit not in {"seconds", "minutes", "hours", "days"}:
            raise commands.BadArgument("Use a positive amount and seconds/minutes/hours/days.")
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
            "user_id": ctx.author.id,
            "message": message,
            "repeat": None
        })
        self.save_reminders()
        await ctx.send(
            f"Okay {ctx.author.mention}, I'll remind you in {amount} {unit}."
        )

    @commands.command(name="repeatme", help=(
        "repeatme day|week|month <message>\n"
        "repeatme interval <amount> <seconds|minutes|hours|days> <message>\n"
        "repeatme day_of_month <1-31> <message>\n"
        "repeatme specific_date <YYYY-MM-DD> <message> (one-time, UTC)"
    ))
    async def repeatme(self, ctx: commands.Context, repeat_type: str, *, details: str):
        repeat_type = repeat_type.lower()
        kwargs = {}
        try:
            if repeat_type == "interval":
                amount, unit, message = details.split(maxsplit=2)
                amount = int(amount)
                unit = unit.lower()
                if amount <= 0 or unit not in {"seconds", "minutes", "hours", "days"}:
                    raise ValueError()
                kwargs = dict(interval_amount=amount, interval_unit=unit)
            elif repeat_type == "day_of_month":
                day, message = details.split(maxsplit=1)
                day = int(day)
                if not 1 <= day <= 31:
                    raise ValueError()
                kwargs = dict(day_of_month=day)
            elif repeat_type == "specific_date":
                date, message = details.split(maxsplit=1)
                kwargs = dict(specific_date=date)
            elif repeat_type in {"day", "week", "month"}:
                message = details
            else:
                raise ValueError()
        except ValueError as error:
            raise commands.BadArgument("Invalid reminder options.") from error
        await self._repeatme(ctx, repeat_type, message, **kwargs)

    async def _repeatme(
        self,
        ctx: commands.Context,
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
                await ctx.send(
                    "Please provide both `interval_amount` and `interval_unit` for 'Every N units'."
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
                "user_id": ctx.author.id,
                "message": message,
                "repeat": "interval",
                "interval_seconds": delta.total_seconds()
            })
            self.save_reminders()
            await ctx.send(
                f"Repeat reminder set every {interval_amount} {interval_unit}."
            )

        elif repeat_type == "day":
            self.reminders.append({
                "time": now + timedelta(days=1),
                "user_id": ctx.author.id,
                "message": message,
                "repeat": "day"
            })
            self.save_reminders()
            await ctx.send("Repeat reminder set for every day.")

        elif repeat_type == "week":
            self.reminders.append({
                "time": now + timedelta(weeks=1),
                "user_id": ctx.author.id,
                "message": message,
                "repeat": "week"
            })
            self.save_reminders()
            await ctx.send("Repeat reminder set for every week.")

        elif repeat_type == "month":
            month = now.month + 1 if now.month < 12 else 1
            year = now.year if now.month < 12 else now.year + 1
            day = min(now.day, calendar.monthrange(year, month)[1])
            next_time = datetime(year, month, day, now.hour, now.minute, now.second)
            self.reminders.append({
                "time": next_time,
                "user_id": ctx.author.id,
                "message": message,
                "repeat": "month"
            })
            self.save_reminders()
            await ctx.send("Repeat reminder set for every month.")

        elif repeat_type == "day_of_month":
            if day_of_month is None:
                await ctx.send(
                    "Please provide `day_of_month` for this repeat type."
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
                "user_id": ctx.author.id,
                "message": message,
                "repeat": "month"
            })
            self.save_reminders()
            await ctx.send(
                f"Repeat reminder set for day {day} of every month."
            )

        elif repeat_type == "specific_date":
            if specific_date is None:
                await ctx.send(
                    "Please provide `specific_date` in YYYY-MM-DD format."
                )
                return
            try:
                next_time = datetime.strptime(specific_date, "%Y-%m-%d")
                if next_time < now:
                    await ctx.send("That date is in the past.")
                    return
                self.reminders.append({
                    "time": next_time,
                    "user_id": ctx.author.id,
                    "message": message,
                    "repeat": None
                })
                self.save_reminders()
                await ctx.send(
                    f"Reminder set for {specific_date}."
                )
            except ValueError:
                await ctx.send(
                    "Invalid date format. Use YYYY-MM-DD."
                )

    @commands.command(name="listreminders", description="List all your upcoming reminders.")
    async def listreminders(self, ctx: commands.Context):
        now = datetime.utcnow()
        user_reminders = [
            r for r in self.reminders
            if r["user_id"] == ctx.author.id and r["time"] > now
        ]

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
        await ctx.send(
            f"Your upcoming reminders:\n{message}"
        )

    @commands.command(name="cancelreminder", description="Cancel a reminder by keyword.")
    async def cancelreminder(self, ctx: commands.Context, *, keyword: str):
        user_reminders = [r for r in self.reminders if r["user_id"] == ctx.author.id]

        if not user_reminders:
            await ctx.send("You have no reminders to cancel.")
            return

        removed = [r for r in user_reminders if keyword.lower() in r["message"].lower()]
        if removed:
            for r in removed:
                self.reminders.remove(r)
            self.save_reminders()
            await ctx.send(
                f"Removed {len(removed)} reminder(s) containing '{keyword}'."
            )
        else:
            await ctx.send(
                f"No reminders found containing '{keyword}'."
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