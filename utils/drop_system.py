import random
import json
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

class DropRarity(Enum):
    COMMON = "common"      # > 0.5 chance
    UNCOMMON = "uncommon"  # 0.1 - 0.5 chance
    RARE = "rare"          # 0.05 - 0.1 chance
    VERY_RARE = "very_rare" # < 0.05 chance

@dataclass
class Drop:
    name: str
    quantity: int
    rarity: DropRarity
    
    def __str__(self):
        return f"{self.name} x{self.quantity} ({self.rarity.value})"

class DropSystem:
    def __init__(self):
        self.rarity_thresholds = {
            DropRarity.COMMON: 0.5,
            DropRarity.UNCOMMON: 0.1,
            DropRarity.RARE: 0.05,
            DropRarity.VERY_RARE: 0.0
        }
    
    def get_rarity(self, chance: float) -> DropRarity:
        """Determine rarity based on drop chance"""
        if chance > self.rarity_thresholds[DropRarity.COMMON]:
            return DropRarity.COMMON
        elif chance > self.rarity_thresholds[DropRarity.UNCOMMON]:
            return DropRarity.UNCOMMON
        elif chance > self.rarity_thresholds[DropRarity.RARE]:
            return DropRarity.RARE
        else:
            return DropRarity.VERY_RARE
    
    def roll_drops(self, drop_table: List[List], luck_modifier: float = 1.0) -> List[Drop]:
        """
        Roll drops from monster's drop table
        
        Args:
            drop_table: List of [item_name, chance] pairs
            luck_modifier: Multiplier for drop chances (1.0 = normal, >1.0 = better luck)
        
        Returns:
            List of Drop objects
        """
        drops = []
        
        for item_name, base_chance in drop_table:
            # Apply luck modifier but cap at 100%
            effective_chance = min(1.0, base_chance * luck_modifier)
            
            if random.random() < effective_chance:
                # Determine quantity based on rarity (rarer items = fewer quantity)
                rarity = self.get_rarity(base_chance)
                quantity = self._calculate_quantity(rarity, base_chance)
                
                drop = Drop(
                    name=item_name,
                    quantity=quantity,
                    rarity=rarity
                )
                drops.append(drop)
        
        return drops
    
    def _calculate_quantity(self, rarity: DropRarity, base_chance: float) -> int:
        """Calculate quantity based on rarity and chance"""
        if rarity == DropRarity.COMMON:
            return random.randint(1, 3)
        elif rarity == DropRarity.UNCOMMON:
            return random.randint(1, 2)
        elif rarity == DropRarity.RARE:
            return 1
        else:  # VERY_RARE
            return 1
    
    def roll_monster_drops(self, monster_data: Dict[str, Any], luck_modifier: float = 1.0) -> List[Drop]:
        """Roll drops for a specific monster"""
        if "drops" not in monster_data:
            return []
        
        return self.roll_drops(monster_data["drops"], luck_modifier)
    
    def get_drop_statistics(self, drop_table: List[List], num_simulations: int = 1000) -> Dict[str, Dict[str, float]]:
        """Calculate drop statistics for balancing"""
        results = {}
        
        for _ in range(num_simulations):
            drops = self.roll_drops(drop_table)
            
            for drop in drops:
                if drop.name not in results:
                    results[drop.name] = {"count": 0, "total_quantity": 0}
                
                results[drop.name]["count"] += 1
                results[drop.name]["total_quantity"] += drop.quantity
        
        # Calculate percentages and averages
        statistics = {}
        for item_name, data in results.items():
            drop_rate = (data["count"] / num_simulations) * 100
            avg_quantity = data["total_quantity"] / data["count"] if data["count"] > 0 else 0
            
            statistics[item_name] = {
                "drop_rate_percent": round(drop_rate, 2),
                "average_quantity": round(avg_quantity, 2),
                "total_drops": data["count"]
            }
        
        return statistics
    
    def format_drops(self, drops: List[Drop]) -> str:
        """Format drops for display"""
        if not drops:
            return "Никаких предметов не выпало."
        
        # Group by rarity for better display
        rarity_groups = {}
        for drop in drops:
            if drop.rarity not in rarity_groups:
                rarity_groups[drop.rarity] = []
            rarity_groups[drop.rarity].append(drop)
        
        # Sort by rarity (rarest first)
        rarity_order = [DropRarity.VERY_RARE, DropRarity.RARE, DropRarity.UNCOMMON, DropRarity.COMMON]
        
        result = "🎁 Выпавшие предметы:\n"
        for rarity in rarity_order:
            if rarity in rarity_groups:
                rarity_emoji = self._get_rarity_emoji(rarity)
                result += f"\n{rarity_emoji} {rarity.value.replace('_', ' ').title()}:\n"
                
                for drop in rarity_groups[rarity]:
                    result += f"  • {drop.name} x{drop.quantity}\n"
        
        return result.strip()
    
    def _get_rarity_emoji(self, rarity: DropRarity) -> str:
        """Get emoji for rarity"""
        emoji_map = {
            DropRarity.COMMON: "⚪",
            DropRarity.UNCOMMON: "🟢", 
            DropRarity.RARE: "🔵",
            DropRarity.VERY_RARE: "🟣"
        }
        return emoji_map.get(rarity, "⚪")

# Monster loader and battle system integration
class MonsterDropManager:
    def __init__(self):
        self.drop_system = DropSystem()
    
    def get_monster_drops(self, monster: Dict[str, Any], luck_modifier: float = 1.0) -> List[Drop]:
        """Get drops for a specific monster"""
        return self.drop_system.roll_monster_drops(monster, luck_modifier)
    
    def get_all_possible_drops(self, monster: Dict[str, Any]) -> List[Tuple[str, float]]:
        """Get all possible drops for a monster with their chances"""
        return monster.get("drops", [])
    
    def analyze_monster_drops(self, monster: Dict[str, Any], simulations: int = 1000) -> Dict[str, Dict[str, float]]:
        """Analyze drop rates for a monster"""
        drop_table = monster.get("drops", [])
        return self.drop_system.get_drop_statistics(drop_table, simulations)

# Example usage with your monster data
def load_monsters_from_json(json_data: str) -> Dict[str, Dict[str, Any]]:
    """Load monsters from JSON string"""
    return json.loads(json_data)

# Example usage
if __name__ == "__main__":
    # Sample monster data (you would load this from your file)
    sample_monster_data = {
        "goblin": {
            "name": "Гоблин",
            "level": 2,
            "drops": [
                ["Гоблинский нож", 0.1],
                ["Камень", 0.5],
                ["Кожа", 0.2],
                ["Медь", 0.05]
            ]
        },
        "ancient_fire_dragon": {
            "name": "Древний Огненный Дракон",
            "level": 50,
            "drops": [
                ["Драконья чешуя", 0.3],
                ["Сердце дракона", 0.01],
                ["Кровь дракона", 0.023]
            ]
        }
    }
    
    # Create drop manager
    drop_manager = MonsterDropManager()
    
    # Test goblin drops
    print("=== Обычные капли гоблина ===")
    goblin_drops = drop_manager.get_monster_drops(sample_monster_data["goblin"])
    print(drop_manager.drop_system.format_drops(goblin_drops))
    
    print("\n=== Капли гоблина с удачей x2 ===")
    lucky_goblin_drops = drop_manager.get_monster_drops(sample_monster_data["goblin"], luck_modifier=2.0)
    print(drop_manager.drop_system.format_drops(lucky_goblin_drops))
    
    # Test dragon drops
    print("\n=== Капли дракона ===")
    dragon_drops = drop_manager.get_monster_drops(sample_monster_data["ancient_fire_dragon"])
    print(drop_manager.drop_system.format_drops(dragon_drops))
    
    # Analyze drop statistics
    print("\n=== Статистика капель гоблина (1000 симуляций) ===")
    goblin_stats = drop_manager.analyze_monster_drops(sample_monster_data["goblin"], 1000)
    for item, stats in goblin_stats.items():
        print(f"{item}: {stats['drop_rate_percent']}% шанс, среднее количество: {stats['average_quantity']}")