import discord
from discord.ui import View, LayoutView
from typing import Callable, Coroutine, Any
import random

from utils.embeds import (
    minigame_layout, work_success_layout,
    generate_random_string, generate_math_problem, generate_scrambled_word
)
from utils.database import update_credits, update_work_timestamp
import time


class JanitorView(LayoutView):
    """Janitor minigame - click button quickly."""

    def __init__(
        self,
        author_id: int,
        payout: int,
        on_complete: Callable[[], Coroutine[Any, Any, None]],
        timeout: float = 5.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.payout = payout
        self.on_complete = on_complete
        self.completed = False

        self._btn = discord.ui.Button(
            label="Clean!",
            style=discord.ButtonStyle.green,
            emoji="🧹"
        )
        self._btn.callback = self._clean_callback

        container = discord.ui.Container(
            *[
                discord.ui.TextDisplay(content="**🧹 Janitor Minigame**"),
                discord.ui.TextDisplay(content="Click the button below quickly to clean!"),
                discord.ui.ActionRow(self._btn),
            ],
            accent_color=discord.Color.blue().value
        )
        self.add_item(container)

    async def _clean_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return

        if self.completed:
            await interaction.response.send_message(
                "You already cleaned!", ephemeral=True
            )
            return

        self.completed = True
        self._btn.disabled = True
        await interaction.response.edit_message(
            view=work_success_layout("janitor", self.payout)
        )
        await update_credits(self.author_id, self.payout)
        await update_work_timestamp(self.author_id, int(time.time()))
        await self.on_complete()
        self.stop()

    async def on_timeout(self):
        if not self.completed:
            self._btn.disabled = True


class CashierMemoryView(LayoutView):
    """Cashier minigame - remember string or pick change."""

    def __init__(
        self,
        author_id: int,
        payout: int,
        on_complete: Callable[[], Coroutine[Any, Any, None]],
        timeout: float = 10.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.payout = payout
        self.on_complete = on_complete
        self.completed = False
        self.correct_change = random.randint(100, 500)

        self._memory_btn = discord.ui.Button(
            label="Memory Challenge",
            style=discord.ButtonStyle.primary
        )
        self._memory_btn.callback = self._memory_callback

        self._change_btn = discord.ui.Button(
            label="Change Challenge",
            style=discord.ButtonStyle.secondary
        )
        self._change_btn.callback = self._change_callback

        container = discord.ui.Container(
            *[
                discord.ui.TextDisplay(content="**🛒 Cashier Minigame**"),
                discord.ui.TextDisplay(content="Choose between Memory or Change challenge!"),
                discord.ui.ActionRow(self._memory_btn, self._change_btn),
            ],
            accent_color=discord.Color.blue().value
        )
        self.add_item(container)

    async def _memory_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return

        if self.completed:
            await interaction.response.send_message(
                "Already completed!", ephemeral=True
            )
            return

        self.completed = True
        code = generate_random_string(4)

        class CodeModal(discord.ui.Modal):
            def __init__(modal_self, target_code: str):
                super().__init__(title="Enter the Code")
                modal_self.code = target_code
                modal_self.answer = discord.ui.TextInput(
                    label="Enter the code",
                    placeholder=f"Type: {target_code}",
                    style=discord.TextStyle.short
                )
                modal_self.add_item(modal_self.answer)

            async def on_submit(modal_self, modal_inter: discord.Interaction):
                if modal_inter.user.id != self.author_id:
                    await modal_inter.response.send_message("not ur button.", ephemeral=True)
                    return

                if self.completed:
                    await modal_inter.response.send_message("Already done!", ephemeral=True)
                    return

                answer = str(modal_self.answer.value).strip()
                if answer == modal_self.code:
                    await modal_inter.response.edit_message(
                        view=work_success_layout("cashier", self.payout)
                    )
                    await update_credits(self.author_id, self.payout)
                    await update_work_timestamp(self.author_id, int(time.time()))
                    await self.on_complete()
                else:
                    await modal_inter.response.edit_message(
                        view=minigame_layout("❌ Wrong", f"Wrong! It was **{modal_self.code}**.", discord.Color.red().value)
                    )
                self.stop()

        await interaction.response.send_modal(CodeModal(code))

    async def _change_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )

        if self.completed:
            return await interaction.response.send_message(
                "Already completed!", ephemeral=True
            )

        self.completed = True

        options = [
            self.correct_change - random.randint(1, 20),
            self.correct_change,
            self.correct_change + random.randint(5, 30),
        ]
        random.shuffle(options)

        class ChangeView(LayoutView):
            def __init__(vself, amount: int):
                super().__init__(timeout=10.0)
                vself.done = False

                vself._opt1 = discord.ui.Button(label=str(options[0]), style=discord.ButtonStyle.primary)
                vself._opt1.callback = lambda i: vself.check_answer(i, options[0])
                vself._opt2 = discord.ui.Button(label=str(options[1]), style=discord.ButtonStyle.primary)
                vself._opt2.callback = lambda i: vself.check_answer(i, options[1])
                vself._opt3 = discord.ui.Button(label=str(options[2]), style=discord.ButtonStyle.primary)
                vself._opt3.callback = lambda i: vself.check_answer(i, options[2])

                container = discord.ui.Container(
                    *[
                        discord.ui.TextDisplay(content="**🛒 Cashier Minigame**"),
                        discord.ui.TextDisplay(content=f"Customer paid with a larger bill.\nSelect the correct change for **{amount}** credits."),
                        discord.ui.ActionRow(vself._opt1, vself._opt2, vself._opt3),
                    ],
                    accent_color=discord.Color.blue().value
                )
                vself.add_item(container)

            async def check_answer(vself, inter: discord.Interaction, selected: int):
                if inter.user.id != self.author_id:
                    await inter.response.send_message("not ur button.", ephemeral=True)
                    return

                if vself.done:
                    await inter.response.send_message("Already done!", ephemeral=True)
                    return

                vself.done = True
                if selected == self.correct_change:
                    await inter.response.edit_message(
                        view=work_success_layout("cashier", self.payout)
                    )
                    await update_credits(self.author_id, self.payout)
                    await update_work_timestamp(self.author_id, int(time.time()))
                    await self.on_complete()
                else:
                    await inter.response.edit_message(
                        view=minigame_layout("❌ Wrong", "That wasn't the right change.", discord.Color.red().value)
                    )
                vself.stop()

        await interaction.response.edit_message(view=ChangeView(self.correct_change))


class LibrarianView(LayoutView):
    """Librarian minigame - unscramble word."""

    def __init__(
        self,
        author_id: int,
        payout: int,
        on_complete: Callable[[], Coroutine[Any, Any, None]],
        timeout: float = 15.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.payout = payout
        self.on_complete = on_complete
        self.completed = False
        self.original, self.scrambled = generate_scrambled_word()

        self._btn = discord.ui.Button(
            label="Unscramble",
            style=discord.ButtonStyle.primary
        )
        self._btn.callback = self._start_callback

        container = discord.ui.Container(
            *[
                discord.ui.TextDisplay(content="**📚 Librarian Minigame**"),
                discord.ui.TextDisplay(content="Ready to unscramble? Click to start!"),
                discord.ui.ActionRow(self._btn),
            ],
            accent_color=discord.Color.blue().value
        )
        self.add_item(container)

    async def _start_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return

        if self.completed:
            return await interaction.response.send_message(
                "Already completed!", ephemeral=True
            )

        class AnswerModal(discord.ui.Modal):
            def __init__(m, scrambled: str, original: str, payout: int, author: int, on_done):
                super().__init__(title="Enter the Unscrambled Word")
                m.original = original
                m.payout = payout
                m.author_id = author
                m.on_done = on_done
                m.answer = discord.ui.TextInput(
                    label="Your answer",
                    placeholder=f"Unscramble: {scrambled}",
                    style=discord.TextStyle.short
                )
                m.add_item(m.answer)

            async def on_submit(m, inter: discord.Interaction):
                if inter.user.id != m.author_id:
                    await inter.response.send_message("not ur button.", ephemeral=True)
                    return

                self.completed = True
                answer = str(m.answer.value).upper().strip()

                if answer == m.original:
                    await inter.response.edit_message(
                        view=work_success_layout("librarian", m.payout)
                    )
                    await update_credits(m.author_id, m.payout)
                    await update_work_timestamp(m.author_id, int(time.time()))
                    await m.on_done()
                else:
                    await inter.response.edit_message(
                        view=minigame_layout("❌ Wrong", f"Wrong! It was **{m.original}**.", discord.Color.red().value)
                    )
                self.stop()

        await interaction.response.send_modal(
            AnswerModal(self.scrambled, self.original, self.payout, self.author_id, self.on_complete)
        )


class DeveloperView(LayoutView):
    """Developer minigame - typing challenge."""

    def __init__(
        self,
        author_id: int,
        payout: int,
        on_complete: Callable[[], Coroutine[Any, Any, None]],
        timeout: float = 20.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.payout = payout
        self.on_complete = on_complete
        self.completed = False
        self.snippets = [
            "def main():\n    return 42",
            "x = 1 + 2\nprint(x)",
            "for i in range(5):\n    print(i)",
            "if True:\n    pass",
        ]
        self.snippet = random.choice(self.snippets)

        self._btn = discord.ui.Button(
            label="Start Typing Test",
            style=discord.ButtonStyle.primary
        )
        self._btn.callback = self._start_callback

        container = discord.ui.Container(
            *[
                discord.ui.TextDisplay(content="**💻 Developer Minigame**"),
                discord.ui.TextDisplay(content="Ready to type? Click to start!"),
                discord.ui.ActionRow(self._btn),
            ],
            accent_color=discord.Color.blue().value
        )
        self.add_item(container)

    async def _start_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return

        if self.completed:
            return await interaction.response.send_message(
                "Already completed!", ephemeral=True
            )

        class TypingModal(discord.ui.Modal):
            def __init__(m, target_snippet: str, payout: int, author: int, on_done):
                super().__init__(title="Type the Code")
                m.target = target_snippet
                m.payout = payout
                m.author_id = author
                m.on_done = on_done
                m.answer = discord.ui.TextInput(
                    label="Your code",
                    placeholder="Type exactly...",
                    style=discord.TextStyle.long,
                    default=target_snippet
                )
                m.add_item(m.answer)

            async def on_submit(m, inter: discord.Interaction):
                if inter.user.id != m.author_id:
                    await inter.response.send_message("not ur button.", ephemeral=True)
                    return

                self.completed = True
                answer = str(m.answer.value).strip()

                if answer == m.target:
                    await inter.response.edit_message(
                        view=work_success_layout("developer", m.payout)
                    )
                    await update_credits(m.author_id, m.payout)
                    await update_work_timestamp(m.author_id, int(time.time()))
                    await m.on_done()
                else:
                    await inter.response.edit_message(
                        view=minigame_layout("❌ Wrong", "Code didn't match exactly.", discord.Color.red().value)
                    )
                self.stop()

        await interaction.response.send_modal(
            TypingModal(self.snippet, self.payout, self.author_id, self.on_complete)
        )


class TraderView(LayoutView):
    """Trader minigame - solve math equation."""

    def __init__(
        self,
        author_id: int,
        payout: int,
        on_complete: Callable[[], Coroutine[Any, Any, None]],
        timeout: float = 15.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.payout = payout
        self.on_complete = on_complete
        self.completed = False
        self.answer, self.problem = generate_math_problem()

        self._btn = discord.ui.Button(
            label="Solve Equation",
            style=discord.ButtonStyle.primary
        )
        self._btn.callback = self._start_callback

        container = discord.ui.Container(
            *[
                discord.ui.TextDisplay(content="**📈 Stock Trader Minigame**"),
                discord.ui.TextDisplay(content="Ready to solve equations? Click to start!"),
                discord.ui.ActionRow(self._btn),
            ],
            accent_color=discord.Color.blue().value
        )
        self.add_item(container)

    async def _start_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return

        if self.completed:
            return await interaction.response.send_message(
                "Already completed!", ephemeral=True
            )

        class MathModal(discord.ui.Modal):
            def __init__(m, target_answer: int, problem: str, payout: int, author: int, on_done):
                super().__init__(title="Enter the Answer")
                m.target = target_answer
                m.problem = problem
                m.payout = payout
                m.author_id = author
                m.on_done = on_done
                m.answer_input = discord.ui.TextInput(
                    label="Your answer",
                    placeholder="Type the number...",
                    style=discord.TextStyle.short
                )
                m.add_item(m.answer_input)

            async def on_submit(m, inter: discord.Interaction):
                if inter.user.id != m.author_id:
                    await inter.response.send_message("not ur button.", ephemeral=True)
                    return

                self.completed = True
                try:
                    answer = int(str(m.answer_input.value).strip())
                except ValueError:
                    await inter.response.edit_message(
                        view=minigame_layout("❌ Error", "Please enter a valid number.", discord.Color.red().value)
                    )
                    return

                if answer == m.target:
                    await inter.response.edit_message(
                        view=work_success_layout("trader", m.payout)
                    )
                    await update_credits(m.author_id, m.payout)
                    await update_work_timestamp(m.author_id, int(time.time()))
                    await m.on_done()
                else:
                    await inter.response.edit_message(
                        view=minigame_layout("❌ Wrong", f"Wrong! The answer was **{m.target}**.", discord.Color.red().value)
                    )
                self.stop()

        await interaction.response.send_modal(
            MathModal(self.answer, self.problem, self.payout, self.author_id, self.on_complete)
        )