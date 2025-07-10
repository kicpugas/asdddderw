from dataclasses import dataclass, field
import time

@dataclass
class Item:
    name: str
    type: str
    quantity: int = 1
    damage: int = 0
    defense: int = 0
    heal_amount: int = 0

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, data):
        if isinstance(data, str):
            return cls(name=data, type="misc")
        return cls(**data)

@dataclass
class Attack:
    name: str
    damage: int
    accuracy: float

@dataclass
class Player:
    user_id: int
    name: str = "Безымянный герой"
    health: int = 100
    max_health: int = 100
    money: int = 0
    level: int = 1
    exp: int = 0
    strength: int = 10
    defense: int = 5
    agility: int = 10
    intelligence: int = 10
    play_time: int = 0
    battles_won: int = 0
    total_damage_dealt: int = 0
    last_activity_time: float = field(default_factory=lambda: time.time())
    inventory: list[Item] = field(default_factory=list)
    attacks: list[Attack] = field(default_factory=lambda: [
        Attack(name="Удар мечом", damage=10, accuracy=0.9),
        Attack(name="Мощный удар", damage=15, accuracy=0.7)
    ])

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "health": self.health,
            "max_health": self.max_health,
            "money": self.money,
            "level": self.level,
            "exp": self.exp,
            "strength": self.strength,
            "defense": self.defense,
            "agility": self.agility,
            "intelligence": self.intelligence,
            "play_time": self.play_time,
            "battles_won": self.battles_won,
            "total_damage_dealt": self.total_damage_dealt,
            "last_activity_time": self.last_activity_time,
            "inventory": [item.to_dict() for item in self.inventory],
            "attacks": [attack.__dict__ for attack in self.attacks]
        }

    @classmethod
    def from_dict(cls, data):
        data_copy = data.copy()
        raw_attacks_data = data_copy.pop('attacks', [])
        level = data_copy.pop('level', 1)
        
        attacks = []
        if isinstance(raw_attacks_data, list):
            attacks = [Attack(**attack_data) for attack_data in raw_attacks_data]
        
        raw_inventory_data = data_copy.pop('inventory', [])
        inventory = []
        if isinstance(raw_inventory_data, list):
            inventory = [Item.from_dict(item_data) for item_data in raw_inventory_data]
        
        last_activity_time = data_copy.pop('last_activity_time', time.time())
        return cls(attacks=attacks, level=level, last_activity_time=last_activity_time, inventory=inventory, **data_copy)