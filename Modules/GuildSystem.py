"""
GuildSystem.py
==============
Motor principal del sistema de Guilds.

Clases:
  GuildResource  — instancia de recurso con cantidad actual
  Territory      — territorio con dueño, producción, defensa
  Guild          — guild con stats, recursos, moral, relaciones
  GuildManager   — singleton: gestiona todas las guilds y la simulación

Simulación:
  Se activa cada N combates del jugador (por defecto 5).
  Las guilds producen recursos, consumen comida, y toman decisiones de guerra.
"""

import os
import json
import random
from typing import Dict, List, Optional, Tuple

_GUILD_RESOURCES_JSON = os.path.join("Data", "GuildResources.json")
_GUILDS_JSON          = os.path.join("Data", "Guilds.json")
_ZONE_GUILDS_JSON     = os.path.join("Data", "ZoneGuilds.json")

SIMULATION_INTERVAL   = 5   # Cada cuántos combates se ejecuta un tick

# ── Recurso de Guild ──────────────────────────────────────────────────────────

class GuildResource:
    def __init__(self, resource_id: str, name: str, icon: str, rarity: str, amount: int = 0):
        self.resource_id = resource_id
        self.name        = name
        self.icon        = icon
        self.rarity      = rarity
        self.amount      = amount

    def to_dict(self) -> dict:
        return {"resource_id": self.resource_id, "amount": self.amount}

    @staticmethod
    def from_dict(data: dict, definitions: dict) -> "GuildResource":
        rid  = data["resource_id"]
        defn = definitions.get(rid, {})
        return GuildResource(
            resource_id=rid,
            name=defn.get("name", rid),
            icon=defn.get("icon", "?"),
            rarity=defn.get("rarity", "Common"),
            amount=data.get("amount", 0),
        )


# ── Territorio ────────────────────────────────────────────────────────────────

class Territory:
    def __init__(self, data: dict):
        self.id                  = data["id"]
        self.name                = data["name"]
        self.icon                = data.get("icon", "🗺")
        self.description         = data.get("description", "")
        self.resource_output     = data.get("resource_output", {})
        self.difficulty          = data.get("difficulty", 1)
        self.defense_value       = data.get("defense_value", 10)
        self.population_capacity = data.get("population_capacity", 50)
        self.owner               = data.get("owner", "neutral")   # guild_id o "neutral"
        self.position            = tuple(data.get("position", [0, 0]))

    def to_dict(self) -> dict:
        return {
            "id":    self.id,
            "owner": self.owner,
        }

    def produce(self, bonus_multiplier: float = 1.0) -> Dict[str, int]:
        """Devuelve un dict de {resource_id: amount} producido este tick."""
        output = {}
        for res_id, base_amount in self.resource_output.items():
            amount = max(1, int(base_amount * bonus_multiplier))
            output[res_id] = amount
        return output


# ── Guild ─────────────────────────────────────────────────────────────────────

class Guild:
    def __init__(
        self,
        guild_id:        str,
        name:            str,
        guild_type:      str,
        icon:            str,
        military_power:  int  = 50,
        population:      int  = 100,
        moral:           int  = 75,
        aggressiveness:  int  = 50,
        is_player_guild: bool = False,
    ):
        self.guild_id        = guild_id
        self.name            = name
        self.guild_type      = guild_type
        self.icon            = icon
        self.military_power  = military_power
        self.population      = population
        self.moral           = moral           # 0–100
        self.aggressiveness  = aggressiveness  # 0–100 (cuánto le gusta atacar)
        self.is_player_guild = is_player_guild

        # Recursos: dict { resource_id -> GuildResource }
        self.resources: Dict[str, GuildResource] = {}

        # Territorios controlados: list de territory_id
        self.territories: List[str] = []

        # Relaciones con otras guilds: { guild_id -> -100..100 }
        self.relations: Dict[str, int] = {}

        # Alianzas activas
        self.alliances: List[str] = []

        # Influencia global
        self.influence: int = 0

        # Skill points disponibles
        self.skill_points: int = 0

        # Nodos desbloqueados del árbol de habilidades
        self.unlocked_skills: List[str] = []

        # Historial de eventos
        self.event_log: List[str] = []

    # ── Recursos ────────────────────────────────────────────────────────────

    def get_resource(self, resource_id: str) -> int:
        r = self.resources.get(resource_id)
        return r.amount if r else 0

    def add_resource(self, resource_id: str, amount: int, definitions: dict) -> None:
        if resource_id not in self.resources:
            defn = definitions.get(resource_id, {})
            self.resources[resource_id] = GuildResource(
                resource_id=resource_id,
                name=defn.get("name", resource_id),
                icon=defn.get("icon", "?"),
                rarity=defn.get("rarity", "Common"),
                amount=0,
            )
        self.resources[resource_id].amount += amount

    def consume_resource(self, resource_id: str, amount: int) -> bool:
        r = self.resources.get(resource_id)
        if r and r.amount >= amount:
            r.amount -= amount
            return True
        if r:
            r.amount = 0
        return False

    # ── Moral / Población ────────────────────────────────────────────────────

    def change_moral(self, delta: int) -> None:
        self.moral = max(0, min(100, self.moral + delta))

    def consume_food(self) -> bool:
        """Consume comida proporcional a la población. Devuelve True si hubo suficiente."""
        food_needed = max(1, self.population // 10)
        if self.get_resource("comida") >= food_needed:
            self.consume_resource("comida", food_needed)
            return True
        else:
            # Sin comida → bajar moral
            self.change_moral(-8)
            self.log_event("⚠ Sin comida. Moral cayendo.")
            return False

    # ── Registro de eventos ──────────────────────────────────────────────────

    def log_event(self, message: str) -> None:
        self.event_log.append(message)
        if len(self.event_log) > 20:
            self.event_log.pop(0)

    # ── Bonus de tipo ────────────────────────────────────────────────────────

    def military_multiplier(self, type_data: dict) -> float:
        return 1.0 + type_data.get("military_bonus", 0.0) + type_data.get("military_penalty", 0.0)

    def economy_multiplier(self, type_data: dict) -> float:
        return 1.0 + type_data.get("economy_bonus", 0.0)

    # ── Serialización ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "guild_id":        self.guild_id,
            "name":            self.name,
            "guild_type":      self.guild_type,
            "icon":            self.icon,
            "military_power":  self.military_power,
            "population":      self.population,
            "moral":           self.moral,
            "aggressiveness":  self.aggressiveness,
            "is_player_guild": self.is_player_guild,
            "resources":       {rid: r.to_dict() for rid, r in self.resources.items()},
            "territories":     list(self.territories),
            "relations":       dict(self.relations),
            "alliances":       list(self.alliances),
            "influence":       self.influence,
            "skill_points":    self.skill_points,
            "unlocked_skills": list(self.unlocked_skills),
            "event_log":       list(self.event_log),
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
            gr = GuildResource.from_dict(rdata, resource_defs)
            g.resources[rid] = gr
        g.territories    = data.get("territories", [])
        g.relations      = data.get("relations", {})
        g.alliances      = data.get("alliances", [])
        g.influence      = data.get("influence", 0)
        g.skill_points   = data.get("skill_points", 0)
        g.unlocked_skills = data.get("unlocked_skills", [])
        g.event_log      = data.get("event_log", [])
        return g


# ── GuildManager ──────────────────────────────────────────────────────────────

class GuildManager:
    """Singleton que gestiona todas las guilds y corre la simulación."""

    def __init__(self):
        self.guilds:           Dict[str, Guild]     = {}
        self.territories:      Dict[str, Territory] = {}
        self.resource_defs:    Dict[str, dict]      = {}
        self.guild_type_defs:  Dict[str, dict]      = {}
        self.guild_name_data:  dict                 = {}
        self.world_events:     List[str]            = []  # Eventos globales pendientes
        self.player_guild_id:  Optional[str]        = None

        self._load_definitions()

    def _load_definitions(self):
        # Recursos
        try:
            with open(_GUILD_RESOURCES_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.resource_defs = data.get("resources", {})
        except Exception as e:
            print(f"[GuildSystem] Error cargando recursos: {e}")

        # Territorios
        try:
            with open(_ZONE_GUILDS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            for tid, tdata in data.get("territories", {}).items():
                self.territories[tid] = Territory(tdata)
        except Exception as e:
            print(f"[GuildSystem] Error cargando territorios: {e}")

        # Nombres y tipos de guild
        try:
            with open(_GUILDS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.guild_name_data  = data.get("guild_names", {})
            self.guild_type_defs  = data.get("guild_types", {})
        except Exception as e:
            print(f"[GuildSystem] Error cargando datos de guilds: {e}")

    # ── Generación ────────────────────────────────────────────────────────────

    def generate_random_guilds(self, count: int = None) -> List[Guild]:
        """Genera entre 3 y 10 guilds aleatorias al inicio de una partida nueva."""
        if count is None:
            count = random.randint(3, 10)
        
        prefixes   = self.guild_name_data.get("prefixes", ["Orden de"])
        nouns      = self.guild_name_data.get("nouns", ["las Sombras"])
        guild_types = list(self.guild_type_defs.keys())
        territory_ids = list(self.territories.keys())

        random.shuffle(territory_ids)
        territory_pool = territory_ids[:]

        created = []
        for i in range(count):
            guild_id   = f"npc_guild_{i}"
            guild_type = random.choice(guild_types)
            type_data  = self.guild_type_defs[guild_type]
            name       = f"{random.choice(prefixes)} {random.choice(nouns)}"
            icon       = type_data.get("icon", "⚔")

            g = Guild(
                guild_id       = guild_id,
                name           = name,
                guild_type     = guild_type,
                icon           = icon,
                military_power = random.randint(30, 80),
                population     = random.randint(80, 200),
                moral          = random.randint(60, 90),
                aggressiveness = random.randint(20, 80),
            )
            # Dar territorios iniciales según tipo
            starting = type_data.get("starting_territories", [])
            for tid in starting:
                if tid in territory_pool:
                    g.territories.append(tid)
                    if tid in self.territories:
                        self.territories[tid].owner = guild_id
                    territory_pool.remove(tid)
            
            # Dar recursos iniciales
            for rid, defn in self.resource_defs.items():
                g.add_resource(rid, random.randint(20, 80), self.resource_defs)

            self.guilds[guild_id] = g
            created.append(g)

        # Inicializar relaciones (todas neutral)
        guild_ids = list(self.guilds.keys())
        for gid, guild in self.guilds.items():
            for other_id in guild_ids:
                if other_id != gid:
                    guild.relations[other_id] = random.randint(-30, 30)

        return created

    # ── Simulación ────────────────────────────────────────────────────────────

    def tick(self) -> List[str]:
        """
        Ejecuta un tick de simulación. Llamar cada N combates del jugador.
        Retorna lista de eventos narrativos para mostrar al jugador.
        """
        events = []
        guild_ids = list(self.guilds.keys())

        for guild in self.guilds.values():
            self._produce_resources(guild)
            guild.consume_food()

        # IA de guerra: cada guild decide si atacar
        random.shuffle(guild_ids)
        for gid in guild_ids:
            guild = self.guilds[gid]
            if guild.moral < 10:
                continue  # Guild colapsada, no ataca
            
            # Decidir si atacar este tick
            attack_roll = random.randint(0, 100)
            if attack_roll < guild.aggressiveness:
                event = self._resolve_ai_attack(guild)
                if event:
                    events.append(event)
                    guild.log_event(event)

        # Guardar eventos globales
        self.world_events.extend(events)
        if len(self.world_events) > 50:
            self.world_events = self.world_events[-50:]

        return events

    def _produce_resources(self, guild: Guild) -> None:
        """Produce recursos de todos los territorios controlados."""
        type_data = self.guild_type_defs.get(guild.guild_type, {})
        eco_mult  = guild.economy_multiplier(type_data)

        # Bonus extra del árbol de habilidades
        if "eco_logistics" in guild.unlocked_skills:
            eco_mult += 0.2
        if "eco_hegemony" in guild.unlocked_skills:
            eco_mult += 0.5

        for tid in guild.territories:
            territory = self.territories.get(tid)
            if not territory:
                continue
            produced = territory.produce(eco_mult)
            for rid, amount in produced.items():
                # Bonus de tipo
                type_bonus = type_data.get("bonus_resources", {}).get(rid, 0.0)
                final = max(1, int(amount * (1 + type_bonus)))
                guild.add_resource(rid, final, self.resource_defs)

        # Ganado produce comida automáticamente
        ganado = guild.get_resource("ganado")
        if ganado > 0:
            food_from_cattle = ganado * 3
            guild.add_resource("comida", food_from_cattle, self.resource_defs)

    def _resolve_ai_attack(self, attacker: Guild) -> Optional[str]:
        """Resuelve un ataque de IA. Retorna string narrativo o None."""
        # Buscar objetivo: guild con menor poder o territorio neutral
        neutral_territories = [
            tid for tid, t in self.territories.items()
            if t.owner == "neutral"
        ]
        
        if neutral_territories:
            target_tid = random.choice(neutral_territories)
            territory  = self.territories[target_tid]
            return self._attack_territory(attacker, None, territory)
        
        # Atacar a una guild enemiga
        enemy_candidates = [
            gid for gid, guild in self.guilds.items()
            if gid != attacker.guild_id
            and guild.territories
            and attacker.relations.get(gid, 0) < 20
        ]
        if not enemy_candidates:
            return None
        
        defender_id = min(
            enemy_candidates,
            key=lambda gid: self.guilds[gid].military_power,
        )
        defender    = self.guilds[defender_id]
        target_tid  = random.choice(defender.territories)
        territory   = self.territories.get(target_tid)
        if not territory:
            return None
        
        return self._attack_territory(attacker, defender, territory)

    def _attack_territory(
        self,
        attacker: Guild,
        defender: Optional[Guild],
        territory: Territory,
    ) -> str:
        """Resuelve combate por un territorio. Retorna mensaje narrativo."""
        type_data_att  = self.guild_type_defs.get(attacker.guild_type, {})
        mil_mult       = attacker.military_multiplier(type_data_att)

        # Bonus árbol de habilidades del atacante
        if "mil_tactics" in attacker.unlocked_skills:
            mil_mult += 0.1
        if "mil_professional" in attacker.unlocked_skills:
            mil_mult += 0.4

        attack_score = (
            attacker.military_power * mil_mult
            + random.randint(0, 25)
            + attacker.moral * 0.3
        )
        defense_score = territory.defense_value + random.randint(0, 20)
        if defender:
            type_data_def  = self.guild_type_defs.get(defender.guild_type, {})
            def_mult       = defender.military_multiplier(type_data_def)
            defense_score += defender.military_power * def_mult + defender.moral * 0.2

        if attack_score > defense_score:
            # Éxito: conquistar territorio
            if defender and territory.id in defender.territories:
                defender.territories.remove(territory.id)
                defender.change_moral(-12)
                # Pérdida de recursos
                for rid in self.resource_defs:
                    defender.consume_resource(rid, random.randint(5, 20))
                attacker.relations[defender.guild_id] = max(
                    -100,
                    attacker.relations.get(defender.guild_id, 0) - 15,
                )
                msg = (
                    f"⚔ [{attacker.icon} {attacker.name}] conquistó "
                    f"[{territory.icon} {territory.name}] de "
                    f"[{defender.icon} {defender.name}]"
                )
            else:
                msg = (
                    f"⚔ [{attacker.icon} {attacker.name}] tomó el territorio neutral "
                    f"[{territory.icon} {territory.name}]"
                )
            territory.owner = attacker.guild_id
            attacker.territories.append(territory.id)
            attacker.change_moral(8)
            attacker.influence += 10
            attacker.skill_points += 1  # Ganar punto por conquista
        else:
            # Fracaso: perder moral
            attacker.change_moral(-10)
            if defender:
                msg = (
                    f"🛡 [{defender.icon} {defender.name}] repelió el ataque de "
                    f"[{attacker.icon} {attacker.name}] en "
                    f"[{territory.icon} {territory.name}]"
                )
                defender.change_moral(5)
            else:
                msg = (
                    f"💨 [{attacker.icon} {attacker.name}] falló al intentar tomar "
                    f"[{territory.icon} {territory.name}]"
                )

        return msg

    # ── Interfaz del jugador ──────────────────────────────────────────────────

    def get_player_guild(self) -> Optional[Guild]:
        if self.player_guild_id:
            return self.guilds.get(self.player_guild_id)
        return None

    def create_player_guild(
        self, name: str, guild_type: str, player
    ) -> Guild:
        guild_id = "player_guild"
        type_data = self.guild_type_defs.get(guild_type, {})
        g = Guild(
            guild_id        = guild_id,
            name            = name,
            guild_type      = guild_type,
            icon            = type_data.get("icon", "🏠"),
            military_power  = 30,
            population      = 50,
            moral           = 80,
            aggressiveness  = 30,
            is_player_guild = True,
        )
        for rid, defn in self.resource_defs.items():
            g.add_resource(rid, 20, self.resource_defs)

        # Relaciones iniciales con todas las demás guilds
        for gid in self.guilds:
            g.relations[gid] = 0
            self.guilds[gid].relations[guild_id] = 0

        self.guilds[guild_id]  = g
        self.player_guild_id   = guild_id
        player.guild_id        = guild_id
        g.log_event(f"✨ La guild '{name}' fue fundada.")
        return g

    def join_guild(self, guild_id: str, player) -> bool:
        if guild_id not in self.guilds:
            return False
        player.guild_id        = guild_id
        self.player_guild_id   = guild_id
        guild = self.guilds[guild_id]
        guild.influence += 5
        guild.log_event(f"➕ Un nuevo miembro se unió a la guild.")
        return True

    def get_player_reputation(self, player, guild_id: str) -> int:
        return getattr(player, "guild_reputation", {}).get(guild_id, 0)

    def change_player_reputation(self, player, guild_id: str, delta: int) -> int:
        if not hasattr(player, "guild_reputation"):
            player.guild_reputation = {}
        current = player.guild_reputation.get(guild_id, 0)
        new_val = max(-100, min(100, current + delta))
        player.guild_reputation[guild_id] = new_val
        return new_val

    def get_reputation_rank(self, reputation: int) -> Tuple[str, str]:
        """Devuelve (rank_name, color)."""
        if reputation <= -50:
            return ("Enemigo",     "bold red")
        elif reputation < 0:
            return ("Hostil",      "red")
        elif reputation < 50:
            return ("Neutral",     "dim white")
        elif reputation < 80:
            return ("Aliado",      "bold green")
        else:
            return ("Hermandad",   "bold bright_cyan")

    def get_sorted_guilds_by_power(self) -> List[Guild]:
        return sorted(self.guilds.values(), key=lambda g: g.military_power, reverse=True)

    def get_territory_map_rows(self) -> List[str]:
        """Genera un mapa ASCII de 4x3 con los territorios."""
        rows = []
        max_col, max_row = 4, 3
        index: Dict[Tuple[int,int], Territory] = {}
        for t in self.territories.values():
            pos = (int(t.position[0]), int(t.position[1]))
            index[pos] = t

        for row in range(max_row):
            cells = []
            for col in range(max_col):
                t = index.get((col, row))
                if t:
                    owner_str = ""
                    if t.owner == "neutral":
                        owner_str = "·"
                    elif t.owner == self.player_guild_id:
                        owner_str = "★"
                    else:
                        owner_guild = self.guilds.get(t.owner)
                        owner_str = owner_guild.icon if owner_guild else "?"
                    cells.append(f"[{t.icon}{owner_str}]")
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
        """Restaura el estado completo desde un dict guardado."""
        # Restaurar guilds
        for gid, gdata in data.get("guilds", {}).items():
            self.guilds[gid] = Guild.from_dict(gdata, self.resource_defs)

        # Restaurar owners de territorios
        for tid, tdata in data.get("territories", {}).items():
            if tid in self.territories:
                self.territories[tid].owner = tdata.get("owner", "neutral")

        self.world_events    = data.get("world_events", [])
        self.player_guild_id = data.get("player_guild_id")


# ── Singleton global ──────────────────────────────────────────────────────────

_guild_manager_instance: Optional[GuildManager] = None


def get_guild_manager() -> GuildManager:
    global _guild_manager_instance
    if _guild_manager_instance is None:
        _guild_manager_instance = GuildManager()
    return _guild_manager_instance


def reset_guild_manager() -> GuildManager:
    """Crea un nuevo GuildManager limpio (para nueva partida)."""
    global _guild_manager_instance
    _guild_manager_instance = GuildManager()
    return _guild_manager_instance
