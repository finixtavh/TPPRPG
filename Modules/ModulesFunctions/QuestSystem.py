import json
import os
import time
from rich.console import Console
from rich.panel import Panel
from Modules.ModulesUtils.input_utils import get_menu_refresh_rate, interactive_menu_select


console = Console()

class cQuest:
    def __init__(self, data: dict):
        self.quest_id = data.get("quest_id")
        self.name = data.get("name")
        self.description = data.get("description")
        self.type = data.get("type")  # kill, gather
        self.target = data.get("target")
        self.required_amount = data.get("required_amount", 1)
        self.rewards = data.get("rewards", {})
        
        # Estado del jugador respecto a la quest
        self.current_amount = 0
        self.completed = False
        self.reward_claimed = False
        
    def to_dict(self):
        return {
            "quest_id": self.quest_id,
            "current_amount": self.current_amount,
            "completed": self.completed,
            "reward_claimed": self.reward_claimed
        }
        
    def load_state(self, state: dict):
        self.current_amount = state.get("current_amount", 0)
        self.completed = state.get("completed", False)
        self.reward_claimed = state.get("reward_claimed", False)

class QuestManager:
    def __init__(self):
        self.quests = {}
        self.active_quests = {}
        self.completed_quests = []
        self.load_quests()

    def load_quests(self):
        path = os.path.join("Data", "DataQuests.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for q_data in data.get("quests", []):
                        q = cQuest(q_data)
                        self.quests[q.quest_id] = q
            except Exception as e:
                console.print(f"[red]Error loading DataQuests.json: {e}[/red]")

    def accept_quest(self, quest_id: str):
        if quest_id in self.quests and quest_id not in self.active_quests and quest_id not in self.completed_quests:
            self.active_quests[quest_id] = self.quests[quest_id]
            console.print(f"[bold yellow]¡Misión aceptada!: {self.quests[quest_id].name}[/]")
            return True
        return False

    def update_kill_quest(self, enemy_name: str, player):
        for q in self.active_quests.values():
            if q.type == "kill" and q.target.lower() == enemy_name.lower() and not q.completed:
                q.current_amount += 1
                if q.current_amount >= q.required_amount:
                    q.completed = True
                    console.print(f"\n[blink bold green]¡Misión completada!: {q.name}[/]")
                else:
                    console.print(f"[yellow]Progreso de Misión ({q.name}): {q.current_amount}/{q.required_amount}[/]")

    def check_gather_quests(self, vInventory):
        for q in self.active_quests.values():
            if q.type == "gather" and not q.completed:
                # Contar materiales en inventario
                count = sum(1 for item in vInventory.Objects if getattr(item, "Name", getattr(item, "name", "")).lower() == q.target.lower())
                q.current_amount = count
                if q.current_amount >= q.required_amount:
                    q.completed = True
                    console.print(f"\n[blink bold green]¡Misión completada!: {q.name}[/]")

    def claim_reward(self, quest_id: str, player, vInventory):
        q = self.active_quests.get(quest_id)
        if q and q.completed and not q.reward_claimed:
            gold = q.rewards.get("gold", 0)
            exp = q.rewards.get("exp", 0)
            player.Gold += gold
            player.EXP += exp
            console.print(f"[bold green]Recompensa de {q.name} obtenida: {gold} de Oro y {exp} de Experiencia.[/]")
            q.reward_claimed = True
            player.level_up()
            
            # Mover a completadas
            self.completed_quests.append(quest_id)
            del self.active_quests[quest_id]
            return True
        return False

    def get_save_data(self):
        return {
            "active_quests": {qid: q.to_dict() for qid, q in self.active_quests.items()},
            "completed_quests": self.completed_quests
        }
        
    def load_save_data(self, data: dict):
        self.active_quests.clear()
        self.completed_quests = data.get("completed_quests", [])
        
        active_data = data.get("active_quests", {})
        for qid, state in active_data.items():
            if qid in self.quests:
                self.quests[qid].load_state(state)
                self.active_quests[qid] = self.quests[qid]

    def open_quest_board(self, player, vInventory):
        
        while True:
            console.clear()
            self.check_gather_quests(vInventory)
            console.print(Panel("[yellow]📜 Tablón de Misiones 📜[/]", style="bold bright_black"))
            
            options = [(0, "Salir")]
            idx = 1
            
            # Listar misiones para aceptar
            available_quests = [q for q_id, q in self.quests.items() if q_id not in self.active_quests and q_id not in self.completed_quests]
            
            # Listar misiones activas
            active_list = list(self.active_quests.values())
            
            if not available_quests and not active_list:
                console.print("\n[dim]No hay misiones disponibles en este momento.[/]")
            
            option_map = {}
            
            for q in active_list:
                status = "[green](Completada - Selecciona para cobrar)[/]" if q.completed else f"[yellow](En progreso: {q.current_amount}/{q.required_amount})[/]"
                label = f"[bold cyan]{q.name}[/] {status}\n      └ {q.description}"
                options.append((idx, label))
                option_map[idx] = ("active", q)
                idx += 1
                
            for q in available_quests:
                rew_str = f"Oro: {q.rewards.get('gold', 0)} | Exp: {q.rewards.get('exp', 0)}"
                label = f"[bold white]{q.name}[/] [dim](Nueva)[/]\n      └ {q.description}\n      └ [green]Recompensa:[/] {rew_str}"
                options.append((idx, label))
                option_map[idx] = ("available", q)
                idx += 1

            choice = interactive_menu_select(
                title="Gestión de Misiones",
                options=options,
                prompt="Selección: ",
                default_value=0,
                border_style="yellow"
            )

            if choice == 0:
                break
                
            action_type, selected_q = option_map[choice]
            
            if action_type == "available":
                self.accept_quest(selected_q.quest_id)
                time.sleep(get_menu_refresh_rate())
            elif action_type == "active":
                if selected_q.completed:
                    self.claim_reward(selected_q.quest_id, player, vInventory)
                    time.sleep(get_menu_refresh_rate())
                else:
                    console.print(f"[yellow]Aún no has completado esta misión.[/]")
                    time.sleep(get_menu_refresh_rate())

# Instancia global
quest_manager = QuestManager()
