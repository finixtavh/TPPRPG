from rich.console import Console
from rich.theme import Theme
from Modules.ModulesUtils.Loader import Write, Read
from dataclasses import dataclass, field
from typing import Any, Dict, List
from rich.panel import Panel
from rich.box import ROUNDED

import os
import random
import time as sp

try:
    from Modules.ModulesFunctions.WeatherSystem import apply_weather_combat_mods
except ImportError:
    # Fallback in case WeatherSystem is not available yet
    def apply_weather_combat_mods(base_val: float, mod_key: str) -> float:
        return base_val
from Modules.ModulesUtils.input_utils import wait_for_enter
from Modules.ModulesFunctions.GuildSystem import get_guild_manager
from Modules.ModulesFunctions.EnchantmentSystem import ENCHANTMENTS_CATALOG, get_item_enchants
from Modules.ModulesFunctions.SkillTreeSystem import skill_tree_manager
from Modules.ModulesUtils.ModLoader import get_mod_api

##################      First Variables
player = None
console = Console()


def _normalize_5_values(values):
    """Normalize list input to 5 slots [Fisico, Termico, Electrico, Tierra, Profundo]."""
    if not isinstance(values, (list, tuple)):
        raise ValueError("Se esperaba una lista/tupla para valores de dano/defensa")
    source = list(values)
    if len(source) == 0:
        return [0, 0, 0, 0, 0]
    if len(source) == 1:
        return [source[0], 0, 0, 0, 0]
    if len(source) == 2:
        return [source[0], source[1], 0, 0, 0]
    if len(source) >= 5:
        return source[:5]
    return source + [0] * (5 - len(source))


def _normalize_4_values(values):
    """Normalize list input to 4 slots [Fisico, Termico, Electrico, Tierra]."""
    if not isinstance(values, (list, tuple)):
        raise ValueError("Se esperaba una lista/tupla para dano minimo")
    source = list(values)
    if len(source) == 0:
        return [0, 0, 0, 0]
    if len(source) == 1:
        return [source[0], 0, 0, 0]
    if len(source) == 2:
        return [source[0], source[1], 0, 0]
    if len(source) >= 4:
        return source[:4]
    return source + [0] * (4 - len(source))

def normalize_group_spawn(values):
    """Normaliza el dict de probabilidades de grupo a {int 1..5: float}.

    Acepta claves str o int. None / vacío => {1: 1.0} (siempre 1 enemigo).
    """
    if not values:
        return {1: 1.0}
    cleaned = {}
    for k, v in values.items():
        try:
            size = int(k)
            weight = float(v)
        except (ValueError, TypeError):
            continue
        if 1 <= size <= 5 and weight > 0:
            cleaned[size] = weight
    return cleaned or {1: 1.0}


def roll_group_size(group_spawn) -> int:
    """Devuelve un tamaño de grupo (1..5) según las probabilidades dadas."""
    gs = normalize_group_spawn(group_spawn)
    sizes = list(gs.keys())
    weights = list(gs.values())
    return random.choices(sizes, weights=weights, k=1)[0]


# Orden de tipos de daño: [Físico, Térmico, Tierra, Eléctrico, Profundo]
AFFINITY_TYPE_ORDER = ["physical", "thermal", "earth", "electric", "deep"]


def normalize_affinities(values):
    """Normaliza afinidades elementales a una lista de 5 multiplicadores (default 1.0).

    Acepta:
        - lista de 5 floats
        - dict por nombre de tipo: {"thermal": 0.5, "earth": 1.5, ...}
    """
    mults = [1.0] * 5
    if not values:
        return mults
    if isinstance(values, (list, tuple)):
        for i in range(min(5, len(values))):
            try:
                mults[i] = float(values[i])
            except (ValueError, TypeError):
                pass
        return mults
    if isinstance(values, dict):
        for key, val in values.items():
            name = str(key).lower()
            if name in AFFINITY_TYPE_ORDER:
                try:
                    mults[AFFINITY_TYPE_ORDER.index(name)] = float(val)
                except (ValueError, TypeError):
                    pass
    return mults


def resolve_enemy_affinities(enemy_data):
    """Obtiene la lista de afinidades de un enemigo desde su JSON.

    Prioridad: `affinities` en línea > perfil nombrado `affinity_profile`
    (definido en Data/Affinities.json) > sin afinidades (todo 1.0).
    """
    inline = enemy_data.get("affinities")
    if inline:
        return normalize_affinities(inline)
    profile_name = enemy_data.get("affinity_profile")
    if profile_name:
        # Perfiles inyectados por mods (tienen prioridad sobre el JSON base)
        mod_profiles = globals().get("_MOD_AFFINITY_PROFILES", {})
        if profile_name in mod_profiles:
            return normalize_affinities(mod_profiles[profile_name])
        # Read cachea Affinities.json, así que esto no re-parsea por enemigo
        profiles = Read(os.path.join("Data", "Affinities.json"), "PROFILES", None)
        if isinstance(profiles, dict) and profile_name in profiles:
            return normalize_affinities(profiles[profile_name])
    return [1.0] * 5


##################      Classes
class Entity:
    """Base común de entidades de combate (jugador, enemigo, compañero).

    Unifica la API: el jugador/compañero usan Health/Mana/name y el enemigo
    históricamente usa HP/MP/NAME. Esta base provee `is_alive` y permite que
    las subclases expongan alias para usar UNA sola convención en el combate.
    """

    @property
    def is_alive(self) -> bool:
        hp = getattr(self, "Health", None)
        if hp is None:
            hp = getattr(self, "HP", 0)
        return hp > 0


class cPlayer(Entity):
    """
    Used for player's character and #?
    
    Status:
        Health & Health_max
        Mana & Mana_max
        EXP: Current XP
        EXP_M: EXP needed for next level
        Gold: Current money
        Level: +1 when EXP >= EXP_M, 1+ skill point and 5+ Health_max
    
    Attributes:
        DEF: List of 5 defense values [Physical, Thermal, Earth, Electric, Deep]
        AGI: AGI% of Dealing damage (base 40%)
        DefensePercentage: Blocks a percentaje of the incoming damage, Ignores Debuff Damage
        CounterAttack: CounterAttack% of attack without using a turn when you receive damage from a enemy, Ignores Debuff Damage
        ManaRegen: Every Turn you regen mana based on this variable value: Mana+= ManaRegen
        EvadeAttacks: EvadeAttacks% of not receiving incoming Damage
        
    Items:
        weapon: cWeapon
        helmet: cEquippableItems TYPE:Helmet
        armor: cEquippableItems TYPE:Armor
        boots: cEquippableItems TYPE:Boots
        ring, ring2, ring3: cEquippableItems TYPE:Ring
        
        TODO: Finish Comments
    """

    def __init__(self, name, weapon):
        self.name = name
        # Main Stats
        self.Health_max = 100
        self.Health = self.Health_max
        self.Mana_max = 100
        self.Mana = self.Mana_max
        self.Level = 1
        self.lvlPoints = 0
        self.skills_purchased = {}
        self._level_health_bonus = 0
        self._level_mana_bonus = 0
        # Secondary Stats
        self.DEF = [0, 0, 0, 0, 0]  # [Phys, Thermal, Earth, Electric, Deep]
        self.AGI = 0
        self.DefensePercentage = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.CounterAttack = 0
        self.Evasion = 0
        self.ManaRegen = 2.5
        self.Barrier = 50
        # Gold and Experience
        self.Gold = 50
        self.EXP = 15
        self.EXP_M = 100
        # Items 
        self.weapon = weapon
        self.helmet = None
        self.armor = cEquippableItems(2, "Armadura", [5, 0, 0, 0, 0], 0, 0, 0, 20, "...", "Armor")
        self.boots = None
        self.ring = None
        self.ring2 = None
        self.ring3 = None
        self.SecHand = None
        self.tool = None 
        
        # New persistence systems
        self.discovered_items = set() # Store item IDs
        self.favorite_recipes = [] # Store recipe IDs
        self.favorite_items = [] # Store item IDs

        # Guild system
        self.guild_id: str = ""           # ID de la guild actual del jugador
        self.guild_reputation: dict = {}  # { guild_id: -100..100 }
        self.combat_counter: int = 0      # Nº de combates realizados (trigger de simulación)

        # Seems like this can changed fore something better
        self.items_in_PlayerClass = [self.weapon, self.helmet, self.armor, self.boots, self.ring, self.ring2, self.ring3, self.SecHand]

        self.applieddebuffs = []
        self.appliedbuffs = []
        self.active_buffs = []
        self.companion = []
        self.companion_bank = []
        self.mastery_manager = None
        self.base_manager = None
        self.lobjectscheck = [
            (self.helmet, "Helmet", "helmet"),
            (self.armor, "Armor", "armor"),
            (self.boots, "Boots", "boots"),
            (self.ring, "Ring", "ring"),
            (self.ring2, "Ring", "ring2"),
            (self.ring3, "Ring", "ring3"),
            (self.SecHand, "SecHand", "SecHand")
        ]

    def attack(self, enemy):
        """Attack an enemy with multi-type damage system"""
        # --- NUEVA LÓGICA DE DETALLE ---
        attack_info = {
            "is_evaded": False,
            "is_counter": False,
            "damage_per_type": [0.0] * 5,
            "total_damage": 0.0,
            "blocked_by_def": [0.0] * 5,
            "blocked_by_pct": [0.0] * 5,
            "enchant_dmg": [0.0] * 5,
            "buff_dmg": [0.0] * 5,
            "weather_dmg": [0.0] * 5,
            "barrier_absorbed": 0.0
        }

        # 1. Comprobar Evasión del enemigo
        enemy_evasion = getattr(enemy, "Evasion", 0)
        enemy_evasion = apply_weather_combat_mods(enemy_evasion, "evasion")
        
        if random.random() < (enemy_evasion / 100.0):
            attack_info["is_evaded"] = True
            return attack_info

        # 2. Comprobar Contraataque del enemigo
        enemy_counter = getattr(enemy, "CounterAttack", 0)
        enemy_counter = apply_weather_combat_mods(enemy_counter, "counter")
        if random.random() < (enemy_counter / 100.0):
            attack_info["is_counter"] = True

        # 3. Calcular Daño
        has_enough_mana = True
        mana_cost = 0
        if self.weapon:
            mana_cost = getattr(self.weapon, "ManaCost", 0)
            
            # Encantamiento Infusión de Maná (si existe)
            try:
                enchants = get_item_enchants(self.weapon)
                for e in enchants:
                    if e.get("family_id") == "mana_infusion":
                        mana_cost += 10 * e.get("level", 1)
            except: pass

            if self.Mana < mana_cost:
                has_enough_mana = False
            else:
                self.Mana -= mana_cost

        if self.weapon:
            weapon_res = self.weapon.use_weapon(self)
            # Aseguramos que sea dict, si no (fallback)
            if isinstance(weapon_res, dict):
                damage_array = weapon_res["damage"]
                attack_info["enchant_dmg"] = weapon_res.get("enchant_dmg", [0.0]*5)
            else:
                damage_array = weapon_res
        else:
            damage_array = [float(random.randint(2, 5)), 0.0, 0.0, 0.0, 0.0]

        # Aplicar penalización si no hubo maná
        if not has_enough_mana:
            damage_array = [d * 0.4 for d in damage_array]
            attack_info["enchant_dmg"] = [0.0] * 5
            # Avisar al jugador
            console.print(f"[yellow]¡No tienes maná suficiente! El ataque es mucho más débil.[/yellow]")

        # Aplicar clima al ataque
        weather_raw = list(damage_array)
        damage_array = [apply_weather_combat_mods(d, "attack") for d in damage_array]
        
        # Aplicar debuffs de impuestos (Guild)
        try:
            gm = get_guild_manager()
            pg = gm.get_player_guild()
            if pg:
                tax_mods = pg.get_tax_debuffs()
                if "damage_mult" in tax_mods:
                    damage_array = [d * tax_mods["damage_mult"] for d in damage_array]
        except: pass

        attack_info["weather_dmg"] = [damage_array[i] - weather_raw[i] for i in range(5)]
        
        # 4. Aplicar daño al enemigo y obtener detalles
        res = enemy.TakeDamage(damage_array, attacker=self)
        attack_info.update(res)

        return attack_info

    def TakeDamage(self, damage, attacker=None):
        """Reduces player HP based on damage array and returns details."""
        details = {
            "total_damage": 0.0,
            "blocked_by_def": [0.0] * 5,
            "blocked_by_pct": [0.0] * 5,
            "def_pct_val": list(self.DefensePercentage),
            "barrier_absorbed": 0.0,
            "damage_per_type": [0.0] * 5,
            "enchant_def": [0.0] * 5,
            "enchant_names": [],
            "buff_def": [0.0] * 5,
            "buff_names": [],
            "weather_def": [0.0] * 5,
            "weather_name": "Clima"
        }

        if not isinstance(damage, (list, tuple)):
            damage = [float(damage), 0.0, 0.0, 0.0, 0.0]
        
        current_damage = list(damage)

        # Impuestos de Guild: calcular UNA vez (antes se recalculaba 5 veces/golpe)
        tax_defense_mult = 1.0
        try:
            pg = get_guild_manager().get_player_guild()
            if pg:
                tax_mods = pg.get_tax_debuffs()
                if "defense_mult" in tax_mods:
                    # debuff de defensa = más daño recibido
                    tax_defense_mult = (2.0 - tax_mods["defense_mult"])
        except Exception:
            pass

        # 0. Clima a la defensa
        for i in range(5):
            orig = current_damage[i]
            current_damage[i] = apply_weather_combat_mods(current_damage[i], "defense")
            if tax_defense_mult != 1.0:
                current_damage[i] *= tax_defense_mult
            details["weather_def"][i] = orig - current_damage[i]
        
        try:
            from Modules.ModulesFunctions.WeatherSystem import current_weather
            if current_weather: details["weather_name"] = current_weather.name
        except: pass

        # 1. Barrera
        if self.Barrier > 0:
            total_now = sum(current_damage)
            if total_now <= self.Barrier:
                details["barrier_absorbed"] = total_now
                self.Barrier -= total_now
                return details
            else:
                absorbed = self.Barrier
                details["barrier_absorbed"] = absorbed
                self.Barrier = 0
                if total_now > 0:
                    ratio = (total_now - absorbed) / total_now
                    current_damage = [d * ratio for d in current_damage]

        # 2. Encantamientos de Armadura (Reducción plana)
        try:
            armor_items = [self.helmet, self.armor, self.boots, self.ring, self.ring2, self.ring3]
            for item in armor_items:
                if item:
                    enchants = get_item_enchants(item)
                    for entry in enchants:
                        for cat_ench in ENCHANTMENTS_CATALOG.values():
                            if cat_ench.family_id == entry["family_id"]:
                                mods = cat_ench.apply_to_equipment(item)
                                if "defense_flat_bonus" in mods:
                                    bonus = mods["defense_flat_bonus"]
                                    for i in range(min(5, len(bonus))):
                                        reduction = bonus[i] * entry.get("level", 1)
                                        actual = min(current_damage[i], reduction)
                                        current_damage[i] -= actual
                                        details["enchant_def"][i] += actual
                                        if cat_ench.name not in details["enchant_names"]:
                                            details["enchant_names"].append(cat_ench.name)
        except: pass

        # 3. Defensas base
        for i in range(5):
            if current_damage[i] > 0:
                player_def = self.DEF[i]
                blocked_fijo = min(current_damage[i], player_def / 2)
                details["blocked_by_def"][i] = blocked_fijo
                remaining = current_damage[i] - blocked_fijo
                
                # Porcentaje de defensa
                block_ratio = min(1.0, self.DefensePercentage[i] / 100.0)
                blocked_pct = remaining * block_ratio
                details["blocked_by_pct"][i] = blocked_pct
                
                final_type_damage = remaining - blocked_pct
                details["damage_per_type"][i] = final_type_damage
                details["total_damage"] += final_type_damage

        self.Health -= details["total_damage"]
        if self.Health < 0:
            self.Health = 0
        return details

    def level_up(self):
        """Maneja la subida de nivel, incrementando la exp requerida en x1.07"""
        Before_Levelup = self.Level
        while self.EXP >= self.EXP_M:
            self.Level += 1
            self.EXP -= self.EXP_M
            self.EXP_M *= 1.07
            self._level_health_bonus += 20
            self._level_mana_bonus += 10
            self.Health_max += 20
            self.Mana_max += 10
            self.Health = self.Health_max
            self.Mana = self.Mana_max
            self.lvlPoints += 1
            
        if Before_Levelup != self.Level:
            console.print(f"Has subido de nivel!")
            console.print(f"Antes: {Before_Levelup}")
            console.print(f"Ahora: {self.Level}")
            pts_ganados = self.Level - Before_Levelup
            console.print(f"[bold #FFFF99]¡Has ganado {pts_ganados} Punto(s) de Habilidad para mejorar tus atributos![/]")

            exp_formated = "{:,.2f}".format(self.EXP).replace(",", "X").replace(".", ",").replace("X", ".")
            exp_m_formated = "{:,.2f}".format(self.EXP_M).replace(",", "X").replace(".", ",").replace("X", ".")

            console.print(f"Tienes: {exp_formated} y ahora requeriras {exp_m_formated} para avanzar al siguiente nivel")
            wait_for_enter()

            # Hook para mods
            try:
                get_mod_api().fire_event("level_up", self, Before_Levelup, self.Level)
            except Exception:
                pass

    def Check(self, lInventory):
        """Valida estado del jugador, equipamiento e inventario. Recibe lInventory (cInventory)."""
        slot_names = ["weapon", "helmet", "armor", "boots", "ring", "ring2", "ring3", "SecHand"]
        self.items_in_PlayerClass = [self.weapon, self.helmet, self.armor, self.boots, self.ring, self.ring2, self.ring3, self.SecHand]
        # Actualizar lobjectscheck con el estado actual (no el de __init__)
        self.lobjectscheck = [
            (self.helmet, "Helmet", "helmet"),
            (self.armor, "Armor", "armor"),
            (self.boots, "Boots", "boots"),
            (self.ring, "Ring", "ring"),
            (self.ring2, "Ring", "ring2"),
            (self.ring3, "Ring", "ring3"),
            (self.SecHand, "SecHand", "SecHand")
        ]

        # Auto-discover currently equipped items, tools, and inventory items
        for item in self.items_in_PlayerClass + [self.tool]:
            if item:
                item_id = getattr(item, "ID", getattr(item, "STATIC_ID", None))
                if item_id is not None:
                    self.discovered_items.add(item_id)
        
        for slot in lInventory.slots:
            item_id = getattr(slot.item, "ID", getattr(slot.item, "STATIC_ID", None))
            if item_id is not None:
                self.discovered_items.add(item_id)


        self.Mana = min(self.Mana + self.ManaRegen, self.Mana_max)

        Companion_Updater(self)

        if self.Health > self.Health_max:
            self.Health = self.Health_max
        if self.Mana > self.Mana_max:
            self.Mana = self.Mana_max

        # Reducción pasiva de moral por impuestos
        try:
            gm = get_guild_manager()
            pg = gm.get_player_guild()
            if pg:
                tax_mods = pg.get_tax_debuffs()
                if "morale_loss" in tax_mods:
                    pg.change_moral(-int(tax_mods["morale_loss"]))
        except: pass

        for i, obj in enumerate(self.items_in_PlayerClass):
            if isinstance(obj, cObject):
                setattr(self, slot_names[i], None)
                lInventory.addObject(obj)
        
        # RESET STATS BEFORE RECALCULATION
        self.DEF = [0, 0, 0, 0, 0]
        self.DefensePercentage = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.Health_max = 100 + getattr(self, "_level_health_bonus", 0)  # Base + level bonuses
        self.ManaRegen = 2.5  # Reset base
        self.AGI = 0
        self.CounterAttack = 0
        self.Evasion = 0
        # Barrera: se regenera a tope (base + equipo) entre combates.
        # Check() corre al volver al menú, así que la barrera vuelve a llenarse.
        self.Barrier = 50

        for item in self.items_in_PlayerClass:
            if isinstance(item, cEquippableItems):
                # Handle defense as array
                for i in range(min(5, len(item.Defense))):
                    self.DEF[i] += item.Defense[i]
                
                # HealthBoost
                if hasattr(item, "HealthBoost"):
                    self.Health_max += item.HealthBoost
                
                # DefensePercentage
                if hasattr(item, "DefensePercentage"):
                    for i in range(min(5, len(item.DefensePercentage))):
                        self.DefensePercentage[i] += item.DefensePercentage[i]
                
                # ManaRegen
                if hasattr(item, "ManaRegen"):
                    self.ManaRegen += item.ManaRegen
                
                # AGI, Evasion, CounterAttack
                if hasattr(item, "AGI"): self.AGI += item.AGI
                if hasattr(item, "Evasion"): self.Evasion += item.Evasion
                if hasattr(item, "CounterAttack"): self.CounterAttack += item.CounterAttack

                # Barrera del equipo (antes nunca se aplicaba)
                if hasattr(item, "Barrier"): self.Barrier += item.Barrier

        for item, objecttype, slot_name in self.lobjectscheck:
            if item and objecttype is not None:
                if item.objectcheck != objecttype:
                    lInventory.addObject(item)
                    setattr(self, slot_name, None)

        self.level_up()

    def Points(self):
        skill_tree_manager.open_menu(self)

    # ── Alias estilo-enemigo (NAME/HP/MP) para una API de combate unificada ──
    @property
    def NAME(self): return self.name
    @NAME.setter
    def NAME(self, v): self.name = v
    @property
    def HP(self): return self.Health
    @HP.setter
    def HP(self, v): self.Health = v
    @property
    def HP_M(self): return self.Health_max
    @HP_M.setter
    def HP_M(self, v): self.Health_max = v
    @property
    def MP(self): return self.Mana
    @MP.setter
    def MP(self, v): self.Mana = v
    @property
    def MP_M(self): return self.Mana_max
    @MP_M.setter
    def MP_M(self, v): self.Mana_max = v


class cEnemy(Entity):
    def __init__ (self, NAME, 
                  HP_M,  
                  DMG, DMG_min,  # Now expects arrays of 5 values
                  MP_M, 
                  EXP_TO_PLAYER, 
                  DEF, LS, AGI,  # DEF is now array of 5 values
                  DBUFF_TO_PLAYER, 
                  BUFF_RECEIVED,
                  GOLD,
                  IS_BOSS=False,
                  SPAWN_CHANCE=1.0,
                  GROUP_SPAWN=None,
                  loot_tables=None,
                  AFFINITIES=None):
        self.NAME = NAME
        self.HP_M = HP_M
        self.HP = self.HP_M
        self.IS_BOSS = IS_BOSS
        self.SPAWN_CHANCE = SPAWN_CHANCE
        # Probabilidades de tamaño del grupo: {"1": 0.8, "2": 0.1, ...} (máx 5)
        self.GROUP_SPAWN = normalize_group_spawn(GROUP_SPAWN)
        # Tabla de loot {item_id(str): peso} usada al morir
        self.loot_tables = loot_tables or {}
        # Afinidades elementales: multiplicador de daño recibido por tipo
        self.AFFINITIES = normalize_affinities(AFFINITIES)

        # Format: [Physical, Thermal, Earth, Electric, Deep]

        self.DMG = _normalize_5_values(DMG)
        self.DMG_min = _normalize_4_values(DMG_min)
        self.DEF = _normalize_5_values(DEF)
        
        self.MP_M = MP_M
        self.MP = self.MP_M
        self.EXP_TO_PLAYER = EXP_TO_PLAYER
        self.LS = LS
        self.AGI = AGI
        self.DBUFF_TO_PLAYER = DBUFF_TO_PLAYER
        self.BUFF_RECEIVED = BUFF_RECEIVED
        self.GOLD = GOLD
        self.applieddebuffs = []
        self.active_buffs = []
        self.Evasion = 0.0
        self.CounterAttack = 0.0

    def attack(self, target):
        """Attack target with multi-type damage system."""
        attack_info = {
            "is_evaded": False,
            "is_counter": False,
            "damage_per_type": [0.0] * 5,
            "total_damage": 0.0,
            "blocked_by_def": [0.0] * 5,
            "blocked_by_pct": [0.0] * 5,
            "barrier_absorbed": 0.0,
            "enchant_dmg": [0.0] * 5,
            "buff_dmg": [0.0] * 5,
            "weather_dmg": [0.0] * 5
        }
        
        # 1. Evasión del target
        target_evasion = getattr(target, "Evasion", 0)
        target_evasion = apply_weather_combat_mods(target_evasion, "evasion")
        if random.random() < (target_evasion / 100.0):
            attack_info["is_evaded"] = True
            return attack_info
            
        # 2. Contraataque del target
        target_counter = getattr(target, "CounterAttack", 0)
        target_counter = apply_weather_combat_mods(target_counter, "counter")
        if random.random() < (target_counter / 100.0):
            attack_info["is_counter"] = True
            
        # 3. Calcular Daño
        raw_damage = [0.0] * 5
        for i in range(5):
            if self.DMG[i] > 0:
                if i == 4:
                    raw_damage[i] = float(self.DMG[4])
                else:
                    lo = int(self.DMG_min[i]) if i < len(self.DMG_min) else 0
                    hi = int(self.DMG[i])
                    raw_damage[i] = float(random.randint(max(0, lo), max(lo, hi)))
        
        # Aplicar clima al ataque enemigo
        weather_raw = list(raw_damage)
        raw_damage = [apply_weather_combat_mods(d, "attack") for d in raw_damage]
        attack_info["weather_dmg"] = [raw_damage[i] - weather_raw[i] for i in range(5)]

        # 4. Target recibe daño
        res = target.TakeDamage(raw_damage, attacker=self)
        attack_info.update(res)
        return attack_info

    def TakeDamage(self, damage, attacker=None):
        """Reduces enemy HP and returns details."""
        details = {
            "total_damage": 0.0,
            "blocked_by_def": [0.0] * 5,
            "blocked_by_pct": [0.0] * 5,
            "def_pct_val": [0.0] * 5,
            "damage_per_type": [0.0] * 5,
            "weather_def": [0.0] * 5,
            "weather_name": "Clima",
            "affinity_mult": [1.0] * 5
        }
        if not isinstance(damage, (list, tuple)):
            damage = [float(damage), 0.0, 0.0, 0.0, 0.0]

        current_damage = list(damage)

        # Clima a la defensa enemiga
        for i in range(5):
            orig = current_damage[i]
            current_damage[i] = apply_weather_combat_mods(current_damage[i], "defense")
            details["weather_def"][i] = orig - current_damage[i]
        
        try:
            from Modules.ModulesFunctions.WeatherSystem import current_weather
            if current_weather: details["weather_name"] = current_weather.name
        except: pass

        affinities = getattr(self, "AFFINITIES", [1.0] * 5)
        for i in range(5):
            if current_damage[i] > 0:
                enemy_def = self.DEF[i]
                blocked_fijo = min(current_damage[i], enemy_def / 2)
                details["blocked_by_def"][i] = blocked_fijo
                remaining = current_damage[i] - blocked_fijo

                # Afinidad elemental: debilidad (>1) o resistencia (<1)
                mult = affinities[i] if i < len(affinities) else 1.0
                details["affinity_mult"][i] = mult
                remaining *= mult

                details["damage_per_type"][i] = remaining
                details["total_damage"] += remaining
        self.HP -= details["total_damage"]
        if self.HP < 0: self.HP = 0
        return details

    # ── Alias estilo-jugador (name/Health/Mana) para una API de combate unificada ──
    @property
    def name(self): return self.NAME
    @name.setter
    def name(self, v): self.NAME = v
    @property
    def Health(self): return self.HP
    @Health.setter
    def Health(self, v): self.HP = v
    @property
    def Health_max(self): return self.HP_M
    @Health_max.setter
    def Health_max(self, v): self.HP_M = v
    @property
    def Mana(self): return self.MP
    @Mana.setter
    def Mana(self, v): self.MP = v
    @property
    def Mana_max(self): return self.MP_M
    @Mana_max.setter
    def Mana_max(self, v): self.MP_M = v


class cWeapon:
    def __init__(self, ID, name, DMG, DMG_min, Gold_Cost, Description):
        """
        Weapon with multi-type damage system.
        
        Args:
            ID: Weapon ID
            name: Weapon name
            DMG: Array of 5 max damage values [Physical, Thermal, Earth, Electric, Deep]
            DMG_min: Array of 4 min damage values [Physical, Thermal, Earth, Electric]
                     Deep damage is always maximum (DMG[4])
            Gold_Cost: Cost in gold
            Description: Weapon description
        """
        self.ID = ID
        self.name = name
        self.Gold_Cost = Gold_Cost
        self.Description = Description
        self.AppliedStats = False

        self.DMG = _normalize_5_values(DMG)
        self.DMG_min = _normalize_4_values(DMG_min)
        
        # Atributos nuevos para mano secundaria y mana
        self.ManaCost = 0
        self.is_two_handed = False
        self.AGI = 0
        self.Evasion = 0
        self.CounterAttack = 0
        self.Buffs = []

    def use_weapon(self, player=None):
        """
        Calculate weapon damage for all 5 types.
        
        Returns:
            Dict containing damage array and enchantment details.
        """
        if player is None or player.weapon is None:
            return {"damage": [float(random.randint(2, 5)), 0, 0, 0, 0], "enchant_dmg": [0]*5}
        
        damage_array = [0.0, 0.0, 0.0, 0.0, 0.0]
        enchant_dmg = [0.0, 0.0, 0.0, 0.0, 0.0]
        
        # Calculate damage for each type
        for i in range(5):
            if self.DMG[i] > 0:
                if i == 4:  # Deep damage is always maximum
                    damage_array[i] = float(self.DMG[4])
                else:
                    damage_array[i] = float(random.randint(max(0, int(self.DMG_min[i])), self.DMG[i]))
        
        # Apply boosts from equipment (only to physical damage for now)
        for item in [player.ring, player.ring2, player.ring3, player.armor]:
            if item and hasattr(item, 'DmgBoost'):
                damage_array[0] += item.DmgBoost
        
        # Apply Enchantments
        try:
            enchants = get_item_enchants(self)
            for entry in enchants:
                for cat_ench in ENCHANTMENTS_CATALOG.values():
                    if cat_ench.family_id == entry["family_id"]:
                        mods = cat_ench.apply_to_weapon(self)
                        if "dmg_flat_bonus" in mods:
                            bonus = mods["dmg_flat_bonus"]
                            for i in range(min(5, len(bonus))):
                                extra = bonus[i] * entry.get("level", 1)
                                damage_array[i] += extra
                                enchant_dmg[i] += extra
        except: pass

        return {"damage": damage_array, "enchant_dmg": enchant_dmg}
    
class cEquippableItems:
    def __init__(self, ID, name, Defense, HealthBoost, HealthSteal, DmgBoost, Gold_Cost, Description, objectcheck):
        """
        Equippable item with multi-type defense.
        
        Args:
            Defense: Can be:
                - Single int (applies to physical defense only)
                - Array of 5 values [Physical, Thermal, Earth, Electric, Deep]
        """
        self.ID = ID
        self.name = name
        
        self.Defense = _normalize_5_values(Defense)
        
        self.HealthBoost = HealthBoost
        self.HealthSteal = HealthSteal
        self.DmgBoost = DmgBoost
        self.Gold_Cost = Gold_Cost
        self.Description = Description
        self.objectcheck = objectcheck
        self.AppliedStats = False

        # Atributos nuevos para SecHand
        self.ManaRegen = 0.0
        self.DefensePercentage = [0.0] * 5
        self.AGI = 0
        self.Evasion = 0
        self.CounterAttack = 0
        self.Barrier = 0
        self.Buffs = []


class cObject:
    def __init__(self, ID, name, HealthRestore, ManaRestore, Gold_Cost, Description):
        """Consumable object (potions, etc.)"""
        self.ID = ID
        self.name = name
        self.HealthRestore = HealthRestore
        self.ManaRestore = ManaRestore
        self.Gold_Cost = Gold_Cost
        self.Description = Description


class InventorySlot:
    """Representa un slot del inventario que puede contener múltiples items apilados"""
    
    def __init__(self, item, quantity: int = 1):
        self.item = item
        self.quantity = quantity
        self.max_stack = getattr(item, 'MaxStack', 1)
    
    def can_add(self, amount: int = 1) -> bool:
        return (self.quantity + amount) <= self.max_stack
    
    def add(self, amount: int = 1) -> int:
        space_available = self.max_stack - self.quantity
        can_add = min(amount, space_available)
        overflow = amount - can_add
        self.quantity += can_add
        return overflow
    
    def remove(self, amount: int = 1) -> int:
        can_remove = min(amount, self.quantity)
        self.quantity -= can_remove
        return can_remove
    
    def is_empty(self) -> bool:
        return self.quantity <= 0
    
    def get_display_name(self) -> str:
        item_name = getattr(self.item, 'Name', getattr(self.item, 'name', 'Unknown'))
        return f"{item_name} x{self.quantity}" if self.quantity > 1 else item_name


class cInventory:
    
    def __init__(self):
        self.slots: List = []
    
    def addObject(self, item, quantity: int = 1, appenditem=True):
        """
        Agrega objeto con sistema de stacking
        
        Args:
            item: Objeto a agregar
            quantity: Cantidad
            appenditem: Si False, remueve en su lugar
        """
        if not appenditem:
            self.remove_item(item, quantity)
            return
        
        item_id = getattr(item, 'ID', None)
        remaining = quantity
        
        for slot in self.slots:
            if getattr(slot.item, 'ID', None) == item_id:
                if slot.can_add(remaining):
                    slot.add(remaining)
                    remaining = 0
                    break
                else:
                    overflow = slot.add(remaining)
                    remaining = overflow
                    if remaining == 0:
                        break
        
        while remaining > 0:
            max_stack = getattr(item, 'MaxStack', 1)
            slot_quantity = min(remaining, max_stack)
            new_slot = InventorySlot(item, slot_quantity)
            self.slots.append(new_slot)
            remaining -= slot_quantity
    
    def remove_item(self, item, quantity: int = 1) -> int:
        item_id = item if isinstance(item, int) else getattr(item, 'ID', None)
        removed = 0
        slots_to_remove = []
        
        for i, slot in enumerate(self.slots):
            if getattr(slot.item, 'ID', None) == item_id:
                can_remove = slot.remove(quantity - removed)
                removed += can_remove
                if slot.is_empty():
                    slots_to_remove.append(i)
                if removed >= quantity:
                    break
        
        for i in reversed(slots_to_remove):
            del self.slots[i]
        
        return removed
    
    def get_item_count(self, item_id: int) -> int:

        total = 0
        for slot in self.slots:
            if getattr(slot.item, 'ID', None) == item_id:
                total += slot.quantity
        return total
    
    def has_item(self, item_id: int, quantity: int = 1) -> bool:
        return self.get_item_count(item_id) >= quantity
    
    @property
    def lObjectsInventory(self):
        items = []
        for slot in self.slots:
            for _ in range(slot.quantity):
                items.append(slot.item)
        return items
    
    @property
    def Objects(self):
        return self.lObjectsInventory


##################      Variables
vInventory = cInventory()

##################      Defs
def setup_player():
    try:
        console.print(Panel("[italic]Escribe tu nombre:  [/italic]", title="[bold green]Entrada[/bold green]", expand=False, box=ROUNDED))
        NamePlayer = input("> ")

    except Exception as e:
        NameLoop = True
        print(f"Error descnonocido\n Exception:\n{e}")
        while NameLoop == True:
                try:
                    console.print(Panel("[italic]Escribe tu nombre:  [/italic]", title="[bold green]Entrada[/bold green]", expand=False, box=ROUNDED))
                    NamePlayer = input("> ")
                    NameLoop = False
                except Exception as e:
                    Write(os.path.join("logs", "logs.txt"), None, f"[Crit] {e}", None, True)
        del NameLoop
    return(cPlayer(NamePlayer, None))

def Companion_Updater(player):
    """
    Se llama desde cPlayer.Check() cada tick.
    Regenera mana de los compañeros vivos.
    """
    for c in player.companion:
        if getattr(c, "is_alive", False):
            c.Mana = min(
                getattr(c, "Mana", 0) + getattr(c, "ManaRegen", 0),
                getattr(c, "Mana_max", 0),
            )

def enemy_loader(data_npc, return_single=False):
    """
    Load enemy data from JSON with multi-type damage system.
    
    Args:
        data_npc: Enemy data from JSON
        return_single: If True, returns a single random enemy; if False, returns list
        
    Returns:
        List of enemy objects or single enemy object if return_single is True
    """
    enemy_total_list = []
    
    NON_ENEMY_KEYS = {"Strings", "Gathering"}
    
    for enemy_group in data_npc:
        for key, enemy_data in enemy_group.items():
            if key not in NON_ENEMY_KEYS:
                try:
                    # Extract damage arrays
                    # DMG [Physical, Thermal, Earth, Electric, Deep]
                    dmg_array = enemy_data.get('DMG', [0, 0, 0, 0, 0])

                    # DMG_min [Physical, Thermal, Earth, Electric]
                    dmg_min_array = enemy_data.get('DMG_min', [0, 0, 0, 0])
                    

                    # DEF [Physical, Thermal, Earth, Electric, Deep]
                    def_array = enemy_data.get('DEF', [0, 0, 0, 0, 0])
                    
                    # Create enemy instance
                    enemy_load_var = cEnemy(
                        NAME=enemy_data.get('NAME', 'Unknown'),
                        HP_M=enemy_data.get('HP_M', 10),
                        DMG=dmg_array,
                        DMG_min=dmg_min_array,
                        MP_M=enemy_data.get('MP_M', 0),
                        EXP_TO_PLAYER=enemy_data.get('EXP_TO_PLAYER', 0),
                        DEF=def_array,
                        LS=enemy_data.get('LS', 0),
                        AGI=enemy_data.get('AGI', 0),
                        DBUFF_TO_PLAYER=enemy_data.get('DBUFF_TO_PLAYER', []),
                        BUFF_RECEIVED=enemy_data.get('BUFF_RECEIVED', []),
                        GOLD=enemy_data.get('GOLD', 0),
                        IS_BOSS=enemy_data.get('IS_BOSS', False),
                        SPAWN_CHANCE=enemy_data.get('SPAWN_CHANCE', 1.0),
                        GROUP_SPAWN=enemy_data.get('group_spawn', enemy_data.get('GROUP_SPAWN')),
                        loot_tables=enemy_data.get('loot_tables', {}),
                        AFFINITIES=resolve_enemy_affinities(enemy_data)
                    )
                    enemy_total_list.append(enemy_load_var)
                except Exception as e:
                    print(f"Error loading enemy {key}: {str(e)}")
                    continue
    
    if not enemy_total_list:
        return [] if not return_single else None
        
    return enemy_total_list if not return_single else random.choice(enemy_total_list)
