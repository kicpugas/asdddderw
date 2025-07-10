import json
from pathlib import Path
from typing import Dict, Optional, List
from contextlib import contextmanager
from database.models import Player, Item
import time


class PlayerManager:
    """Manages player data persistence and operations."""
    
    def __init__(self, data_file: str = 'data/players.json'):
        self.data_file = Path(data_file)
        self._players: Dict[int, Player] = {}
        self._dirty = False  # Track if data needs saving
        self._load_players()
    
    def _load_players(self) -> None:
        """Load players from JSON file."""
        try:
            if not self.data_file.exists() or self.data_file.stat().st_size == 0:
                self._players = {}
                return
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._players = {int(k): Player.from_dict(v) for k, v in data.items()}
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading players: {e}")
            self._players = {}
        
        self._dirty = False
    
    def _save_players(self) -> None:
        """Save players to JSON file."""
        if not self._dirty:
            return  # No changes to save
        
        try:
            # Ensure directory exists
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"Attempting to save players to {self.data_file.absolute()}")
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.to_dict() for k, v in self._players.items()}, 
                    f, 
                    indent=4, 
                    ensure_ascii=False
                )
            self._dirty = False
            print(f"Players saved successfully. Dirty flag reset.")
            
        except Exception as e:
            print(f"Error saving players: {e}")
    
    @contextmanager
    def auto_save(self):
        """Context manager for automatic saving after operations."""
        try:
            yield
        finally:
            self._save_players()
    
    def get_player(self, user_id: int, user_name: str = "Безымянный герой") -> Player:
        """Get player by user ID, creating new player if doesn't exist."""
        current_time = time.time()
        if user_id not in self._players:
            self._players[user_id] = Player(user_id, name=user_name)
            self._dirty = True
            self._save_players()
        else:
            # Update play_time based on last activity
            time_since_last_activity = current_time - self._players[user_id].last_activity_time
            self._players[user_id].play_time += int(time_since_last_activity)
            self._dirty = True
        
        self._players[user_id].last_activity_time = current_time
        return self._players[user_id]
    
    def player_exists(self, user_id: int) -> bool:
        """Check if player exists."""
        return user_id in self._players
    
    def get_all_players(self) -> Dict[int, Player]:
        """Get all players (copy to prevent external modification)."""
        return self._players.copy()
    
    def delete_player(self, user_id: int) -> bool:
        """Delete a player. Returns True if player existed."""
        if user_id in self._players:
            del self._players[user_id]
            self._dirty = True
            self._save_players()
            return True
        return False
    
    def force_save(self) -> None:
        """Force save all player data."""
        self._dirty = True
        self._save_players()
    
    def reload_players(self) -> None:
        """Reload players from file."""
        self._load_players()


class PlayerOperations:
    """Handles player-specific operations and calculations."""
    
    def __init__(self, player_manager: PlayerManager):
        self.player_manager = player_manager
    
    def add_item_to_inventory(self, player: Player, item: Item) -> None:
        """Add item to player's inventory, stacking if item already exists."""
        found = False
        for existing_item in player.inventory:
            if existing_item.name == item.name and existing_item.type == item.type:
                existing_item.quantity += item.quantity
                found = True
                break
        if not found:
            player.inventory.append(item)
        print(f"DEBUG: Added {item.name} to {player.name}'s inventory. Current inventory: {[f'{i.name} x{i.quantity}' for i in player.inventory]}")
        self.player_manager._dirty = True
        self.player_manager._save_players()
    
    def remove_item_from_inventory(self, player: Player, item: str) -> bool:
        """Remove item from inventory. Returns True if item was found and removed."""
        if item in player.inventory:
            player.inventory.remove(item)
            self.player_manager._dirty = True
            self.player_manager._save_players()
            return True
        return False
    
    def calculate_required_exp(self, level: int) -> int:
        """Calculate experience required for given level."""
        return level * 20
    
    def can_level_up(self, player: Player) -> bool:
        """Check if player can level up."""
        required_exp = self.calculate_required_exp(player.level)
        return player.exp >= required_exp
    
    def level_up(self, player: Player) -> bool:
        """Attempt to level up player. Returns True if successful."""
        required_exp = self.calculate_required_exp(player.level)
        
        if player.exp >= required_exp:
            player.level += 1
            player.exp -= required_exp
            player.max_health += 10
            player.health = player.max_health
            player.strength += 2
            self.player_manager._dirty = True
            return True
        
        return False
    
    def add_exp(self, player: Player, exp: int) -> bool:
        """Add experience to player. Returns True if player leveled up."""
        if exp <= 0:
            return False
        
        player.exp += exp
        leveled_up = self.level_up(player)
        self.player_manager._dirty = True
        self.player_manager._save_players()
        return leveled_up
    
    def add_money(self, player: Player, money: int) -> None:
        """Add or subtract money from player."""
        player.money += money
        self.player_manager._dirty = True
        self.player_manager._save_players()
    
    def spend_money(self, player: Player, amount: int) -> bool:
        """Spend money. Returns True if player had enough money."""
        if player.money >= amount:
            player.money -= amount
            self.player_manager._dirty = True
            self.player_manager._save_players()
            return True
        return False
    
    def heal_player(self, player: Player, amount: int) -> int:
        """Heal player. Returns actual amount healed."""
        if amount <= 0:
            return 0
        
        old_health = player.health
        player.health = min(player.health + amount, player.max_health)
        actual_healed = player.health - old_health
        
        if actual_healed > 0:
            self.player_manager._dirty = True
            self.player_manager._save_players()
        
        return actual_healed
    
    def damage_player(self, player: Player, damage: int) -> int:
        """Apply damage to player. Returns actual damage dealt."""
        if damage <= 0:
            return 0
        
        old_health = player.health
        player.health = max(0, player.health - damage)
        actual_damage = old_health - player.health
        
        if actual_damage > 0:
            self.player_manager._dirty = True
            self.player_manager._save_players()
        
        return actual_damage
    
    def is_player_alive(self, player: Player) -> bool:
        """Check if player is alive."""
        return player.health > 0
    
    def get_player_stats(self, player: Player) -> str:
        """Get formatted player statistics."""
        required_exp = self.calculate_required_exp(player.level)
        inventory_text = ', '.join(player.inventory) if player.inventory else 'пусто'
        
        return (
            f"Уровень: {player.level}\n"
            f"Здоровье: {player.health}/{player.max_health}\n"
            f"Опыт: {player.exp}/{required_exp}\n"
            f"Сила: {player.strength}\n"
            f"Защита: {player.defense}\n"
            f"Деньги: {player.money}\n"
            f"Инвентарь: {inventory_text}"
        )
    
    def get_player_level_progress(self, player: Player) -> float:
        """Get level progress as percentage (0.0 to 1.0)."""
        required_exp = self.calculate_required_exp(player.level)
        return min(player.exp / required_exp, 1.0) if required_exp > 0 else 1.0


# Global instances for backward compatibility
player_manager = PlayerManager()
player_operations = PlayerOperations(player_manager)

# Backward compatibility functions
def load_players() -> Dict[int, Player]:
    """Load and return all players. Maintained for backward compatibility."""
    return player_manager.get_all_players()

def save_players(players: Dict[int, Player]) -> None:
    """Save players. Maintained for backward compatibility."""
    player_manager.force_save()

def get_player(user_id: int) -> Player:
    """Get player by user ID."""
    return player_manager.get_player(user_id)

def add_item_to_inventory(player: Player, item: Item) -> None:
    """Add item to player's inventory."""
    player_operations.add_item_to_inventory(player, item)

def level_up(player: Player) -> bool:
    """Attempt to level up player."""
    return player_operations.level_up(player)

def add_exp(player: Player, exp: int) -> bool:
    """Add experience to player."""
    return player_operations.add_exp(player, exp)

def add_money(player: Player, money: int) -> None:
    """Add money to player."""
    player_operations.add_money(player, money)

def get_player_stats(player: Player) -> str:
    """Get formatted player statistics."""
    return player_operations.get_player_stats(player)

# Additional utility functions
def get_top_players_by_level(limit: int = 10) -> List[Player]:
    """Get top players by level."""
    all_players = player_manager.get_all_players()
    return sorted(all_players.values(), key=lambda p: p.level, reverse=True)[:limit]

def get_player_by_name(name: str) -> Optional[Player]:
    """Get player by name (if Player model has name attribute)."""
    all_players = player_manager.get_all_players()
    for player in all_players.values():
        if hasattr(player, 'name') and player.name == name:
            return player
    return None