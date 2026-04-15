import os
import random
from typing import Optional, List, Dict


_DEFAULT_JSON_PATH: str = os.path.join("Data", "DataCompanions.json")

# ── Constantes ────────────────────────────────────────────────────────────────
COMPANION_REVIVAL_GOLD_COST: int = 100
"""Oro necesario para revivir un compañero."""


# ── Helpers de normalización (mismo estilo que setup.py) ─────────────────────

def _norm5(values) -> List[float]:
    src = list(values)
    if len(src) >= 5:
        return [float(v) for v in src[:5]]
    return [float(v) for v in src] + [0.0] * (5 - len(src))


def _norm4(values) -> List[float]:
    src = list(values)
    if len(src) >= 4:
        return [float(v) for v in src[:4]]
    return [float(v) for v in src] + [0.0] * (4 - len(src))


# ── Clases internas de equipamiento por defecto ───────────────────────────────

class _DefaultWeapon:
    """Arma generada desde los datos JSON de un compañero."""

    def __init__(self, data: dict):
        self.name: str = data.get("name", "Arma básica")
        self.DMG: List[float] = _norm5(data.get("DMG", [5, 0, 0, 0, 0]))
        self.DMG_min: List[float] = _norm4(data.get("DMG_min", [2, 0, 0, 0]))
        self.StatsBoosts: dict = data.get("StatsBoosts", {})

    def __repr__(self):
        return f"<DefaultWeapon '{self.name}' DMG={self.DMG}>"


class _DefaultArmor:
    """Armadura generada desde los datos JSON de un compañero."""

    def __init__(self, data: dict):
        self.name: str = data.get("name", "Armadura básica")
        self.Defense: List[float] = _norm5(data.get("Defense", [0, 0, 0, 0, 0]))
        self.HealthBoost: int = int(data.get("HealthBoost", 0))
        self.DmgBoost: int = int(data.get("DmgBoost", 0))
        self.objectcheck: str = data.get("objectcheck", "Armor")

    def __repr__(self):
        return f"<DefaultArmor '{self.name}' DEF={self.Defense}>"


# ── Clase principal ────────────────────────────────────────────────────────────

class cCompanion:
    """
    Compañero del jugador, construido a partir de datos de DataCompanions.json.

    Equipamiento simplificado respecto a cPlayer:
        weapon  → cWeapon o _DefaultWeapon  (arma)
        armor   → cEquippableItems o _DefaultArmor  (solo pechera)

    Estados:
        is_alive = True 
        is_alive = False  
    """

    def __init__(
        self,
        companion_id: str,
        name: str,
        description: str = "",
        icon: str = "👤",
        rarity: str = "Common",
        health_max: float = 80,
        mana_max: float = 60,
        def_array: Optional[List[float]] = None,
        agi: float = 10,
        mana_regen: float = 2.0,
        c_class: str = "Daño",
        gold_cost: int = 0,
        default_weapon_data: Optional[dict] = None,
        default_armor_data: Optional[dict] = None,
    ):
        self.companion_id: str = companion_id
        self.name: str = name
        self.description: str = description
        self.icon: str = icon
        self.rarity: str = rarity
        self.c_class: str = c_class
        self.gold_cost: int = gold_cost
        self.Health_max: float = float(health_max)
        self.Health: float = self.Health_max
        self.Mana_max: float = float(mana_max)
        self.Mana: float = self.Mana_max
        self.Level: int = 1
        self.DEF: List[float] = _norm5(def_array or [0, 0, 0, 0, 0])
        self.AGI: float = float(agi)
        self.DefensePercentage: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.ManaRegen: float = float(mana_regen)
        self.Barrier: float = 0
        self._default_weapon = _DefaultWeapon(default_weapon_data) if default_weapon_data else None
        self._default_armor  = _DefaultArmor(default_armor_data)   if default_armor_data  else None
        self.weapon = self._default_weapon
        self.armor: Optional[object] = None
        if self.weapon and hasattr(self.weapon, "StatsBoosts"):
            self._apply_weapon_stats(self.weapon)
        if self._default_armor is not None:
            self._apply_armor_stats(self._default_armor)
            self.armor = self._default_armor
        self.is_alive: bool = True
        self.active_buffs: list = []
        self.applieddebuffs: list = []

    def equip_weapon(self, weapon) -> None:
        if self.weapon and hasattr(self.weapon, "StatsBoosts"):
            self._remove_weapon_stats(self.weapon)
        self.weapon = weapon
        if weapon and hasattr(weapon, "StatsBoosts"):
            self._apply_weapon_stats(weapon)

    def _apply_weapon_stats(self, weapon) -> None:
        boosts = getattr(weapon, "StatsBoosts", {})
        if not boosts: return
        self.Health_max += boosts.get("Health_max", 0)
        self.Health = min(self.Health, self.Health_max)
        self.Mana_max += boosts.get("Mana_max", 0)
        self.Mana = min(self.Mana, self.Mana_max)
        self.ManaRegen += boosts.get("ManaRegen", 0)
        self.AGI += boosts.get("AGI", 0)

    def _remove_weapon_stats(self, weapon) -> None:
        boosts = getattr(weapon, "StatsBoosts", {})
        if not boosts: return
        self.Health_max = max(1.0, self.Health_max - boosts.get("Health_max", 0))
        self.Health = min(self.Health, self.Health_max)
        self.Mana_max = max(0.0, self.Mana_max - boosts.get("Mana_max", 0))
        self.Mana = min(self.Mana, self.Mana_max)
        self.ManaRegen -= boosts.get("ManaRegen", 0)
        self.AGI -= boosts.get("AGI", 0)

    def equip_armor(self, armor) -> None:
        if self.armor is not None:
            self._remove_armor_stats(self.armor)
        self.armor = armor
        if armor is not None:
            self._apply_armor_stats(armor)

    def _apply_armor_stats(self, armor) -> None:
        for i in range(min(5, len(armor.Defense))):
            self.DEF[i] += armor.Defense[i]
        self.Health_max += armor.HealthBoost
        self.Health = min(self.Health, self.Health_max)

    def _remove_armor_stats(self, armor) -> None:
        for i in range(min(5, len(armor.Defense))):
            self.DEF[i] = max(0.0, self.DEF[i] - armor.Defense[i])
        self.Health_max = max(1.0, self.Health_max - armor.HealthBoost)
        self.Health = min(self.Health, self.Health_max)

    # ── Combate ───────────────────────────────────────────────────────────────

    def attack(self, enemy) -> float:
        """
        Ataque automático contra un enemigo.
        Returns:
            Daño total infligido (0.0 si KO).
        """
        if not self.is_alive:
            return 0.0

        DMGTYPE = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]

        if self.weapon is None:
            dmg = float(random.randint(1, 4))
            enemy.TakeDamage([dmg, 0, 0, 0, 0])
            print(f"  {self.name} golpea a {enemy.NAME} con sus puños → {dmg:.0f} daño físico.")
            return dmg

        raw = [0.0] * 5
        for i in range(5):
            if self.weapon.DMG[i] > 0:
                if i == 4:
                    raw[i] = float(self.weapon.DMG[4])
                else:
                    lo = int(self.weapon.DMG_min[i]) if i < len(self.weapon.DMG_min) else 0
                    hi = int(self.weapon.DMG[i])
                    raw[i] = float(random.randint(max(0, lo), max(lo, hi)))

        if self.armor and hasattr(self.armor, "DmgBoost") and self.armor.DmgBoost:
            raw[0] += self.armor.DmgBoost

        final = [max(0.0, raw[i] - enemy.DEF[i] / 2) for i in range(5)]
        total = sum(final)
        if total < 1:
            total = 1.0
            final[0] = 1.0

        enemy.TakeDamage(final)

        breakdown = ", ".join(
            f"{DMGTYPE[i]}: {final[i]:.1f}" for i in range(5) if final[i] > 0
        )
        print(f"  {self.icon} {self.name} ataca a {enemy.NAME} con {self.weapon.name} → {total:.1f} daño ({breakdown}).")
        return total

    def TakeDamage(self, damage) -> None:
        if not self.is_alive:
            return
        if not isinstance(damage, (list, tuple)):
            damage = [float(damage), 0, 0, 0, 0]

        raw_total = sum(damage)

        # ── Barrera absorbe daño bruto (sin resistencias) ──
        if self.Barrier > 0:
            if raw_total <= self.Barrier:
                self.Barrier -= raw_total
                return  # Barrera absorbió todo
            else:
                absorbed = self.Barrier
                self.Barrier = 0
                if raw_total > 0:
                    ratio = (raw_total - absorbed) / raw_total
                    damage = [d * ratio for d in damage]

        # ── Aplicar defensas al daño restante ──
        final_damage = 0.0
        for i in range(min(len(damage), 5)):
            if damage[i] > 0:
                comp_def = self.DEF[i] if i < len(self.DEF) else 0
                remaining = max(0, damage[i] - (comp_def / 2))
                block_ratio = 0.0
                if i < len(self.DefensePercentage):
                    block_ratio = min(1.0, self.DefensePercentage[i] / 100.0)
                final_damage += remaining * (1.0 - block_ratio)

        self.Health = max(0.0, self.Health - final_damage)
        if self.Health <= 0:
            self.is_alive = False

    # ── Resurrección ──────────────────────────────────────────────────────────

    def revive(self, heal_fraction: float = 0.5) -> None:
        self.is_alive = True
        self.Health = max(1.0, self.Health_max * heal_fraction)
        self.Mana   = max(0.0, self.Mana_max * 0.25)

    # ── Utilidades ────────────────────────────────────────────────────────────

    def tick_regen(self) -> None:
        if self.is_alive:
            self.Mana = min(self.Mana + self.ManaRegen, self.Mana_max)

    def __repr__(self) -> str:
        status = "VIVO" if self.is_alive else "KO"
        return (
            f"<cCompanion '{self.icon}{self.name}' [{self.rarity}] "
            f"HP:{self.Health:.0f}/{self.Health_max:.0f} [{status}]>"
        )


# ── Carga desde JSON vía Loader ───────────────────────────────────────────────

def load_companion_from_data(data: dict) -> cCompanion:
    """
    Construye un cCompanion desde un dict leído de DataCompanions.json.
    """
    return cCompanion(
        companion_id        = data["COMPANION_ID"],
        name                = data["Name"],
        description         = data.get("Description", ""),
        icon                = data.get("Icon", "👤"),
        rarity              = data.get("Rarity", "Common"),
        health_max          = data.get("Health_max", 80),
        mana_max            = data.get("Mana_max", 60),
        def_array           = data.get("DEF", [0, 0, 0, 0, 0]),
        agi                 = data.get("AGI", 10),
        mana_regen          = data.get("ManaRegen", 2.0),
        c_class             = data.get("Class", "Daño"),
        default_weapon_data = data.get("DefaultWeapon"),
        default_armor_data  = data.get("DefaultArmor"),
    )


def load_all_companions(json_path: str = _DEFAULT_JSON_PATH) -> Dict[str, cCompanion]:
    """
    Carga todos los compañeros de DataCompanions.json usando Loader.Read.
        Read(json_path, "COMPANIONS", None)

    Returns:
        Dict { companion_id: cCompanion }
    """
    try:
        from Modules.Loader import Read
    except ImportError:
        from Loader import Read  # type: ignore

    raw_dict = Read(json_path, "COMPANIONS", None)

    if not raw_dict or not isinstance(raw_dict, dict):
        print(f"[WARNING] No se pudieron cargar compañeros desde {json_path}")
        return {}

    companions: Dict[str, cCompanion] = {}
    for cid, cdata in raw_dict.items():
        try:
            companions[cid] = load_companion_from_data(cdata)
        except Exception as e:
            print(f"[WARNING] Error al cargar compañero '{cid}': {e}")

    print(f"[SUCCESS] {len(companions)} compañeros cargados desde {json_path}")
    return companions


def load_companion_by_id(
    companion_id: str,
    json_path: str = _DEFAULT_JSON_PATH,
) -> Optional[cCompanion]:
    """
    Carga un compañero por su COMPANION_ID usando Loader.Read.
        Read(json_path, "COMPANIONS", companion_id)
    """
    try:
        from Modules.Loader import Read
    except ImportError:
        from Loader import Read  # type: ignore

    data = Read(json_path, "COMPANIONS", companion_id)

    if not data or not isinstance(data, dict):
        print(f"[WARNING] Compañero '{companion_id}' no encontrado en {json_path}")
        return None

    try:
        return load_companion_from_data(data)
    except Exception as e:
        print(f"[ERROR] No se pudo construir el compañero '{companion_id}': {e}")
        return None


# ── Caché global del catálogo ─────────────────────────────────────────────────

_companions_catalog: Optional[Dict[str, cCompanion]] = None


def get_companions_catalog(json_path: str = _DEFAULT_JSON_PATH) -> Dict[str, cCompanion]:
    """Devuelve (y cachea en memoria) el catálogo completo de compañeros."""
    global _companions_catalog
    if _companions_catalog is None:
        _companions_catalog = load_all_companions(json_path)
    return _companions_catalog


def create_companion_instance(
    companion_id: str,
    json_path: str = _DEFAULT_JSON_PATH,
) -> Optional[cCompanion]:
    """
    Devuelve una NUEVA instancia del compañero indicado.
    Útil para añadir al equipo sin compartir estado con el catálogo.
    """
    return load_companion_by_id(companion_id, json_path)


# ── Funciones de resurrección ─────────────────────────────────────────────────

def try_revive_with_gold(companion: cCompanion, player) -> bool:
    if companion.is_alive:
        return False
    if player.Gold < COMPANION_REVIVAL_GOLD_COST:
        return False
    player.Gold -= COMPANION_REVIVAL_GOLD_COST
    companion.revive(heal_fraction=0.5)
    return True


def try_revive_with_item(companion: cCompanion, inventory) -> bool:
    if companion.is_alive:
        return False
    for slot in list(inventory.slots):
        item = slot.item
        if getattr(item, "is_revival_item", False):
            inventory.remove_item(item, 1)
            companion.revive(heal_fraction=1.0)
            return True
    return False


# ── Menú de gestión ───────────────────────────────────────────────────────────

def companion_management_menu(
    player,
    inventory,
    console,
    interactive_menu_select_fn,
    wait_for_enter_fn,
) -> None:
    """
    Menú interactivo principal de compañeros:
        - Ver / gestionar compañeros actuales
        - Reclutar nuevos desde el catálogo JSON
    """
    from rich.panel import Panel

    try:
        from Modules.setup import cWeapon, cEquippableItems
    except ImportError:
        from setup import cWeapon, cEquippableItems  # type: ignore

    while True:
        options = [(0, "Volver al menú principal")]

        for i, comp in enumerate(player.companion, 1):
            badge  = "✓" if comp.is_alive else "💀 KO"
            hp_str = f"{comp.Health:.0f}/{comp.Health_max:.0f}"
            options.append((
                i,
                f"{comp.icon} {comp.name}  [{badge}]  HP:{hp_str}  ({comp.rarity})",
            ))

        recruit_idx = len(player.companion) + 1
        options.append((recruit_idx, "➕ Reclutar nuevo compañero"))

        choice = interactive_menu_select_fn(
            title="Gestión de Compañeros",
            subtitle=f"Compañeros activos: {len(player.companion)}",
            options=options,
            prompt="Compañero: ",
            default_value=0,
            border_style="cyan",
        )

        if choice == 0:
            break

        if choice == recruit_idx:
            _recruit_companion_menu(player, console, interactive_menu_select_fn, wait_for_enter_fn)
            continue

        comp = player.companion[choice - 1]
        _companion_submenu(
            comp, player, inventory, console,
            interactive_menu_select_fn, wait_for_enter_fn,
            cWeapon, cEquippableItems,
        )


def _recruit_companion_menu(player, console, menu_fn, pause_fn) -> None:
    catalog = get_companions_catalog()
    if not catalog:
        console.print("[warning]No hay compañeros disponibles en el catálogo.[/warning]")
        pause_fn()
        return

    current_ids = {c.companion_id for c in player.companion}

    opts = [(0, "Cancelar")]
    available = []
    for cid, tmpl in catalog.items():
        tag = " [dim](ya en equipo)[/dim]" if cid in current_ids else ""
        opts.append((
            len(available) + 1,
            f"{tmpl.icon} {tmpl.name} [{tmpl.rarity}]{tag}  — {tmpl.description[:55]}",
        ))
        available.append(cid)

    chosen = menu_fn(
        title="Catálogo de Compañeros",
        subtitle="Selecciona un compañero para reclutar",
        options=opts,
        prompt="Compañero: ",
        default_value=1 if len(opts) > 1 else 0,
        border_style="cyan",
    )

    if chosen == 0:
        return

    selected_id = available[chosen - 1]
    if selected_id in current_ids:
        console.print("[warning]Este compañero ya está en tu equipo.[/warning]")
        pause_fn()
        return

    new_comp = create_companion_instance(selected_id)
    if new_comp:
        player.companion.append(new_comp)
        console.print(
            f"[success]✨ {new_comp.icon} {new_comp.name} se ha unido a tu equipo![/success]"
        )
    else:
        console.print("[danger]Error al reclutar el compañero.[/danger]")
    pause_fn()


def _companion_submenu(comp, player, inventory, console, menu_fn, pause_fn, cWeapon, cEquippableItems) -> None:
    from rich.panel import Panel

    while True:
        sub = [(0, "Volver")]

        if not comp.is_alive:
            sub.append((1, f"💰 Revivir  ({COMPANION_REVIVAL_GOLD_COST} oro)  [Oro: {player.Gold}]"))
            sub.append((5, "💊 Revivir con ítem de resurrección"))
        else:
            sub.append((2, "🗡  Equipar arma del inventario"))
            sub.append((3, "🛡  Equipar armadura del inventario"))

        sub.append((4, "📊 Ver estadísticas"))
        sub.append((6, "❌ Retirar del equipo"))

        choice = menu_fn(
            title=f"{comp.icon} {comp.name}  [{comp.rarity}]",
            subtitle=comp.description,
            options=sub,
            prompt="Acción: ",
            default_value=0,
            border_style="cyan",
        )

        if choice == 0:
            break

        elif choice == 1:
            if try_revive_with_gold(comp, player):
                console.print(
                    f"[success]✨ {comp.name} revivido con {comp.Health:.0f} HP. "
                    f"Oro restante: {player.Gold}[/success]"
                )
            else:
                console.print(
                    f"[danger]Oro insuficiente. Necesitas {COMPANION_REVIVAL_GOLD_COST} "
                    f"(tienes {player.Gold}).[/danger]"
                )
            pause_fn()

        elif choice == 5:
            if try_revive_with_item(comp, inventory):
                console.print(f"[success]✨ {comp.name} revivido al 100% con un ítem.[/success]")
            else:
                console.print("[warning]No tienes ítems de resurrección.[/warning]")
            pause_fn()

        elif choice == 2:
            _equip_weapon_from_inventory(comp, inventory, console, menu_fn, pause_fn, cWeapon)

        elif choice == 3:
            _equip_armor_from_inventory(comp, inventory, console, menu_fn, pause_fn, cEquippableItems)

        elif choice == 4:
            _show_companion_stats(comp, console, pause_fn)

        elif choice == 6:
            player.companion.remove(comp)
            console.print(f"[info]{comp.name} retirado del equipo.[/info]")
            pause_fn()
            break


def _equip_weapon_from_inventory(comp, inventory, console, menu_fn, pause_fn, cWeapon) -> None:
    weapons = [s for s in inventory.slots if isinstance(s.item, cWeapon)]
    if not weapons:
        console.print("[warning]No tienes armas en el inventario.[/warning]")
        pause_fn()
        return
    opts = [(0, "Cancelar")] + [
        (i + 1, f"{s.item.name}  (Daño fís: {s.item.DMG[0]})")
        for i, s in enumerate(weapons)
    ]
    c = menu_fn(title=f"Equipar arma → {comp.name}", options=opts,
                prompt="Arma: ", default_value=1 if len(opts) > 1 else 0, border_style="cyan")
    if c > 0:
        comp.equip_weapon(weapons[c - 1].item)
        console.print(f"[success]{comp.name} ahora empuña {weapons[c-1].item.name}.[/success]")
    pause_fn()


def _equip_armor_from_inventory(comp, inventory, console, menu_fn, pause_fn, cEquippableItems) -> None:
    armors = [
        s for s in inventory.slots
        if isinstance(s.item, cEquippableItems) and s.item.objectcheck == "Armor"
    ]
    if not armors:
        console.print("[warning]No tienes armaduras en el inventario.[/warning]")
        pause_fn()
        return
    opts = [(0, "Cancelar")] + [
        (i + 1, f"{s.item.name}  (Def fís: {s.item.Defense[0]})")
        for i, s in enumerate(armors)
    ]
    c = menu_fn(title=f"Equipar armadura → {comp.name}", options=opts,
                prompt="Armadura: ", default_value=1 if len(opts) > 1 else 0, border_style="cyan")
    if c > 0:
        comp.equip_armor(armors[c - 1].item)
        console.print(f"[success]{comp.name} ahora viste {armors[c-1].item.name}.[/success]")
    pause_fn()


def _show_companion_stats(comp, console, pause_fn) -> None:
    from rich.panel import Panel

    weapon_str = comp.weapon.name if comp.weapon else "[dim]Sin arma[/dim]"
    armor_str  = comp.armor.name  if comp.armor  else "[dim]Sin armadura[/dim]"
    status_str = "[green]Vivo ✓[/green]" if comp.is_alive else "[red]💀 KO – necesita ser revivido[/red]"

    rarity_colors = {
        "Common": "white", "Uncommon": "green",
        "Rare": "blue", "Epic": "magenta", "Legendary": "yellow",
    }
    rc = rarity_colors.get(comp.rarity, "white")

    lines = [
        f"[bold]Nombre:[/bold]      {comp.icon} {comp.name}",
        f"[bold]Rareza:[/bold]      [{rc}]{comp.rarity}[/{rc}]",
        f"[bold]Descripción:[/bold] {comp.description}",
        f"[bold]Estado:[/bold]      {status_str}",
        "",
        f"[bold red]HP:[/bold red]  {comp.Health:.0f} / {comp.Health_max:.0f}",
        f"[bold blue]MP:[/bold blue]  {comp.Mana:.0f} / {comp.Mana_max:.0f}  "
        f"[dim](Regen: +{comp.ManaRegen}/turno)[/dim]",
        "",
        f"[bold]DEF:[/bold]   "
        f"Fís [red]{comp.DEF[0]:.0f}[/red]  "
        f"Tér [yellow]{comp.DEF[1]:.0f}[/yellow]  "
        f"Tir [green]{comp.DEF[2]:.0f}[/green]  "
        f"Eléc [cyan]{comp.DEF[3]:.0f}[/cyan]  "
        f"Prof [magenta]{comp.DEF[4]:.0f}[/magenta]",
        f"[bold]AGI:[/bold]   {comp.AGI:.0f}",
        "",
        f"[bold]Arma:[/bold]      {weapon_str}",
        f"[bold]Armadura:[/bold]  {armor_str}",
    ]
    console.print(Panel("\n".join(lines), title=f"Stats – {comp.name}", border_style="cyan"))
    pause_fn()
