# Scaffold - Python - Discord Bot

## What?
Scaffold is a half vibecoded, half drunkcoded discord.py based Bot that serves as a framework to expand on.

## Why?
I got tired of managing multiple versions accross multiple devices so i decided to consolidate it all in one repo so i can sync it.

## License?
I have no clue, it's half vibecoded, how do i license this?

## Can i use it?
Yeah sure be my guest, just keep in mind it's probably horrendously coded or as barebones as it gets so **Use at your own Risk.**
## Run (Python 3.10+)

Create a virtual environment, install `pip install -r requirements.txt`, copy
`.env.example` to `.env`, and set `DISCORD_TOKEN` locally. Run `python bot.py`.
Invite the application with the `bot` and `applications.commands` scopes.
Message Content Intent is not required. Commands are synced globally at startup;
Discord may take time to display updated commands.

## Slash commands

- `/ping`: gateway latency.
- `/cogs`: loaded modules (private response).
- `/remindme amount unit message`: one-time DM reminder.
- `/repeatme repeat_type message ...`: repeating reminder; the specific-date
  option creates a one-time reminder. Dates are interpreted as UTC.
- `/listreminders`: your upcoming reminders.
- `/cancelreminder keyword`: cancel your reminders matching the keyword.
- `/reload [module]`: reload one module or all modules and sync commands (owner only).
- `/shutdown`: stop the process (owner only).

Prefix commands and `PREFIX` configuration are no longer used. Reminder delivery
is checked every 30 seconds and requires that the bot can DM the recipient.
Reminder data remains in `reminders.json`; existing data is not migrated or removed.
Add modules under `cogs` using `app_commands.command` and async `setup(bot)`.

## Tests

Run `python -m unittest discover -s tests -v` with the dependencies installed.
Tests mock Discord network operations; live command registration and delivery
require a running bot with a valid token.
