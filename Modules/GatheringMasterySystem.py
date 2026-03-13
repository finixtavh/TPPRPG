from dataclasses import dataclass, field
from typing import Dict, List
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
import time

class cSkill:
    exp_total: float = 0.0
    exp_to_next_lvl: float = 100.0
    current_level: int = 1

class cFarm:
    GATHERING_SKILLS = ["mining", "lumberjack", "fishing", "herbs", "hunting", "astrology"]

    WEAPON_SKILLS = ["swords", "electric_wands", "thermal_wands", "earth_wands", 
                     "void_staffs", "shields", "blessed_ornament", "ornament", "cursed_ornament"]

    def __init__(self):
        self.gathering: Dict[str, cSkill] = {skill: cSkill() for skill in self.GATHERING_SKILLS}
        self.weapons: Dict[str, cSkill] = {skill: cSkill() for skill in self.WEAPON_SKILLS}

    def gather(self, Material, Tool, vInventory, buffs=None):
        if buffs is None:
            buffs = []

        Gathering_Skill_Bonus = 1 + (self.gathering[Material.SkillName.lower()].current_level * 0.05)
        total_modifier = 1.0
        for b in buffs:
            total_modifier *= b

        # Tool efficiency
        tool_eff = Tool.Efficiency if Tool else 1.0

        # Total
        power = tool_eff * Gathering_Skill_Bonus * total_modifier

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
        ) as progress:

            task = progress.add_task("Recolectando", total=Material.Hardness)

            while not progress.finished:
                progress.update(task, advance=power)
                time.sleep(0.1)

        self.gathering[Material.SkillName.lower()].exp_total += Material.Hardness / 13

                
class cMaterial:
    def __init__(self, MATERIAL_ID, TypeStr, Name, Hardness, SkillName):
        self.MATERIAL_ID = MATERIAL_ID
        self.Material_Type: str = "TYPE_M:" + TypeStr
        self.Name = Name
        self.Hardness = Hardness
        self.SkillName = SkillName

class cTool:
    def __init__(self, STATIC_ID, TypeStr, Name, Desc, Efficiency, Enchantments: List, ):
        self.STATIC_ID = STATIC_ID
        self.ToolTypeStr: str = "TYPE_M:" + TypeStr # Needs support for multiple materials
        self.Name = Name
        self.Desc = Desc
        self.Efficiency = Efficiency
        self.Enchantments = Enchantments

Gathering_init = cFarm()


