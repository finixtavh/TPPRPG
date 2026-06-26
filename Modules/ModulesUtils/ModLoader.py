import sys
import re
import operator
import importlib
import importlib.util
import json
import inspect
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import logging

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ModuleNotFoundError:
    Console = None
    Panel = None
    Table = None

logger = logging.getLogger('TPPRPG.ModLoader')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _handler = logging.FileHandler('tpprpg_mods.log', mode='a', encoding='utf-8')
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)
    logger.propagate = False

if Console is not None:
    console = Console()
else:
    class _FallbackConsole:
        def print(self, *args, **kwargs):
            print(*args)
    console = _FallbackConsole()


# Versión del juego que los mods pueden exigir con manifest.game_version
GAME_VERSION = "1.1.0"

# Categorías de contribución que un mod puede aportar (data + código).
_CONTRIB_DICT_KEYS = (
    "items", "zones", "shops", "enchantments", "quests", "gathering",
    "guild_skills", "affinities", "companions", "buffs", "player_skills",
    "localization", "player_attributes", "buildings", "enemies", "commands",
)
_CONTRIB_LIST_KEYS = ("recipes", "guild_events", "weathers")


# ─────────────────────────────────────────────────────────────────────────────
#  Utilidades de versión / dependencias
# ─────────────────────────────────────────────────────────────────────────────

def _ver_tuple(v) -> tuple:
    nums = re.findall(r'\d+', str(v))
    return tuple(int(n) for n in nums) if nums else (0,)


_VER_OPS = {">=": operator.ge, "<=": operator.le, "==": operator.eq,
            ">": operator.gt, "<": operator.lt, "!=": operator.ne}


def version_satisfies(have: str, spec: Optional[str]) -> bool:
    """¿`have` cumple la restricción `spec` (ej. '>=1.0', '==2.1', '1.0')?"""
    if not spec:
        return True
    spec = str(spec).strip()
    m = re.match(r'^(>=|<=|==|!=|>|<)?\s*([\d.]+)$', spec)
    if not m:
        return True
    op = m.group(1) or "=="
    want = _ver_tuple(m.group(2))
    h = _ver_tuple(have)
    n = max(len(want), len(h))
    want = want + (0,) * (n - len(want))
    h = h + (0,) * (n - len(h))
    return _VER_OPS[op](h, want)


def parse_dependency(dep: str):
    """'base_mod>=2.0' -> ('base_mod', '>=2.0'); 'base_mod' -> ('base_mod', None)."""
    m = re.match(r'^\s*([^<>=!]+?)\s*(>=|<=|==|!=|>|<)\s*([\d.]+)\s*$', dep)
    if m:
        return m.group(1).strip(), m.group(2) + m.group(3)
    return dep.strip(), None


class ModAPI:
    """API para que los mods interactúen con el juego."""

    def __init__(self):
        # Agregados (vistas mergeadas de todos los mods habilitados).
        self.registered_items = {}
        self.registered_enemies = {}
        self.registered_zones = {}
        self.event_handlers: Dict[str, list] = {}
        self.custom_commands: Dict[str, dict] = {}
        self.registered_shops = {}
        self.registered_buildings = {}
        self.player_attributes = {}
        self.item_injections = {}
        self.stats_injections = {}
        self.shop_injections = {}
        self.enchantment_injections = {}
        self.quest_injections = {}
        self.recipe_injections: list = []
        self.gathering_injections = {}

        # GUILD / WEATHER
        self.guild_skill_injections: Dict[str, dict] = {}
        self.guild_event_injections: list = []
        self.guild_tick_handlers: List[Callable] = []
        self.weather_injections: List[dict] = []

        # NUEVOS targets de inyección
        self.affinity_injections: Dict[str, dict] = {}      # {profile_name: {type: mult}}
        self.companion_injections: Dict[str, dict] = {}     # {companion_id: data}
        self.buff_injections: Dict[str, dict] = {}          # {buff_id: data}
        self.player_skill_injections: Dict[str, dict] = {}  # {skill_id: data}
        self.localization_injections: Dict[str, str] = {}   # {key: text}

        # Datos crudos de los JSON de mods
        self.mod_data_files = {}

        # ── Tracking por mod (para reload/unload sin duplicar) ──────────────
        # _contrib[mod_name] = {cat: dict|list} con lo que aportó ese mod.
        self._contrib: Dict[str, Dict[str, Any]] = {}
        self._current_mod: Optional[str] = None   # mod cargándose ahora mismo
        self._enabled_order: List[str] = []        # orden de merge (load order)
        self._applied_weather_ids: set = set()

        # Settings y estado persistente de mods
        self.mod_settings: Dict[str, dict] = {}    # {mod: {key: value}}
        self.mod_settings_schema: Dict[str, dict] = {}  # {mod: {key: schema}}
        self.mod_states: Dict[str, dict] = {}      # estado runtime guardable

    # =========================================================================
    # CONTEXTO DE CARGA (atribuir aportes al mod correcto)
    # =========================================================================

    def _begin_mod(self, mod_name: str):
        self._current_mod = mod_name
        self._contrib.setdefault(mod_name, self._empty_contrib())

    def _end_mod(self):
        self._current_mod = None

    @staticmethod
    def _empty_contrib() -> Dict[str, Any]:
        c = {k: {} for k in _CONTRIB_DICT_KEYS}
        for k in _CONTRIB_LIST_KEYS:
            c[k] = []
        c["event_handlers"] = {}   # {event: [fn,...]}
        return c

    def _contrib_for(self, mod_name: Optional[str]) -> Dict[str, Any]:
        mod_name = mod_name or self._current_mod or "_runtime"
        return self._contrib.setdefault(mod_name, self._empty_contrib())

    # =========================================================================
    # CARGA DE DATOS DE MOD
    # =========================================================================

    def load_mod_data(self, mod_name: str, json_path: str) -> Dict:
        """Carga (y mergea) uno o varios JSON de datos de un mod."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.mod_data_files[mod_name] = data
            logger.info(f"Datos del mod '{mod_name}' cargados desde {json_path}")
            return data
        except FileNotFoundError:
            logger.warning(f"Archivo de datos no encontrado para mod '{mod_name}': {json_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON del mod '{mod_name}': {e}")
            return {}
        except Exception as e:
            logger.error(f"Error cargando datos del mod '{mod_name}': {e}")
            return {}

    def get_mod_data(self, mod_name: str) -> Dict:
        return self.mod_data_files.get(mod_name, {})

    # =========================================================================
    # INYECCIÓN AUTOMÁTICA DESDE JSON DEL MOD (-> _contrib, sin duplicar)
    # =========================================================================

    def auto_inject_from_mod_data(self, mod_name: str):
        """Registra en _contrib[mod_name] todo lo que el JSON del mod aporta."""
        mod_data = self.get_mod_data(mod_name)
        if not mod_data:
            logger.warning(f"No hay datos para auto-inyectar del mod '{mod_name}'")
            return

        c = self._contrib_for(mod_name)

        # Settings declarados en el manifest
        manifest = mod_data.get("manifest", mod_data.get("mod_info", {}))
        if isinstance(manifest, dict) and "settings" in manifest:
            self._register_settings(mod_name, manifest["settings"])

        def _ok(entry, *required) -> bool:
            return isinstance(entry, dict) and all(k in entry for k in required)

        # items: {TYPE:x: {key: data}}
        for item_type, items in mod_data.get("items", {}).items():
            dst = c["items"].setdefault(item_type, {})
            for k, v in items.items():
                if _ok(v, "STATIC_ID") or item_type == "TYPE:Materials":
                    dst[k] = v
                else:
                    logger.warning(f"[{mod_name}] item '{k}' inválido (falta STATIC_ID)")

        for cat, jkey in (("zones", "zones"), ("shops", "shops"),
                          ("enchantments", "enchantments"), ("gathering", "gathering"),
                          ("guild_skills", "guild_skills"), ("affinities", "affinities"),
                          ("buffs", "buffs"), ("player_skills", "player_skills"),
                          ("localization", "localization"), ("buildings", "buildings"),
                          ("enemies", "enemies")):
            for k, v in mod_data.get(jkey, {}).items():
                c[cat][k] = v

        # companions pueden venir como {"COMPANIONS": {...}} o plano
        comp_block = mod_data.get("companions", {})
        if "COMPANIONS" in comp_block:
            comp_block = comp_block["COMPANIONS"]
        for k, v in comp_block.items():
            c["companions"][k] = v

        # quests (lista con quest_id)
        for q in mod_data.get("quests", []):
            qid = q.get("quest_id")
            if qid:
                c["quests"][qid] = q

        # listas
        c["recipes"].extend(mod_data.get("recipes", []))
        c["guild_events"].extend(mod_data.get("guild_events", []))
        c["weathers"].extend(mod_data.get("weathers", []))

        logger.info(f"[{mod_name}] datos JSON registrados en contribución.")

    # =========================================================================
    # REBUILD: recomputar agregados desde mods habilitados (anti-duplicación)
    # =========================================================================

    def rebuild(self, enabled_order: Optional[List[str]] = None):
        """Reconstruye todos los agregados desde _contrib de los mods habilitados."""
        if enabled_order is not None:
            self._enabled_order = list(enabled_order)
        order = self._enabled_order or list(self._contrib.keys())

        # Limpiar agregados
        self.item_injections = {}
        self.stats_injections = {}
        self.shop_injections = {}
        self.enchantment_injections = {}
        self.quest_injections = {}
        self.recipe_injections = []
        self.gathering_injections = {}
        self.guild_skill_injections = {}
        self.guild_event_injections = []
        self.weather_injections = []
        self.affinity_injections = {}
        self.companion_injections = {}
        self.buff_injections = {}
        self.player_skill_injections = {}
        self.localization_injections = {}
        self.player_attributes = {}
        self.registered_buildings = {}
        self.registered_enemies = {}
        self.event_handlers = {}
        self.custom_commands = {}

        for mod in order:
            c = self._contrib.get(mod)
            if not c:
                continue
            for item_type, items in c["items"].items():
                self.item_injections.setdefault(item_type, {}).update(items)
            self.stats_injections.update(c["zones"])
            for sname, sdata in c["shops"].items():
                self.shop_injections[sname] = sdata
            self.enchantment_injections.update(c["enchantments"])
            self.quest_injections.update(c["quests"])
            self.gathering_injections.update(c["gathering"])
            self.guild_skill_injections.update(c["guild_skills"])
            self.affinity_injections.update(c["affinities"])
            self.companion_injections.update(c["companions"])
            self.buff_injections.update(c["buffs"])
            self.player_skill_injections.update(c["player_skills"])
            self.localization_injections.update(c["localization"])
            self.player_attributes.update(c["player_attributes"])
            self.registered_buildings.update(c["buildings"])
            self.registered_enemies.update(c["enemies"])
            self.custom_commands.update(c["commands"])
            self.recipe_injections.extend(c["recipes"])
            self.guild_event_injections.extend(c["guild_events"])
            self.weather_injections.extend(c["weathers"])
            for ev, fns in c["event_handlers"].items():
                self.event_handlers.setdefault(ev, []).extend(fns)

        # Re-aplicar a sistemas externos (idempotente)
        self._apply_guild_skills()
        self._apply_guild_events()
        self._apply_weathers()
        self._apply_affinities()
        logger.info(f"Agregados reconstruidos desde {len(order)} mod(s).")

    # =========================================================================
    # SETTINGS DE MOD
    # =========================================================================

    def _register_settings(self, mod_name: str, schema: dict):
        self.mod_settings_schema[mod_name] = schema
        cur = self.mod_settings.setdefault(mod_name, {})
        for key, meta in schema.items():
            if key not in cur:
                cur[key] = meta.get("default")

    def get_setting(self, mod_name: str, key: str, fallback=None):
        return self.mod_settings.get(mod_name, {}).get(key, fallback)

    def set_setting(self, mod_name: str, key: str, value) -> None:
        self.mod_settings.setdefault(mod_name, {})[key] = value

    # =========================================================================
    # ESTADO PERSISTENTE DE MODS (para SaveSystem)
    # =========================================================================

    def save_mod_state(self, mod_name: str, state: dict) -> None:
        self.mod_states[mod_name] = state

    def get_mod_state(self, mod_name: str) -> dict:
        return self.mod_states.get(mod_name, {})

    def serialize_states(self) -> dict:
        """Para SaveSystem: settings + estados runtime de mods."""
        return {"settings": self.mod_settings, "states": self.mod_states}

    def restore_states(self, blob: dict) -> None:
        if not blob:
            return
        self.mod_settings.update(blob.get("settings", {}) or {})
        self.mod_states.update(blob.get("states", {}) or {})

    # =========================================================================
    # REGISTRO MANUAL (mantiene compat; ahora atribuido al mod actual)
    # =========================================================================

    def register_item(self, item_or_class, item_data: Dict):
        item_id = item_data.get('id', f'mod_item_{len(self.registered_items)}')
        item_class = item_or_class if inspect.isclass(item_or_class) else item_or_class.__class__
        self.registered_items[item_id] = {
            'class': item_class,
            'instance': None if inspect.isclass(item_or_class) else item_or_class,
            'data': item_data
        }
        logger.info(f"Item registrado: {item_id}")

    def inject_item_to_json(self, item_type: str, item_key: str, item_data: Dict):
        self._contrib_for(None)["items"].setdefault(item_type, {})[item_key] = item_data
        self.item_injections.setdefault(item_type, {})[item_key] = item_data
        logger.info(f"Item inyectado a {item_type}: {item_key}")

    def register_enemy(self, enemy_or_class, enemy_data: Dict):
        enemy_id = enemy_data.get('id', f'mod_enemy_{len(self.registered_enemies)}')
        enemy_class = enemy_or_class if inspect.isclass(enemy_or_class) else enemy_or_class.__class__
        entry = {
            'class': enemy_class,
            'instance': None if inspect.isclass(enemy_or_class) else enemy_or_class,
            'data': enemy_data
        }
        self.registered_enemies[enemy_id] = entry
        self._contrib_for(None)["enemies"][enemy_id] = entry
        logger.info(f"Enemigo registrado: {enemy_id}")

    def register_zone(self, zone_name: str, zone_data: Dict):
        self.registered_zones[zone_name] = zone_data
        logger.info(f"Zona registrada: {zone_name}")

    def inject_zone_to_json(self, zone_name: str, zone_data: List[Dict]):
        self._contrib_for(None)["zones"][zone_name] = zone_data
        self.stats_injections[zone_name] = zone_data
        logger.info(f"Zona inyectada a DataStats: {zone_name}")

    def register_shop(self, shop_name: str, shop_data: Dict):
        self.registered_shops[shop_name] = shop_data
        logger.info(f"Tienda registrada: {shop_name}")

    def inject_shop_to_json(self, shop_name: str, item_ids: List[int]):
        data = [{"IDs": item_ids}]
        self._contrib_for(None)["shops"][shop_name] = data
        self.shop_injections[shop_name] = data
        logger.info(f"Tienda inyectada: {shop_name}")

    # ── NUEVOS registros ────────────────────────────────────────────────────

    def register_affinity_profile(self, profile_name: str, mults: Dict[str, float]):
        """Registra un perfil de afinidad elemental usable por enemigos (affinity_profile)."""
        self._contrib_for(None)["affinities"][profile_name] = mults
        self.affinity_injections[profile_name] = mults
        self._apply_affinities()
        logger.info(f"Perfil de afinidad registrado: {profile_name}")

    def register_companion(self, companion_id: str, data: Dict):
        self._contrib_for(None)["companions"][companion_id] = data
        self.companion_injections[companion_id] = data
        logger.info(f"Compañero registrado: {companion_id}")

    def register_buff(self, buff_id: str, data: Dict):
        self._contrib_for(None)["buffs"][buff_id] = data
        self.buff_injections[buff_id] = data
        logger.info(f"Buff registrado: {buff_id}")

    def register_player_skill(self, skill_id: str, data: Dict):
        self._contrib_for(None)["player_skills"][skill_id] = data
        self.player_skill_injections[skill_id] = data
        logger.info(f"Skill de jugador registrada: {skill_id}")

    def register_localization(self, key: str, text: str):
        self._contrib_for(None)["localization"][key] = text
        self.localization_injections[key] = text

    def localize(self, key: str, fallback: str = "") -> str:
        return self.localization_injections.get(key, fallback or key)

    # =========================================================================
    # ATRIBUTOS PERSONALIZADOS DEL JUGADOR
    # =========================================================================

    def register_player_attribute(self, attr_name: str, default_value: Any, description: str = ""):
        meta = {'default': default_value, 'description': description}
        self.player_attributes[attr_name] = meta
        self._contrib_for(None)["player_attributes"][attr_name] = meta
        logger.info(f"Atributo de jugador registrado: {attr_name}")

    def apply_player_attributes(self, player):
        for attr_name, attr_data in self.player_attributes.items():
            if not hasattr(player, attr_name):
                setattr(player, attr_name, attr_data['default'])
                logger.info(f"Atributo '{attr_name}' agregado al jugador: {attr_data['default']}")

    def serialize_player_attributes(self, player) -> dict:
        """Valores actuales de los atributos de mod en el jugador (para guardar)."""
        return {name: getattr(player, name) for name in self.player_attributes if hasattr(player, name)}

    def restore_player_attributes(self, player, data: dict) -> None:
        self.apply_player_attributes(player)
        for name, val in (data or {}).items():
            setattr(player, name, val)

    # =========================================================================
    # EVENTOS
    # =========================================================================

    def register_event_handler(self, event_name: str, handler_func: Callable):
        self.event_handlers.setdefault(event_name, []).append(handler_func)
        self._contrib_for(None)["event_handlers"].setdefault(event_name, []).append(handler_func)
        logger.info(f"Event handler registrado para: {event_name}")

    def fire_event(self, event_name: str, *args, **kwargs):
        for handler in self.event_handlers.get(event_name, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en event handler {getattr(handler, '__name__', '?')} ({event_name}): {e}")

    # =========================================================================
    # COMANDOS PERSONALIZADOS
    # =========================================================================

    def register_command(self, command_name: str, handler_func: Callable, description: str = ""):
        entry = {'handler': handler_func, 'description': description}
        self.custom_commands[command_name] = entry
        self._contrib_for(None)["commands"][command_name] = entry
        logger.info(f"Comando registrado: {command_name}")

    def run_command(self, command_name: str, *args, **kwargs):
        """Ejecuta un comando personalizado registrado por un mod."""
        cmd = self.custom_commands.get(command_name)
        if not cmd:
            logger.warning(f"Comando desconocido: {command_name}")
            return None
        try:
            return cmd['handler'](*args, **kwargs)
        except Exception as e:
            logger.error(f"Error ejecutando comando '{command_name}': {e}")
            return None

    # =========================================================================
    # GUILD MODDING API
    # =========================================================================

    def register_guild_skill(self, skill_id: str, skill_def: dict):
        self._contrib_for(None)["guild_skills"][skill_id] = skill_def
        self.guild_skill_injections[skill_id] = skill_def
        self._apply_guild_skills()
        logger.info(f"Guild skill registrada: {skill_id}")

    def register_guild_event(self, event_def: dict):
        self._contrib_for(None)["guild_events"].append(event_def)
        self.guild_event_injections.append(event_def)
        self._apply_guild_events()
        logger.info(f"Guild event registrado: {event_def.get('event_id', '?')}")

    def register_guild_tick_handler(self, handler_func: Callable):
        self.guild_tick_handlers.append(handler_func)
        logger.info(f"Guild tick handler registrado: {handler_func.__name__}")

    def _apply_guild_skills(self):
        try:
            from Modules.ModulesFunctions.GuildSkillTree import GUILD_SKILL_TREE, BRANCH_ORDER
            for skill_id, skill_def in self.guild_skill_injections.items():
                GUILD_SKILL_TREE[skill_id] = skill_def
                branch = skill_def.get("branch", "Militar")
                if branch in BRANCH_ORDER and skill_id not in BRANCH_ORDER[branch]:
                    BRANCH_ORDER[branch].append(skill_id)
        except Exception as e:
            logger.warning(f"No se pudo inyectar guild skills: {e}")

    def _apply_guild_events(self):
        try:
            import Modules.ModulesFunctions.GuildSystem as gs
            for ev in self.guild_event_injections:
                if not any(e.get("event_id") == ev.get("event_id") for e in gs.GUILD_EVENTS_POOL):
                    gs.GUILD_EVENTS_POOL.append(ev)
        except Exception as e:
            logger.warning(f"No se pudo inyectar guild events: {e}")

    def fire_guild_tick_handlers(self, guild_manager):
        for handler in self.guild_tick_handlers:
            try:
                handler(guild_manager)
            except Exception as e:
                logger.error(f"Error en guild tick handler {handler.__name__}: {e}")

    # =========================================================================
    # WEATHER / AFFINITY MODDING
    # =========================================================================

    def register_weather(self, weather_data: dict):
        self._contrib_for(None)["weathers"].append(weather_data)
        self.weather_injections.append(weather_data)
        self._apply_weathers()
        logger.info(f"Clima registrado: {weather_data.get('id', '?')}")

    def _apply_weathers(self):
        try:
            from Modules.ModulesFunctions.WeatherSystem import get_weather_manager
            wm = get_weather_manager()
            for w in self.weather_injections:
                wid = w.get("id", w.get("name"))
                if wid in self._applied_weather_ids:
                    continue
                wm.register_weather(w)
                self._applied_weather_ids.add(wid)
        except Exception as e:
            logger.warning(f"No se pudo inyectar climas: {e}")

    def _apply_affinities(self):
        """Inyecta perfiles de afinidad en Data/Affinities.json virtual (cache de setup)."""
        if not self.affinity_injections:
            return
        try:
            from Modules.ModulesUtils import setup
            # setup.resolve_enemy_affinities lee perfiles vía Loader.Read (cacheado).
            # Exponemos los perfiles de mod a través de un override en memoria.
            if not hasattr(setup, "_MOD_AFFINITY_PROFILES"):
                setup._MOD_AFFINITY_PROFILES = {}
            setup._MOD_AFFINITY_PROFILES.update(self.affinity_injections)
        except Exception as e:
            logger.warning(f"No se pudo inyectar afinidades: {e}")

    def register_building(self, building_id: str, building_data: Dict):
        self._contrib_for(None)["buildings"][building_id] = building_data
        self.registered_buildings[building_id] = building_data
        logger.info(f"Edificio de mod registrado: {building_id}")

    # =========================================================================
    # INTEGRACIÓN CON MANAGERS
    # =========================================================================

    def integrate_with_item_manager(self, item_manager):
        for item_type, items in self.item_injections.items():
            item_manager.items_data.setdefault(item_type, {})
            for item_key, item_data in items.items():
                item_manager.items_data[item_type][item_key] = item_data
        # Reindexar para que get_item_by_id encuentre los items del mod
        if hasattr(item_manager, "_build_indexes"):
            item_manager._build_indexes()
        if self.item_injections:
            console.print(f"[green]✓ {len(self.item_injections)} tipos de items integrados[/green]")

    def integrate_with_shop_manager(self, shop_manager):
        for shop_name, shop_data in self.shop_injections.items():
            shop_manager.shops_data[shop_name] = shop_data
        if self.shop_injections:
            console.print(f"[green]✓ {len(self.shop_injections)} tiendas integradas[/green]")

    def integrate_with_enchantment_system(self):
        try:
            from Modules.ModulesFunctions.EnchantmentSystem import register_enchantment, load_enchantment_from_json
            count = 0
            for ench_key, ench_data in self.enchantment_injections.items():
                register_enchantment(load_enchantment_from_json(ench_data))
                count += 1
            if count:
                logger.info(f"{count} encantamientos integrados.")
        except ImportError:
            logger.warning("No se pudo cargar EnchantmentSystem para la integración")

    def integrate_with_quest_manager(self, quest_manager):
        from Modules.ModulesFunctions.QuestSystem import cQuest
        count = 0
        for quest_id, quest_data in self.quest_injections.items():
            if quest_id not in quest_manager.quests:
                quest_manager.quests[quest_id] = cQuest(quest_data)
                count += 1
        if count:
            console.print(f"[green]✓ {count} quests integradas[/green]")

    def integrate_with_crafting_system(self, crafting_system):
        from Modules.ModulesFunctions.CraftingSystem import cRecipe
        existing = {getattr(r, "name", id(r)) for r in crafting_system.recipes}
        count = 0
        for r_data in self.recipe_injections:
            if r_data.get("name") in existing:
                continue
            crafting_system.recipes.append(cRecipe(r_data))
            count += 1
        if count:
            logger.info(f"{count} recetas integradas.")

    def integrate_with_gathering_system(self, farm):
        for skill_key, params in self.gathering_injections.items():
            if skill_key in farm.gathering:
                skill_obj = farm.gathering[skill_key]
                for p_key, p_val in params.items():
                    if hasattr(skill_obj, p_key):
                        setattr(skill_obj, p_key, p_val)
        if self.gathering_injections:
            logger.info(f"{len(self.gathering_injections)} configs de gathering integradas.")

    def integrate_with_buff_manager(self, buff_manager=None):
        """Inyecta buffs/debuffs de mods en BuffManager (DataBuffs virtual)."""
        if not self.buff_injections:
            return
        try:
            if buff_manager is None:
                from Modules.ModulesManager.BuffManager import get_buff_manager
                buff_manager = get_buff_manager()
            buffs = getattr(buff_manager, "buffs_data", None)
            debuffs = getattr(buff_manager, "debuffs_data", None)
            if isinstance(buffs, dict) and isinstance(debuffs, dict):
                for bid, bdata in self.buff_injections.items():
                    (debuffs if "_debuff" in bid else buffs)[bid] = bdata
                logger.info(f"{len(self.buff_injections)} buffs integrados.")
        except Exception as e:
            logger.warning(f"No se pudieron integrar buffs: {e}")

    def integrate_all(self):
        """Ejecuta todas las integraciones cuyos managers son singletons accesibles."""
        try:
            from Modules.ModulesManager.ItemManager import get_item_manager
            self.integrate_with_item_manager(get_item_manager())
        except Exception as e:
            logger.warning(f"integrate item_manager: {e}")
        try:
            from Modules.ModulesManager.ShopManager import get_shop_manager
            self.integrate_with_shop_manager(get_shop_manager())
        except Exception as e:
            logger.warning(f"integrate shop_manager: {e}")
        self.integrate_with_enchantment_system()
        self.integrate_with_buff_manager()

    def integrate_with_base_manager(self, base_manager) -> int:
        if not self.registered_buildings:
            return 0
        count = 0
        for building_id, building_data in self.registered_buildings.items():
            if building_id not in base_manager.buildings:
                try:
                    from Modules.ModulesFunctions.BaseSystem import Building
                    base_manager.buildings[building_id] = Building(building_id, building_data)
                    count += 1
                except Exception as e:
                    logger.warning(f"No se pudo inyectar edificio {building_id}: {e}")
        return count

    # ── getters ──────────────────────────────────────────────────────────────
    def get_all_items(self) -> Dict:
        return self.item_injections

    def get_all_zones(self) -> Dict:
        return self.stats_injections

    def get_all_shops(self) -> Dict:
        return self.shop_injections

    def get_all_buildings(self) -> Dict:
        return self.registered_buildings


class ModInfo:
    """Información / manifest de un mod."""

    def __init__(self, mod_name: str, file_path: Path):
        self.mod_name = mod_name
        self.file_path = file_path
        self.py_file = file_path / f"{mod_name}.py"
        self.json_file = file_path / f"{mod_name}.json"
        self.loaded = False
        self.enabled = True

        # Metadata (rellenada desde el manifest)
        self.display_name = mod_name
        self.version = "1.0.0"
        self.author = "Unknown"
        self.description = ""
        self.game_version = None        # requisito ej. ">=1.0"
        self.dependencies: List[str] = []
        self.load_priority = 0
        self.has_code = self.py_file.exists()
        self.error: Optional[str] = None

    def apply_manifest(self, data: dict):
        """Lee 'manifest' o 'mod_info' del JSON."""
        manifest = {}
        if isinstance(data, dict):
            manifest = data.get("manifest") or data.get("mod_info") or {}
        self.display_name = manifest.get("name", self.mod_name)
        self.version = str(manifest.get("version", self.version))
        self.author = manifest.get("author", self.author)
        self.description = manifest.get("description", self.description)
        self.game_version = manifest.get("game_version")
        deps = manifest.get("dependencies", [])
        self.dependencies = list(deps) if isinstance(deps, (list, tuple)) else []
        self.load_priority = int(manifest.get("load_priority", 0))


class ModLoader:
    """Cargador de mods con manifest, dependencias, enable/disable y reload seguro."""

    def __init__(self, mods_directory="mods"):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.mods_directory = (base_dir / mods_directory) if not Path(mods_directory).is_absolute() else Path(mods_directory)
        self.loaded_mods = {}
        self.mod_api = ModAPI()
        self.config_path = self.mods_directory / "mods_config.json"
        self.mods_directory.mkdir(exist_ok=True, parents=True)
        self._disabled: set = set()
        self._load_config()

    # ── Config persistente (enable/disable + settings) ───────────────────────

    def _load_config(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                for mod_name, entry in cfg.items():
                    if not entry.get("enabled", True):
                        self._disabled.add(mod_name)
                    if "settings" in entry:
                        self.mod_api.mod_settings[mod_name] = entry["settings"]
        except Exception as e:
            logger.warning(f"No se pudo leer mods_config.json: {e}")

    def _save_config(self):
        try:
            cfg = {}
            for mod_name in set(list(self.loaded_mods.keys()) + list(self._disabled)):
                cfg[mod_name] = {
                    "enabled": mod_name not in self._disabled,
                    "settings": self.mod_api.mod_settings.get(mod_name, {}),
                }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"No se pudo guardar mods_config.json: {e}")

    def is_enabled(self, mod_name: str) -> bool:
        return mod_name not in self._disabled

    def enable_mod(self, mod_name: str):
        self._disabled.discard(mod_name)
        self._save_config()

    def disable_mod(self, mod_name: str):
        self._disabled.add(mod_name)
        if mod_name in self.loaded_mods:
            self.unload_mod(mod_name)
        self._save_config()

    # ── Descubrimiento ───────────────────────────────────────────────────────

    def discover_mods(self) -> Dict[str, ModInfo]:
        """Descubre mods: carpeta con <name>.json (el <name>.py es opcional)."""
        discovered = {}
        for mod_dir in self.mods_directory.iterdir():
            if not mod_dir.is_dir():
                continue
            json_files = list(mod_dir.glob("*.json"))
            # Ignorar el config global si estuviera dentro
            json_files = [j for j in json_files if j.name != "mods_config.json"]
            for json_file in json_files:
                mod_name = json_file.stem
                mod_info = ModInfo(mod_name, mod_dir)
                # Pre-cargar manifest para metadata/orden
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        mod_info.apply_manifest(json.load(f))
                except Exception as e:
                    logger.warning(f"Mod {mod_name}: manifest ilegible ({e})")
                mod_info.enabled = self.is_enabled(mod_name)
                discovered[mod_name] = mod_info
                logger.info(f"Mod descubierto: {mod_name} (py={'sí' if mod_info.has_code else 'no'})")
        return discovered

    # ── Resolución de orden (dependencias + prioridad) ───────────────────────

    def _resolve_order(self, mods: Dict[str, ModInfo]) -> List[ModInfo]:
        names = set(mods.keys())
        placed: List[str] = []
        placed_set: set = set()
        # Orden base: mayor prioridad primero, luego alfabético
        remaining = sorted(mods.values(), key=lambda m: (-m.load_priority, m.mod_name))

        progressed = True
        while remaining and progressed:
            progressed = False
            for m in list(remaining):
                dep_names = [parse_dependency(d)[0] for d in m.dependencies]
                unmet = [d for d in dep_names if d in names and d not in placed_set]
                if not unmet:
                    placed.append(m.mod_name)
                    placed_set.add(m.mod_name)
                    remaining.remove(m)
                    progressed = True
        # Ciclos / deps faltantes: colocar al final para que fallen en validación
        for m in remaining:
            placed.append(m.mod_name)
        return [mods[n] for n in placed]

    def _validate(self, mod_info: ModInfo, all_mods: Dict[str, ModInfo]) -> Optional[str]:
        if mod_info.game_version and not version_satisfies(GAME_VERSION, mod_info.game_version):
            return f"requiere juego {mod_info.game_version} (actual {GAME_VERSION})"
        for dep in mod_info.dependencies:
            dname, dspec = parse_dependency(dep)
            if dname not in all_mods:
                return f"falta dependencia '{dname}'"
            if self._disabled and dname in self._disabled:
                return f"dependencia '{dname}' está desactivada"
            if dspec and not version_satisfies(all_mods[dname].version, dspec):
                return f"dependencia '{dname}' versión {all_mods[dname].version} no cumple {dspec}"
        return None

    # ── Carga ────────────────────────────────────────────────────────────────

    def load_mod(self, mod_info: ModInfo, all_mods: Dict[str, ModInfo]) -> bool:
        mod_name = mod_info.mod_name
        err = self._validate(mod_info, all_mods)
        if err:
            mod_info.error = err
            logger.warning(f"Mod '{mod_name}' rechazado: {err}")
            console.print(f"[yellow]⚠ {mod_name}: {err}[/yellow]")
            return False
        try:
            self.mod_api._begin_mod(mod_name)

            mod_data = {}
            if mod_info.json_file.exists():
                mod_data = self.mod_api.load_mod_data(mod_name, str(mod_info.json_file))
                self.mod_api.auto_inject_from_mod_data(mod_name)

            mod_module = None
            if mod_info.py_file.exists():
                spec = importlib.util.spec_from_file_location(f"mod_{mod_name}", mod_info.py_file)
                if spec is None or spec.loader is None:
                    logger.error(f"No se pudo crear spec para {mod_name}")
                    self.mod_api._end_mod()
                    return False
                mod_module = importlib.util.module_from_spec(spec)
                sys.modules[f"mod_{mod_name}"] = mod_module
                spec.loader.exec_module(mod_module)
                if hasattr(mod_module, 'init_mod'):
                    mod_module.init_mod(self.mod_api, mod_data)

            mod_info.loaded = True
            mod_info.error = None
            self.loaded_mods[mod_name] = {'info': mod_info, 'module': mod_module, 'data': mod_data}
            logger.info(f"Mod cargado: {mod_name} v{mod_info.version}")
            return True
        except Exception as e:
            mod_info.error = str(e)
            logger.error(f"Error cargando mod {mod_name}: {e}", exc_info=True)
            console.print(f"[red]✗ Error cargando {mod_name}: {e}[/red]")
            return False
        finally:
            self.mod_api._end_mod()

    def load_all_mods(self):
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

        # Reset limpio (evita duplicación al recargar)
        for mod_name in list(self.loaded_mods.keys()):
            self._unload_module_only(mod_name)
        self.mod_api._contrib.clear()
        self.mod_api._applied_weather_ids.clear()

        discovered = self.discover_mods()
        if not discovered:
            console.print("[yellow]No se encontraron mods para cargar.[/yellow]")
            self.mod_api.rebuild([])
            return

        ordered = self._resolve_order(discovered)
        enabled = [m for m in ordered if self.is_enabled(m.mod_name)]

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("[cyan]Cargando Mods...", total=len(enabled) or 1)
            loaded_count = 0
            loaded_order = []
            for mod_info in enabled:
                if self.load_mod(mod_info, discovered):
                    loaded_count += 1
                    loaded_order.append(mod_info.mod_name)
                progress.advance(task)

        # Reconstruir agregados desde lo que se cargó
        self.mod_api.rebuild(loaded_order)
        self._save_config()

        skipped = len(discovered) - len(enabled)
        msg = f"[bold green]✓ Carga Completada[/bold green]\nMods activos: {loaded_count} de {len(discovered)}"
        if skipped:
            msg += f"\n[dim]{skipped} desactivado(s)[/dim]"
        console.print(Panel(msg, style="cyan"))

    # ── Descarga / recarga ───────────────────────────────────────────────────

    def _unload_module_only(self, mod_name: str):
        """Quita el módulo de sys.modules y llama cleanup, sin tocar config."""
        data = self.loaded_mods.get(mod_name)
        if not data:
            return
        mod_module = data.get('module')
        if mod_module is not None and hasattr(mod_module, 'cleanup_mod'):
            try:
                mod_module.cleanup_mod()
            except Exception as e:
                logger.error(f"Error en cleanup de {mod_name}: {e}")
        sys.modules.pop(f"mod_{mod_name}", None)
        self.loaded_mods.pop(mod_name, None)

    def unload_mod(self, mod_name: str) -> bool:
        """Descarga un mod y REVIERTE sus inyecciones (rebuild sin él)."""
        if mod_name not in self.loaded_mods:
            return False
        self._unload_module_only(mod_name)
        self.mod_api._contrib.pop(mod_name, None)
        remaining = [m for m in self.mod_api._enabled_order if m in self.loaded_mods]
        self.mod_api.rebuild(remaining)
        console.print(f"[yellow]Mod descargado: {mod_name}[/yellow]")
        logger.info(f"Mod descargado y revertido: {mod_name}")
        return True

    def reload_mod(self, mod_name: str) -> bool:
        """Recarga un mod concreto (unload + load) sin duplicar datos."""
        discovered = self.discover_mods()
        if mod_name not in discovered:
            console.print(f"[red]Mod '{mod_name}' no encontrado.[/red]")
            return False
        if mod_name in self.loaded_mods:
            self.unload_mod(mod_name)
        ok = self.load_mod(discovered[mod_name], discovered)
        if ok:
            order = [m for m in self.mod_api._enabled_order if m in self.loaded_mods]
            if mod_name not in order:
                order.append(mod_name)
            self.mod_api.rebuild(order)
        return ok

    # ── Info ─────────────────────────────────────────────────────────────────

    def get_loaded_mods_info(self) -> List:
        return [mod_data['info'] for mod_data in self.loaded_mods.values()]

    def get_all_mods_info(self) -> Dict[str, ModInfo]:
        return self.discover_mods()

    def display_mods_info(self):
        all_mods = self.discover_mods()
        if not all_mods:
            console.print("[yellow]No hay mods[/yellow]")
            return
        if Table is None:
            for name, info in all_mods.items():
                state = "ON" if self.is_enabled(name) else "OFF"
                console.print(f"- {name} v{info.version} [{state}]")
            return

        table = Table(title="Mods")
        table.add_column("Estado", justify="center")
        table.add_column("Nombre", style="cyan")
        table.add_column("Ver", style="green")
        table.add_column("Autor", style="dim")
        table.add_column("Código", justify="center")
        table.add_column("Nota", style="dim")
        for name, info in all_mods.items():
            loaded = name in self.loaded_mods
            if not self.is_enabled(name):
                state = "[red]OFF[/red]"
            elif loaded:
                state = "[green]ON[/green]"
            elif info.error:
                state = "[yellow]ERR[/yellow]"
            else:
                state = "[dim]—[/dim]"
            note = info.error or (info.description[:40] if info.description else "")
            table.add_row(state, info.display_name, info.version, info.author,
                          "py" if info.has_code else "data", note)
        console.print(table)


# Singleton
mod_loader: Optional[ModLoader] = None


def get_mod_api():
    """Retorna la instancia de ModAPI."""
    return get_mod_loader().mod_api


def get_mod_loader():
    """Retorna la instancia del ModLoader."""
    global mod_loader
    if mod_loader is None:
        mod_loader = ModLoader()
    return mod_loader
