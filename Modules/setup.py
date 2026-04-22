from rich.console import Console
from rich.theme import Theme
from Modules.Loader import Write, Read
from dataclasses import dataclass, field
from typing import Any, Dict, List
from rich.panel import Panel
from rich.box import ROUNDED

import random
import time as sp
from Modules.input_utils import wait_for_enter

##################      First Variables
player = None
LObject = []
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

##################      Classes
class cPlayer:
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
        self.skills_purchased = []
        # Secondary Stats
        self.DEF = [0, 0, 0, 0, 0]  # [Phys, Thermal, Earth, Electric, Deep]
        self.AGI = 0
        self.DefensePercentage = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.CounterAttack = 0
        self.Evasion = 0
        self.ManaRegen = 2.5
        self.RAC = 0
        self.Control = 0
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

        # Seems like this can changed fore something better
        self.items_in_PlayerClass = [self.weapon, self.helmet, self.armor, self.boots, self.ring, self.ring2, self.ring3]

        self.applieddebuffs = []
        self.appliedbuffs = []
        self.companion = []
        self.lobjectscheck = [
            (self.helmet, "Helmet"),
            (self.armor, "Armor"),
            (self.boots, "Boots"),
            (self.ring, "Ring"),
            (self.ring2, "Ring"),
            (self.ring3, "Ring")
        ]

    def attack(self, enemy):
        """Attack an enemy with multi-type damage system"""
        if self.weapon is None:
            # Base attack without weapon
            damage = random.randint(1, 3)
            enemy.TakeDamage([damage, 0, 0, 0, 0])
            print(f"{self.name} ataca a {enemy.NAME} con sus puños causando {damage} de daño!")
            return damage
        
        # Get damage from weapon - returns [physical, thermal, earth, electric, deep]
        damage_array = self.weapon.use_weapon(self)
        
        # Apply defense calcs
        final_damage = [0, 0, 0, 0, 0]
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
        
        for i in range(5):
            if damage_array[i] > 0:
                enemy_def = enemy.DEF[i]
                final_damage[i] = max(0, damage_array[i] - (enemy_def / 2))
        
        # Calculate total damage
        total_damage = sum(final_damage)
        
        if total_damage < 1:
            total_damage = 2
            final_damage[0] = 2
        
        # Apply damage to enemy
        enemy.TakeDamage(final_damage)
        
        # Display attack message with damage breakdown
        print(f"{self.name} ataca a {enemy.NAME} con {self.weapon.name} causando {total_damage:.1f} de daño total!", end=" ")
        
        # Show breakdown of non-zero damage types
        damage_breakdown = []
        for i, dmg in enumerate(final_damage):
            if dmg > 0:
                damage_breakdown.append(f"{damage_type_names[i]}: {dmg:.1f}")
        
        if damage_breakdown:
            print(f"({', '.join(damage_breakdown)})")
        else:
            print()
        
        return total_damage

    def TakeDamage(self, damage):
        """
        Reduces player's HP based on the {damage} variable.
        Damage must be a list/tuple of 5 values
        [physical, thermal, electric, earth, deep].

        Flujo de daño:
        1. Se calcula el daño bruto total.
        2. La BARRERA absorbe daño BRUTO (sin resistencias).
        3. Si queda exceso, se aplican las defensas/resistencias del jugador
           al daño restante, y el resultado impacta HP.
        """
        if not isinstance(damage, (list, tuple)):
            raise ValueError("TakeDamage requiere una lista/tupla de dano")

        raw_total = sum(damage)

        # ── Paso 1: Barrera absorbe daño bruto ──
        if self.Barrier > 0:
            if raw_total <= self.Barrier:
                self.Barrier -= raw_total
                return  # Barrera absorbió todo, 0 daño a HP
            else:
                # Barrera destruida, calcular porcentaje restante
                absorbed = self.Barrier
                self.Barrier = 0
                # Reducir proporcionalmente cada tipo de daño
                if raw_total > 0:
                    ratio = (raw_total - absorbed) / raw_total
                    damage = [d * ratio for d in damage]

        # ── Paso 2: Aplicar defensas al daño restante ──
        final_damage = 0.0
        for i in range(min(len(damage), 5)):
            if damage[i] > 0:
                player_def = self.DEF[i] if i < len(self.DEF) else 0
                remaining = max(0, damage[i] - (player_def / 2))
                block_ratio = 0.0
                if isinstance(self.DefensePercentage, list) and i < len(self.DefensePercentage):
                    block_ratio = min(1.0, self.DefensePercentage[i] / 100.0)
                final_damage += remaining * (1.0 - block_ratio)

        self.Health -= final_damage
        if self.Health < 0:
            self.Health = 0

    def level_up(self):
        """Maneja la subida de nivel, incrementando la exp requerida en x1.07"""
        Before_Levelup = self.Level
        while self.EXP >= self.EXP_M:  
            self.Level += 1
            self.EXP -= self.EXP_M
            self.EXP_M *= 1.07
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

    def Check(self, lInventory):
        """Valida estado del jugador, equipamiento e inventario. Recibe lInventory (cInventory)."""
        slot_names = ["weapon", "helmet", "armor", "boots", "ring", "ring2", "ring3"]
        self.items_in_PlayerClass = [self.weapon, self.helmet, self.armor, self.boots, self.ring, self.ring2, self.ring3]
        # Actualizar lobjectscheck con el estado actual (no el de __init__)
        self.lobjectscheck = [
            (self.helmet, "Helmet"),
            (self.armor, "Armor"),
            (self.boots, "Boots"),
            (self.ring, "Ring"),
            (self.ring2, "Ring"),
            (self.ring3, "Ring")
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

        for i, obj in enumerate(self.items_in_PlayerClass):
            if isinstance(obj, cObject):
                setattr(self, slot_names[i], None)
                lInventory.addObject(obj)
        if self.Health <= 0:
            self.Health = self.Health_max
            self.Gold -= (self.Health_max * 0.6)
        
        for item in self.items_in_PlayerClass:
            if isinstance(item, cEquippableItems) and item.AppliedStats == False:
                # Handle defense as array
                for i in range(min(5, len(item.Defense))):
                    self.DEF[i] += item.Defense[i]
                    
                self.Health_max += item.HealthBoost
                
                # Marcar el item como aplicado para evitar aplicar stats múltiples veces
                item.AppliedStats = True
                
        for item, objecttype in self.lobjectscheck:
            if item and objecttype is not None:
                if item.objectcheck != objecttype:
                    lInventory.addObject(item)
                    setattr(self, objecttype.lower(), None)

        self.level_up()

    def Points(self):
        from Modules.SkillTreeSystem import skill_tree_manager
        skill_tree_manager.open_menu(self)

class cEnemy:
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
                  SPAWN_CHANCE=1.0):
        self.NAME = NAME
        self.HP_M = HP_M
        self.HP = self.HP_M
        self.IS_BOSS = IS_BOSS
        self.SPAWN_CHANCE = SPAWN_CHANCE

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

    def attack(self, target):
        """Attack target with multi-type RAW damage.
        La defensa la aplica el target en su propio TakeDamage."""
        raw_damage = [0, 0, 0, 0, 0]
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]

        # Calculate raw damage for each type
        for i in range(5):
            if self.DMG[i] > 0:
                if i == 4:  # Deep damage is always maximum
                    raw_damage[i] = self.DMG[4]
                else:
                    raw_damage[i] = random.randint(self.DMG_min[i], self.DMG[i])

        total_raw = sum(raw_damage)

        # Apply damage to target (target handles its own barrier + defense)
        target.TakeDamage(raw_damage)

        # Display damage breakdown
        print(f"\n{self.NAME} ataca a {target.name} causando {total_raw:.1f} puntos de daño!", end=" ")

        damage_breakdown = []
        for i, dmg in enumerate(raw_damage):
            if dmg > 0:
                damage_breakdown.append(f"{damage_type_names[i]}: {dmg:.1f}")

        if damage_breakdown:
            print(f"({', '.join(damage_breakdown)})")
        else:
            print()

        return total_raw

    def TakeDamage(self, damage):
        """
        Reduces enemy HP.
        - A list/tuple of 5 damage values
        """
        if not isinstance(damage, (list, tuple)):
            raise ValueError("TakeDamage requiere una lista/tupla de dano")
        total_damage = sum(damage)
            
        self.HP -= total_damage
        if self.HP < 0:
            self.HP = 0
    


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
        
        LObject.append(self)
        

    def use_weapon(self, player=None):
        """
        Calculate weapon damage for all 5 types.
        
        Returns:
            Array of 5 damage values [Physical, Thermal, Earth, Electric, Deep]
        """
        if player is None or player.weapon is None:
            return [random.randint(2, 5), 0, 0, 0, 0]  # Base physical damage
        
        damage_array = [0, 0, 0, 0, 0]
        
        # Calculate damage for each type
        for i in range(5):
            if self.DMG[i] > 0:
                if i == 4:  # Deep damage is always maximum
                    damage_array[i] = self.DMG[4]
                else:
                    damage_array[i] = random.randint(self.DMG_min[i], self.DMG[i])
        
        # Apply boosts from equipment (only to physical damage for now)
        for item in [player.ring, player.ring2, player.ring3, player.armor]:
            if item and hasattr(item, 'DmgBoost'):
                damage_array[0] += item.DmgBoost
        
        return damage_array
    
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

        LObject.append(self)
        


class cObject:
    def __init__(self, ID, name, HealthRestore, ManaRestore, Gold_Cost, Description):
        """Consumable object (potions, etc.)"""
        self.ID = ID
        self.name = name
        self.HealthRestore = HealthRestore
        self.ManaRestore = ManaRestore
        self.Gold_Cost = Gold_Cost
        self.Description = Description
        LObject.append(self)
        

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


class cIDSorter:
    def __init__(self, lvObjects):
        self.lvObjects = lvObjects

    def SearchObject(self, ID):
        for vObject in self.lvObjects:
            if vObject.ID == ID:
                return vObject
        
class cShop:
    def __init__(self, BuyObject, Gold_Cost):
        self.BuyObject = BuyObject
        self.Gold_Cost = Gold_Cost

    def buy(self):
        if player.Gold >= self.Gold_Cost:
            player.Gold -= self.Gold_Cost
            vInventory.addObject(self.BuyObject)
            print(f"Se ha comprado: {self.BuyObject.name}")
        else:
            text_input = "No tienes Dinero suficiente"
            print(f"Dinero actual: {player.Gold}")
            print(f"El vObject cuesta: {self.Gold_Cost}")
            return text_input

##################      Variables
vInventory = cInventory()
InventorySorter = cIDSorter(vInventory.lObjectsInventory)
LObjectSorter = cIDSorter(LObject)
SLObject = sorted(LObject, key=lambda x: x.ID)

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
                    Write("\\logs\\logs.txt", None, None, "[Crit]", e, True, True)
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
                        SPAWN_CHANCE=enemy_data.get('SPAWN_CHANCE', 1.0)
                    )
                    enemy_total_list.append(enemy_load_var)
                except Exception as e:
                    print(f"Error loading enemy {key}: {str(e)}")
                    continue
    
    if not enemy_total_list:
        return [] if not return_single else None
        
    return enemy_total_list if not return_single else random.choice(enemy_total_list)
