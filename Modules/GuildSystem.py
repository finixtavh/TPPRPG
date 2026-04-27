"""
GuildSystem.py V2
=================
Motor del sistema de Guilds con economia viva, ejercitos, IA y eventos.
"""

import os, json, random
from typing import Dict, List, Optional, Tuple

_GUILD_RESOURCES_JSON = os.path.join("Data", "GuildResources.json")
_GUILDS_JSON          = os.path.join("Data", "Guilds.json")
_ZONE_GUILDS_JSON     = os.path.join("Data", "ZoneGuilds.json")

SIMULATION_INTERVAL = 5
RARITY_BASE_CAPS = {"Common": 250, "Uncommon": 100, "Rare": 50, "Legendary": 25}

# ── Pool de eventos para el jugador ──────────────────────────────────────────

GUILD_EVENTS_POOL = [
    {
        "event_id":   "allied_request_help",
        "title":      "Petición de Aliado",
        "desc_tmpl":  "{guild} necesita refuerzos ante un ataque inminente. ¿Envías ayuda?",
        "options": [
            {"text": "Enviar 10 soldados",       "effects": {"soldiers": -10, "rel_src": +15, "moral": +5}},
            {"text": "Enviar 30 Comida",          "effects": {"comida": -30,  "rel_src": +8}},
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
            {"text": "Dejar pasar (recibir 20 Comida)", "effects": {"comida": +20}},
            {"text": "Cobrar peaje (obtener 15 Cuero)", "effects": {"cuero_endurecido": +15}},
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
            {"text": "Pedir rescate (50 Cuero)",  "effects": {"cuero_endurecido": +50, "rel_src": -5}},
        ],
    },
    {
        "event_id":   "plague",
        "title":      "Plaga en las Tierras",
        "desc_tmpl":  "Una enfermedad se extiende por tus territorios.",
        "options": [
            {"text": "Gastar 40 Comida (detener plaga)",  "effects": {"comida": -40}},
            {"text": "Cuarentena (-20 pop)",               "effects": {"population": -20, "moral": -5}},
            {"text": "Ignorar (-5% pop, -10 moral)",       "effects": {"population_pct": -0.05, "moral": -10}},
        ],
    },
    {
        "event_id":   "revolt",
        "title":      "Revuelta Interna",
        "desc_tmpl":  "La moral baja ha causado una revuelta en tus filas.",
        "options": [
            {"text": "Sofocar con recursos (30C+20M)",  "effects": {"comida": -30, "madera": -20, "moral": +15}},
            {"text": "Negociar (-15 soldados, +moral)", "effects": {"soldiers": -15, "moral": +12}},
            {"text": "Dejar que se calme (-12 moral)",  "effects": {"moral": -12}},
        ],
    },
    {
        "event_id":   "discovered_deposit",
        "title":      "Depósito Descubierto",
        "desc_tmpl":  "Exploradores encuentran un depósito oculto.",
        "options": [
            {"text": "Explotar (50 Xar)",              "effects": {"lingote_xar": +50}},
            {"text": "Gradual (30 Xar + 20 Piedra)",   "effects": {"lingote_xar": +30, "piedra": +20}},
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

    def to_dict(self):
        return {"id": self.id, "owner": self.owner}

    def produce(self, bonus_multiplier=1.0):
        return {rid: max(1, int(amt * bonus_multiplier))
                for rid, amt in self.resource_output.items()}


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

        # Recursos
        self.resources: Dict[str, GuildResource] = {}
        # Territorios
        self.territories: List[str] = []
        # Relaciones { guild_id -> -100..100 }
        self.relations:   Dict[str, int] = {}
        self.alliances:   List[str] = []
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

        # ── V2: Ejército ─────────────────────────────────────────────
        self.soldiers:       int = 0
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
        r = self.resources.get(resource_id)
        if r and r.amount >= amount:
            r.amount -= amount
            return True
        if r:
            r.amount = 0
        return False

    def get_resource_cap(self, resource_id: str, resource_defs: dict,
                          guild_type_defs: dict) -> int:
        defn   = resource_defs.get(resource_id, {})
        rarity = defn.get("rarity", "Common")
        cap    = defn.get("rarity_cap", RARITY_BASE_CAPS.get(rarity, 250))
        # Guild type bonus
        type_data    = guild_type_defs.get(self.guild_type, {})
        storage_bonus = type_data.get("storage_bonus", {})
        cap += storage_bonus.get(rarity, 0)
        # Building bonus
        if "almacen" in self.buildings:
            if rarity == "Common":   cap += 150
            elif rarity == "Uncommon": cap += 75
        # Skill tree bonus
        if "eco_storage" in self.unlocked_skills:
            if rarity == "Common":   cap += 100
            elif rarity == "Uncommon": cap += 50
        return cap

    def clamp_resources(self, resource_defs: dict, guild_type_defs: dict) -> None:
        """Clamp all resources to their caps after production."""
        for rid, res in self.resources.items():
            cap = self.get_resource_cap(rid, resource_defs, guild_type_defs)
            if res.amount > cap:
                res.amount = cap

    # ── Ejército ──────────────────────────────────────────────────────────────

    def get_max_soldiers(self, guild_type_defs: dict) -> int:
        type_data = guild_type_defs.get(self.guild_type, {})
        pct = 0.10 + type_data.get("recruit_pct_bonus", 0.0)
        if "mil_vanguard"   in self.unlocked_skills: pct += 0.05
        if "mil_logistics"  in self.unlocked_skills: pct += 0.05
        return max(1, int(self.population * pct))

    def recruit_soldiers(self, count: int, resource_defs: dict,
                         guild_type_defs: dict) -> Tuple[int, str]:
        slots = max(0, self.get_max_soldiers(guild_type_defs) - self.soldiers)
        n     = min(count, slots)
        if n <= 0:
            return 0, "Ya tienes el máximo de soldados."
        food_cost   = n
        leather_cost = max(1, n // 2)
        if self.get_resource("comida") < food_cost:
            return 0, f"Necesitas {food_cost} Comida para reclutar."
        if self.get_resource("cuero_endurecido") < leather_cost:
            return 0, f"Necesitas {leather_cost} Cuero Endurecido para reclutar."
        self.consume_resource("comida", food_cost)
        self.consume_resource("cuero_endurecido", leather_cost)
        self.soldiers += n
        return n, f"✓ Reclutaste {n} soldados."

    def upgrade_army_stat(self, stat: str, resource_defs: dict) -> Tuple[bool, str]:
        """stat: 'attack' | 'defense' | 'armor'. Costs Cuero Endurecido."""
        costs = {"attack": 5, "defense": 5, "armor": 8}
        attr  = {"attack": "attack_rating", "defense": "defense_rating", "armor": "armor_rating"}
        if stat not in costs:
            return False, "Stat inválida."
        current = getattr(self, attr[stat], 1)
        if current >= 10:
            return False, "Ya está al máximo (nivel 10)."
        cost = costs[stat] * current   # coste escala con el nivel
        if self.get_resource("cuero_endurecido") < cost:
            return False, f"Necesitas {cost} Cuero Endurecido."
        self.consume_resource("cuero_endurecido", cost)
        setattr(self, attr[stat], current + 1)
        return True, f"✓ {stat.capitalize()} subió a nivel {current + 1}."

    # ── Población ─────────────────────────────────────────────────────────────

    def grow_population(self, resource_defs: dict) -> str:
        food_needed = max(1, self.population // 8)
        food_have   = self.get_resource("comida")
        if food_have >= food_needed:
            growth = max(1, int(self.population * self.population_growth_pct))
            # Bonus de edificio granja
            if "granja" in self.buildings:
                growth = int(growth * 1.5)
            self.population += growth
            self.consume_resource("comida", food_needed)
            return f"Población +{growth}."
        else:
            ratio    = food_have / food_needed if food_needed > 0 else 0
            pop_loss = max(1, int(self.population * 0.02 * (1 - ratio)))
            self.population = max(10, self.population - pop_loss)
            sol_loss = min(self.soldiers, pop_loss // 3)
            self.soldiers   = max(0, self.soldiers - sol_loss)
            self.change_moral(-3)
            self.log_event(f"🍞 Hambruna: -{pop_loss} población.")
            return f"Hambruna: -{pop_loss} pop."

    # ── Moral / Utilidad ──────────────────────────────────────────────────────

    def change_moral(self, delta: int) -> None:
        self.moral = max(0, min(100, self.moral + delta))

    def consume_food(self) -> bool:
        """Legacy: llamado en tick solo para guilds NPC."""
        food_needed = max(1, self.population // 8)
        if self.get_resource("comida") >= food_needed:
            self.consume_resource("comida", food_needed)
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
        g.influence              = data.get("influence", 0)
        g.skill_points           = data.get("skill_points", 0)
        g.unlocked_skills        = data.get("unlocked_skills", [])
        g.event_log              = data.get("event_log", [])
        g.buildings              = data.get("buildings", [])
        g.pending_events         = data.get("pending_events", [])
        g.soldiers               = data.get("soldiers", 0)
        g.attack_rating          = data.get("attack_rating", 1)
        g.defense_rating         = data.get("defense_rating", 1)
        g.armor_rating           = data.get("armor_rating", 1)
        g.population_growth_pct  = data.get("population_growth_pct", 0.03)
        g.trade_cooldown         = data.get("trade_cooldown", 0)
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
        self._load_definitions()

    def _load_definitions(self):
        for path, attr, key in [
            (_GUILD_RESOURCES_JSON, "resource_defs",   "resources"),
            (_ZONE_GUILDS_JSON,     None,               "territories"),
            (_GUILDS_JSON,          None,               None),
        ]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if attr:
                    setattr(self, attr, data.get(key, {}))
                elif key == "territories":
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
            count = random.randint(20, 35)
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
            g.soldiers = int(g.population * 0.10)
            self.guilds[g.guild_id] = g

        guild_ids = list(self.guilds.keys())
        for gid, guild in self.guilds.items():
            for other in guild_ids:
                if other != gid:
                    guild.relations[other] = random.randint(-30, 30)

    # ── Tick de simulación ────────────────────────────────────────────────────

    def tick(self) -> List[str]:
        events = []
        for guild in self.guilds.values():
            self._produce_resources(guild)
            guild.clamp_resources(self.resource_defs, self.guild_type_defs)
            guild.grow_population(self.resource_defs)
            if guild.trade_cooldown > 0:
                guild.trade_cooldown -= 1
            # Academia: ganar 1 skill_point cada 3 ticks (simplified: random 1/3)
            if "academia" in guild.buildings and random.random() < 0.33:
                guild.skill_points += 1

        for guild in self.guilds.values():
            ev = self._ai_decide(guild)
            if ev:
                events.append(ev)
                guild.log_event(ev)

        # Eventos aleatorios para el jugador (1% de chance por tick)
        pg = self.get_player_guild()
        if pg and random.random() < 0.35 and len(pg.pending_events) < 3:
            ev = self._generate_random_event(pg)
            if ev:
                pg.pending_events.append(ev)

        self.world_events.extend(events)
        if len(self.world_events) > 60:
            self.world_events = self.world_events[-60:]
        return events

    def _produce_resources(self, guild: Guild):
        td       = self.guild_type_defs.get(guild.guild_type, {})
        eco_mult = guild.economy_multiplier(td)
        if "eco_logistics" in guild.unlocked_skills: eco_mult += 0.2
        if "eco_hegemony"  in guild.unlocked_skills: eco_mult += 0.5
        if "mercado"       in guild.buildings:        eco_mult += 0.15
        for tid in guild.territories:
            terr = self.territories.get(tid)
            if not terr: continue
            for rid, amt in terr.produce(eco_mult).items():
                bonus = td.get("bonus_resources", {}).get(rid, 0.0)
                guild.add_resource(rid, max(1, int(amt * (1 + bonus))), self.resource_defs)
        # Ganado produce comida
        ganado = guild.get_resource("ganado")
        if ganado > 0:
            guild.add_resource("comida", ganado * 3, self.resource_defs)

    # ── Mini-IA ───────────────────────────────────────────────────────────────

    def _ai_decide(self, guild: Guild) -> Optional[str]:
        # 1. SOBREVIVIR: comida crítica
        food_needed = max(1, guild.population // 8)
        if guild.get_resource("comida") < food_needed * 0.3:
            food_terrs = [t for t in self.territories.values()
                          if ("comida" in t.resource_output or "ganado" in t.resource_output)
                          and t.owner != guild.guild_id and t.difficulty <= 3]
            if food_terrs and guild.soldiers > 3:
                target = min(food_terrs, key=lambda t: t.difficulty)
                return self._attack_territory(guild,
                    self.guilds.get(target.owner) if target.owner not in ("neutral","") else None,
                    target)

        # 2. EXPANDIR: buen poder y moral
        if guild.moral >= 55 and guild.military_power >= 35 and guild.soldiers > 0:
            if random.randint(0, 100) < guild.aggressiveness:
                return self._resolve_ai_attack(guild)

        # 3. FORTALECER: moral baja o pocos soldados
        if guild.moral < 35 or guild.soldiers < guild.get_max_soldiers(self.guild_type_defs) // 4:
            guild.recruit_soldiers(min(5, 20), self.resource_defs, self.guild_type_defs)
            return None

        # 4. DIPLOMACIA: proponer alianza si relación alta
        if "dip_alliances" in guild.unlocked_skills:
            for gid, rel in guild.relations.items():
                if rel > 45 and gid not in guild.alliances and gid in self.guilds:
                    other = self.guilds[gid]
                    guild.alliances.append(gid)
                    if guild.guild_id not in other.alliances:
                        other.alliances.append(guild.guild_id)
                    msg = f"🤝 [{guild.icon} {guild.name}] y [{other.icon} {other.name}] formaron alianza."
                    self.world_events.append(msg)
                    return msg

        # 5. TRADE entre NPCs: proponer intercambio si exceso
        self._ai_npc_trade(guild)

        # 6. MEJORAR: gastar skill_points según preferencias del tipo
        if guild.skill_points > 0:
            self._ai_spend_skill_point(guild)

        return None

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
                            "desc_tmpl":   f"{proposer.icon} {proposer.name} ofrece {offer_amt} {rname1} a cambio de {req_amt} {rname2}.",
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
            from Modules.GuildSkillTree import BRANCH_ORDER, can_unlock, unlock_skill
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

    def _attack_territory(self, attacker: Guild, defender: Optional[Guild],
                          territory: Territory) -> str:
        td_att  = self.guild_type_defs.get(attacker.guild_type, {})
        mil_mul = attacker.military_multiplier(td_att)
        if "mil_tactics"      in attacker.unlocked_skills: mil_mul += 0.10
        if "mil_professional" in attacker.unlocked_skills: mil_mul += 0.40

        moral_bonus = attacker.moral / 200  # 0.0–0.5
        att_score = (attacker.military_power * mil_mul * (1 + moral_bonus)
                     + attacker.soldiers * 0.5
                     + attacker.attack_rating * 8
                     + random.randint(0, 25))

        def_score = territory.defense_value + random.randint(0, 20)
        # Torre de Guardia bonus
        if "torre_guardia" in (attacker.buildings if attacker else []):
            def_score += 30
        if defender:
            td_def   = self.guild_type_defs.get(defender.guild_type, {})
            def_mul  = defender.military_multiplier(td_def)
            def_moral = defender.moral / 200
            def_score += (defender.military_power * def_mul * (1 + def_moral)
                          + defender.soldiers * 0.3
                          + defender.defense_rating * 8
                          + defender.armor_rating * 5)
            # Alianza: bonus defensivo
            for ally_id in defender.alliances:
                ally = self.guilds.get(ally_id)
                if ally:
                    def_score += ally.military_power * 0.15

        # Bajas
        if att_score > def_score:
            att_losses = max(0, int(attacker.soldiers * 0.08 * (def_score / max(1, att_score))))
            def_losses = max(0, int((defender.soldiers * 0.12) if defender else 0))
        else:
            att_losses = max(1, int(attacker.soldiers * 0.15))
            def_losses = max(0, int((defender.soldiers * 0.05) if defender else 0))

        attacker.soldiers   = max(0, attacker.soldiers   - att_losses)
        attacker.population = max(10, attacker.population - att_losses)
        if defender:
            defender.soldiers   = max(0, defender.soldiers   - def_losses)
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
                   and attacker.relations.get(gid, 0) < 20]
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
        for rid in self.resource_defs:
            g.add_resource(rid, 20, self.resource_defs)
        g.soldiers = int(g.population * 0.10)
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
        }

    def load_from_dict(self, data: dict) -> None:
        for gid, gdata in data.get("guilds", {}).items():
            self.guilds[gid] = Guild.from_dict(gdata, self.resource_defs)
        for tid, tdata in data.get("territories", {}).items():
            if tid in self.territories:
                self.territories[tid].owner = tdata.get("owner", "neutral")
        self.world_events    = data.get("world_events", [])
        self.player_guild_id = data.get("player_guild_id")


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
