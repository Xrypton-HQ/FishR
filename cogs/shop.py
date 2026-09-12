import discord
import time
from discord.ext import commands
from typing import Optional
import logging

from utils.database import (
    get_user, create_user, safe_deduct_credits, safe_update_fish,
    get_upgrades, get_buffs, set_frenzy_until, update_upgrade, get_inventory
)
from utils.embeds import shop_view, error_layout, create_container, inventory_view
from utils.constants import UPGRADES, EMOJI_FISH, EMOJI_CREDITS, COLOR_SUCCESS, EMOJI_VERIFY
from config import FRENZY_PRICE, FRENZY_DURATION

logger = logging.getLogger(__name__)


class ShopView(discord.ui.LayoutView):
    def __init__(self, user_data: dict, cog, author_id: int, ctx: commands.Context):
        super().__init__()
        self.cog = cog
        self.author_id = author_id
        self.user_data = user_data
        self.ctx = ctx
        self.selected_item = None
        self.selected_quantity = None

        container = shop_view(user_data).children[0]

        for child in container.children:
            if isinstance(child, discord.ui.ActionRow):
                for component in child.children:
                    if isinstance(component, discord.ui.Select):
                        if component.custom_id == "502487d1255d431dd59cd93aac88b028":
                            component.callback = self._item_select_callback
                        elif component.custom_id == "4051a5da010a49c2bc9038c8b70bc820":
                            component.callback = self._quantity_select_callback

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This interaction is not for you.", ephemeral=True)
            return False
        return True

    async def _item_select_callback(self, interaction: discord.Interaction):
        self.selected_item = interaction.data["values"][0]
        if self.selected_quantity:
            await self._process_purchase(interaction)
        else:
            await interaction.response.defer()

    async def _quantity_select_callback(self, interaction: discord.Interaction):
        quantity_value = interaction.data["values"][0]
        QUANTITY_MAP = {
            "4450ffd035cb4c6ed308863827be4e34": 1,
            "9a64ba4aa0b74f00e8b3ab9f1fac93a0": 5,
            "e3f1c5b357ff4325e8e5e42962582367": 10,
            "d614625aef204590a19204c02bcd0431": 0,
        }
        if quantity_value not in QUANTITY_MAP:
            await interaction.response.send_message(
                view=error_layout("Invalid quantity selected."),
                ephemeral=True
            )
            return

        if quantity_value == "d614625aef204590a19204c02bcd0431":
            user = await get_user(self.ctx.author.id)
            credits = user["credits"] if user else 0
            upgrades_row = await get_upgrades(self.ctx.author.id)
            current = 0 if self.selected_item == "frenzy" else (upgrades_row[self.selected_item] if upgrades_row else 0)
            self.selected_quantity = self.cog._calculate_max_affordable(self.selected_item, current, credits)
        else:
            self.selected_quantity = QUANTITY_MAP[quantity_value]

        if self.selected_item:
            await self._process_purchase(interaction)
        else:
            await interaction.response.defer()

    async def _process_purchase(self, interaction: discord.Interaction):
        if not self.selected_item or not self.selected_quantity:
            return

        success, message = await self.cog._purchase_upgrade(self.ctx.author.id, self.selected_item, self.selected_quantity)

        if success:
            self.selected_item = None
            self.selected_quantity = None
            upgrades = await get_upgrades(self.ctx.author.id)
            buffs = await get_buffs(self.ctx.author.id)
            self.user_data = {
                "stronger_rod": upgrades["stronger_rod"],
                "new_rod": upgrades["new_rod"],
                "frenzy": 1 if buffs["frenzy_until"] > 0 else 0,
            }
            new_container = shop_view(self.user_data).children[0]
            self.children[0] = new_container
            for child in new_container.children:
                if isinstance(child, discord.ui.ActionRow):
                    for component in child.children:
                        if isinstance(component, discord.ui.Select):
                            if component.custom_id == "502487d1255d431dd59cd93aac88b028":
                                component.callback = self._item_select_callback
                            elif component.custom_id == "4051a5da010a49c2bc9038c8b70bc820":
                                component.callback = self._quantity_select_callback
            await interaction.response.edit_message(view=self)
            await self.ctx.send(
                view=create_container(
                    title=f"{EMOJI_VERIFY} Purchase Successful",
                    description=message,
                    color=discord.Color.green().value
                ),
                delete_after=5
            )
        else:
            await interaction.response.send_message(
                view=error_layout(message),
                ephemeral=True
            )


class Shop(commands.Cog):
    """Shop system for upgrades."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _calculate_single_price(
        self, upgrade_key: str, level: int
    ) -> int:
        """Calculate price for a single level of upgrade."""
        upgrade = UPGRADES[upgrade_key]
        base_price = upgrade["base_price"]
        multiplier = upgrade["price_multiplier"]
        return int(base_price * (multiplier ** (level - 1)))

    def _calculate_total_price(
        self, upgrade_key: str, current_level: int, quantity: int
    ) -> int:
        """Calculate total price for quantity of upgrade."""
        if upgrade_key == "frenzy":
            return UPGRADES["frenzy"]["base_price"] * quantity

        total = 0
        for i in range(quantity):
            level = current_level + i
            total += self._calculate_single_price(upgrade_key, level + 1)
        return total

    def _calculate_max_affordable(
        self, upgrade_key: str, current_level: int, credits: int
    ) -> int:
        """Calculate maximum quantity affordable for given upgrade."""
        if credits <= 0:
            return 0

        if upgrade_key == "frenzy":
            price = UPGRADES["frenzy"]["base_price"]
            return credits // price

        max_qty = 0
        total = 0
        for i in range(1, 101):  # up to 100 purchases
            cost = self._calculate_single_price(upgrade_key, current_level + i)
            if total + cost > credits:
                break
            total += cost
            max_qty += 1
        return max_qty

    async def _purchase_upgrade(
        self, user_id: int, upgrade_key: str, quantity: int
    ) -> tuple[bool, str]:
        """Process an upgrade purchase atomically."""
        try:
            await create_user(user_id)

            if upgrade_key == "frenzy":
                total_price = UPGRADES["frenzy"]["base_price"] * quantity
                if not await safe_deduct_credits(user_id, total_price):
                    user = await get_user(user_id)
                    have = user["credits"] if user else 0
                    return False, f"Not enough credits. Need {total_price}, have {have}."

                import time
                new_end = int(time.time()) + (FRENZY_DURATION * quantity)
                await set_frenzy_until(user_id, new_end)
                return True, f"Successfully purchased Fishing Frenzy ({quantity}x) for {total_price} credits!"
            else:
                upgrades = await get_upgrades(user_id)
                current_level = upgrades[upgrade_key] if upgrades else 0
                total_price = self._calculate_total_price(upgrade_key, current_level, quantity)

                if not await safe_deduct_credits(user_id, total_price):
                    user = await get_user(user_id)
                    have = user["credits"] if user else 0
                    return False, f"Not enough credits. Need {total_price}, have {have}."

                new_level = current_level + quantity
                await update_upgrade(user_id, upgrade_key, new_level)
                name = UPGRADES[upgrade_key]["name"]
                return True, f"Successfully purchased {quantity}x {name} for {total_price} credits! New level: {new_level}"

        except Exception as e:
            logger.error(f"Purchase error: {e}", exc_info=True)
            return False, "An error occurred during purchase."

    @commands.hybrid_command(name="shop")
    async def shop(self, ctx: commands.Context):
        """Display the upgrade shop."""
        user_id = ctx.author.id
        await create_user(user_id)

        upgrades_data = await get_upgrades(user_id)
        buffs_data = await get_buffs(user_id)

        user_data = {
            "stronger_rod": upgrades_data["stronger_rod"] if upgrades_data else 0,
            "new_rod": upgrades_data["new_rod"] if upgrades_data else 0,
            "frenzy": 1 if buffs_data and buffs_data["frenzy_until"] > 0 else 0,
        }

        view = ShopView(user_data, self, ctx.author.id, ctx)
        await ctx.send(view=view)

    @commands.hybrid_command(name="inventory", aliases=["inv"])
    async def inventory(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ):
        """Show your inventory and active buffs."""
        target = member or ctx.author
        user_id = target.id
        await create_user(user_id)

        inv = await get_inventory(user_id)
        upgrades = await get_upgrades(user_id)
        buffs = await get_buffs(user_id)

        view = inventory_view(target, inv["fish"], upgrades, buffs["frenzy_until"])
        await ctx.send(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
