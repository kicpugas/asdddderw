from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import random
import asyncio

from utils.enemies import enemy_manager, Enemy
from utils.drop_system import MonsterDropManager

monster_drop_manager = MonsterDropManager()
from utils.player_utils import get_player, add_item_to_inventory, add_exp, add_money, player_manager
from database.models import Item

router = Router()

# Constants for better maintainability
DEFEAT_HEALTH_RESTORE = 0.5
DEFEAT_MONEY_LOSS = 0.1
CRITICAL_HIT_CHANCE = 0.15
CRITICAL_HIT_MULTIPLIER = 1.5
COMBAT_TIMEOUT = 300  # 5 minutes

class GameStates(StatesGroup):
    in_combat = State()
    selecting_enemy = State()

def get_health_bar(current: int, maximum: int, length: int = 10) -> str:
    """Generate a visual health bar"""
    if maximum <= 0:
        return "💀"
    
    filled = int((current / maximum) * length)
    empty = length - filled
    
    if current <= 0:
        return "💀" + "⬜" * (length - 1)
    elif current <= maximum * 0.2:
        return "🟥" * filled + "⬜" * empty
    elif current <= maximum * 0.5:
        return "🟨" * filled + "⬜" * empty
    else:
        return "🟩" * filled + "⬜" * empty

def get_combat_keyboard(player, enemy):
    """Enhanced keyboard with more options"""
    builder = InlineKeyboardBuilder()
    
    # Attack buttons with damage preview
    for i, attack in enumerate(player.attacks):
        estimated_damage = max(0, player.strength + attack.damage - enemy.defense)
        accuracy_icon = "🎯" if attack.accuracy >= 0.8 else "⚡" if attack.accuracy >= 0.6 else "💫"
        builder.button(
            text=f"{accuracy_icon} {attack.name} (~{estimated_damage} dmg)",
            callback_data=f"attack_{i}"
        )
    
    # Add utility buttons
    builder.button(text="🛡️ Защита", callback_data="defend")
    builder.button(text="🏃 Бежать", callback_data="flee")
    builder.button(text="📊 Статистика", callback_data="stats")
    
    builder.adjust(1, 1, 1, 2)  # Layout: attacks in column, then defend/flee in row
    return builder.as_markup()

def get_enemy_selection_keyboard(available_enemies, player_level):
    """Allow players to choose their opponent"""
    builder = InlineKeyboardBuilder()
    
    for enemy in available_enemies:
        difficulty = "🟢" if enemy.level < player_level else "🟡" if enemy.level == player_level else "🔴"
        builder.button(
            text=f"{difficulty} {enemy.name} (ур.{enemy.level})",
            callback_data=f"select_enemy_{enemy.name}"
        )
    
    builder.button(text="🎲 Случайный враг", callback_data="random_enemy")
    builder.button(text="❌ Отмена", callback_data="cancel_fight")
    builder.adjust(1)
    return builder.as_markup()



def format_combat_message(player, enemy, last_action="", turn_count=0):
    """Create a rich, informative combat message"""
    player_health_bar = get_health_bar(player.health, player.max_health)
    enemy_health_bar = get_health_bar(enemy.health, enemy.max_health)
    
    message = f"⚔️ <b>БОЙ</b> (Раунд {turn_count})\n\n"
    
    # Player status
    message += f"🧙‍♂️ <b>Вы</b> (ур.{player.level})\n"
    message += f"{player_health_bar} {player.health}/{player.max_health} HP\n"
    message += f"⚔️ Сила: {player.strength} | 🛡️ Защита: {player.defense}\n\n"
    
    # Enemy status  
    message += f"👹 <b>{enemy.name}</b> (ур.{enemy.level})\n"
    message += f"{enemy_health_bar} {enemy.health} HP\n"
    message += f"⚔️ Сила: {enemy.strength} | 🛡️ Защита: {enemy.defense}\n\n"
    
    # Last action
    if last_action:
        message += f"📝 <b>Последнее действие:</b>\n{last_action}\n\n"
    
    message += "🎯 <b>Выберите действие:</b>"
    
    return message



async def initiate_fight(user_id: int, state: FSMContext, source: Message | CallbackQuery):
    """Unified logic to start a fight from a command or callback."""
    try:
        player = get_player(user_id)

        if isinstance(source, Message):
            responder = source.answer
        else: # CallbackQuery
            responder = source.message.edit_text

        if not player:
            await responder("❌ Игрок не найден. Используйте /start для регистрации.")
            return
        if player.health <= 0:
            await responder("💀 Вы не можете сражаться с 0 HP! Используйте /heal для восстановления.")
            return

        available_enemies = [e for e in enemy_manager.get_all_enemies().values() if e.level <= player.level + 2]
        if not available_enemies:
            await responder("🚫 Пока нет доступных врагов для вашего уровня.")
            return

        await state.set_state(GameStates.selecting_enemy)
        await state.update_data(player_id=user_id, available_enemies=[e.to_dict() for e in available_enemies])
        keyboard = get_enemy_selection_keyboard(available_enemies, player.level)
        
        await responder(
            f"🎯 <b>Выберите противника:</b>\n\n"
            f"🟢 - Легкий\n🟡 - Равный\n🔴 - Сложный\n\n"
            f"Ваш уровень: {player.level}",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Error in initiate_fight: {e}")
        error_message = "❌ Произошла ошибка при начале боя."
        if isinstance(source, Message):
            await source.answer(error_message)
        else:
            # In case of callback, just send a new message as something went wrong
            await source.message.answer(error_message)
        await state.clear()


@router.message(Command("fight"))
async def fight_handler(msg: Message, state: FSMContext):
    """Handles the /fight command by calling the unified fight logic."""
    await initiate_fight(msg.from_user.id, state, msg)



@router.callback_query(GameStates.in_combat, F.data.startswith("attack_"))
async def attack_handler(callback: CallbackQuery, state: FSMContext):
    """Enhanced attack handler with better feedback"""
    try:
        data = await state.get_data()
        player = get_player(data['player_id'])
        enemy = Enemy.from_dict(data['enemy'])
        turn_count = data.get('turn_count', 1)
        
        # Validate attack
        try:
            attack_index = int(callback.data.split("_")[1])
            if attack_index >= len(player.attacks):
                await callback.answer("❌ Неверная атака!")
                return
        except (ValueError, IndexError):
            await callback.answer("❌ Неверная атака!")
            return
        
        attack = player.attacks[attack_index]
        action_log = ""
        
        # Player's turn with enhanced feedback
        await callback.bot.send_chat_action(callback.message.chat.id, "typing")
        await asyncio.sleep(0.5)
        
        if random.random() < attack.accuracy:
            base_damage = max(0, player.strength + attack.damage - enemy.defense)
            is_critical = random.random() < CRITICAL_HIT_CHANCE
            
            if is_critical:
                damage = int(base_damage * CRITICAL_HIT_MULTIPLIER)
                action_log = f"💥 <b>КРИТИЧЕСКИЙ УДАР!</b>\n🗡️ Вы нанесли {damage} урона атакой '{attack.name}'"
            else:
                damage = base_damage
                action_log = f"🗡️ Вы нанесли {damage} урона атакой '{attack.name}'"
            
            enemy.health -= damage
            player.total_damage_dealt += damage
        else:
            action_log = f"💨 Промах! Атака '{attack.name}' не достигла цели"
        
        # Check for victory
        if enemy.health <= 0:
            await handle_victory(callback, state, player, enemy, action_log)
            return
        
        # Enemy's turn
        await asyncio.sleep(1)
        enemy_attack = random.choice(enemy.attacks)
        
        if random.random() < enemy_attack.accuracy:
            enemy_damage = max(0, enemy.strength + enemy_attack.damage - player.defense)
            player.health -= enemy_damage
            action_log += f"\n🩸 {enemy.name} нанес вам {enemy_damage} урона атакой '{enemy_attack.name}'"
        else:
            action_log += f"\n🛡️ Вы уклонились от атаки '{enemy_attack.name}'"
        
        # Check for defeat
        if player.health <= 0:
            await handle_defeat(callback, state, player, action_log)
            return
        
        # Continue combat
        turn_count += 1
        await state.update_data(enemy=enemy.to_dict(), turn_count=turn_count)
        player_manager.force_save()
        message = format_combat_message(player, enemy, action_log, turn_count)
        keyboard = get_combat_keyboard(player, enemy)
        
        await callback.message.edit_text(message, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        print(e)
        await callback.answer("❌ Ошибка во время атаки!")
        await state.clear()

@router.callback_query(GameStates.selecting_enemy)
async def enemy_selection_handler(callback: CallbackQuery, state: FSMContext):
    """Handle enemy selection"""
    try:
        data = await state.get_data()
        player = get_player(data['player_id'])
        available_enemies = [Enemy.from_dict(e) for e in data['available_enemies']]
        
        if callback.data == "cancel_fight":
            await callback.message.edit_text("❌ Бой отменен.")
            await state.clear()
            return
        
        if callback.data == "random_enemy":
            enemy = random.choice(available_enemies)
        else:
            enemy_name = callback.data.split("select_enemy_")[1]
            enemy = next((e for e in available_enemies if e.name == enemy_name), None)
            if not enemy:
                await callback.answer("❌ Враг не найден!")
                return
        
        # Start combat
        await state.set_state(GameStates.in_combat)
        await state.update_data(
            enemy=enemy.to_dict(),
            player_id=data['player_id'],
            turn_count=1,
            combat_log=[]
        )
        
        # Show dramatic combat start
        await callback.bot.send_chat_action(callback.message.chat.id, "typing")
        await asyncio.sleep(1)
        
        message = format_combat_message(player, enemy, turn_count=1)
        keyboard = get_combat_keyboard(player, enemy)
        
        await callback.message.edit_text(message, reply_markup=keyboard)
        
    except Exception as e:
        print(e)
        await callback.answer("❌ Ошибка при выборе врага!")
        await state.clear()
async def attack_handler(callback: CallbackQuery, state: FSMContext):
    """Enhanced attack handler with better feedback"""
    try:
        data = await state.get_data()
        player = get_player(data['player_id'])
        enemy = Enemy.from_dict(data['enemy'])
        turn_count = data.get('turn_count', 1)
        
        # Validate attack
        try:
            attack_index = int(callback.data.split("_")[1])
            if attack_index >= len(player.attacks):
                await callback.answer("❌ Неверная атака!")
                return
        except (ValueError, IndexError):
            await callback.answer("❌ Неверная атака!")
            return
        
        attack = player.attacks[attack_index]
        action_log = ""
        
        # Player's turn with enhanced feedback
        await callback.bot.send_chat_action(callback.message.chat.id, "typing")
        await asyncio.sleep(0.5)
        
        if random.random() < attack.accuracy:
            base_damage = max(0, player.strength + attack.damage - enemy.defense)
            is_critical = random.random() < CRITICAL_HIT_CHANCE
            
            if is_critical:
                damage = int(base_damage * CRITICAL_HIT_MULTIPLIER)
                action_log = f"💥 <b>КРИТИЧЕСКИЙ УДАР!</b>\n🗡️ Вы нанесли {damage} урона атакой '{attack.name}'"
            else:
                damage = base_damage
                action_log = f"🗡️ Вы нанесли {damage} урона атакой '{attack.name}'"
            
            enemy.health -= damage
            player.total_damage_dealt += damage
        else:
            action_log = f"💨 Промах! Атака '{attack.name}' не достигла цели"
        
        # Check for victory
        if enemy.health <= 0:
            await handle_victory(callback, state, player, enemy, action_log)
            return
        
        # Enemy's turn
        await asyncio.sleep(1)
        enemy_attack = random.choice(enemy.attacks)
        
        if random.random() < enemy_attack.accuracy:
            enemy_damage = max(0, enemy.strength + enemy_attack.damage - player.defense)
            player.health -= enemy_damage
            action_log += f"\n🩸 {enemy.name} нанес вам {enemy_damage} урона атакой '{enemy_attack.name}'"
        else:
            action_log += f"\n🛡️ Вы уклонились от атаки '{enemy_attack.name}'"
        
        # Check for defeat
        if player.health <= 0:
            await handle_defeat(callback, state, player, action_log)
            return
        
        # Continue combat
        turn_count += 1
        await state.update_data(enemy=enemy.to_dict(), turn_count=turn_count)
        player_manager.force_save()
        message = format_combat_message(player, enemy, action_log, turn_count)
        keyboard = get_combat_keyboard(player, enemy)
        
        await callback.message.edit_text(message, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        print(e)
        await callback.answer("❌ Ошибка во время атаки!")
        await state.clear()

@router.callback_query(GameStates.in_combat, F.data == "defend")
async def defend_handler(callback: CallbackQuery, state: FSMContext):
    """Handle defend action"""
    try:
        data = await state.get_data()
        player = get_player(data['player_id'])
        enemy = Enemy.from_dict(data['enemy'])
        turn_count = data.get('turn_count', 1)
        
        # Player defends (reduces incoming damage)
        defense_bonus = player.defense // 2
        action_log = f"🛡️ Вы заняли оборонительную позицию (\+{defense_bonus} защиты)"
        
        # Enemy's turn with reduced damage
        enemy_attack = random.choice(enemy.attacks)
        if random.random() < enemy_attack.accuracy:
            enemy_damage = max(0, enemy.strength + enemy_attack.damage - (player.defense + defense_bonus))
            player.health -= enemy_damage
            action_log += f"\n🩸 {enemy.name} нанес вам {enemy_damage} урона (заблокировано {defense_bonus})"
        else:
            action_log += f"\n🛡️ Вы полностью заблокировали атаку '{enemy_attack.name}'"
        
        if player.health <= 0:
            await handle_defeat(callback, state, player, action_log)
            return
        
        turn_count += 1
        await state.update_data(turn_count=turn_count)
        
        message = format_combat_message(player, enemy, action_log, turn_count)
        keyboard = get_combat_keyboard(player, enemy)
        
        await callback.message.edit_text(message, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        print(e)
        await callback.answer("❌ Ошибка при защите!")

@router.callback_query(GameStates.in_combat, F.data == "flee")
async def flee_handler(callback: CallbackQuery, state: FSMContext):
    """Handle flee action"""
    try:
        data = await state.get_data()
        player = get_player(data['player_id'], callback.from_user.full_name)
        enemy = Enemy.from_dict(data['enemy'])
        
        # 70% chance to flee successfully
        if random.random() < 0.7:
            await callback.message.edit_text(
                f"🏃 Вы успешно сбежали от {enemy.name}!\n"
                f"💰 Потеряно 5% денег за трусость."
            )
            add_money(player, -max(1, player.money // 20))  # Lose 5% money
        else:
            # Failed to flee, enemy gets a free attack
            enemy_attack = random.choice(enemy.attacks)
            enemy_damage = max(0, enemy.strength + enemy_attack.damage - player.defense)
            player.health -= enemy_damage
            
            if player.health <= 0:
                await handle_defeat(callback, state, player, f"💨 Побег не удался! {enemy.name} нанес {enemy_damage} урона")
                return
            
            await state.update_data(turn_count=data.get('turn_count', 1) + 1)
            
            action_log = f"💨 Побег не удался! {enemy.name} нанес {enemy_damage} урона"
            message = format_combat_message(player, enemy, action_log, data.get('turn_count', 1) + 1)
            keyboard = get_combat_keyboard(player, enemy)
            
            await callback.message.edit_text(message, reply_markup=keyboard)
            await callback.answer("Побег не удался")
            return
        
        await state.clear()
        
    except Exception:
        await callback.answer("❌ Ошибка при попытке бегства!")

@router.callback_query(GameStates.in_combat, F.data == "stats")
async def stats_handler(callback: CallbackQuery, state: FSMContext):
    """Show detailed combat statistics"""
    try:
        data = await state.get_data()
        player = get_player(data['player_id'])
        enemy = Enemy.from_dict(data['enemy'])
        
        stats_text = "📊 <b>Статистика боя:</b>\n\n"
        stats_text += "👤 <b>Ваши характеристики:</b>\n"
        stats_text += f"❤️ Здоровье: {player.health}/{player.max_health}\n"
        stats_text += f"⚔️ Сила: {player.strength}\n"
        stats_text += f"🛡️ Защита: {player.defense}\n"
        stats_text += f"⭐ Уровень: {player.level}\n\n"
        
        stats_text += f"👹 <b>{enemy.name}:</b>\n"
        stats_text += f"❤️ Здоровье: {enemy.health}\n"
        stats_text += f"⚔️ Сила: {enemy.strength}\n"
        stats_text += f"🛡️ Защита: {enemy.defense}\n"
        stats_text += f"⭐ Уровень: {enemy.level}\n\n"
        
        stats_text += "🎯 <b>Ваши атаки:</b>\n"
        for attack in player.attacks:
            estimated_damage = max(0, player.strength + attack.damage - enemy.defense)
            accuracy_percent = int(attack.accuracy * 100)
            stats_text += f"• {attack.name}: ~{estimated_damage} урона ({accuracy_percent}% точность)\n"
        
        await callback.answer(stats_text, show_alert=True)
        
    except Exception:
        await callback.answer("❌ Ошибка при получении статистики!")

async def handle_victory(callback: CallbackQuery, state: FSMContext, player, enemy, action_log):
    """Handle victory with enhanced rewards display"""
    try:
        drops = monster_drop_manager.get_monster_drops(enemy.to_dict())
        for drop_item in drops:
            # Convert Drop object to Item object before adding to inventory
            item = Item(name=drop_item.name, type="misc", quantity=drop_item.quantity) # Assuming 'misc' type for now
            add_item_to_inventory(player, item)
        
        leveled_up = add_exp(player, enemy.exp)
        add_money(player, enemy.reward)
        player.battles_won += 1
        
        victory_message = f"{action_log}\n\n"
        victory_message += f"🎉 <b>ПОБЕДА!</b> {enemy.name} побежден!\n\n"
        victory_message += "🏆 <b>Награды:</b>\n"
        victory_message += f"⚡ Опыт: +{enemy.exp} XP\n"
        victory_message += f"💰 Деньги: +{enemy.reward} монет\n"
        
        if drops:
            victory_message += f"📦 Дроп: {', '.join([d.name for d in drops])}\n"
        else:
            victory_message += "📦 Дроп: Ничего\n"
        
        if leveled_up:
            victory_message += f"⬆️ <b>УРОВЕНЬ ПОВЫШЕН!</b> Теперь {player.level} уровень!"
        player_manager.force_save()
        await callback.message.edit_text(victory_message)
        await state.clear()
        
    except Exception as e:
        print(e)
        await callback.message.edit_text("🎉 Победа\! (Ошибка при обработке наград)")
        await state.clear()

async def handle_defeat(callback: CallbackQuery, state: FSMContext, player, action_log):
    """Handle defeat with mercy mechanics"""
    try:
        player.health = int(player.max_health * DEFEAT_HEALTH_RESTORE)
        money_lost = max(1, int(player.money * DEFEAT_MONEY_LOSS))
        add_money(player, -money_lost)
        
        defeat_message = f"{action_log}\n\n"
        defeat_message += "💀 <b>ПОРАЖЕНИЕ!</b>"
        defeat_message += f"🏥 Здоровье восстановлено до {player.health}/{player.max_health}"
        defeat_message += f"💸 Потеряно {money_lost} монет ({int(DEFEAT_MONEY_LOSS*100)})%"       
        defeat_message += f"💰 Осталось: {player.money} монет"
        defeat_message += "💪 Не сдавайтесь! Тренируйтесь и возвращайтесь сильнее!"
        
        await callback.message.edit_text(defeat_message)
        await state.clear()
        
    except Exception as e:
        print(e)
        await callback.message.edit_text("💀 Поражение\! (Ошибка при обработке)")
        await state.clear()

async def combat_timeout_handler():
    pass