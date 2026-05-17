from typing import Dict, Any, List, Optional
import copy
from Modules.ModulesUtils.input_utils import get_menu_refresh_rate


# ── Constantes ──
MAX_ENCHANT_SLOTS = 5  # Máximo de encantamientos ÚNICOS por item

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
          6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}

def to_roman(n: int) -> str:
    """Convierte un entero (1-10) a número romano."""
    return _ROMAN.get(n, str(n))


class cEnchantment:
    """
    Clase universal para todos los encantamientos.

    Cada encantamiento del catálogo (JSON) define un "family_id" que agrupa
    todos los niveles del mismo encantamiento.  Cuando se aplica al item
    dos veces, en vez de ocupar un slot nuevo sube de nivel (I → II → III …).
    Al llegar a MaxLevel, si existe "max_level_name" el nombre muta
    (p.ej. "Sharpness V" → "Destrucción").
    """

    def __init__(self, ENCHANT_ID: int, Name: str, TargetClass: str,
                 Description: str, Rarity: str, Effects: Dict[str, Any],
                 MaxLevel: int = 1, GoldCost: int = 0,
                 family_id: str = "", max_level_name: str = "",
                 max_level_effects: Optional[Dict[str, Any]] = None,
                 max_level_description: str = ""):
        self.ENCHANT_ID = ENCHANT_ID
        self.Name = Name
        self.TargetClass = TargetClass
        self.Description = Description
        self.Rarity = Rarity
        self.Effects = Effects
        self.MaxLevel = MaxLevel
        self.GoldCost = GoldCost

        # ── Familia ──
        #   family_id agrupa los niveles del mismo encantamiento.
        #   Si no se define, se autogenera a partir del nombre.
        self.family_id = family_id or Name.lower().replace(" ", "_")

        # ── Transformación a nivel máximo ──
        self.max_level_name = max_level_name          # Nombre que adopta al llegar a MaxLevel
        self.max_level_effects = max_level_effects     # Efectos reemplazantes (opcional)
        self.max_level_description = max_level_description

        # Metadata de instancia (cuando ya está aplicado a un item)
        self.current_level = 1
    
    def can_apply_to(self, item) -> bool:
        """
        Verifica si este encantamiento puede aplicarse al item
        
        Args:
            item: Objeto (cWeapon, cEquippableItems, cTool)
            
        Returns:
            True si el encantamiento es compatible
        """
        item_class = type(item).__name__
        target = self.TargetClass.lower()
        
        # 1. Retrocompatibilidad: Si el target_class de JSON sigue diciendo "cWeapon"
        if target == item_class.lower():
            return True
            
        # 2. Validación por tipo de objeto (Nombre)
        item_name = getattr(item, "Name", getattr(item, "name", "")).lower()
        
        # Función rápida para ignorar las tildes al buscar
        import unicodedata
        def strip_accents(s):
            return ''.join(c for c in unicodedata.normalize('NFD', s)
                           if unicodedata.category(c) != 'Mn')
                           
        target_stripped = strip_accents(target)
        item_name_stripped = strip_accents(item_name)
        
        # Chequear si en "Espada de Acero" dice "espada" o "Armadura de cuero" dice "armadura"
        if target_stripped in item_name_stripped:
            return True
            
        return False
    
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
        """Nombre con nivel romano.
        Si está al máximo y tiene max_level_name, muta el nombre."""
        if self.current_level >= self.MaxLevel and self.max_level_name:
            return self.max_level_name
        if self.MaxLevel > 1:
            return f"{self.Name} {to_roman(self.current_level)}"
        return self.Name

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
ENCHANTMENTS_CATALOG: Dict[str, cEnchantment] = {}

def load_base_enchantments():
    """Carga todos los encantamientos base desde Data/DataEnchantments.json"""
    import json, os
    path = os.path.join("Data", "DataEnchantments.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        for category, enchants in data.items():
            if isinstance(enchants, dict):
                for key, ench_data in enchants.items():
                    if isinstance(ench_data, dict) and "ENCHANT_ID" in ench_data:
                        ench = load_enchantment_from_json(ench_data)
                        register_enchantment(ench)
                        count += 1
    except Exception as e:
        print(f"[WARNING] Error cargando DataEnchantments.json: {e}")

# Auto-cargar al importar el módulo (se ejecuta después de definir load_enchantment_from_json)
_BASE_LOADED = False

def register_enchantment(enchantment: cEnchantment):
    """Registra y almacena un encantamiento en el registro global"""
    ENCHANTMENTS_CATALOG[enchantment.Name] = enchantment

def get_enchantment(name: str) -> Optional[cEnchantment]:
    """Obtiene un encantamiento registrado por su nombre"""
    return ENCHANTMENTS_CATALOG.get(name)

def load_enchantment_from_json(enchant_data: Dict) -> cEnchantment:
    """Crea un objeto cEnchantment desde datos JSON"""
    return cEnchantment(
        ENCHANT_ID=enchant_data['ENCHANT_ID'],
        Name=enchant_data['Name'],
        TargetClass=enchant_data['TargetClass'],
        Description=enchant_data['Description'],
        Rarity=enchant_data['Rarity'],
        Effects=enchant_data['Effects'],
        MaxLevel=enchant_data.get('MaxLevel', 1),
        GoldCost=enchant_data.get('GoldCost', 0),
        family_id=enchant_data.get('family_id', ''),
        max_level_name=enchant_data.get('max_level_name', ''),
        max_level_effects=enchant_data.get('max_level_effects', None),
        max_level_description=enchant_data.get('max_level_description', ''),
    )


def get_enchantments_for_item(item, enchantments_list: List[cEnchantment]) -> List[cEnchantment]:
    """Filtra encantamientos aplicables a un item"""
    return [ench for ench in enchantments_list if ench.can_apply_to(item)]


# ── Helpers para los encantamientos aplicados a un item ──

def get_item_enchants(item) -> List[Dict[str, Any]]:
    """Devuelve la lista de encantamientos aplicados (list of dicts).
    Normaliza listas legacy de strings a dicts."""
    if not hasattr(item, "Enchantments") or item.Enchantments is None:
        item.Enchantments = []
        return item.Enchantments
    raw = item.Enchantments
    # Migración: strings viejos → dicts nuevos
    migrated = []
    changed = False
    for entry in raw:
        if isinstance(entry, str):
            migrated.append({"family_id": entry.lower().replace(" ", "_"),
                             "name": entry, "level": 1})
            changed = True
        elif isinstance(entry, dict):
            migrated.append(entry)
    if changed:
        item.Enchantments = migrated
    return item.Enchantments


def count_unique_families(item) -> int:
    """Cuántas *familias* distintas tiene el item."""
    enchants = get_item_enchants(item)
    return len({e["family_id"] for e in enchants})


def find_existing_family(item, family_id: str) -> Optional[Dict[str, Any]]:
    """Busca si ya existe un encantamiento de la misma familia."""
    for e in get_item_enchants(item):
        if e["family_id"] == family_id:
            return e
    return None


def format_enchant_display(entry: Dict[str, Any], catalog: Dict) -> str:
    """Devuelve la cadena bonita para un encantamiento aplicado.
    Ejemplo: 'Sharpness III' o 'Destrucción' si está al max."""
    fam = entry["family_id"]
    level = entry.get("level", 1)
    base_name = entry.get("name", fam)

    # Buscar en catálogo por family_id
    cat_ench = None
    for ench in catalog.values():
        if ench.family_id == fam:
            cat_ench = ench
            break

    if cat_ench and level >= cat_ench.MaxLevel and cat_ench.max_level_name:
        return cat_ench.max_level_name

    if cat_ench and cat_ench.MaxLevel > 1:
        return f"{base_name} {to_roman(level)}"
    return base_name


def open_enchantment_menu(player, vInventory):
    from rich.console import Console
    from rich.panel import Panel
    from Modules.ModulesUtils.input_utils import interactive_menu_select
    import time
    
    console = Console()
    
    while True:
        console.clear()
        console.print(Panel("[magenta]✦ Mesa de Encantamientos ✦[/]", style="bold blue", subtitle=f"Oro Disponible: {int(player.Gold)}g"))
        
        # Recolectar objetos encantables: slots equipados + inventario
        from Modules.ModulesUtils.setup import cWeapon, cEquippableItems
        try:
            from Modules.ModulesFunctions.GatheringMasterySystem import cTool
            has_tool_class = True
        except Exception:
            has_tool_class = False

        enchantable_items = []
        seen_ids = set()

        def _collect(item):
            if item is None:
                return
            obj_id = id(item)
            if obj_id in seen_ids:
                return
            if isinstance(item, (cWeapon, cEquippableItems)):
                enchantable_items.append(item)
                seen_ids.add(obj_id)
            elif has_tool_class and isinstance(item, cTool):
                enchantable_items.append(item)
                seen_ids.add(obj_id)

        # Slots equipados del player
        for slot in [player.weapon, player.helmet, player.armor,
                     player.boots, player.ring, player.ring2, player.ring3,
                     getattr(player, "SecHand", None), getattr(player, "tool", None)]:
            _collect(slot)

        # También buscar en inventario (items no equipados)
        for item in vInventory.Objects:
            _collect(item)


        if not enchantable_items:
            console.print("\n[dim]No posees ningún objeto de Equipamiento o Herramienta válida para encantar.[/]")
            time.sleep(get_menu_refresh_rate())
            break

        options = [(0, "Volver al Menú Principal")]
        for idx, item in enumerate(enchantable_items, 1):
            name = getattr(item, "Name", getattr(item, "name", "Objeto Desconocido"))
            n_families = count_unique_families(item)
            enchant_strs = []
            for entry in get_item_enchants(item):
                enchant_strs.append(format_enchant_display(entry, ENCHANTMENTS_CATALOG))
            enchant_preview = ", ".join(enchant_strs) if enchant_strs else "Sin encantamientos"
            options.append((idx, f"Seleccionar {name} [dim]({n_families}/{MAX_ENCHANT_SLOTS} slots)[/]\n      └ [magenta]{enchant_preview}[/]"))

        choice = interactive_menu_select(
            title="Selección de Equipo",
            subtitle="¿Qué objeto quieres mejorar?",
            options=options,
            prompt="Selección: ",
            default_value=0,
            border_style="magenta"
        )

        if choice == 0:
            break

        target_item = enchantable_items[choice-1]

        # Submenú de encantamientos compatibles
        while True:
            console.clear()
            item_name = getattr(target_item, "Name", getattr(target_item, "name", "Objeto"))
            n_families = count_unique_families(target_item)

            # Mostrar encantamientos actuales
            current_enchants_display = []
            for entry in get_item_enchants(target_item):
                display = format_enchant_display(entry, ENCHANTMENTS_CATALOG)
                current_enchants_display.append(f"[bright_magenta]✨ {display}[/]")
            enchant_block = "\n".join(current_enchants_display) if current_enchants_display else "[dim]Ninguno[/]"

            console.print(Panel(
                f"Objeto: [bold cyan]{item_name}[/]\nSlots: {n_families}/{MAX_ENCHANT_SLOTS}\n\n{enchant_block}",
                subtitle=f"Oro: {int(player.Gold)}g",
                border_style="magenta"
            ))

            compatible_enchants = get_enchantments_for_item(target_item, list(ENCHANTMENTS_CATALOG.values()))

            e_options = [(0, "Atrás")]
            for idx, e in enumerate(compatible_enchants, 1):
                existing = find_existing_family(target_item, e.family_id)
                if existing:
                    cur_lv = existing["level"]
                    if cur_lv >= e.MaxLevel:
                        label = f"[dim]{e.Name} [Máx Nv.{cur_lv}] — Ya al máximo[/]"
                    else:
                        next_lv = cur_lv + 1
                        cost = e.GoldCost * next_lv
                        label = f"{e.Name} {to_roman(cur_lv)} → {to_roman(next_lv)} [yellow]({cost}g)[/]\n      └ {e.Description}"
                else:
                    if n_families >= MAX_ENCHANT_SLOTS:
                        label = f"[dim]{e.Name} — Sin slots libres[/]"
                    else:
                        label = f"{e.Name} I [yellow]({e.GoldCost}g)[/]\n      └ {e.Description}"
                e_options.append((idx, label))

            if len(e_options) == 1:
                console.print("[dim]No hay encantamientos conocidos compatibles con este objeto.[/]")
                time.sleep(get_menu_refresh_rate())
                break

            e_choice = interactive_menu_select(
                title="Catálogo Místico",
                subtitle="Elige el encantamiento a infundir",
                options=e_options,
                prompt="Selección: ",
                default_value=0,
                border_style="magenta"
            )

            if e_choice == 0:
                break

            selected_enchant = compatible_enchants[e_choice-1]
            existing = find_existing_family(target_item, selected_enchant.family_id)

            if existing:
                cur_lv = existing["level"]
                if cur_lv >= selected_enchant.MaxLevel:
                    console.print(f"\n[bold red]{selected_enchant.Name} ya está al nivel máximo.[/]")
                    time.sleep(get_menu_refresh_rate())
                    continue
                # Upgrade: costo escala con el nivel
                upgrade_cost = selected_enchant.GoldCost * (cur_lv + 1)
                if player.Gold < upgrade_cost:
                    console.print(f"\n[bold red]Necesitas {upgrade_cost}g para la mejora.[/]")
                    time.sleep(get_menu_refresh_rate())
                    continue
                player.Gold -= upgrade_cost
                existing["level"] = cur_lv + 1
                new_display = format_enchant_display(existing, ENCHANTMENTS_CATALOG)
                console.print(f"\n[green]¡Éxito! {selected_enchant.Name} ha subido a [bold]{new_display}[/]![/]")
                time.sleep(get_menu_refresh_rate())
            else:
                # Nuevo encantamiento
                if n_families >= MAX_ENCHANT_SLOTS:
                    console.print(f"\n[bold red]El item ya tiene {MAX_ENCHANT_SLOTS} encantamientos. ¡No caben más![/]")
                    time.sleep(get_menu_refresh_rate())
                    continue
                if player.Gold < selected_enchant.GoldCost:
                    console.print(f"\n[bold red]Estás pobre. {selected_enchant.Name} I cuesta {selected_enchant.GoldCost}g.[/]")
                    time.sleep(get_menu_refresh_rate())
                    continue
                player.Gold -= selected_enchant.GoldCost
                if not hasattr(target_item, "Enchantments") or target_item.Enchantments is None:
                    target_item.Enchantments = []
                target_item.Enchantments.append({
                    "family_id": selected_enchant.family_id,
                    "name": selected_enchant.Name,
                    "level": 1
                })
                console.print(f"\n[green]¡Éxito! Infundiste [bold]{selected_enchant.Name} I[/] en tu {item_name}.[/]")
                time.sleep(get_menu_refresh_rate())

# ── Auto-carga de encantamientos base al importar ──
if not _BASE_LOADED:
    load_base_enchantments()
    _BASE_LOADED = True
