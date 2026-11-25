import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from discord import app_commands
import bot as scaffold


def interaction():
    return SimpleNamespace(
        user=SimpleNamespace(id=123),
        response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock(), is_done=lambda: False),
        followup=SimpleNamespace(send=AsyncMock()),
    )


class SlashTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = scaffold.ScaffoldBot()
        await self.bot.__aenter__()
        self.bot.tree.sync = AsyncMock(return_value=[])
        self.owner_patch = patch.object(scaffold, "bot", self.bot)
        self.owner_patch.start()

    async def asyncTearDown(self):
        await self.bot.close()
        self.owner_patch.stop()

    async def test_setup_registers_cogs_as_slash_commands(self):
        await self.bot.setup_hook()
        names = {c.name for c in self.bot.tree.get_commands()}
        self.assertEqual(names, {"cogs", "remindme", "repeatme", "listreminders", "cancelreminder"})
        self.assertEqual(len(self.bot.commands), 0)
        self.assertFalse(self.bot.intents.message_content)
        self.bot.tree.sync.assert_awaited_once()
        for command in self.bot.tree.get_commands():
            self.assertEqual(command.to_dict(self.bot.tree)["type"], 1)

    async def test_ready_does_not_reload_or_sync(self):
        with patch.object(self.bot, "load_extension", new_callable=AsyncMock) as load:
            self.bot._connection.user = SimpleNamespace(id=123)
            await scaffold.on_ready()
            await scaffold.on_ready()
            load.assert_not_awaited()
            self.bot.tree.sync.assert_not_awaited()

    async def test_cogs_response(self):
        await self.bot.load_extension("cogs.coglist")
        command = self.bot.tree.get_command("cogs")
        event = interaction()
        await command.callback(command.binding, event)
        self.assertIn("CogList", event.response.send_message.call_args.args[0])

    async def test_admin_checks_deny_nonowner(self):
        event = interaction()
        self.bot.is_owner = AsyncMock(return_value=False)
        for command in (scaffold.reload, scaffold.shutdown):
            self.assertFalse(await command._check_can_run(event))

    async def test_admin_checks_allow_owner(self):
        self.bot.is_owner = AsyncMock(return_value=True)
        for command in (scaffold.reload, scaffold.shutdown):
            self.assertTrue(await command._check_can_run(interaction()))

    async def test_reload_all_defers_and_syncs(self):
        event = interaction()
        await scaffold.reload.callback(event)
        event.response.defer.assert_awaited_once()
        event.response.send_message.assert_not_awaited()
        event.followup.send.assert_awaited_once()
        self.bot.tree.sync.assert_awaited_once()

    async def test_reload_existing_extension(self):
        await self.bot.load_extension("cogs.coglist")
        with patch.object(self.bot, "reload_extension", new_callable=AsyncMock) as reload:
            await scaffold.reload.callback(interaction(), "coglist")
            reload.assert_awaited_once_with("cogs.coglist")

    async def test_reload_unknown_module(self):
        event = interaction()
        await scaffold.reload.callback(event, "../nope")
        self.assertIn("Unknown module", event.followup.send.call_args.args[0])
        self.bot.tree.sync.assert_not_awaited()

    async def test_reload_failure_is_reported(self):
        event = interaction()
        with patch.object(self.bot, "load_extension", side_effect=RuntimeError("test")), \
             patch.object(scaffold, "notify_owner_of_failure", new_callable=AsyncMock) as notify:
            await scaffold.reload.callback(event, "coglist")
            notify.assert_awaited_once()
        self.assertIn("Failed to reload", event.followup.send.call_args.args[0])

    async def test_permission_error_is_private(self):
        event = interaction()
        await scaffold.on_app_command_error(event, app_commands.CheckFailure())
        self.assertTrue(event.response.send_message.call_args.kwargs["ephemeral"])

    async def test_shutdown(self):
        self.bot.close = AsyncMock()
        event = interaction()
        await scaffold.shutdown.callback(event)
        event.response.send_message.assert_awaited_once()
        self.bot.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
