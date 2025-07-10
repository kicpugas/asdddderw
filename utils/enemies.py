import json
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class Attack:
    name: str
    damage: int
    accuracy: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Attack':
        return cls(name=data['name'], damage=data['damage'], accuracy=data['accuracy'])

@dataclass
class Enemy:
    name: str
    level: int
    health: int
    max_health: int
    strength: int
    defense: int
    speed: int
    attacks: List[Attack]
    exp: int
    reward: int
    drops: List[List[Any]]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Enemy':
        attacks = [Attack.from_dict(attack) for attack in data['attacks']]
        return cls(
            name=data['name'],
            level=data['level'],
            health=data['health'],
            max_health=data.get('max_health', data['health']), # Set max_health, default to current health
            strength=data['strength'],
            defense=data['defense'],
            speed=data['speed'],
            attacks=attacks,
            exp=data['exp'],
            reward=data['reward'],
            drops=data['drops']
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'level': self.level,
            'health': self.health,
            'max_health': self.max_health,
            'strength': self.strength,
            'defense': self.defense,
            'speed': self.speed,
            'attacks': [{'name': a.name, 'damage': a.damage, 'accuracy': a.accuracy} for a in self.attacks],
            'exp': self.exp,
            'reward': self.reward,
            'drops': self.drops
        }

class EnemyManager:
    def __init__(self, data_file: str = 'data/enemies.json'):
        self.data_file = data_file
        self._enemies = self._load_enemies()

    def _load_enemies(self) -> Dict[str, Enemy]:
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {name: Enemy.from_dict(enemy_data) for name, enemy_data in data.items()}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading enemies: {e}")
            return {}

    def get_enemy(self, name: str) -> Enemy:
        return self._enemies.get(name)

    def get_all_enemies(self) -> Dict[str, Enemy]:
        return self._enemies

enemy_manager = EnemyManager()
