from dataclasses import dataclass, field
from typing import Dict

@dataclass
class Skill:
    exp_total: float = 0.0
    exp_to_next_lvl: float = 100.0
    current_level: int = 1

class Farm:
    GATHERING_SKILLS = ["mining", "lumberjack", "fishing", "herbs", "hunting", "astrology"]

    WEAPON_SKILLS = ["swords", "electric_wands", "thermal_wands", "earth_wands", 
                     "void_staffs", "shields", "blessed_ornament", "ornament", "cursed_ornament"]

    def __init__(self):
        self.gathering: Dict[str, Skill] = {skill: Skill() for skill in self.GATHERING_SKILLS}
        self.weapons: Dict[str, Skill] = {skill: Skill() for skill in self.WEAPON_SKILLS}

    def gather(self, Skill):
        NotImplemented


