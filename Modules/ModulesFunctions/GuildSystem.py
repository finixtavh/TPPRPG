"""
GuildSystem.py V2
=================
Motor del sistema de Guilds con economia viva, ejercitos, IA y eventos.
"""

import os, json, random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def _get_guild_config():
    cfg_path = Path(__file__).parent.parent.parent / "config.json"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f).get("GUILDS_PARAMS", {})
    except:
        return {}

try:
    from Modules.ModulesFunctions.WeatherSystem import apply_weather_combat_mods
except ImportError:
    def apply_weather_combat_mods(base_val: float, mod_key: str) -> float:
        return base_val

_DATA_ITEMS_JSON      = os.path.join("Data", "DataItems.json")
_GUILDS_JSON          = os.path.join("Data", "Guilds.json")
_ZONE_GUILDS_JSON     = os.path.join("Data", "ZoneGuilds.json")

SIMULATION_INTERVAL = 5
RARITY_BASE_CAPS = {"Common": 250, "Uncommon": 100, "Rare": 50, "Legendary": 25}

# ── Economía de materiales (reemplaza los viejos recursos de guild) ───────────
# Los "recursos" de guild ahora son materiales de DataItems.json TYPE:Materials.
MAX_TERRITORY_LEVEL = 5
TIER_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
ROMAN_TIER = {v: k for k, v in TIER_ROMAN.items()}
# Tope de almacenamiento por tier (tier bajo = más abundante/almacenable)
TIER_STORAGE_CAP = {"I": 500, "II": 300, "III": 200, "IV": 120, "V": 60}
# Valor base por tier (comercio/precio)
TIER_VALUE = {"I": 2, "II": 5, "III": 12, "IV": 30, "V": 70}
# Habilidades cuyo output cuenta como "alimento" para la población
FOOD_SKILLS = {"Herbalism", "Skinning"}
_SKILL_ICON = {"Woodcutting": "🪵", "Mining": "⛏️", "Herbalism": "🌿", "Skinning": "🦊"}

# Poblados al cargar definiciones (una sola instancia de manager en la práctica)
_TIER_MATERIALS: Dict[int, List[str]] = {1: [], 2: [], 3: [], 4: [], 5: []}
_FOOD_MATERIAL_IDS: List[str] = []


def _load_material_defs():
    """Carga TYPE:Materials de DataItems como definiciones de recurso de guild.

    Returns:
        (defs, tier_materials, food_ids)
        defs: {rid(str): {name, icon, rarity, tier, tier_roman, rarity_cap, base_value, skill}}
    """
    defs: Dict[str, dict] = {}
    tier_materials: Dict[int, List[str]] = {1: [], 2: [], 3: [], 4: [], 5: []}
    food_ids: List[str] = []
    try:
        with open(_DATA_ITEMS_JSON, "r", encoding="utf-8") as f:
            mats = json.load(f).get("TYPE:Materials", {})
        for v in mats.values():
            mid = v.get("MATERIAL_ID")
            if mid is None:
                continue
            rid = str(mid)
            tier_roman = v.get("Tier", "I")
            tier_n = ROMAN_TIER.get(tier_roman, 1)
            skill = v.get("SkillName", "")
            defs[rid] = {
                "name":       v.get("Name", rid),
                "icon":       _SKILL_ICON.get(skill, "📦"),
                "rarity":     tier_roman,                       # el tier hace de "rareza"
                "tier":       tier_n,
                "tier_roman": tier_roman,
                "rarity_cap": TIER_STORAGE_CAP.get(tier_roman, 250),
                "base_value": TIER_VALUE.get(tier_roman, 2),
                "skill":      skill,
            }
            tier_materials[tier_n].append(rid)
            if skill in FOOD_SKILLS:
                food_ids.append(rid)
    except Exception as e:
        print(f"[GuildSystem] Error cargando materiales: {e}")
    # Oro: moneda especial, no es material gatherable
    defs["oro"] = {"name": "Oro", "icon": "🪙", "rarity": "Currency", "tier": 0,
                   "tier_roman": "$", "rarity_cap": 9_999_999, "base_value": 1, "skill": ""}
    return defs, tier_materials, food_ids


def material_tier(resource_defs: dict, rid: str) -> int:
    return resource_defs.get(rid, {}).get("tier", 1)

# ── Edificios de Guild ────────────────────────────────────────────────────────
GUILD_BUILDINGS = {
    "cuartel": {
        "name":        "Cuartel",
        "icon":        "⚔",
        "description": "+20 Poder Militar permanente.",
        "cost":        {"tier_I": 45},
        "effect":      {"military_power": 20},
        "unique":      True,
    },
    "granero": {
        "name":        "Granero",
        "icon":        "🏚",
        "description": "Reduce el consumo de Comida a la mitad.",
        "cost":        {"tier_I": 30},
        "effect":      {"food_efficiency": True},
        "unique":      True,
    },
    "torre_guardia": {
        "name":        "Torre de Guardia",
        "icon":        "🗼",
        "description": "+30 defensa de territorios ante ataques enemigos.",
        "cost":        {"tier_I": 35, "tier_II": 10},
        "effect":      {"territory_defense": 30},
        "unique":      True,
    },
    "mercado": {
        "name":        "Mercado",
        "icon":        "🪙",
        "description": "+15% producción de recursos por tick.",
        "cost":        {"tier_I": 55},
        "effect":      {"resource_bonus": 0.15},
        "unique":      True,
    },
    "herreria": {
        "name":        "Herrería",
        "icon":        "🔨",
        "description": "+15 Poder Militar y acceso a equipamiento avanzado.",
        "cost":        {"tier_I": 15, "tier_II": 20},
        "effect":      {"military_power": 15},
        "unique":      True,
    },
    "almacen": {
        "name":        "Gran Almacén",
        "icon":        "🗃",
        "description": "+150 capacidad Común, +75 Poco Común.",
        "cost":        {"tier_I": 70},
        "effect":      {},
        "unique":      True,
    },
    "templo": {
        "name":        "Templo",
        "icon":        "⛪",
        "description": "Aumenta pasivamente la moral.",
        "cost":        {"tier_I": 20, "tier_II": 10},
        "effect":      {},
        "unique":      True,
    },
    "academia": {
        "name":        "Academia",
        "icon":        "🎓",
        "description": "Genera 1 Skill Point de vez en cuando.",
        "cost":        {"tier_I": 25, "tier_II": 15},
        "effect":      {},
        "unique":      True,
    },
    "granja": {
        "name":        "Granja Comunal",
        "icon":        "🚜",
        "description": "+50% al crecimiento base poblacional por tick.",
        "cost":        {"tier_I": 25},
        "effect":      {},
        "unique":      True,
    },
    "muralla": {
        "name":        "Muralla",
        "icon":        "🧱",
        "description": "+50 defensa territorial.",
        "cost":        {"tier_I": 50, "tier_III": 5},
        "effect":      {"territory_defense": 50},
        "unique":      True,
    },
    "mantenimiento": {
        "name":        "Puesto de Mantenimiento",
        "icon":        "🛠️",
        "description": "-75% probabilidad de daños por desastres naturales.",
        "cost":        {"tier_I": 30, "tier_II": 10},
        "effect":      {"disaster_protection": 0.75},
        "unique":      True,
    }
}

# ── Pool de eventos para el jugador ──────────────────────────────────────────

GUILD_EVENTS_POOL = [
    {
        "event_id":   "allied_request_help",
        "title":      "Petición de Aliado",
        "desc_tmpl":  "{guild} necesita refuerzos ante un ataque inminente. ¿Envías ayuda?",
        "options": [
            {"text": "Enviar 10 soldados",       "effects": {"soldiers": -10, "rel_src": +15, "moral": +5}},
            {"text": "Enviar 30 Comida",          "effects": {"17": -30,  "rel_src": +8}},
            {"text": "Rechazar la petición",      "effects": {"rel_src": -10}},
        ],
    },
    {
        "event_id":   "enemy_truce",
        "title":      "Propuesta de Tregua",
        "desc_tmpl":  "{guild} ofrece un alto al fuego temporal.",
        "options": [
            {"text": "Aceptar tregua",            "effects": {"rel_src": +20}},
            {"text": "Rechazar",                  "effects": {"rel_src": -5,  "moral": +3}},
        ],
    },
    {
        "event_id":   "merchants_pass",
        "title":      "Caravana de Mercaderes",
        "desc_tmpl":  "Una caravana pide paso por tus territorios.",
        "options": [
            {"text": "Dejar pasar (recibir 20 Comida)", "effects": {"17": +20}},
            {"text": "Cobrar peaje (obtener 15 Cuero)", "effects": {"20": +15}},
            {"text": "Bloquear (-5 rep todas guilds)",  "effects": {"rel_all": -5}},
        ],
    },
    {
        "event_id":   "spy_captured",
        "title":      "Espía Capturado",
        "desc_tmpl":  "Tus guardias capturaron a un espía de {guild}.",
        "options": [
            {"text": "Ejecutar (-rel, +info)",    "effects": {"rel_src": -15, "moral": +2}},
            {"text": "Liberar (+rel)",             "effects": {"rel_src": +10}},
            {"text": "Pedir rescate (50 Cuero)",  "effects": {"20": +50, "rel_src": -5}},
        ],
    },
    {
        "event_id":   "plague",
        "title":      "Plaga en las Tierras",
        "desc_tmpl":  "Una enfermedad se extiende por tus territorios.",
        "options": [
            {"text": "Gastar 40 Comida (detener plaga)",  "effects": {"17": -40}},
            {"text": "Cuarentena (-20 pop)",               "effects": {"population": -20, "moral": -5}},
            {"text": "Ignorar (-5% pop, -10 moral)",       "effects": {"population_pct": -0.05, "moral": -10}},
        ],
    },
    {
        "event_id":   "revolt",
        "title":      "Revuelta Interna",
        "desc_tmpl":  "La moral baja ha causado una revuelta en tus filas.",
        "options": [
            {"text": "Sofocar con recursos (30C+20M)",  "effects": {"17": -30, "1": -20, "moral": +15}},
            {"text": "Negociar (-15 soldados, +moral)", "effects": {"soldiers": -15, "moral": +12}},
            {"text": "Dejar que se calme (-12 moral)",  "effects": {"moral": -12}},
        ],
    },
    {
        "event_id":   "discovered_deposit",
        "title":      "Depósito Descubierto",
        "desc_tmpl":  "Exploradores encuentran un depósito oculto.",
        "options": [
            {"text": "Explotar (50 Xar)",              "effects": {"11": +50}},
            {"text": "Gradual (30 Xar + 20 Piedra)",   "effects": {"11": +30, "6": +20}},
        ],
    },
    {
        "event_id":   "trade_proposal",
        "title":      "Propuesta Comercial",
        "desc_tmpl":  "{guild} ofrece {offer_amt} {offer_res} a cambio de {req_amt} {req_res}.",
        "options": [
            {"text": "Aceptar el trato",  "effects": {"trade_accept": True}},
            {"text": "Rechazar",          "effects": {"rel_src": -3}},
        ],
    },
]


# ── GuildResource ─────────────────────────────────────────────────────────────

class GuildResource:
    def __init__(self, resource_id, name, icon, rarity, amount=0):
        self.resource_id = resource_id
        self.name        = name
        self.icon        = icon
        self.rarity      = rarity
        self.amount      = amount

    def to_dict(self):
        return {"resource_id": self.resource_id, "amount": self.amount}

    @staticmethod
    def from_dict(data, definitions):
        rid  = data["resource_id"]
        defn = definitions.get(rid, {})
        return GuildResource(rid, defn.get("name", rid), defn.get("icon", "?"),
                             defn.get("rarity", "Common"), data.get("amount", 0))


# ── Territory ─────────────────────────────────────────────────────────────────

class Territory:
    def __init__(self, data):
        self.id                  = data["id"]
        self.name                = data["name"]
        self.icon                = data.get("icon", "🗺")
        self.description         = data.get("description", "")
        self.resource_output     = data.get("resource_output", {})
        self.difficulty          = data.get("difficulty", 1)
        self.defense_value       = data.get("defense_value", 10)
        self.population_capacity = data.get("population_capacity", 50)
        self.owner               = data.get("owner", "neutral")
        self.position            = tuple(data.get("position", [0, 0]))
        # V3: Guarnición física en el territorio
        self.garrison: Dict[str, int] = data.get("garrison", {"infantry": 0, "archers": 0, "cavalry": 0, "siege": 0})
        # V3: Lealtad del territorio
        self.loyalty: int = data.get("loyalty", 100)
        # V3: Gobernador (Companion ID o similar)
        self.governor_id = data.get("governor_id", None)
        # NUEVO: Nivel del territorio (1..5). Produce materiales del tier = nivel.
        self.level: int = data.get("level", 1)

    def to_dict(self):
        return {"id": self.id, "owner": self.owner, "garrison": self.garrison,
                "loyalty": self.loyalty, "governor_id": self.governor_id, "level": self.level}

    def upgrade_cost(self) -> dict:
        """Coste para subir de nivel: materiales del tier siguiente (nivel+1).

        El jugador los recolecta a mano. Escala con el nivel objetivo.
        Returns {} si ya está al máximo.
        """
        if self.level >= MAX_TERRITORY_LEVEL:
            return {}
        next_level = self.level + 1
        amount = 15 + next_level * 10   # nivel 2: 35 ... nivel 5: 65
        return {f"tier_{TIER_ROMAN[next_level]}": amount}

    def produce_materials(self, tier_materials: dict, bonus_multiplier: float = 1.0) -> Dict[str, int]:
        """Produce materiales del tier = nivel del territorio. Escala con el nivel."""
        pool = tier_materials.get(self.level, [])
        if not pool:
            return {}
        # Cuántos tipos distintos y cuánto de cada uno
        n_types = min(len(pool), 1 + self.level // 2)   # 1..3 tipos
        chosen = random.sample(pool, n_types)
        base_amt = max(1, int((2 + self.level) * bonus_multiplier))
        return {rid: base_amt for rid in chosen}


# ── Guild ─────────────────────────────────────────────────────────────────────

class Guild:
    def __init__(self, guild_id, name, guild_type, icon,
                 military_power=50, population=100, moral=75,
                 aggressiveness=50, is_player_guild=False):
        self.guild_id        = guild_id
        self.name            = name
        self.guild_type      = guild_type
        self.icon            = icon
        self.military_power  = military_power
        self.population      = population
        self.moral           = moral
        self.aggressiveness  = aggressiveness
        self.is_player_guild = is_player_guild

        # ── V4: Taxes and Fights ────────────────────────────────────────────────
        self.tax_rate:       float = 0.05  # Default 5%
        self.fight_count:    int   = 0     # Fights since last tax
        self.tax_gold_pool:  int   = 0     # Accumulated gold from taxes
        self.ai_priority:    str   = "Balanced" # "Balanced", "Survival", "Expansion", "Economic"

        # Recursos
        self.resources: Dict[str, GuildResource] = {}
        # Territorios
        self.territories: List[str] = []
        self.relations:   Dict[str, int] = {}
        self.alliances:   List[str] = []
        self.at_war_with: List[str] = []
        self.influence:   int = 0
        # Skill tree
        self.skill_points:    int = 0
        self.unlocked_skills: List[str] = []
        # Logs
        self.event_log:   List[str] = []
        # Edificios construidos
        self.buildings:   List[str] = []
        # Pending events (solo guild del jugador)
        self.pending_events: List[dict] = []

        # ── V3: Ejército (Tipos de Tropas) ───────────────────────────────────────────
        self.soldiers: Dict[str, int] = {"infantry": 0, "archers": 0, "cavalry": 0, "siege": 0}
        self.attack_rating:  int = 1   # nivel de ataque (1-10)
        self.defense_rating: int = 1   # nivel de defensa (1-10)
        self.armor_rating:   int = 1   # nivel de armadura (1-10)

        # ── V2: Población ─────────────────────────────────────────────
        self.population_growth_pct: float = 0.03   # 3% default
        self.trade_cooldown:        int   = 0       # ticks hasta siguiente trade

    # ── Recursos ──────────────────────────────────────────────────────────────

    def get_resource(self, resource_id: str) -> int:
        r = self.resources.get(resource_id)
        return r.amount if r else 0

    def add_resource(self, resource_id: str, amount: int, definitions: dict) -> None:
        if resource_id not in self.resources:
            defn = definitions.get(resource_id, {})
            self.resources[resource_id] = GuildResource(
                resource_id, defn.get("name", resource_id),
                defn.get("icon", "?"), defn.get("rarity", "Common"), 0)
        self.resources[resource_id].amount += amount

    def consume_resource(self, resource_id: str, amount: int) -> bool:
        """Consume si hay suficiente. NO drena el recurso si falla."""
        r = self.resources.get(resource_id)
        if r and r.amount >= amount:
            r.amount -= amount
            return True
        return False

    # ── Helpers de TIER (la economía ahora va por tier de material) ───────────

    def get_tier_total(self, tier_n: int) -> int:
        return sum(self.get_resource(rid) for rid in _TIER_MATERIALS.get(tier_n, []))

    def consume_tier(self, tier_n: int, amount: int) -> bool:
        """Consume 'amount' total de materiales del tier dado (repartido). True si alcanzó."""
        avail = [(rid, self.get_resource(rid)) for rid in _TIER_MATERIALS.get(tier_n, [])]
        avail = [(rid, a) for rid, a in avail if a > 0]
        if sum(a for _, a in avail) < amount:
            return False
        need = amount
        for rid, have in avail:
            take = min(have, need)
            self.consume_resource(rid, take)
            need -= take
            if need <= 0:
                break
        return True

    def can_afford_tier_cost(self, cost: dict) -> bool:
        """cost = {'tier_I': n, 'tier_II': m, ...} o {'oro': k}."""
        for key, amt in cost.items():
            if key == "oro":
                if self.get_resource("oro") < amt:
                    return False
            elif key.startswith("tier_"):
                tier_n = ROMAN_TIER.get(key.split("_", 1)[1], 1)
                if self.get_tier_total(tier_n) < amt:
                    return False
        return True

    def pay_tier_cost(self, cost: dict) -> bool:
        """Paga un coste tier-based; asume can_afford_tier_cost ya verificado."""
        if not self.can_afford_tier_cost(cost):
            return False
        for key, amt in cost.items():
            if key == "oro":
                self.consume_resource("oro", amt)
            elif key.startswith("tier_"):
                self.consume_tier(ROMAN_TIER.get(key.split("_", 1)[1], 1), amt)
        return True

    def get_resource_cap(self, resource_id: str, resource_defs: dict,
                          guild_type_defs: dict) -> int:
        defn = resource_defs.get(resource_id, {})
        tier = defn.get("tier_roman", "I")
        cap  = defn.get("rarity_cap", TIER_STORAGE_CAP.get(tier, 250))
        # Building bonus (Gran Almacén): +capacidad a tiers bajos
        if "almacen" in self.buildings:
            if tier == "I":   cap += 250
            elif tier == "II": cap += 120
            elif tier == "III": cap += 60
        # Skill tree bonus
        if "eco_storage" in self.unlocked_skills:
            if tier == "I":   cap += 150
            elif tier == "II": cap += 80
        return cap

    def clamp_resources(self, resource_defs: dict, guild_type_defs: dict) -> None:
        """Clamp all resources to their caps after production."""
        for rid, res in self.resources.items():
            cap = self.get_resource_cap(rid, resource_defs, guild_type_defs)
            if res.amount > cap:
                res.amount = cap

    # ── Ejército ──────────────────────────────────────────────────────────────

    def lose_soldiers(self, amount: int) -> None:
        """Removes 'amount' soldiers proportionally from the army types."""
        total = self.get_total_soldiers()
        if total <= 0 or amount <= 0: return
        amount = min(amount, total)
        for ttype, count in self.soldiers.items():
            if count > 0:
                loss = int((count / total) * amount)
                self.soldiers[ttype] = max(0, count - loss)
        
        remaining_loss = amount - (total - self.get_total_soldiers())
        while remaining_loss > 0 and self.get_total_soldiers() > 0:
            for ttype in self.soldiers:
                if self.soldiers[ttype] > 0:
                    self.soldiers[ttype] -= 1
                    remaining_loss -= 1
                    if remaining_loss <= 0: break

    def get_total_soldiers(self) -> int:
        return sum(self.soldiers.values())

    def get_max_soldiers(self, guild_type_defs: dict) -> int:
        type_data = guild_type_defs.get(self.guild_type, {})
        pct = 0.10 + type_data.get("recruit_pct_bonus", 0.0)
        if "mil_vanguard"   in self.unlocked_skills: pct += 0.05
        if "mil_logistics"  in self.unlocked_skills: pct += 0.05
        return max(1, int(self.population * pct))

    def recruit_soldiers(self, troop_type: str, count: int, resource_defs: dict,
                         guild_type_defs: dict) -> Tuple[int, str]:
        if troop_type not in ["infantry", "archers", "cavalry", "siege"]:
            troop_type = "infantry"
            
        slots = max(0, self.get_max_soldiers(guild_type_defs) - self.get_total_soldiers())
        n     = min(count, slots)
        if n <= 0:
            return 0, "Ya tienes el máximo de soldados."
        # Reclutar cuesta materiales tier I (provisiones) + tier II (equipo)
        food_cost    = n                 # tier I
        leather_cost = max(1, n // 2)    # tier II
        if self.get_tier_total(1) < food_cost:
            return 0, f"Necesitas {food_cost} materiales Tier I (provisiones)."
        if self.get_tier_total(2) < leather_cost:
            return 0, f"Necesitas {leather_cost} materiales Tier II (equipo)."
        self.consume_tier(1, food_cost)
        self.consume_tier(2, leather_cost)
        self.soldiers[troop_type] += n
        return n, f"✓ Reclutaste {n} soldados."

    def upgrade_army_stat(self, stat: str, resource_defs: dict) -> Tuple[bool, str]:
        """stat: 'attack' | 'defense' | 'armor'. Cuesta materiales Tier II/III."""
        # (tier_n, base) escala con el nivel actual
        specs = {"attack": (2, 5), "defense": (2, 5), "armor": (3, 4)}
        attr  = {"attack": "attack_rating", "defense": "defense_rating", "armor": "armor_rating"}
        if stat not in specs:
            return False, "Stat inválida."
        current = getattr(self, attr[stat], 1)
        if current >= 10:
            return False, "Ya está al máximo (nivel 10)."
        tier_n, base = specs[stat]
        cost = base * current
        if self.get_tier_total(tier_n) < cost:
            return False, f"Necesitas {cost} materiales Tier {TIER_ROMAN[tier_n]}."
        self.consume_tier(tier_n, cost)
        setattr(self, attr[stat], current + 1)
        return True, f"✓ {stat.capitalize()} subió a nivel {current + 1}."

    # ── Población ─────────────────────────────────────────────────────────────

    def get_food_total(self) -> int:
        """Alimento = materiales de herboristería/peletería en stock."""
        return sum(self.get_resource(rid) for rid in _FOOD_MATERIAL_IDS)

    def consume_food_materials(self, amount: int) -> bool:
        """Consume 'amount' de alimento repartido entre materiales-comida."""
        avail = [(rid, self.get_resource(rid)) for rid in _FOOD_MATERIAL_IDS]
        avail = [(rid, a) for rid, a in avail if a > 0]
        if sum(a for _, a in avail) < amount:
            return False
        need = amount
        for rid, have in avail:
            take = min(have, need)
            self.consume_resource(rid, take)
            need -= take
            if need <= 0:
                break
        return True

    def grow_population(self, resource_defs: dict) -> str:
        food_needed = max(1, self.population // 8)
        # Granero reduce el consumo de comida a la mitad
        if "granero" in self.buildings:
            food_needed = max(1, food_needed // 2)
        food_have = self.get_food_total()
        if food_have >= food_needed:
            growth = max(1, int(self.population * self.population_growth_pct))
            if "granja" in self.buildings:
                growth = int(growth * 1.5)
            self.population += growth
            self.consume_food_materials(food_needed)
            return f"Población +{growth}."
        else:
            ratio    = food_have / food_needed if food_needed > 0 else 0
            pop_loss = max(1, int(self.population * 0.02 * (1 - ratio)))
            self.population = max(10, self.population - pop_loss)
            sol_loss = min(self.get_total_soldiers(), pop_loss // 3)
            self.lose_soldiers(sol_loss)
            self.change_moral(-3)
            self.consume_food_materials(food_have)  # consume lo que quede
            self.log_event(f"🍞 Hambruna: -{pop_loss} población.")
            return f"Hambruna: -{pop_loss} pop."

    # ── V4: Taxes ─────────────────────────────────────────────────────────────

    def apply_taxes(self) -> str:
        """Calculates taxes based on population. Triggered every 5 fights."""
        # Gold generated: pop * tax_rate * multiplier (economy)
        mult = 2.5
        if "eco_caravans" in self.unlocked_skills:
            # Caravanas ahora dan un bonus a la recaudación por territorio
            mult += len(self.territories) * 0.5
            
        gold_generated = int(self.population * self.tax_rate * mult) 
        self.tax_gold_pool += gold_generated
        
        # Moral penalty for high taxes
        if self.tax_rate > 0.10:
            # -1 morale for every 5% above 10%, plus a base penalty
            moral_loss = 2 + int((self.tax_rate - 0.10) * 20)
            self.change_moral(-moral_loss)
            self.log_event(f"📉 Impuestos altos ({int(self.tax_rate*100)}%): -{moral_loss} Moral.")
        
        self.log_event(f"💰 Recaudación de impuestos: +{gold_generated} Oro.")
        return f"¡Día de Impuestos! Se recaudaron {gold_generated} Oro de la población."

    def get_tax_debuffs(self) -> Dict[str, float]:
        """Returns debuffs based on tax rate for player/guild."""
        debuffs = {}
        if self.tax_rate > 0.10:
            # Max penalty at 50% tax: (0.50 - 0.10) * 1.0 = 0.40 (40% reduction)
            penalty = (self.tax_rate - 0.10) * 1.0
            debuffs["damage_mult"] = max(0.5, 1.0 - penalty)
            debuffs["defense_mult"] = max(0.5, 1.0 - penalty)
            debuffs["morale_loss"] = (self.tax_rate - 0.10) * 5 # Passive morale loss per tick
        return debuffs

    # ── Moral / Utilidad ──────────────────────────────────────────────────────

    def change_moral(self, delta: int) -> None:
        self.moral = max(0, min(100, self.moral + delta))

    def consume_food(self) -> bool:
        """Consumo de alimento por tick (materiales de herboristería/peletería)."""
        food_needed = max(1, self.population // 8)
        if "granero" in self.buildings:
            food_needed = max(1, food_needed // 2)
        if self.get_food_total() >= food_needed:
            self.consume_food_materials(food_needed)
            return True
        self.change_moral(-5)
        self.log_event("⚠ Sin comida.")
        return False

    def log_event(self, message: str) -> None:
        self.event_log.append(message)
        if len(self.event_log) > 25:
            self.event_log.pop(0)

    def military_multiplier(self, type_data: dict) -> float:
        return 1.0 + type_data.get("military_bonus", 0.0) + type_data.get("military_penalty", 0.0)

    def economy_multiplier(self, type_data: dict) -> float:
        return 1.0 + type_data.get("economy_bonus", 0.0)

    # ── Serialización ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "guild_id":             self.guild_id,
            "name":                 self.name,
            "guild_type":           self.guild_type,
            "icon":                 self.icon,
            "military_power":       self.military_power,
            "population":           self.population,
            "moral":                self.moral,
            "aggressiveness":       self.aggressiveness,
            "is_player_guild":      self.is_player_guild,
            "resources":            {rid: r.to_dict() for rid, r in self.resources.items()},
            "territories":          list(self.territories),
            "relations":            dict(self.relations),
            "alliances":            list(self.alliances),
            "at_war_with":          list(self.at_war_with),
            "influence":            self.influence,
            "skill_points":         self.skill_points,
            "unlocked_skills":      list(self.unlocked_skills),
            "event_log":            list(self.event_log),
            "buildings":            list(self.buildings),
            "pending_events":       list(self.pending_events),
            "soldiers":             self.soldiers,
            "attack_rating":        self.attack_rating,
            "defense_rating":       self.defense_rating,
            "armor_rating":         self.armor_rating,
            "population_growth_pct": self.population_growth_pct,
            "trade_cooldown":       self.trade_cooldown,
            "tax_rate":             self.tax_rate,
            "fight_count":          self.fight_count,
            "tax_gold_pool":        self.tax_gold_pool,
            "ai_priority":          self.ai_priority,
        }

    @staticmethod
    def from_dict(data: dict, resource_defs: dict) -> "Guild":
        g = Guild(
            guild_id        = data["guild_id"],
            name            = data["name"],
            guild_type      = data.get("guild_type", "Militar"),
            icon            = data.get("icon", "⚔"),
            military_power  = data.get("military_power", 50),
            population      = data.get("population", 100),
            moral           = data.get("moral", 75),
            aggressiveness  = data.get("aggressiveness", 50),
            is_player_guild = data.get("is_player_guild", False),
        )
        for rid, rdata in data.get("resources", {}).items():
            g.resources[rid] = GuildResource.from_dict(rdata, resource_defs)
        g.territories            = data.get("territories", [])
        g.relations              = data.get("relations", {})
        g.alliances              = data.get("alliances", [])
        g.at_war_with            = data.get("at_war_with", [])
        g.influence              = data.get("influence", 0)
        g.skill_points           = data.get("skill_points", 0)
        g.unlocked_skills        = data.get("unlocked_skills", [])
        g.event_log              = data.get("event_log", [])
        g.buildings              = data.get("buildings", [])
        g.pending_events         = data.get("pending_events", [])
        
        loaded_soldiers = data.get("soldiers", 0)
        if isinstance(loaded_soldiers, int):
            # Migración automática V2 -> V3
            g.soldiers = {"infantry": loaded_soldiers, "archers": 0, "cavalry": 0, "siege": 0}
        else:
            g.soldiers = {
                "infantry": loaded_soldiers.get("infantry", 0),
                "archers": loaded_soldiers.get("archers", 0),
                "cavalry": loaded_soldiers.get("cavalry", 0),
                "siege": loaded_soldiers.get("siege", 0)
            }
            
        g.attack_rating          = data.get("attack_rating", 1)
        g.defense_rating         = data.get("defense_rating", 1)
        g.armor_rating           = data.get("armor_rating", 1)
        g.population_growth_pct  = data.get("population_growth_pct", 0.03)
        g.trade_cooldown         = data.get("trade_cooldown", 0)
        g.tax_rate               = data.get("tax_rate", 0.05)
        g.fight_count            = data.get("fight_count", 0)
        g.tax_gold_pool          = data.get("tax_gold_pool", 0)
        g.ai_priority            = data.get("ai_priority", "Balanced")
        return g


# ── GuildManager ──────────────────────────────────────────────────────────────

class GuildManager:
    def __init__(self):
        self.guilds:          Dict[str, Guild]     = {}
        self.territories:     Dict[str, Territory] = {}
        self.resource_defs:   Dict[str, dict]      = {}
        self.guild_type_defs: Dict[str, dict]      = {}
        self.guild_name_data: dict                 = {}
        self.world_events:    List[str]            = []
        self.player_guild_id: Optional[str]        = None
        self.world_tension:   float                = 0.0
        self.tier_materials:  Dict[int, List[str]] = {1: [], 2: [], 3: [], 4: [], 5: []}
        self.food_material_ids: List[str]          = []
        self._guild_config_cache: Optional[dict]   = None  # cache de GUILDS_PARAMS
        self._load_definitions()

    def get_config(self) -> dict:
        """GUILDS_PARAMS de config.json, cacheado (antes se re-leía por territorio/tick)."""
        if self._guild_config_cache is None:
            self._guild_config_cache = _get_guild_config()
        return self._guild_config_cache

    def generate_initial_player_events(self):
        """Genera eventos interactivos iniciales para el jugador al fundar/unirse a una guild."""
        pg = self.get_player_guild()
        if not pg:
            return

        pg.pending_events = []

        ev_welcome = {
            "event_id": "initial_welcome",
            "title": "Un Nuevo Amanecer",
            "description": "Has tomado el mando. El mundo observa tus próximos movimientos con gran expectación. ¿Qué mensaje deseas dar a tus seguidores para motivarlos en este comienzo?",
            "source_guild_id": pg.guild_id,
            "options": [
                {"text": "Discurso inspirador (+20 Moral)", "effects": {"moral": 20}},
                {"text": "Promesa de riqueza (+100 Oro)", "effects": {"oro": 100}},
                {"text": "Llamado a las armas (+5 Soldados)", "effects": {"soldiers": 5}},
            ]
        }
        pg.pending_events.append(ev_welcome)

        ev_merchant = {
            "event_id": "initial_merchant",
            "title": "Mercader Errante",
            "description": "Un mercader ha escuchado sobre la actividad de tu gremio. Ofrece una inversión inicial a cambio de garantías, o venta de materiales.",
            "source_guild_id": "",
            "options": [
                {"text": "Aceptar la inversión (+250 Oro)", "effects": {"oro": 250}},
                {"text": "Comprar materiales (Pagar 100 Oro, +30 Tier I, +15 Tier II)", "effects": {"oro": -100, "tier_I": 30, "tier_II": 15}},
                {"text": "Rechazar cordialmente (Sin efecto)", "effects": {}},
            ]
        }
        pg.pending_events.append(ev_merchant)

        npc_guilds = [g for g in self.guilds.values() if not g.is_player_guild]
        if npc_guilds:
            import random
            neighbor = random.choice(npc_guilds)
            ev_neighbor = {
                "event_id": "initial_neighbor",
                "title": "Mensajero Cercano",
                "description": f"Un enviado de la guild vecina [{neighbor.icon} {neighbor.name}] llega con saludos formales. Expresan su deseo de paz, pero su tono es cauteloso.",
                "source_guild_id": neighbor.guild_id,
                "options": [
                    {"text": "Enviar regalos de vuelta (-50 Oro, +15 Relación)", "effects": {"oro": -50, "rel_src": 15, "src_id": neighbor.guild_id}},
                    {"text": "Agradecer verbalmente (+5 Relación)", "effects": {"rel_src": 5, "src_id": neighbor.guild_id}},
                    {"text": "Despedir al enviado fríamente (-10 Relación)", "effects": {"rel_src": -10, "src_id": neighbor.guild_id}},
                ]
            }
            pg.pending_events.append(ev_neighbor)

    def _load_definitions(self):
        global _TIER_MATERIALS, _FOOD_MATERIAL_IDS
        # Recursos de guild = materiales de DataItems.json
        self.resource_defs, self.tier_materials, self.food_material_ids = _load_material_defs()
        _TIER_MATERIALS = self.tier_materials
        _FOOD_MATERIAL_IDS = self.food_material_ids

        for path, key in [(_ZONE_GUILDS_JSON, "territories"), (_GUILDS_JSON, None)]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if key == "territories":
                    for tid, td in data.get("territories", {}).items():
                        self.territories[tid] = Territory(td)
                else:
                    self.guild_name_data = data.get("guild_names", {})
                    self.guild_type_defs = data.get("guild_types", {})
            except Exception as e:
                print(f"[GuildSystem] Error: {e}")

    # ── Generación ────────────────────────────────────────────────────────────

    def generate_random_guilds(self, count=None):
        if count is None:
            cfg = _get_guild_config()
            min_g = cfg.get("MIN_NPC_GUILDS", 20)
            max_g = cfg.get("MAX_NPC_GUILDS", 35)
            count = random.randint(min_g, max_g)
        prefixes   = self.guild_name_data.get("prefixes", ["Orden de"])
        nouns      = self.guild_name_data.get("nouns", ["las Sombras"])
        guild_types = list(self.guild_type_defs.keys())
        territory_pool = list(self.territories.keys())
        random.shuffle(territory_pool)

        for i in range(count):
            gt       = random.choice(guild_types)
            td       = self.guild_type_defs[gt]
            name     = f"{random.choice(prefixes)} {random.choice(nouns)}"
            g = Guild(f"npc_guild_{i}", name, gt, td.get("icon","⚔"),
                      random.randint(30,80), random.randint(80,200),
                      random.randint(60,90), random.randint(20,80))
            if territory_pool:
                tid = territory_pool.pop()
                g.territories.append(tid)
                self.territories[tid].owner = g.guild_id
            for rid in self.resource_defs:
                g.add_resource(rid, random.randint(20,80), self.resource_defs)
            # Initial soldiers = ~10% population
            g.soldiers = {"infantry": int(g.population * 0.10), "archers": 0, "cavalry": 0, "siege": 0}
            self.guilds[g.guild_id] = g

        guild_ids = list(self.guilds.keys())
        for gid, guild in self.guilds.items():
            for other in guild_ids:
                if other != gid:
                    guild.relations[other] = random.randint(-30, 30)

    def initialize_world_state(self, world_cfg: dict) -> List[str]:
        """
        Ejecuta eventos y guerras iniciales procedurales al comenzar una partida nueva.
        Llamar después de generate_random_guilds().

        Args:
            world_cfg: sección CONFIG["WORLD"]
        Returns:
            Lista de mensajes generados (para mostrar en el log del mundo).
        """
        n_events = int(round(world_cfg.get("AMOUNT_OF_STARTING_EVENTS", 10)))
        n_wars   = int(round(world_cfg.get("AMOUNT_OF_STARTING_WARS",   2)))

        npc_guilds = [g for g in self.guilds.values() if not g.is_player_guild]
        if not npc_guilds:
            return []

        messages = []

        # ── Eventos aleatorios procedurales ──────────────────────────────────
        for _ in range(n_events):
            g = random.choice(npc_guilds)
            # Usamos _generate_random_event si existe, si no, generamos uno simple
            try:
                evt = self._generate_random_event(g)
                if evt and isinstance(evt, dict):
                    msg = evt.get("message", "")
                    if msg:
                        self.world_events.append(msg)
                        messages.append(msg)
                elif evt and isinstance(evt, str):
                    self.world_events.append(evt)
                    messages.append(evt)
                else:
                    # Fallback: evento simple de relación
                    candidates = [other for oid, other in self.guilds.items()
                                  if oid != g.guild_id and not other.is_player_guild]
                    if candidates:
                        other = random.choice(candidates)
                        delta = random.choice([-15, -10, -5, 5, 10, 15])
                        old   = g.relations.get(other.guild_id, 0)
                        g.relations[other.guild_id]     = max(-100, min(100, old + delta))
                        other.relations[g.guild_id]     = max(-100, min(100, old + delta))
                        verb = "mejoró" if delta > 0 else "deterioró"
                        msg  = (f"📜 Las relaciones entre [{g.icon} {g.name}] y "
                                f"[{other.icon} {other.name}] se {verb} ({delta:+d}).")
                        self.world_events.append(msg)
                        messages.append(msg)
            except Exception:
                pass  # Eventos no son críticos, si falla uno lo ignoramos

        # ── Guerras iniciales ─────────────────────────────────────────────────
        wars_declared = 0
        # Candidatos: pares de guilds con relación <= -10 que no estén ya en guerra
        candidates_war = []
        guild_list = list(self.guilds.items())
        for i, (gid_a, ga) in enumerate(guild_list):
            if ga.is_player_guild:
                continue
            for gid_b, gb in guild_list[i+1:]:
                if gb.is_player_guild:
                    continue
                rel_ab = ga.relations.get(gid_b, 0)
                rel_ba = gb.relations.get(gid_a, 0)
                avg_rel = (rel_ab + rel_ba) / 2
                if avg_rel <= -10 and gid_b not in getattr(ga, "at_war_with", []):
                    candidates_war.append((ga, gb, avg_rel))

        # Ordenar por peor relación primero (más probable que peleen)
        candidates_war.sort(key=lambda x: x[2])

        for ga, gb, _ in candidates_war:
            if wars_declared >= n_wars:
                break
            if not hasattr(ga, "at_war_with"):
                ga.at_war_with = []
            if not hasattr(gb, "at_war_with"):
                gb.at_war_with = []
            ga.at_war_with.append(gb.guild_id)
            gb.at_war_with.append(ga.guild_id)
            # Reducir relaciones más aún
            ga.relations[gb.guild_id] = max(-100, ga.relations.get(gb.guild_id, -10) - 20)
            gb.relations[ga.guild_id] = max(-100, gb.relations.get(ga.guild_id, -10) - 20)
            msg = (f"⚔ [GUERRA INICIAL] [{ga.icon} {ga.name}] y [{gb.icon} {gb.name}] "
                   f"ya están en conflicto desde el inicio del mundo.")
            self.world_events.append(msg)
            messages.append(msg)
            wars_declared += 1

        return messages

    # ── Tick de simulación ────────────────────────────────────────────────────

    def _ai_build_structures(self, guild: Guild):
        """Intento de la IA de construir algo estratégicamente."""
        if guild.is_player_guild: return
        
        # Prioridades según estado
        priority = []
        if guild.moral < 40: priority.append("templo")
        if guild.population < 100: priority.append("granja")
        if guild.military_power < 40: priority.extend(["cuartel", "herreria"])
        if guild.get_food_total() < guild.population // 4: priority.append("granero")

        # Añadir resto de edificios al final del pool
        all_ids = list(GUILD_BUILDINGS.keys())
        random.shuffle(all_ids)
        priority.extend(all_ids)

        for b_id in priority:
            if b_id not in GUILD_BUILDINGS: continue
            b_data = GUILD_BUILDINGS[b_id]
            if b_id in guild.buildings and b_data.get("unique"): continue

            cost = b_data.get("cost", {})
            if guild.can_afford_tier_cost(cost) and guild.pay_tier_cost(cost):
                guild.buildings.append(b_id)
                guild.log_event(f"🏗 Estratégico: {b_data['name']}")
                eff = b_data.get("effect", {})
                if "military_power" in eff:
                    guild.military_power += eff["military_power"]
                break

    def _ai_trade_surplus(self, guild: Guild):
        """IA intenta vender excedentes si tiene mercado."""
        if guild.is_player_guild or "mercado" not in guild.buildings: return
        if guild.trade_cooldown > 0: return
        
        for rid, res in guild.resources.items():
            cap = guild.get_resource_cap(rid, self.resource_defs, self.guild_type_defs)
            if res.amount > cap * 0.9:
                # Intentar vender a otra guild
                other = random.choice(list(self.guilds.values()))
                if other.guild_id != guild.guild_id:
                    trade_amt = min(20, res.amount // 4)
                    guild.consume_resource(rid, trade_amt)
                    other.add_resource(rid, trade_amt, self.resource_defs)
                    guild.add_resource("oro", trade_amt * 2, self.resource_defs)
                    guild.trade_cooldown = 4
                    break

    def tick(self, resource_defs: dict = None, type_defs: dict = None) -> List[str]:
        resource_defs = resource_defs if resource_defs is not None else self.resource_defs
        type_defs = type_defs if type_defs is not None else self.guild_type_defs
        self.world_events = []
        for guild in list(self.guilds.values()):
            self._produce_resources(guild)
            self._process_territories(guild, self.world_events)
            guild.clamp_resources(resource_defs, type_defs)
            # Población crece/decrece según alimento (antes estaba desactivado)
            guild.grow_population(resource_defs)

            if not guild.is_player_guild:
                guild.consume_food()
                self._ai_build_structures(guild)   # única ruta de construcción IA
                self._ai_trade_surplus(guild)

                msg = self._ai_decide(guild)
                if msg:
                    self.world_events.append(msg)   # _ai_decide ya NO auto-appendea

            if guild.trade_cooldown > 0:
                guild.trade_cooldown -= 1

        self._process_disasters(self.world_events)
        return self.world_events


    def _process_disasters(self, events: List[str], force: bool = False):
        """Procesa desastres naturales basados en el clima actual."""
        try:
            from Modules.ModulesFunctions.WeatherSystem import get_weather_manager
            wm = get_weather_manager()
            w = wm.get_current_weather()
            
            # Si forzamos, elegimos un clima de desastre al azar para el efecto
            if force:
                w = random.choice([v for v in wm.weathers.values() if v.disaster_effect])
                
            if not w.disaster_effect:
                return
                
            effect = w.disaster_effect
            chance = effect.get("chance", 0.0) if not force else 1.0
            
            # El desastre tiene una probabilidad global de intentar golpear a alguien
            if force or random.random() < chance:
                all_guilds = list(self.guilds.values())
                if not all_guilds: return
                
                target_guild = random.choice(all_guilds)
                
                # Protección por edificio de mantenimiento
                actual_chance = 1.0 # Una vez seleccionado el target, ¿le afecta?
                if not force and "mantenimiento" in target_guild.buildings:
                    actual_chance = 0.25 # 75% de esquivarlo
                
                if force or random.random() < actual_chance:
                    if effect.get("type") == "building_destruction":
                        if target_guild.buildings:
                            destroyed = random.choice(target_guild.buildings)
                            target_guild.buildings.remove(destroyed)
                            
                            # Obtener nombre legible del edificio
                            from Modules.ModulesMenu.GuildMenu import GUILD_BUILDINGS
                            b_data = GUILD_BUILDINGS.get(destroyed, {"name": destroyed, "icon": "🏗"})
                            b_name = f"{b_data['icon']} {b_data['name']}"
                            
                            msg = effect.get("message", "¡Desastre! {building} destruido.").format(
                                building=b_name, guild=target_guild.name
                            )
                            events.append(msg)
                            target_guild.log_event(msg)
                            target_guild.change_moral(-15)
                        elif force:
                            events.append(f"💨 El desastre golpeó a {target_guild.name} pero no tenía edificios que destruir.")
                else:
                    events.append(f"🛠️ El Puesto de Mantenimiento de {target_guild.name} evitó daños mayores durante el {w.name}.")

        except Exception as e:
            pass

    def trigger_debug_disaster(self) -> List[str]:
        """Fuerza un desastre aleatorio para debugging."""
        events = []
        self._process_disasters(events, force=True)
        return events

    def sell_surplus_resources(self, guild: Guild, resource_id: str, amount: int, player) -> Tuple[bool, str]:
        """Vende recursos de la guild a otras guilds NPC a cambio de Oro y Reputación."""
        if guild.get_resource(resource_id) < amount:
            return False, "No tienes suficientes recursos."
            
        # Buscar compradores interesados (Guilds aliadas o neutrales con buena relación)
        potential_buyers = [
            g for gid, g in self.guilds.items() 
            if gid != guild.guild_id and guild.relations.get(gid, 0) > -10
        ]
        
        if not potential_buyers:
            return False, "No hay guilds interesadas en comerciar contigo ahora mismo."
            
        buyer = random.choice(potential_buyers)
        
        # Precio basado en el tier del material (base_value)
        res_def = self.resource_defs.get(resource_id, {})
        base_price = res_def.get("base_value", 2)

        total_gold = amount * base_price
        
        # Aplicar transacción
        guild.consume_resource(resource_id, amount)
        guild.add_resource("oro", total_gold, self.resource_defs)
        
        # Mejora de relación con el comprador
        rep_gain = max(1, amount // 20)
        self.change_player_reputation(player, buyer.guild_id, rep_gain) 
        buyer.relations[guild.guild_id] = min(100, buyer.relations.get(guild.guild_id, 0) + rep_gain)
        
        msg = f"✓ Has vendido {amount} {res_def.get('name', resource_id)} a {buyer.name} por {total_gold} Oro."
        guild.log_event(msg)
        return True, msg

    # ── Mejora de territorios (consume materiales del inventario del jugador) ──

    def _consume_materials_from_inventory(self, inventory, tier_n: int, amount: int) -> Tuple[bool, int]:
        """Consume 'amount' de materiales del tier dado desde el inventario del jugador."""
        wanted = set(self.tier_materials.get(tier_n, []))
        matching = []
        total = 0
        for slot in inventory.slots:
            mid = getattr(slot.item, "MATERIAL_ID", getattr(slot.item, "ID", None))
            if mid is not None and str(mid) in wanted:
                matching.append(slot)
                total += slot.quantity
        if total < amount:
            return False, total
        need = amount
        for slot in matching:
            take = min(slot.quantity, need)
            slot.quantity -= take
            need -= take
            if need <= 0:
                break
        inventory.slots[:] = [s for s in inventory.slots if s.quantity > 0]
        return True, amount

    def upgrade_territory(self, territory: Territory, player, inventory) -> Tuple[bool, str]:
        """Sube de nivel un territorio del jugador consumiendo materiales tier (nivel+1)."""
        pg = self.get_player_guild()
        if not pg or territory.owner != pg.guild_id:
            return False, "Solo puedes mejorar territorios de tu propia guild."
        if territory.level >= MAX_TERRITORY_LEVEL:
            return False, f"{territory.name} ya está al nivel máximo ({MAX_TERRITORY_LEVEL})."
        cost = territory.upgrade_cost()
        (tier_key, amount), = cost.items()
        tier_n = ROMAN_TIER.get(tier_key.split("_", 1)[1], 1)
        ok, have = self._consume_materials_from_inventory(inventory, tier_n, amount)
        if not ok:
            return False, (f"Necesitas {amount} materiales Tier {TIER_ROMAN[tier_n]} "
                           f"(tienes {have}). Recoléctalos a mano en las zonas.")
        territory.level += 1
        territory.defense_value += 10
        territory.population_capacity += 20
        pg.influence += 5
        pg.log_event(f"🏗 {territory.name} mejorado a nivel {territory.level}.")
        return True, (f"✓ {territory.name} ahora es nivel {territory.level}: "
                      f"produce materiales Tier {TIER_ROMAN[territory.level]}.")

    def _process_territories(self, guild: Guild, events: List[str]):
        rebel_territories = []
        for tid in list(guild.territories):
            terr = self.territories.get(tid)
            if not terr: continue
            
            total_garrison = sum(terr.garrison.values())
            
            if total_garrison == 0:
                terr.loyalty = max(0, terr.loyalty - random.randint(2, 5))
            else:
                terr.loyalty = min(100, terr.loyalty + random.randint(2, 4))
                
            if terr.loyalty <= 0:
                rebel_territories.append(tid)
                
        for tid in rebel_territories:
            terr = self.territories.get(tid)
            if tid in guild.territories:
                guild.territories.remove(tid)
            terr.owner = "neutral"
            terr.loyalty = 100
            msg = f"🔥 ¡REBELIÓN! [{terr.name}] se ha independizado de [{guild.icon} {guild.name}] por falta de guarnición."
            events.append(msg)
            guild.log_event(msg)

    def _produce_resources(self, guild: Guild):
        """Los territorios producen MATERIALES del tier = su nivel (1..5)."""
        td       = self.guild_type_defs.get(guild.guild_type, {})
        eco_mult = guild.economy_multiplier(td)
        if "eco_logistics" in guild.unlocked_skills: eco_mult += 0.2
        if "eco_hegemony"  in guild.unlocked_skills: eco_mult += 0.5
        if "mercado"       in guild.buildings:        eco_mult += 0.15

        # RESOURCE_BONUS_PCT global (cacheado, antes se re-leía por territorio)
        bonus_pct_dict = self.get_config().get("RESOURCE_BONUS_PCT", {})

        for tid in guild.territories:
            terr = self.territories.get(tid)
            if not terr:
                continue
            local_eco_mult = eco_mult
            if terr.governor_id is not None:
                local_eco_mult += 0.20  # +20% prod con gobernador

            for rid, amt in terr.produce_materials(self.tier_materials, local_eco_mult).items():
                global_bonus = bonus_pct_dict.get(rid, 0) / 100.0
                guild.add_resource(rid, max(1, int(amt * (1 + global_bonus))), self.resource_defs)

    # ── Mini-IA ───────────────────────────────────────────────────────────────

    def _ai_decide(self, guild: Guild) -> Optional[str]:
        # --- NUEVA LÓGICA ESTRATÉGICA ---
        # Determinar prioridad actual (food = materiales-alimento)
        food_ratio = guild.get_food_total() / max(1, guild.population // 4)
        soldiers_ratio = guild.get_total_soldiers() / max(1, guild.get_max_soldiers(self.guild_type_defs))

        if food_ratio < 0.2 or guild.moral < 30:
            guild.ai_priority = "Survival"
        elif soldiers_ratio < 0.3 or guild.military_power < 30:
            guild.ai_priority = "Balanced" # Recuperar fuerzas
        elif guild.get_resource("oro") > 500 and len(guild.buildings) < 4:
            guild.ai_priority = "Economic"
        elif soldiers_ratio > 0.7 and guild.moral > 60:
            guild.ai_priority = "Expansion"
        else:
            guild.ai_priority = "Balanced"

        # Ejecutar acciones según prioridad (la construcción la maneja _ai_build_structures en el tick)
        if guild.ai_priority == "Survival":
            # Conquistar un territorio fácil para más producción de materiales
            target_terrs = [t for t in self.territories.values()
                            if t.owner != guild.guild_id and t.difficulty <= 4]
            if target_terrs and guild.get_total_soldiers() > 5:
                target = min(target_terrs, key=lambda t: t.difficulty)
                return self._attack_territory(guild, self.guilds.get(target.owner), target)

        elif guild.ai_priority == "Expansion":
            return self._resolve_ai_attack(guild)

        elif guild.ai_priority == "Economic":
            self._ai_npc_trade(guild)
            return None

        # Acciones genéricas de tick
        # 4. COALICIONES: IA forma alianzas contra imperios dominantes
        total_terrs = max(1, len(self.territories))
        for other_id, other_guild in self.guilds.items():
            if other_id == guild.guild_id: continue
            if len(other_guild.territories) / total_terrs > 0.25: # Imperios
                if guild.military_power < other_guild.military_power:
                    for third_id, third_guild in self.guilds.items():
                        if third_id in [guild.guild_id, other_id]: continue
                        if third_id not in guild.alliances and third_guild.relations.get(guild.guild_id, 0) > -10:
                            guild.alliances.append(third_id)
                            third_guild.alliances.append(guild.guild_id)
                            msg = f"🛡️ [COALICIÓN] [{guild.icon} {guild.name}] y [{third_guild.icon} {third_guild.name}] se han aliado contra la amenaza de [{other_guild.icon} {other_guild.name}]."
                            return msg  # tick lo agrega una vez

        # 5. GUERRA FORMAL
        for gid, rel in list(guild.relations.items()):
            if rel <= -15 and gid != guild.guild_id and gid in self.guilds:
                if gid not in getattr(guild, "at_war_with", []):
                    guild.at_war_with.append(gid)
                    msg = f"⚔ [GUERRA] [{guild.icon} {guild.name}] ha declarado la guerra a [{self.guilds[gid].name}]."
                    return msg  # tick lo agrega una vez

        # 9. MEJORAR SKILLS
        if guild.skill_points > 0:
            self._ai_spend_skill_point(guild)

        return None

    def evaluate_trade_proposal(self, npc_guild: Guild, player_offer: Dict[str, int], 
                                player_request: Dict[str, int], reputation: int) -> Tuple[bool, str]:
        """
        AI strategically evaluates a trade.
        Factors:
        1. Fairness (Value of items)
        2. Need (Does the NPC need the items or have too many of the requested ones?)
        3. Reputation
        """
        def calculate_value(items):
            val = 0
            for rid, amt in items.items():
                r_def = self.resource_defs.get(rid, {})
                val += r_def.get("base_value", 2) * amt
            return val

        offer_val = calculate_value(player_offer)
        request_val = calculate_value(player_request)
        
        if request_val <= 0: return True, "¡Claro! No pides nada a cambio."
        
        # Base fairness ratio
        ratio = offer_val / request_val
        
        # Reputation bonus (up to +0.3 to ratio)
        rep_bonus = max(0, reputation / 200) 
        effective_ratio = ratio + rep_bonus
        
        # Strategic check: Does NPC have enough?
        for rid, amt in player_request.items():
            if npc_guild.get_resource(rid) < amt:
                return False, f"Lo siento, no tenemos suficiente {rid}."
        
        # Thresholds
        threshold = 1.0
        if npc_guild.ai_priority == "Survival":
            # Si necesitan algo desesperadamente, aceptan tratos menos favorables
            for rid in player_offer:
                if self.resource_defs.get(rid, {}).get("skill") in FOOD_SKILLS: threshold -= 0.2
        elif npc_guild.ai_priority == "Economic":
            threshold += 0.1 # Son más exigentes con el valor
            
        if effective_ratio < threshold * 0.8:
            return False, "Ese trato es un insulto a nuestro gremio."
        elif effective_ratio < threshold:
            if random.random() > (reputation / 100): # Si tienes buena rep, aceptan más fácil
                return False, "Necesitarás ofrecer algo más valioso para convencernos."
        
        return True, "Trato hecho. Un placer hacer negocios con usted."


    def _ai_npc_trade(self, guild: Guild):
        """Intercambio de recursos entre guilds NPC."""
        if guild.trade_cooldown > 0:
            return
        for rid, res in guild.resources.items():
            cap = guild.get_resource_cap(rid, self.resource_defs, self.guild_type_defs)
            if res.amount > cap * 0.65:
                # Buscar guild que necesite este recurso
                for other in self.guilds.values():
                    if other.guild_id == guild.guild_id: continue
                    if other.get_resource(rid) < cap * 0.25:
                        # Trade: dar 20 del exceso, recibir algo que te falte
                        trade_amt = 20
                        guild.consume_resource(rid, trade_amt)
                        other.add_resource(rid, trade_amt, self.resource_defs)
                        # Buscar contrapartida
                        for r2, r2res in other.resources.items():
                            if guild.get_resource(r2) < guild.get_resource_cap(r2, self.resource_defs, self.guild_type_defs) * 0.3:
                                give_back = min(15, r2res.amount // 3)
                                if give_back > 0:
                                    other.consume_resource(r2, give_back)
                                    guild.add_resource(r2, give_back, self.resource_defs)
                                break
                        guild.relations[other.guild_id] = min(100, guild.relations.get(other.guild_id, 0) + 3)
                        other.relations[guild.guild_id] = min(100, other.relations.get(guild.guild_id, 0) + 3)
                        guild.trade_cooldown = 2
                        rname = self.resource_defs.get(rid, {}).get("name", rid)
                        msg = f"⚖ [{guild.icon} {guild.name}] comerció {trade_amt} {rname} con [{other.icon} {other.name}]."
                        self.world_events.append(msg)
                        # ¿Proponer trade al jugador?
                        self._maybe_propose_player_trade(guild)
                        return

    def _maybe_propose_player_trade(self, proposer: Guild):
        """Si hay guild jugador y la relacion es ok, proponer trade."""
        pg = self.get_player_guild()
        if not pg or proposer.trade_cooldown > 0:
            return
        if proposer.relations.get(pg.guild_id, 0) < 0:
            return
        if len(pg.pending_events) >= 3:
            return
        # Buscar recurso que el proposer tenga en exceso
        for rid, res in proposer.resources.items():
            cap = proposer.get_resource_cap(rid, self.resource_defs, self.guild_type_defs)
            if res.amount > cap * 0.60:
                # Buscar recurso que el jugador tenga
                for r2 in pg.resources:
                    if pg.get_resource(r2) > 15 and r2 != rid:
                        offer_amt = min(25, res.amount // 4)
                        req_amt   = max(5, offer_amt // 2)
                        rname1 = self.resource_defs.get(rid, {}).get("name", rid)
                        rname2 = self.resource_defs.get(r2, {}).get("name", r2)
                        ev = {
                            "event_id":    "trade_proposal",
                            "title":       "Propuesta Comercial",
                            "description": f"{proposer.icon} {proposer.name} ofrece {offer_amt} {rname1} a cambio de {req_amt} {rname2}.",
                            "source_guild_id": proposer.guild_id,
                            "options": [
                                {"text": f"Aceptar (recibir {offer_amt} {rname1})",
                                 "effects": {"trade_accept": True, "offer_rid": rid, "offer_amt": offer_amt,
                                             "req_rid": r2, "req_amt": req_amt, "src_id": proposer.guild_id}},
                                {"text": "Rechazar", "effects": {"rel_src": -3, "src_id": proposer.guild_id}},
                            ],
                        }
                        pg.pending_events.append(ev)
                        proposer.trade_cooldown = 3
                        return

    def _ai_spend_skill_point(self, guild: Guild):
        try:
            from Modules.ModulesFunctions.GuildSkillTree import BRANCH_ORDER, can_unlock, unlock_skill
            prefs = self.guild_type_defs.get(guild.guild_type, {}).get(
                "skill_branch_pref", ["Militar", "Economía", "Diplomacia"])
            for branch in prefs:
                for skill_id in BRANCH_ORDER.get(branch, []):
                    ok, _ = can_unlock(skill_id, guild)
                    if ok:
                        unlock_skill(skill_id, guild)
                        return
        except Exception:
            pass

    # ── Combate V2 (con soldados y ratings) ──────────────────────────────────

    def _calculate_troop_power(self, troops: Dict[str, int], enemy_troops: Dict[str, int]) -> float:
        power = 0.0
        if not troops: return power
        inf = troops.get("infantry", 0)
        arc = troops.get("archers", 0)
        cav = troops.get("cavalry", 0)
        e_inf = enemy_troops.get("infantry", 0) if enemy_troops else 0
        e_arc = enemy_troops.get("archers", 0) if enemy_troops else 0
        e_cav = enemy_troops.get("cavalry", 0) if enemy_troops else 0
        
        power += inf * 0.5 + arc * 0.6 + cav * 0.8
        # Counters
        if inf > 0 and e_cav > 0: power += min(inf, e_cav) * 0.3
        if arc > 0 and e_inf > 0: power += min(arc, e_inf) * 0.3
        if cav > 0 and e_arc > 0: power += min(cav, e_arc) * 0.3
        return power

    def _attack_territory(self, attacker: Guild, defender: Optional[Guild],
                          territory: Territory) -> str:
        td_att  = self.guild_type_defs.get(attacker.guild_type, {})
        mil_mul = attacker.military_multiplier(td_att)
        if "mil_tactics"      in attacker.unlocked_skills: mil_mul += 0.10
        if "mil_professional" in attacker.unlocked_skills: mil_mul += 0.40

        moral_bonus = attacker.moral / 200  # 0.0–0.5
        
        def_troops = defender.soldiers if defender else territory.garrison
        att_troop_power = self._calculate_troop_power(attacker.soldiers, def_troops)
        
        # Asedio ignora/destruye parte de la defensa del territorio
        siege_power = attacker.soldiers.get("siege", 0) * 2.0
        
        att_score = (attacker.military_power * mil_mul * (1 + moral_bonus)
                     + att_troop_power
                     + attacker.attack_rating * 8
                     + siege_power
                     + random.randint(0, 25))

        base_defense = max(0, territory.defense_value - siege_power)
        if territory.governor_id is not None:
            base_defense += 25  # Bonus del gobernador
            
        def_score = base_defense + random.randint(0, 20)
        # Torre de Guardia bonus
        if "torre_guardia" in (attacker.buildings if attacker else []):
            def_score += 30
        if defender:
            td_def   = self.guild_type_defs.get(defender.guild_type, {})
            def_mul  = defender.military_multiplier(td_def)
            def_moral = defender.moral / 200
            def_troop_power = self._calculate_troop_power(defender.soldiers, attacker.soldiers)
            def_score += (defender.military_power * def_mul * (1 + def_moral)
                          + def_troop_power
                          + defender.defense_rating * 8
                          + defender.armor_rating * 5)
            # Alianza: bonus defensivo
            for ally_id in defender.alliances:
                ally = self.guilds.get(ally_id)
                if ally:
                    def_score += ally.military_power * 0.15

        # Bajas
        if att_score > def_score:
            att_losses = max(0, int(attacker.get_total_soldiers() * 0.08 * (def_score / max(1, att_score))))
            def_losses = max(0, int((defender.get_total_soldiers() * 0.12) if defender else 0))
        else:
            att_losses = max(1, int(attacker.get_total_soldiers() * 0.15))
            def_losses = max(0, int((defender.get_total_soldiers() * 0.05) if defender else 0))

        attacker.lose_soldiers(att_losses)
        attacker.population = max(10, attacker.population - att_losses)
        if defender:
            defender.lose_soldiers(def_losses)
            defender.population = max(10, defender.population - def_losses)

        if att_score > def_score:
            if defender and territory.id in defender.territories:
                defender.territories.remove(territory.id)
                defender.change_moral(-12)
                attacker.relations[defender.guild_id] = max(-100, attacker.relations.get(defender.guild_id, 0) - 15)
                msg = (f"⚔ [{attacker.icon} {attacker.name}] conquistó "
                       f"[{territory.icon} {territory.name}] de [{defender.icon} {defender.name}]"
                       f" (bajas: {att_losses} vs {def_losses})")
            else:
                msg = (f"⚔ [{attacker.icon} {attacker.name}] tomó "
                       f"[{territory.icon} {territory.name}] neutral (bajas: {att_losses})")
            territory.owner = attacker.guild_id
            if territory.id not in attacker.territories:
                attacker.territories.append(territory.id)
            attacker.change_moral(8)
            attacker.influence += 10
            attacker.skill_points += 1
        else:
            attacker.change_moral(-10)
            if defender:
                defender.change_moral(5)
                msg = (f"🛡 [{defender.icon} {defender.name}] repelió a "
                       f"[{attacker.icon} {attacker.name}] en [{territory.icon} {territory.name}]"
                       f" (bajas: {att_losses} vs {def_losses})")
            else:
                msg = (f"💨 [{attacker.icon} {attacker.name}] falló en "
                       f"[{territory.icon} {territory.name}] (bajas: {att_losses})")
        return msg

    def _resolve_ai_attack(self, attacker: Guild) -> Optional[str]:
        neutral = [tid for tid, t in self.territories.items() if t.owner == "neutral"]
        if neutral:
            terr = self.territories[random.choice(neutral)]
            return self._attack_territory(attacker, None, terr)
        enemies = [gid for gid, g in self.guilds.items()
                   if gid != attacker.guild_id and g.territories
                   and gid in getattr(attacker, "at_war_with", [])]
        if not enemies:
            return None
        def_id  = min(enemies, key=lambda gid: self.guilds[gid].military_power)
        defender = self.guilds[def_id]
        tid     = random.choice(defender.territories)
        terr    = self.territories.get(tid)
        return self._attack_territory(attacker, defender, terr) if terr else None

    def _generate_random_event(self, guild: Guild) -> Optional[dict]:
        pool = [e for e in GUILD_EVENTS_POOL if e["event_id"] != "trade_proposal"]
        ev_template = random.choice(pool)
        npc_guilds  = [g for g in self.guilds.values() if not g.is_player_guild]
        source_guild = random.choice(npc_guilds) if npc_guilds else None

        # Filtros de coherencia
        if ev_template["event_id"] == "revolt" and guild.moral > 40:
            return None
        if ev_template["event_id"] == "allied_request_help":
            allied = [gid for gid in guild.alliances if gid in self.guilds]
            if not allied:
                return None
            source_guild = self.guilds[random.choice(allied)]
        if ev_template["event_id"] == "spy_captured" and not source_guild:
            return None

        desc = ev_template["desc_tmpl"].format(
            guild=f"{source_guild.icon} {source_guild.name}" if source_guild else "desconocido"
        )
        return {
            "event_id":       ev_template["event_id"],
            "title":          ev_template["title"],
            "description":    desc,
            "options":        [dict(o) for o in ev_template["options"]],
            "source_guild_id": source_guild.guild_id if source_guild else "",
        }

    # ── Interfaz del jugador ──────────────────────────────────────────────────

    def get_player_guild(self) -> Optional[Guild]:
        return self.guilds.get(self.player_guild_id) if self.player_guild_id else None

    def create_player_guild(self, name: str, guild_type: str, player) -> Guild:
        td = self.guild_type_defs.get(guild_type, {})
        g  = Guild("player_guild", name, guild_type, td.get("icon","🏠"),
                   30, 50, 80, 30, is_player_guild=True)
        # Stock inicial: solo materiales tier I (abundante) y tier II (poco).
        # El resto se consigue produciendo (territorios) o recolectando a mano.
        for rid in self.tier_materials.get(1, []):
            g.add_resource(rid, 25, self.resource_defs)
        for rid in self.tier_materials.get(2, []):
            g.add_resource(rid, 10, self.resource_defs)
        g.add_resource("oro", 100, self.resource_defs)
        g.soldiers = {"infantry": int(g.population * 0.10), "archers": 0, "cavalry": 0, "siege": 0}
        for gid in self.guilds:
            g.relations[gid] = 0
            self.guilds[gid].relations["player_guild"] = 0
        self.guilds["player_guild"] = g
        self.player_guild_id = "player_guild"
        player.guild_id = "player_guild"
        g.log_event(f"✨ La guild '{name}' fue fundada.")
        return g

    def join_guild(self, guild_id: str, player) -> bool:
        if guild_id not in self.guilds:
            return False
        player.guild_id      = guild_id
        self.player_guild_id = guild_id
        g = self.guilds[guild_id]
        g.influence += 5
        g.log_event("➕ Un nuevo miembro se unió.")
        return True

    def get_player_reputation(self, player, guild_id: str) -> int:
        return getattr(player, "guild_reputation", {}).get(guild_id, 0)

    def change_player_reputation(self, player, guild_id: str, delta: int) -> int:
        if not hasattr(player, "guild_reputation"):
            player.guild_reputation = {}
        new_val = max(-100, min(100, player.guild_reputation.get(guild_id, 0) + delta))
        player.guild_reputation[guild_id] = new_val
        return new_val

    def get_reputation_rank(self, reputation: int) -> Tuple[str, str]:
        if reputation <= -50: return ("Enemigo",   "bold red")
        elif reputation < 0:  return ("Hostil",    "red")
        elif reputation < 50: return ("Neutral",   "dim white")
        elif reputation < 80: return ("Aliado",    "bold green")
        else:                 return ("Hermandad", "bold bright_cyan")

    def get_sorted_guilds_by_power(self) -> List[Guild]:
        return sorted(self.guilds.values(), key=lambda g: g.military_power, reverse=True)

    def get_territory_map_rows(self) -> List[str]:
        rows = []
        idx: Dict[Tuple[int,int], Territory] = {}
        max_row = 0
        max_col = 0
        for t in self.territories.values():
            col, row = int(t.position[0]), int(t.position[1])
            idx[(col, row)] = t
            max_col = max(max_col, col)
            max_row = max(max_row, row)
        
        for row in range(max_row + 1):
            cells = []
            for col in range(max_col + 1):
                t = idx.get((col, row))
                if t:
                    if t.owner == "neutral":          sym = "·"
                    elif t.owner == self.player_guild_id: sym = "★"
                    else:
                        og = self.guilds.get(t.owner)
                        sym = og.icon if og else "?"
                    cells.append(f"[{t.icon}{sym}]")
                else:
                    cells.append("     ")
            rows.append("  ".join(cells))
        return rows

    # ── Persistencia ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "guilds":          {gid: g.to_dict() for gid, g in self.guilds.items()},
            "territories":     {tid: t.to_dict() for tid, t in self.territories.items()},
            "world_events":    list(self.world_events),
            "player_guild_id": self.player_guild_id,
            "world_tension":   self.world_tension,
        }

    def load_from_dict(self, data: dict) -> None:
        for gid, gdata in data.get("guilds", {}).items():
            self.guilds[gid] = Guild.from_dict(gdata, self.resource_defs)
        for tid, tdata in data.get("territories", {}).items():
            if tid in self.territories:
                terr = self.territories[tid]
                terr.owner       = tdata.get("owner", "neutral")
                terr.garrison    = tdata.get("garrison", terr.garrison)
                terr.loyalty     = tdata.get("loyalty", terr.loyalty)
                terr.governor_id = tdata.get("governor_id", terr.governor_id)
                terr.level       = tdata.get("level", terr.level)
        self.world_events    = data.get("world_events", [])
        self.player_guild_id = data.get("player_guild_id")
        self.world_tension   = data.get("world_tension", 0.0)


# ── Singleton ─────────────────────────────────────────────────────────────────

_guild_manager_instance: Optional[GuildManager] = None

def get_guild_manager() -> GuildManager:
    global _guild_manager_instance
    if _guild_manager_instance is None:
        _guild_manager_instance = GuildManager()
    return _guild_manager_instance

def reset_guild_manager() -> GuildManager:
    global _guild_manager_instance
    _guild_manager_instance = GuildManager()
    return _guild_manager_instance
