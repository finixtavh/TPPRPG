import re

with open("Modules/GuildSystem.py", "r") as f:
    content = f.read()

# 1. Add lose_soldiers method
lose_soldiers_code = """    def lose_soldiers(self, amount: int) -> None:
        \"\"\"Removes 'amount' soldiers proportionally from the army types.\"\"\"
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

    def get_max_soldiers(self, guild_type_defs: dict) -> int:"""
content = content.replace("    def get_max_soldiers(self, guild_type_defs: dict) -> int:", lose_soldiers_code)

# 2. Fix recruit_soldiers
old_recruit = """    def recruit_soldiers(self, troop_type: str, count: int, resource_defs: dict,
                         guild_type_defs: dict) -> Tuple[int, str]:
        if troop_type not in ["infantry", "archers", "cavalry", "siege"]:
            troop_type = "infantry"
            
        slots = max(0, self.get_max_soldiers(guild_type_defs) - self.get_total_soldiers())
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
        return n, f"✓ Reclutaste {n} soldados.""""

new_recruit = """    def recruit_soldiers(self, troop_type: str, count: int, resource_defs: dict,
                         guild_type_defs: dict) -> Tuple[int, str]:
        if troop_type not in ["infantry", "archers", "cavalry", "siege"]:
            troop_type = "infantry"
            
        slots = max(0, self.get_max_soldiers(guild_type_defs) - self.get_total_soldiers())
        n     = min(count, slots)
        if n <= 0:
            return 0, "Ya tienes el máximo de soldados."
            
        cost_map = {
            "infantry": {"comida": n, "cuero_endurecido": max(1, n // 2)},
            "archers":  {"madera": n, "cuero_endurecido": max(1, n // 2)},
            "cavalry":  {"comida": n, "ganado": max(1, n // 3)},
            "siege":    {"madera": n * 2, "lingotes_xar": max(1, n // 5)}
        }
        
        reqs = cost_map[troop_type]
        for res, amt in reqs.items():
            if self.get_resource(res) < amt:
                return 0, f"No tienes suficientes recursos ({res}) para reclutar {troop_type}."
                
        for res, amt in reqs.items():
            self.consume_resource(res, amt)
            
        if isinstance(self.soldiers, dict):
            self.soldiers[troop_type] += n
            
        return n, f"Reclutaste {n} de {troop_type}." """
content = content.replace(old_recruit, new_recruit)

# 3. Replace .soldiers uses with .get_total_soldiers() and .lose_soldiers()
content = content.replace("self.soldiers > 3", "self.get_total_soldiers() > 3")
content = content.replace("guild.soldiers > 3", "guild.get_total_soldiers() > 3")
content = content.replace("guild.soldiers > 0", "guild.get_total_soldiers() > 0")
content = content.replace("guild.soldiers < guild", "guild.get_total_soldiers() < guild")
content = content.replace("attacker.soldiers *", "attacker.get_total_soldiers() *")
content = content.replace("defender.soldiers *", "defender.get_total_soldiers() *")

# In change_moral:
content = content.replace("sol_loss = min(self.soldiers, pop_loss // 3)", "sol_loss = min(self.get_total_soldiers(), pop_loss // 3)")
content = content.replace("self.soldiers   = max(0, self.soldiers - sol_loss)", "self.lose_soldiers(sol_loss)")

# In _attack_territory
content = content.replace("attacker.soldiers   = max(0, attacker.soldiers   - att_losses)", "attacker.lose_soldiers(att_losses)")
content = content.replace("defender.soldiers   = max(0, defender.soldiers   - def_losses)", "defender.lose_soldiers(def_losses)")

# Generation (generate_random_guilds and populate zones)
content = content.replace("g.soldiers = int(g.population * 0.10)", 'g.soldiers = {"infantry": int(g.population * 0.10), "archers": 0, "cavalry": 0, "siege": 0}')

with open("Modules/GuildSystem.py", "w") as f:
    f.write(content)
print("Done")
