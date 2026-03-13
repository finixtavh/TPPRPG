"""
Sistema de Encantamientos para TPPRPG
======================================
Gestiona encantamientos para Armas, Equipamiento y Herramientas
"""

from typing import Dict, Any, List, Optional


class cEnchantment:
    """
    Clase universal para todos los encantamientos
    
    Los encantamientos tienen efectos específicos según la clase objetivo:
    - cWeapon: Modifican daño, crit, efectos especiales
    - cEquippableItems: Modifican defensa, HP, robo de vida, resistencias
    - cTool: Modifican eficiencia, durabilidad, drops extras
    """
    
    def __init__(self, ENCHANT_ID: int, Name: str, TargetClass: str,
                 Description: str, Rarity: str, Effects: Dict[str, Any],
                 MaxLevel: int = 1, GoldCost: int = 0):
        """
        Args:
            ENCHANT_ID: ID único del encantamiento
            Name: Nombre del encantamiento
            TargetClass: Clase objetivo ("cWeapon", "cEquippableItems", "cTool")
            Description: Descripción del efecto
            Rarity: Rareza ("Common", "Uncommon", "Rare", "Epic", "Legendary")
            Effects: Dict con efectos del encantamiento
            MaxLevel: Nivel máximo del encantamiento (para encantamientos mejorables)
            GoldCost: Costo base para aplicar el encantamiento
        """
        self.ENCHANT_ID = ENCHANT_ID
        self.Name = Name
        self.TargetClass = TargetClass
        self.Description = Description
        self.Rarity = Rarity
        self.Effects = Effects
        self.MaxLevel = MaxLevel
        self.GoldCost = GoldCost
        
        # Metadata
        self.current_level = 1  # Nivel actual cuando está aplicado
    
    def can_apply_to(self, item) -> bool:
        """
        Verifica si este encantamiento puede aplicarse al item
        
        Args:
            item: Objeto (cWeapon, cEquippableItems, cTool)
            
        Returns:
            True si el encantamiento es compatible
        """
        item_class = type(item).__name__
        return item_class == self.TargetClass
    
    def apply_to_weapon(self, weapon) -> Dict[str, Any]:
        """
        Aplica efectos del encantamiento a un arma
        
        Effects disponibles para armas:
        - dmg_bonus: [Physical, Thermal, Earth, Electric, Deep] o float (% bonus)
        - dmg_min_bonus: [Physical, Thermal, Earth, Electric] o float
        - crit_chance: Float (0.0 - 1.0)
        - crit_damage: Float (multiplicador, ej: 2.0 = 200%)
        - lifesteal: Float (% de daño como vida robada)
        - elemental_boost: Dict {"thermal": 1.2, "electric": 1.5}
        - special_effect: String (nombre del efecto especial)
        
        Returns:
            Dict con modificadores aplicados
        """
        if self.TargetClass != "cWeapon":
            return {}
        
        modifications = {}
        
        # Bonus de daño
        if "dmg_bonus" in self.Effects:
            bonus = self.Effects["dmg_bonus"]
            if isinstance(bonus, (int, float)):
                # Bonus porcentual a todos los tipos
                modifications["dmg_multiplier"] = 1.0 + bonus
            elif isinstance(bonus, list):
                # Bonus específico por tipo
                modifications["dmg_flat_bonus"] = bonus
        
        # Bonus de daño mínimo
        if "dmg_min_bonus" in self.Effects:
            modifications["dmg_min_bonus"] = self.Effects["dmg_min_bonus"]
        
        # Critical
        if "crit_chance" in self.Effects:
            modifications["crit_chance"] = self.Effects["crit_chance"]
        
        if "crit_damage" in self.Effects:
            modifications["crit_damage"] = self.Effects["crit_damage"]
        
        # Robo de vida
        if "lifesteal" in self.Effects:
            modifications["lifesteal"] = self.Effects["lifesteal"]
        
        # Boost elemental
        if "elemental_boost" in self.Effects:
            modifications["elemental_boost"] = self.Effects["elemental_boost"]
        
        # Efectos especiales
        if "special_effect" in self.Effects:
            modifications["special_effect"] = self.Effects["special_effect"]
        
        return modifications
    
    def apply_to_equipment(self, equipment) -> Dict[str, Any]:
        """
        Aplica efectos del encantamiento a equipamiento
        
        Effects disponibles para equipamiento:
        - defense_bonus: [Physical, Thermal, Earth, Electric, Deep] o float (%)
        - health_bonus: Int (HP extra)
        - health_regen: Float (HP por segundo)
        - damage_reduction: Float (% reducción de daño, 0.0-1.0)
        - elemental_resistance: Dict {"thermal": 0.2, "deep": 0.15}
        - reflect_damage: Float (% de daño reflejado)
        - thorns: Int (daño fijo devuelto)
        - special_effect: String
        
        Returns:
            Dict con modificadores aplicados
        """
        if self.TargetClass != "cEquippableItems":
            return {}
        
        modifications = {}
        
        # Bonus de defensa
        if "defense_bonus" in self.Effects:
            bonus = self.Effects["defense_bonus"]
            if isinstance(bonus, (int, float)):
                modifications["defense_multiplier"] = 1.0 + bonus
            elif isinstance(bonus, list):
                modifications["defense_flat_bonus"] = bonus
        
        # HP extra
        if "health_bonus" in self.Effects:
            modifications["health_bonus"] = self.Effects["health_bonus"]
        
        # Regeneración
        if "health_regen" in self.Effects:
            modifications["health_regen"] = self.Effects["health_regen"]
        
        # Reducción de daño
        if "damage_reduction" in self.Effects:
            modifications["damage_reduction"] = self.Effects["damage_reduction"]
        
        # Resistencias elementales
        if "elemental_resistance" in self.Effects:
            modifications["elemental_resistance"] = self.Effects["elemental_resistance"]
        
        # Daño reflejado
        if "reflect_damage" in self.Effects:
            modifications["reflect_damage"] = self.Effects["reflect_damage"]
        
        if "thorns" in self.Effects:
            modifications["thorns"] = self.Effects["thorns"]
        
        # Efectos especiales
        if "special_effect" in self.Effects:
            modifications["special_effect"] = self.Effects["special_effect"]
        
        return modifications
    
    def apply_to_tool(self, tool) -> Dict[str, Any]:
        """
        Aplica efectos del encantamiento a herramienta
        
        Effects disponibles para herramientas:
        - efficiency_bonus: Float (multiplicador de eficiencia)
        - durability_bonus: Float (multiplicador de durabilidad)
        - fortune: Int (nivel de Fortune - items extra)
        - auto_smelt: Bool (fundir automáticamente)
        - silk_touch: Bool (obtener bloque sin procesar)
        - speed_bonus: Float (velocidad extra)
        - exp_bonus: Float (multiplicador de EXP)
        - special_effect: String
        
        Returns:
            Dict con modificadores aplicados
        """
        if self.TargetClass != "cTool":
            return {}
        
        modifications = {}
        
        # Eficiencia
        if "efficiency_bonus" in self.Effects:
            modifications["efficiency_multiplier"] = self.Effects["efficiency_bonus"]
        
        # Durabilidad
        if "durability_bonus" in self.Effects:
            modifications["durability_multiplier"] = self.Effects["durability_bonus"]
        
        # Fortune
        if "fortune" in self.Effects:
            modifications["fortune_level"] = self.Effects["fortune"]
        
        # Auto Smelt
        if "auto_smelt" in self.Effects:
            modifications["auto_smelt"] = self.Effects["auto_smelt"]
        
        # Silk Touch
        if "silk_touch" in self.Effects:
            modifications["silk_touch"] = self.Effects["silk_touch"]
        
        # Velocidad
        if "speed_bonus" in self.Effects:
            modifications["speed_multiplier"] = self.Effects["speed_bonus"]
        
        # EXP
        if "exp_bonus" in self.Effects:
            modifications["exp_multiplier"] = self.Effects["exp_bonus"]
        
        # Efectos especiales
        if "special_effect" in self.Effects:
            modifications["special_effect"] = self.Effects["special_effect"]
        
        return modifications
    
    def get_display_name(self) -> str:
        """Obtiene nombre con nivel si es mejorable"""
        if self.MaxLevel > 1:
            return f"{self.Name} {self.get_roman_numeral(self.current_level)}"
        return self.Name
    
    @staticmethod
    def get_roman_numeral(num: int) -> str:
        """Convierte número a romano (I-V)"""
        numerals = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
        return numerals.get(num, str(num))
    
    def get_rarity_color(self) -> str:
        """Obtiene color según rareza"""
        colors = {
            "Common": "white",
            "Uncommon": "green",
            "Rare": "blue",
            "Epic": "purple",
            "Legendary": "gold"
        }
        return colors.get(self.Rarity, "white")
    
    def __repr__(self):
        return f"<cEnchantment: {self.get_display_name()} [{self.Rarity}] for {self.TargetClass}>"


# Funciones helper para cargar encantamientos desde JSON

def load_enchantment_from_json(enchant_data: Dict) -> cEnchantment:
    """
    Crea un objeto cEnchantment desde datos JSON
    
    Args:
        enchant_data: Dict con datos del encantamiento
        
    Returns:
        Objeto cEnchantment
    """
    return cEnchantment(
        ENCHANT_ID=enchant_data['ENCHANT_ID'],
        Name=enchant_data['Name'],
        TargetClass=enchant_data['TargetClass'],
        Description=enchant_data['Description'],
        Rarity=enchant_data['Rarity'],
        Effects=enchant_data['Effects'],
        MaxLevel=enchant_data.get('MaxLevel', 1),
        GoldCost=enchant_data.get('GoldCost', 0)
    )


def get_enchantments_for_item(item, enchantments_list: List[cEnchantment]) -> List[cEnchantment]:
    """
    Filtra encantamientos aplicables a un item
    
    Args:
        item: Objeto (cWeapon, cEquippableItems, cTool)
        enchantments_list: Lista de todos los encantamientos disponibles
        
    Returns:
        Lista de encantamientos compatibles
    """
    return [ench for ench in enchantments_list if ench.can_apply_to(item)]


# Ejemplo de uso
if __name__ == "__main__":
    # Crear encantamiento de ejemplo para arma
    sharpness = cEnchantment(
        ENCHANT_ID=1,
        Name="Sharpness",
        TargetClass="cWeapon",
        Description="Aumenta el daño físico del arma",
        Rarity="Common",
        Effects={
            "dmg_bonus": [5, 0, 0, 0, 0],  # +5 daño físico
            "dmg_min_bonus": [3, 0, 0, 0]   # +3 daño mínimo físico
        },
        MaxLevel=5,
        GoldCost=100
    )
    
    print(sharpness)
    print(f"Display name: {sharpness.get_display_name()}")
    print(f"Color: {sharpness.get_rarity_color()}")
    
    # Simular aplicación a arma (necesitarías objeto real)
    modifications = sharpness.apply_to_weapon(None)
    print(f"Modifications: {modifications}")
