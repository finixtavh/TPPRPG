from rich.console import Console
from rich.theme import Theme
from Modules.Loader import Write, Read
from dataclasses import dataclass, field
from typing import Any, Dict, List

import random
import time as sp
from Modules.input_utils import wait_for_enter

##################      First Variables
player = None
LObject = []
console = Console()

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
        # Secondary Stats
        self.DEF = [0, 0, 0, 0, 0]  # [Phys, Thermal, Earth, Electric, Deep]
        self.AGI = 0
        self.DefensePercentage = 0
        self.CounterAttack = 0
        self.Evasion = 0
        self.ManaRegen = 2.5
        self.RAC = 0
        self.Control = 0
        self.Barrier = 0
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
        
        # Apply defense calculations for each damage type
        final_damage = [0, 0, 0, 0, 0]
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
        
        for i in range(5):
            if damage_array[i] > 0:
                # Apply defense (you can customize the formula here)
                enemy_def = enemy.DEF[i] if isinstance(enemy.DEF, (list, tuple)) else 0
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
        Damage can be:
        - A single number (backward compatibility)
        - A list/tuple of 5 damage values [physical, thermal, earth, electric, deep]
        """
        if isinstance(damage, (list, tuple)):
            total_damage = sum(damage)
        else:
            total_damage = damage
            
        self.Health -= total_damage
        if self.Health < 0:
            self.Health = 0

    def win(self, quantity, quantity2):
        """ This shall be called when the player defeats an enemy, 
        {quantity} is EXP 
        {quantity2}  is GOLD"""

        self.EXP += quantity
        self.Gold += quantity2
        if player.Level >= 2:
            player.EXP_M *= round(1.07)
        if self.EXP >= player.EXP_M:
            while self.EXP >= self.EXP_M:
                self.Level += 1
                self.EXP -= self.EXP_M
                self.Health_max += 10
                self.Health += round(self.Health_max/3.18*1.145)
                print(f"{self.name} sube de Level y ahora es Level {self.Level}!")

    def PlayerObjects(self):
        """ Prints atrributes of the player's equipment """

        for item in self.items_in_PlayerClass:
            if isinstance(item, cEquippableItems):
                print(f"{item.name}", end=" ")
                for attr_name in ["ID", "Defense", "HealthBoost", "HealthSteal", "DmgBoost", "Description"]:
                    attr_value = getattr(item, attr_name, None)
                    if attr_value is not None:
                        if attr_name == "Defense" and isinstance(attr_value, (list, tuple)):
                            # Display defense array
                            defense_str = "/".join([str(d) for d in attr_value])
                            print(f"-Defense: [{defense_str}]", end=" ")
                        elif isinstance(attr_value, (int, float)) and attr_value > 0:
                            if attr_name == "Description":
                                print(f"-Description: {attr_value}\n")
                            else:
                                print(f"-{attr_name}: {attr_value}", end=" ")

                        
            elif isinstance(item, cWeapon):
                dmg_str = "/".join([f"{item.DMG[i]}" for i in range(5)])
                print(f"{item.name} -ID: {item.ID} -Daño: [{dmg_str}] -Description: {item.Description}")
                print("\n")
                
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

        Companion_Updater(self)
        Before_Levelup = self.Level

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
                if isinstance(item.Defense, (list, tuple)):
                    for i in range(min(5, len(item.Defense))):
                        self.DEF[i] += item.Defense[i]
                else:
                    # Backward compatibility - single value applies to physical defense
                    self.DEF[0] += item.Defense
                    
                self.Health_max += item.HealthBoost
                
                # Marcar el item como aplicado para evitar aplicar stats múltiples veces
                item.AppliedStats = True
                
        for item, objecttype in self.lobjectscheck:
            if item and objecttype is not None:
                if item.objectcheck != objecttype:
                    lInventory.addObject(item)
                    setattr(self, objecttype.lower(), None)

        while self.EXP >= self.EXP_M:  
            self.Level += 1
            self.EXP_M *= 1.4
        if Before_Levelup != self.Level:
            console.print(f"Has subido de nivel!")
            console.print(f"Antes: {Before_Levelup}")
            console.print(f"Ahora: {self.Level}")

            exp_formated = "{:,.2f}".format(self.EXP)
            exp_m_formated = "{:,.2f}".format(self.EXP_M)

            exp_formated = exp_formated.replace(",", "X").replace(".", ",").replace("X", ".")
            exp_m_formated = exp_m_formated.replace(",", "X").replace(".", ",").replace("X", ".")

            console.print(f"Tienes: {exp_formated} y ahora requeriras {exp_m_formated} para avanzar al siguiente nivel")

            wait_for_enter()

    def Equip(self, vInventory, InventorySortervar, player):
        print("\nInventario: \n")
        try:
            EquipInput = int(input("[1]- Equipa [2]-Desequipar"))
        except Exception as e:
            print(f"\nException\n{e}") # Necesita revision 08/02/2024
        if EquipInput == 1:
            for i, var in enumerate(vInventory.lObjectsInventory, start=1):
                if var is not None:
                    if i % 2 == 0:
                        print(f"ID: {var.ID} | {var.name}\t", end=" ")
                    else:
                        print(f"ID: {var.ID} | {var.name}\t", end="\n")
            print("\nIngresa el ID del Objeto: \n")
        elif EquipInput == 2:
            for i, var in enumerate(vInventory.lObjectsInventory, start=1):
                if var is not None:
                    if i % 2 == 0:
                        print(f"ID: {var.ID} | {var.name}\t", end=" ")
                    else:
                        print(f"ID: {var.ID} | {var.name}\t", end="\n")
            print("\nIngresa el ID del Objeto: \n")

            EquipInput = int(input("ID:: "))
            weapon_get = InventorySortervar.SearchObject(EquipInput)
            print(weapon_get.name)

            if isinstance(weapon_get, cEquippableItems):
                if weapon_get.objectcheck == "Ring" or weapon_get.objectcheck == "ring":
                    for ring in [self.ring, self.ring2, self.ring3]:
                        if ring is None:
                            ring = InventorySortervar
                            break
                        elif ring is not None:
                            vInventory.addObject(ring)
                            ring = InventorySortervar
                            break
                else:
                    setattr(self, weapon_get.objectcheck.lower(), InventorySortervar)

            elif isinstance(weapon_get, cWeapon):
                if self.weapon is not None:
                    vInventory.addObject(self.weapon)
                    print(f"Se desequipó {self.weapon.name}")

                player.weapon = weapon_get
                
                print(f"Se equipó {weapon_get.name}")
                vInventory.addObject(weapon_get, False)
                sp.sleep(3.5)


class cEnemy:
    def __init__ (self, NAME, 
                  HP_M,  
                  DMG, DMG_min,  # Now expects arrays of 5 values
                  MP_M, 
                  EXP_TO_PLAYER, 
                  DEF, LS, AGI,  # DEF is now array of 5 values
                  DBUFF_TO_PLAYER, 
                  BUFF_RECEIVED,
                  GOLD):
        self.NAME = NAME
        self.HP_M = HP_M
        self.HP = self.HP_M
        
        # Store damage arrays - DMG has 5 values, DMG_min has 4 (deep always max)
        # Format: [Physical, Thermal, Earth, Electric, Deep]
        if isinstance(DMG, (list, tuple)) and len(DMG) >= 5:
            self.DMG = list(DMG)
        elif isinstance(DMG, (list, tuple)) and len(DMG) == 2:
            # Old format: [Physical, Magical] -> [Physical, Thermal, Earth, Electric, Deep]
            # Assign the old "Magical" damage to Thermal (index 1)
            self.DMG = [DMG[0], DMG[1], 0, 0, 0]
        else:
            # Single value or other format
            dmg_val = DMG if isinstance(DMG, (int, float)) else (DMG[0] if isinstance(DMG, (list, tuple)) and len(DMG) > 0 else 0)
            self.DMG = [dmg_val, 0, 0, 0, 0]
        
        if isinstance(DMG_min, (list, tuple)) and len(DMG_min) >= 4:
            self.DMG_min = list(DMG_min) + [self.DMG[4]]  # Deep damage always at max
        elif isinstance(DMG_min, (list, tuple)) and len(DMG_min) == 2:
            # Old format: [Physical_min, Magical_min] -> [Physical, Thermal, Earth, Electric]
            # Assign the old "Magical_min" to Thermal (index 1)
            self.DMG_min = [DMG_min[0], DMG_min[1], 0, 0, self.DMG[4]]
        else:
            # Single value or other format
            dmg_min_val = DMG_min if isinstance(DMG_min, (int, float)) else (DMG_min[0] if isinstance(DMG_min, (list, tuple)) and len(DMG_min) > 0 else 0)
            self.DMG_min = [dmg_min_val, 0, 0, 0, self.DMG[4]]
        
        # Defense is now array: [Physical, Thermal, Earth, Electric, Deep]
        if isinstance(DEF, (list, tuple)) and len(DEF) >= 5:
            self.DEF = list(DEF)
        elif isinstance(DEF, (list, tuple)) and len(DEF) == 2:
            # Old format: [Physical_def, Magical_def] -> apply magical_def to all magic types
            # [Physical, Thermal, Earth, Electric, Deep]
            self.DEF = [DEF[0], DEF[1], DEF[1], DEF[1], DEF[1]]
        else:
            # Single value applies to all defenses
            def_value = DEF if isinstance(DEF, (int, float)) else (DEF[0] if isinstance(DEF, (list, tuple)) and len(DEF) > 0 else 0)
            self.DEF = [def_value, def_value, def_value, def_value, def_value]
        
        self.MP_M = MP_M
        self.MP = self.MP_M
        self.EXP_TO_PLAYER = EXP_TO_PLAYER
        self.LS = LS
        self.AGI = AGI
        self.DBUFF_TO_PLAYER = DBUFF_TO_PLAYER
        self.BUFF_RECEIVED = BUFF_RECEIVED
        self.GOLD = GOLD

    def attack(self, player):
        """Attack player with multi-type damage"""
        damage_array = [0, 0, 0, 0, 0]
        damage_type_names = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
        
        # Calculate damage for each type
        for i in range(5):
            if self.DMG[i] > 0:
                if i == 4:  # Deep damage is always maximum
                    raw_damage = self.DMG[4]
                else:
                    raw_damage = random.randint(self.DMG_min[i], self.DMG[i])
                
                # Apply player defense
                player_def = player.DEF[i] if isinstance(player.DEF, (list, tuple)) else 0
                damage_array[i] = max(0, raw_damage - (player_def / 2))
        
        total_damage = sum(damage_array)
        
        # Apply damage to player
        player.TakeDamage(damage_array)
        
        # Display damage breakdown
        print(f"\n{self.NAME} ataca a {player.name} causando {total_damage:.1f} puntos de daño!", end=" ")
        
        damage_breakdown = []
        for i, dmg in enumerate(damage_array):
            if dmg > 0:
                damage_breakdown.append(f"{damage_type_names[i]}: {dmg:.1f}")
        
        if damage_breakdown:
            print(f"({', '.join(damage_breakdown)})")
        else:
            print()
        
        return total_damage

    def TakeDamage(self, damage):
        """
        Reduces enemy HP.
        Damage can be:
        - A single number (backward compatibility)
        - A list/tuple of 5 damage values
        """
        if isinstance(damage, (list, tuple)):
            total_damage = sum(damage)
        else:
            total_damage = damage
            
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
        
        # Store damage arrays
        # DMG format: [Physical, Thermal, Earth, Electric, Deep]
        if isinstance(DMG, (list, tuple)) and len(DMG) >= 5:
            self.DMG = list(DMG)
        else:
            # Backward compatibility
            self.DMG = [DMG if not isinstance(DMG, (list, tuple)) else DMG[0], 0, 0, 0, 0]
        
        # DMG_min format: [Physical, Thermal, Earth, Electric]
        # Deep damage is always at maximum (self.DMG[4])
        if isinstance(DMG_min, (list, tuple)) and len(DMG_min) >= 4:
            self.DMG_min = list(DMG_min)
        else:
            # Backward compatibility
            self.DMG_min = [DMG_min if not isinstance(DMG_min, (list, tuple)) else DMG_min[0], 0, 0, 0]
        
        # For backward compatibility with old code
        self.PHYSICAL_DMG = self.DMG[0]
        self.PHYSICAL_DMG_min = self.DMG_min[0]
        self.damage_min = self.DMG_min[0]
        self.damage_max = self.DMG[0]
        
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
        
        # Handle defense as array or single value
        if isinstance(Defense, (list, tuple)) and len(Defense) >= 5:
            self.Defense = list(Defense)
        else:
            # Single value applies only to physical defense
            def_value = Defense if isinstance(Defense, (int, float)) else 0
            self.Defense = [def_value, 0, 0, 0, 0]
        
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
        """Verifica si se puede agregar más items a este slot"""
        return (self.quantity + amount) <= self.max_stack
    
    def add(self, amount: int = 1) -> int:
        """Agrega items al slot. Returns: overflow"""
        space_available = self.max_stack - self.quantity
        can_add = min(amount, space_available)
        overflow = amount - can_add
        self.quantity += can_add
        return overflow
    
    def remove(self, amount: int = 1) -> int:
        """Remueve items del slot. Returns: cantidad removida"""
        can_remove = min(amount, self.quantity)
        self.quantity -= can_remove
        return can_remove
    
    def is_empty(self) -> bool:
        return self.quantity <= 0
    
    def get_display_name(self) -> str:
        """Nombre con cantidad si >1"""
        item_name = getattr(self.item, 'Name', getattr(self.item, 'name', 'Unknown'))
        return f"{item_name} x{self.quantity}" if self.quantity > 1 else item_name


class cInventory:
    """Sistema de inventario mejorado con stacks y menú interactivo"""
    
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
        
        # Intentar apilar en slots existentes
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
        
        # Crear nuevos slots si sobra
        while remaining > 0:
            max_stack = getattr(item, 'MaxStack', 1)
            slot_quantity = min(remaining, max_stack)
            new_slot = InventorySlot(item, slot_quantity)
            self.slots.append(new_slot)
            remaining -= slot_quantity
    
    def remove_item(self, item, quantity: int = 1) -> int:
        """Remueve item del inventario"""
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
        """Cantidad total de un item"""
        total = 0
        for slot in self.slots:
            if getattr(slot.item, 'ID', None) == item_id:
                total += slot.quantity
        return total
    
    def has_item(self, item_id: int, quantity: int = 1) -> bool:
        """Verifica si tiene suficiente cantidad"""
        return self.get_item_count(item_id) >= quantity
    
    def PrintObjects(self):
        """Muestra inventario simple (compatibilidad)"""
        if not self.slots:
            print("[yellow]El inventario está vacío[/yellow]")
            wait_for_enter()
            return
        
        print("\n[cyan]Inventario:[/cyan]\n")
        for slot in self.slots:
            item = slot.item
            display_name = slot.get_display_name()
            
            if hasattr(item, 'DMG'):
                dmg_str = "/".join([str(d) for d in item.DMG])
                print(f"  • {display_name} - Daño: [{dmg_str}]")
            elif hasattr(item, 'Defense'):
                if isinstance(item.Defense, (list, tuple)):
                    defense_str = "/".join([str(d) for d in item.Defense])
                    print(f"  • {display_name} - DEF: [{defense_str}]")
                else:
                    print(f"  • {display_name} - DEF: {item.Defense}")
            else:
                print(f"  • {display_name}")
        
        print("\nPresiona enter ↵")
        wait_for_enter()
    
    @property
    def lObjectsInventory(self):
        """Compatibilidad: retorna lista plana de items"""
        items = []
        for slot in self.slots:
            for _ in range(slot.quantity):
                items.append(slot.item)
        return items
    
    @property
    def Objects(self):
        """Alias para lObjectsInventory"""
        return self.lObjectsInventory


    
class cDebuff:
    def __init__(self, name, PersistentDamageDebuff=None, HealDebuff=None, ArmorPierce=None, AgilityDebuff=None, MPDisruption=None, EvadeDebuff=None, CounterAttackDebuff=None): 
        self.name = name
        self.PersistentDamageDebuff = PersistentDamageDebuff
        self.HealDebuff = HealDebuff
        self.ArmorPierce = ArmorPierce
        self.AgilityDebuff = AgilityDebuff
        self.MPDisruption = MPDisruption
        self.EvadeDebuff = EvadeDebuff
        self.CounterAttackDebuff = CounterAttackDebuff

    def Apply(self, Value, player):
        if Value is not None:
            if hasattr(self, Value):
                debuff_value = getattr(self, Value, None)
                if debuff_value is not None:
                    if Value == "PersistentDamageDebuff":
                        NotImplemented
                    if Value == "HealDebuff":
                        player.Health -= debuff_value
                    if Value == "ArmorPierce":
                        # Now handles defense arrays
                        if isinstance(player.DEF, (list, tuple)):
                            for i in range(5):
                                player.DEF[i] -= debuff_value
                        else:
                            player.Defense -= debuff_value
                    if Value == "AgilityDebuff":
                        NotImplemented
                    if Value == "MPDisruption":
                        NotImplemented                    
                    if Value == "EvadeDebuff":
                        NotImplemented
                    if Value == "CounterAttackDebuff":
                        NotImplemented

class cBuffs:
    def __init__(self, name, EvadeBuff=None, Heal=None, MagicArmor=None, MPregen=None, Strenght=None):    
        self.name = name
        self.EvadeBuff = EvadeBuff
        self.Heal = Heal
        self.MagicArmor = MagicArmor
        self.MPregen = MPregen
        self.Strength = Strenght

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
        NamePlayer = input("N:: ") 
    except Exception as e:
        NameLoop = True
        print(f"Error descnonocido\n Exception:\n{e}")
        while NameLoop == True:
                try:
                    NamePlayer = input("\nN:: ")
                    NameLoop = False
                except Exception as e:
                    Write("\\logs\\logs.txt", None, None, "[Crit]", e, True, True)
        del NameLoop
    return(cPlayer(NamePlayer, None))

def Companion_Updater(player):
    Chars = []
    for c in player.companion:
        Chars.append(c)

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
                        GOLD=enemy_data.get('GOLD', 0)
                    )
                    enemy_total_list.append(enemy_load_var)
                except Exception as e:
                    print(f"Error loading enemy {key}: {str(e)}")
                    continue
    
    if not enemy_total_list:
        return [] if not return_single else None
        
    return enemy_total_list if not return_single else random.choice(enemy_total_list)
