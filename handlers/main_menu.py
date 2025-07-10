from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import random

from utils.player_utils import get_player, get_player_stats, add_money, player_operations
from database.models import Item
from handlers.combat import initiate_fight

ADMIN_USER_ID = 8092842581  # Replace with your actual admin user ID

router = Router()

class MenuStates(StatesGroup):
    main_menu = State()
    character_sheet = State()
    inventory = State()
    settings = State()

# Constants
DAILY_BONUS_AMOUNT = 100
HEAL_COST_PER_HP = 5
REST_HEAL_AMOUNT = 0.3  # 30% health restoration
REST_COOLDOWN = 300  # 5 minutes in seconds

def get_health_bar(current: int, maximum: int, length: int = 10) -> str:
    """Enhanced health bar with better visuals"""
    if maximum <= 0:
        return "💀 МЕРТВ"
    
    percentage = current / maximum
    filled = int(percentage * length)
    empty = length - filled
    
    if current <= 0:
        return "💀 " + "⬛" * length
    elif percentage <= 0.2:
        return "❤️‍🩹 " + "🟥" * filled + "⬛" * empty
    elif percentage <= 0.5:
        return "💛 " + "🟨" * filled + "⬛" * empty
    elif percentage <= 0.8:
        return "💚 " + "🟩" * filled + "⬛" * empty
    else:
        return "💚 " + "🟩" * filled + "⬛" * empty

def get_level_progress_bar(current_exp: int, required_exp: int, length: int = 10) -> str:
    """Visual representation of level progress"""
    if required_exp <= 0:
        return "⭐ MAX"
    
    percentage = min(current_exp / required_exp, 1.0)
    filled = int(percentage * length)
    empty = length - filled
    
    return "⭐ " + "🟦" * filled + "⬜" * empty + f" ({current_exp}/{required_exp})"

def get_main_menu_keyboard(player):
    """Create the main menu with contextual options"""
    builder = InlineKeyboardBuilder()
    
    # Core actions
    builder.button(text="⚔️ Сражаться", callback_data="fight")
    
    # Character management
    builder.button(text="👤 Персонаж", callback_data="character")
    builder.button(text="🎒 Инвентарь", callback_data="inventory")
    
    # Utilities
    if player.health < player.max_health:
        builder.button(text="🏥 Лечение", callback_data="heal_menu")
    
    builder.button(text="🎁 Дневной бонус", callback_data="daily_bonus")
    builder.button(text="🛏️ Отдых", callback_data="rest")
    
    # Settings and info
    builder.button(text="📊 Статистика", callback_data="detailed_stats")
    builder.button(text="🆘 Помощь", callback_data="help")
    
    # Layout: 2 columns for main actions, then single column
    builder.adjust(1, 2, 1, 1, 1, 2)
    return builder.as_markup()

def get_character_keyboard():
    """Character sheet navigation"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🔙 Назад", callback_data="main_menu")
    
    builder.adjust(1)
    return builder.as_markup()

def get_heal_menu_keyboard(player):
    """Healing options menu"""
    builder = InlineKeyboardBuilder()
    
    missing_hp = player.max_health - player.health
    full_heal_cost = missing_hp * HEAL_COST_PER_HP
    half_heal_cost = (missing_hp // 2) * HEAL_COST_PER_HP
    
    if player.money >= full_heal_cost and missing_hp > 0:
        builder.button(text=f"💚 Полное лечение ({full_heal_cost} монет)", callback_data="heal_full")
    
    if player.money >= half_heal_cost and missing_hp > 0:
        builder.button(text=f"💛 Половина HP ({half_heal_cost} монет)", callback_data="heal_half")
    
    builder.button(text="🛏️ Отдых (бесплатно)", callback_data="rest")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    
    builder.adjust(1)
    return builder.as_markup()

def format_welcome_message(player, is_new_player=False):
    """Create an engaging welcome message"""
    health_bar = get_health_bar(player.health, player.max_health)
    
    if is_new_player:
        message = "🎉 <b>Добро пожаловать в игру, герой!</b>\n\n"
        message += "🗡️ Вас ждут эпические сражения и великие приключения!\n"
        message += "💪 Сражайтесь с монстрами, повышайте уровень и становитесь сильнее!\n\n"
    else:
        greetings = [
            "🌟 С возвращением, герой!",
            "⚔️ Готовы к новым приключениям?",
            "🏆 Время для великих свершений!",
            "🔥 Ваша легенда продолжается!",
            "💎 Добро пожаловать обратно!"
        ]
        message = f"{random.choice(greetings)}\n\n"
    
    # Player status
    message += f"👤 <b>{player.name or 'Безымянный герой'}</b> (Уровень {player.level})\n"
    message += f"{health_bar}\n"
    message += f"💰 <b>Деньги:</b> {player.money:,} монет\n"
    
    # Experience progress
    if hasattr(player, 'exp'):
        required_exp = player_operations.calculate_required_exp(player.level)
        level_bar = get_level_progress_bar(player.exp, required_exp)
        message += f"{level_bar}\n"
    
    message += "\n🎯 <b>Что хотите сделать?</b>"
    
    return message

def format_character_sheet(player):
    """Detailed character information"""
    health_bar = get_health_bar(player.health, player.max_health)
    
    message = "👤 <b>ЛИСТ ПЕРСОНАЖА</b>\n\n"
    message += f"📛 <b>Имя:</b> {player.name or 'Безымянный герой'}\n"
    message += f"⭐ <b>Уровень:</b> {player.level}\n"
    message += f"❤️ <b>Здоровье:</b> {health_bar}\n"
    message += f"💰 <b>Деньги:</b> {player.money:,} монет\n"
    
    # Stats
    message += "📊 <b>ХАРАКТЕРИСТИКИ:</b>\n\n"
    message += f"⚔️ Сила: {player.strength}\n"
    message += f"🛡️ Защита: {player.defense}\n"
    message += f"🏃 Ловкость: {getattr(player, 'agility', 10)}\n"
    message += f"🧠 Интеллект: {getattr(player, 'intelligence', 10)}\n"
    
    # Combat stats
    message += "⚔️ <b>БОЕВЫЕ ПОКАЗАТЕЛИ:</b>\n\n"
    message += f"🗡️ Атак доступно: {len(player.attacks)}\n"
    message += f"💥 Общий урон: {player.strength + sum(a.damage for a in player.attacks)}\n"
    message += f"🛡️ Общая защита: {player.defense}\n"
    
    # Experience
    if hasattr(player, 'exp'):
        required_exp = player_operations.calculate_required_exp(player.level)
        level_bar = get_level_progress_bar(player.exp, required_exp)
        message += f"✨ <b>ОПЫТ:</b>{level_bar}\n"
    
    # Play time and other stats
    if hasattr(player, 'play_time'):
        hours = player.play_time // 3600
        minutes = (player.play_time % 3600) // 60
        message += f"⏰ <b>Время игры:</b> {hours}ч {minutes}м\n"
    
    if hasattr(player, 'battles_won'):
        message += f"🏆 <b>Побед:</b> {player.battles_won}\n"
    
    if hasattr(player, 'total_damage_dealt'):
        message += f"💥 <b>Общий урон:</b> {player.total_damage_dealt:,}\n"
    
    return message

ITEMS_PER_PAGE = 10

def format_inventory_message(player, page: int = 0):
    """Show player inventory with better formatting and pagination"""
    # Ensure all items are Item objects
    processed_inventory = [item if isinstance(item, Item) else Item(name=item, type="misc") for item in player.inventory]
    
    # Sort inventory for consistent pagination
    processed_inventory.sort(key=lambda x: x.name.lower())

    total_items = len(processed_inventory)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    # Adjust page if out of bounds
    if page < 0: page = 0
    if page >= total_pages and total_pages > 0: page = total_pages - 1

    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    current_page_items = processed_inventory[start_index:end_index]
    
    message = "🎒 <b>ИНВЕНТАРЬ</b>\n"    
    if not processed_inventory:
        message += "📦 Инвентарь пуст\n"
        message += "💡 Сражайтесь с монстрами, чтобы получить предметы!"
    else:
        message += f"Страница {page + 1}/{total_pages}\n\n"
        # Group items by type for the current page
        weapons = [item for item in current_page_items if item.type == 'weapon']
        armor = [item for item in current_page_items if item.type == 'armor']
        consumables = [item for item in current_page_items if item.type == 'consumable']
        misc = [item for item in current_page_items if item.type == 'misc']
        
        if weapons:
            message += "⚔️ <b>ОРУЖИЕ:</b>\n"
            for item in weapons:
                message += f"• {item.name} (+{item.damage} урон) x{item.quantity}\n"
            message += "\n"
        
        if armor:
            message += "🛡️ <b>БРОНЯ:</b>\n"
            for item in armor:
                message += f"• {item.name} (+{item.defense} защита) x{item.quantity}\n"
            message += "\n"
        
        if consumables:
            message += "🧪 <b>РАСХОДНИКИ:</b>\n"
            for item in consumables:
                message += f"• {item.name} x{item.quantity}\n"
            message += "\n"
        
        if misc:
            message += "💎 <b>ПРОЧЕЕ:</b>\n"
            for item in misc:
                message += f"• {item.name} x{item.quantity}\n"
    
    return message

@router.message(CommandStart())
async def start_game(msg: Message, state: FSMContext):
    """Enhanced start command with rich interface"""
    try:
        player = get_player(msg.from_user.id)
        is_new_player = player.level == 1 and player.exp == 0
        
        # Set up main menu state
        await state.set_state(MenuStates.main_menu)
        await state.update_data(player_id=msg.from_user.id)
        
        # Create welcome message
        welcome_text = format_welcome_message(player, is_new_player)
        keyboard = get_main_menu_keyboard(player)
        
        # Add typing effect for new players
        if is_new_player:
            await msg.bot.send_chat_action(msg.chat.id, "typing")
            await asyncio.sleep(1.5)
        
        await msg.answer(welcome_text, reply_markup=keyboard)
        
        # Send tutorial for new players
        if is_new_player:
            await asyncio.sleep(2)
            tutorial_text = (
                "💡 <b>Быстрый старт:</b>\n"
                "• Нажмите '⚔️ Сражаться' для боя\n"
                "• Проверьте '👤 Персонаж' для характеристик\n"
                "• Используйте '🎁 Дневной бонус' для денег\n"
                "• Нажмите '🆘 Помощь' для подробного руководства"
            )
            await msg.answer(tutorial_text)
        
    except Exception:
        await msg.answer("❌ Произошла ошибка при запуске игры. Попробуйте еще раз.")

@router.message(Command("stats"))
async def stats_handler(msg: Message, state: FSMContext):
    """Enhanced stats with interactive menu"""
    try:
        player = get_player(msg.from_user.id)
        
        await state.set_state(MenuStates.character_sheet)
        await state.update_data(player_id=msg.from_user.id)
        
        character_text = format_character_sheet(player)
        keyboard = get_character_keyboard()
        
        await msg.answer(character_text, reply_markup=keyboard)
        
    except Exception:
        await msg.answer("❌ Ошибка при получении статистики.")

@router.message(Command("menu"))
async def menu_handler(msg: Message, state: FSMContext):
    """Quick access to main menu"""
    try:
        player = get_player(msg.from_user.id)
        
        await state.set_state(MenuStates.main_menu)
        await state.update_data(player_id=msg.from_user.id)
        
        menu_text = format_welcome_message(player)
        keyboard = get_main_menu_keyboard(player)
        
        await msg.answer(menu_text, reply_markup=keyboard)
        
    except Exception:
        await msg.answer("❌ Ошибка при открытии меню.")

# Callback handlers for interactive menu
@router.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Return to main menu"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        await state.set_state(MenuStates.main_menu)
        
        menu_text = format_welcome_message(player)
        keyboard = get_main_menu_keyboard(player)
        
        await callback.message.edit_text(menu_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception:
        await callback.answer("❌ Ошибка при возврате в меню!")

@router.callback_query(F.data == "character")
async def character_handler(callback: CallbackQuery, state: FSMContext):
    """Show character sheet"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        await state.set_state(MenuStates.character_sheet)
        
        character_text = format_character_sheet(player)
        keyboard = get_character_keyboard()
        
        await callback.message.edit_text(character_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception:
        await callback.answer("❌ Ошибка при отображении персонажа!")

@router.callback_query(F.data == "inventory")
async def inventory_handler(callback: CallbackQuery, state: FSMContext):
    """Show inventory"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        await state.set_state(MenuStates.inventory)
        
        inventory_text = format_inventory_message(player)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="main_menu")
        
        await callback.message.edit_text(inventory_text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        print(e)
        await callback.answer("❌ Ошибка при отображении инвентаря.")

@router.callback_query(F.data == "heal_menu")
async def heal_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Show healing options"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        if player.health >= player.max_health:
            await callback.answer("❤️ Вы уже полностью здоровы!")
            return
        
        missing_hp = player.max_health - player.health
        health_bar = get_health_bar(player.health, player.max_health)
        
        heal_text = "🏥 <b>ЛЕЧЕНИЕ</b>\n\n"
        heal_text += f"Текущее здоровье: {health_bar}\n"
        heal_text += f"Нужно восстановить: {missing_hp} HP\n"
        heal_text += f"Ваши деньги: {player.money} монет\n\n"
        heal_text += f"💰 Стоимость: {HEAL_COST_PER_HP} монет за HP\n"
        heal_text += f"🛏️ Отдых: восстанавливает {int(player.max_health * REST_HEAL_AMOUNT)} HP бесплатно\n"
        heal_text += "Выберите способ лечения:"
        
        keyboard = get_heal_menu_keyboard(player)
        await callback.message.edit_text(heal_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception:
        await callback.answer("❌ Ошибка при отображении меню лечения!")

@router.callback_query(F.data.startswith("heal_"))
async def heal_handler(callback: CallbackQuery, state: FSMContext):
    """Handle healing actions"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        heal_type = callback.data.split("_")[1]
        
        if heal_type == "full":
            missing_hp = player.max_health - player.health
            cost = missing_hp * HEAL_COST_PER_HP
            
            if player.money >= cost:
                player.health = player.max_health
                add_money(player, -cost)
                await callback.message.edit_text(
                    f"💚 Вы полностью излечились!\n"
                    f"❤️ Здоровье: {player.health}/{player.max_health}\n"
                    f"💰 Потрачено: {cost} монет\n"
                    f"💰 Осталось: {player.money} монет"
                )
                player_operations.player_manager.force_save()
            else:
                await callback.answer("❌ Недостаточно денег!")
                return
                
        elif heal_type == "half":
            missing_hp = player.max_health - player.health
            heal_amount = missing_hp // 2
            cost = heal_amount * HEAL_COST_PER_HP
            
            if player.money >= cost:
                player.health += heal_amount
                add_money(player, -cost)
                health_bar = get_health_bar(player.health, player.max_health)
                await callback.message.edit_text(
                    f"💛 Вы частично излечились!\n"
                    f"{health_bar}\n"
                    f"💰 Потрачено: {cost} монет\n"
                    f"💰 Осталось: {player.money} монет"
                )
                player_operations.player_manager.force_save()
            else:
                await callback.answer("❌ Недостаточно денег!")
                return
        
        await callback.answer()
        
    except Exception:
        await callback.answer("❌ Ошибка при лечении!")

@router.callback_query(F.data == "rest")
async def rest_handler(callback: CallbackQuery, state: FSMContext):
    """Handle rest action"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        # Check cooldown (simplified - in real app, store last_rest_time)
        heal_amount = int(player.max_health * REST_HEAL_AMOUNT)
        new_health = min(player.max_health, player.health + heal_amount)
        actual_heal = new_health - player.health
        
        if actual_heal > 0:
            player.health = new_health
            health_bar = get_health_bar(player.health, player.max_health)
            
            await callback.message.edit_text(
                f"🛏️ Вы отдохнули и восстановили {actual_heal} HP\n"
                f"{health_bar}\n"
                f"💤 Отдых доступен снова через 5 минут"
            )
        else:
            await callback.answer("❤️ Вы уже полностью здоровы!")
            return
        
        await callback.answer()
        
    except Exception:
        await callback.answer("❌ Ошибка при отдыхе!")

@router.callback_query(F.data == "daily_bonus")
async def daily_bonus_handler(callback: CallbackQuery, state: FSMContext):
    """Handle daily bonus"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        # Simplified daily bonus (in real app, check last_bonus_time)
        add_money(player, DAILY_BONUS_AMOUNT)
        
        await callback.message.edit_text(
            f"🎁 **ДНЕВНОЙ БОНУС ПОЛУЧЕН!**\n\n"
            f"💰 Получено: {DAILY_BONUS_AMOUNT} монет\n"
            f"💰 Всего денег: {player.money} монет\n\n"
            f"🕐 Следующий бонус через 24 часа"
        )
        await callback.answer("🎁 Дневной бонус получен!")
        
    except Exception:
        await callback.answer("❌ Ошибка при получении бонуса!")

@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery, state: FSMContext):
    """Show help information"""
    help_text = (
        "🆘 <b>РУКОВОДСТВО ПО ИГРЕ</b>\n\n"
        "🎮 <b>Основы:</b>\n"
        "• Сражайтесь с монстрами для получения опыта\n"
        "• Повышайте уровень для доступа к новым врагам\n"
        "• Собирайте предметы и деньги\n\n"
        "⚔️ <b>Сражения:</b>\n"
        "• Выбирайте противников по уровню сложности\n"
        "• Используйте разные атаки и защиту\n"
        "• Можете сбежать, если бой идет плохо\n\n"
        "🏥 <b>Лечение:</b>\n"
        "• Платное лечение в меню\n"
        "• Бесплатный отдых каждые 5 минут\n"
        "• При поражении теряете деньги, но не умираете\n\n"
        "💰 <b>Экономика:</b>\n"
        "• Получайте деньги за победы\n"
        "• Дневной бонус каждые 24 часа\n"
        "• Тратьте на лечение и улучшения\n\n"
        "🎯 <b>Команды:</b>\n"
        "/start - Главное меню\n"
        "/stats - Характеристики\n"
        "/fight - Быстрый бой\n"
        "/menu - Открыть меню"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")
    
    await callback.message.edit_text(help_text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "fight")
async def quick_fight_handler(callback: CallbackQuery, state: FSMContext):
    """Quick transition to fight mode"""
    await callback.answer("⚔️ Переход к бою...")
    # We call the unified fight initiation function here
    await initiate_fight(callback.from_user.id, state, callback)

@router.callback_query(F.data == "detailed_stats")
async def detailed_stats_handler(callback: CallbackQuery, state: FSMContext):
    """Show detailed statistics"""
    try:
        data = await state.get_data()
        player = get_player(data.get('player_id', callback.from_user.id))
        
        stats_text = get_player_stats(player)  # Use existing function
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="main_menu")
        
        await callback.message.edit_text(stats_text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception:
        await callback.answer("❌ Ошибка при получении статистики")

# Add command for quick menu access
@router.message(Command("heal"))
async def quick_heal_handler(msg: Message, state: FSMContext):
    """Quick heal command"""
    try:
        player = get_player(msg.from_user.id)
        
        if player.health >= player.max_health:
            await msg.answer("❤️ Вы уже полностью здоровы!")
            return
        
        await state.set_state(MenuStates.main_menu)
        await state.update_data(player_id=msg.from_user.id)
        
        heal_text = "🏥 <b>БЫСТРОЕ ЛЕЧЕНИЕ</b>\n\n"
        heal_text += f"Текущее здоровье: {get_health_bar(player.health, player.max_health)}\n\n"
        
        keyboard = get_heal_menu_keyboard(player)
        await msg.answer(heal_text, reply_markup=keyboard)
        
    except Exception:
        await msg.answer("❌ Ошибка при лечении.")

@router.message(Command("inventory"))
async def quick_inventory_handler(msg: Message, state: FSMContext):
    """Quick inventory command"""
    try:
        player = get_player(msg.from_user.id)
        
        await state.set_state(MenuStates.inventory)
        await state.update_data(player_id=msg.from_user.id, inventory_page=0)
        
        inventory_text = format_inventory_message(player, page=0)
        
        builder = InlineKeyboardBuilder()
        total_items = len(player.inventory)
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        if total_pages > 1:
            if 0 > 0:
                builder.button(text="⬅️ Назад", callback_data=f"inventory_page_prev_{0}")
            builder.button(text=f"{0 + 1}/{total_pages}", callback_data="_ignore")
            if 0 < total_pages - 1:
                builder.button(text="Вперед ➡️", callback_data=f"inventory_page_next_{0}")
            builder.adjust(3)
        
        builder.row(InlineKeyboardBuilder().button(text="🔙 Главное меню", callback_data="main_menu").as_markup().inline_keyboard[0][0])
        
        await msg.answer(inventory_text, reply_markup=builder.as_markup())
        
    except Exception:
        await msg.answer("❌ Ошибка при отображении инвентаря.")

@router.callback_query(F.data.startswith("inventory_page_prev_"))
async def inventory_page_prev_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    player = get_player(data.get('player_id', callback.from_user.id))
    current_page = int(callback.data.split("_")[3])
    new_page = max(0, current_page - 1)
    await state.update_data(inventory_page=new_page)
    await inventory_handler(callback, state)

@router.callback_query(F.data.startswith("inventory_page_next_"))
async def inventory_page_next_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    player = get_player(data.get('player_id', callback.from_user.id), callback.from_user.full_name)
    current_page = int(callback.data.split("_")[3])
    total_items = len(player.inventory)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    new_page = min(total_pages - 1, current_page + 1)
    await state.update_data(inventory_page=new_page)
    await inventory_handler(callback, state)

@router.message(F.text.startswith('+стата') | F.text.startswith('-стата'))
async def admin_stat_handler(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_USER_ID:
        await msg.reply("❌ У вас нет прав для использования этой команды.")
        return

    if not msg.reply_to_message:
        await msg.reply("❌ Эта команда должна быть ответом на сообщение игрока, чью статистику вы хотите изменить.")
        return

    target_user_id = msg.reply_to_message.from_user.id
    command_parts = msg.text.split()

    if len(command_parts) < 3:
        await msg.reply("❌ Неверный формат команды. Используйте: `+стата [характеристика] [количество]` или `-стата [характеристика] [количество]`")
        return

    stat_name_ru = command_parts[1].lower()
    try:
        amount = int(command_parts[2])
    except ValueError:
        await msg.reply("❌ Количество должно быть числом.")
        return

    if msg.text.startswith('-стата'):
        amount = -amount

    # Map Russian names to internal English names
    STAT_NAME_MAP = {
        'здоровье': 'health',
        'макс_здоровье': 'max_health',
        'деньги': 'money',
        'уровень': 'level',
        'опыт': 'exp',
        'сила': 'strength',
        'защита': 'defense',
        'ловкость': 'agility',
        'интеллект': 'intelligence',
        'время_игры': 'play_time',
        'побед': 'battles_won',
        'урон_нанесен': 'total_damage_dealt'
    }

    if stat_name_ru not in STAT_NAME_MAP:
        await msg.reply(f"❌ Характеристика '{stat_name_ru}' не найдена. Доступные: {', '.join(STAT_NAME_MAP.keys())}")
        return
    
    stat_name_en = STAT_NAME_MAP[stat_name_ru]

    try:
        player = get_player(target_user_id, msg.reply_to_message.from_user.full_name)
        
        current_value = getattr(player, stat_name_en)
        setattr(player, stat_name_en, current_value + amount)
        
        # Special handling for health to not exceed max_health
        if stat_name_en == 'health' and player.health > player.max_health:
            player.health = player.max_health
        
        player_operations.player_manager.force_save()
        await msg.reply(f"✅ Статистика '{stat_name_ru}' игрока {player.name} (ID: {target_user_id}) изменена на {amount}. Новое значение: {getattr(player, stat_name_en)}")

    except Exception as e:
        await msg.reply(f"❌ Произошла ошибка при изменении статистики: {e}")