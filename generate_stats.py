import json

with open("Data/DataStats.json", "r") as f:
    data = json.load(f)

# Update existing zones with loot_tables and gathering materials

# Forest
data["Forest"][0]["enemy"]["loot_tables"] = {"1": 0.5, "10": 0.2, "50": 0.4, "20": 0.8}
data["Forest"][0]["enemy2"]["loot_tables"] = {"2": 0.4, "20": 0.5, "50": 0.3}
data["Forest"][0]["fire_spirit"]["loot_tables"] = {"4": 0.3, "45": 0.1, "21": 0.5}
data["Forest"][0]["goblin_king"]["loot_tables"] = {"3": 0.5, "22": 0.3, "6": 0.1, "51": 1.0}
data["Forest"][0]["Gathering"]["Materials"] = ["1_G", "2_G", "16_G", "20_G"]

# Cave
data["Cave"][0]["rock_golem"]["loot_tables"] = {"6": 0.3, "14": 0.1, "46": 0.05, "6": 0.8}
data["Cave"][0]["electric_bat"]["loot_tables"] = {"7": 0.05, "47": 0.05, "50": 0.5}
data["Cave"][0]["shadow_beast"]["loot_tables"] = {"8": 0.01, "43": 0.1, "20": 0.5}
data["Cave"][0]["elder_golem"]["loot_tables"] = {"6": 0.5, "14": 0.5, "33": 0.2, "46": 0.2, "23": 0.3}
data["Cave"][0]["Gathering"]["Materials"] = ["6_G", "7_G", "11_G", "12_G", "8_G"]

# Volcano
data["Volcano"][0]["magma_elemental"]["loot_tables"] = {"5": 0.1, "45": 0.2, "10": 0.5, "21": 0.4}
data["Volcano"][0]["lava_serpent"]["loot_tables"] = {"13": 0.05, "45": 0.1, "20": 0.3}
data["Volcano"][0]["Gathering"]["Materials"] = ["10_G", "8_G", "14_G", "21_G"]

# Abyss
data["Abyss"][0]["void_walker"]["loot_tables"] = {"8": 0.05, "15": 0.02, "43": 0.1}
data["Abyss"][0]["abyssal_horror"]["loot_tables"] = {"8": 0.1, "15": 0.05, "44": 0.05, "22": 0.8}
data["Abyss"][0]["Gathering"]["Materials"] = ["5_G", "15_G", "19_G", "22_G"]

# Create New Zones
new_zones = {
    "EnchantedForest": [{
        "fairy": {
            "NAME": "Hada del Bosque",
            "HP_M": 80,
            "DMG": [5, 10, 10, 10, 0],
            "DMG_min": [2, 5, 5, 5],
            "MP_M": 100,
            "EXP_TO_PLAYER": 60,
            "DEF": [5, 5, 5, 5, 5],
            "LS": 0,
            "AGI": 30,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 70,
            "loot_tables": {"90": 0.1, "19": 0.5, "52": 0.3}
        },
        "treant": {
            "NAME": "Treant Antiguo",
            "HP_M": 200,
            "DMG": [30, 0, 20, 0, 0],
            "DMG_min": [15, 0, 10, 0],
            "MP_M": 50,
            "EXP_TO_PLAYER": 120,
            "DEF": [20, 0, 30, 5, 5],
            "LS": 0,
            "AGI": 5,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 150,
            "loot_tables": {"4": 0.2, "14": 0.1, "1": 0.9, "17": 0.6}
        },
        "Strings": {
            "name": "Bosque Encantado",
            "desc": "Un bosque repleto de magia vibrante",
            "exit": "Saliendo del Bosque Encantado",
            "color": "green"
        },
        "Gathering": {
            "Materials": ["3_G", "17_G", "18_G", "19_G"]
        }
    }],
    "ForgottenRuins": [{
        "stone_gargoyle": {
            "NAME": "Gárgola de Piedra",
            "HP_M": 120,
            "DMG": [25, 0, 10, 0, 0],
            "DMG_min": [12, 0, 5, 0],
            "MP_M": 20,
            "EXP_TO_PLAYER": 80,
            "DEF": [25, 5, 15, 10, 5],
            "LS": 0,
            "AGI": 10,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 90,
            "loot_tables": {"23": 0.4, "6": 0.1, "9": 0.05}
        },
        "ruin_guardian": {
            "NAME": "Guardián de las Ruinas",
            "HP_M": 250,
            "DMG": [35, 15, 15, 15, 0],
            "DMG_min": [18, 7, 7, 7],
            "MP_M": 100,
            "EXP_TO_PLAYER": 180,
            "DEF": [30, 20, 20, 20, 10],
            "LS": 0,
            "AGI": 8,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 250,
            "IS_BOSS": True,
            "SPAWN_CHANCE": 0.05,
            "loot_tables": {"9": 0.2, "22": 0.1, "23": 0.8, "44": 0.1}
        },
        "Strings": {
            "name": "Ruinas Olvidadas",
            "desc": "Vestigios de una antigua civilización",
            "exit": "Saliendo de las Ruinas",
            "color": "yellow"
        },
        "Gathering": {
            "Materials": ["9_G", "13_G", "23_G", "14_G"]
        }
    }],
    "FrozenMountain": [{
        "ice_wolf": {
            "NAME": "Lobo de Hielo",
            "HP_M": 80,
            "DMG": [15, 0, 0, 0, 0],
            "DMG_min": [8, 0, 0, 0],
            "MP_M": 20,
            "EXP_TO_PLAYER": 60,
            "DEF": [10, 0, 5, 5, 2],
            "LS": 0,
            "AGI": 20,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 70,
            "loot_tables": {"20": 0.6, "24": 0.2}
        },
        "frost_giant": {
            "NAME": "Gigante de Escarcha",
            "HP_M": 300,
            "DMG": [40, 0, 20, 0, 0],
            "DMG_min": [20, 0, 10, 0],
            "MP_M": 50,
            "EXP_TO_PLAYER": 200,
            "DEF": [25, 0, 20, 10, 5],
            "LS": 0,
            "AGI": 2,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 300,
            "loot_tables": {"6": 0.1, "14": 0.1, "24": 0.7, "46": 0.05}
        },
        "Strings": {
            "name": "Montaña Helada",
            "desc": "Picos cubiertos de nieve eterna",
            "exit": "Descendiendo de la Montaña",
            "color": "cyan"
        },
        "Gathering": {
            "Materials": ["2_G", "13_G", "24_G", "18_G"]
        }
    }],
    "CrystalDesert": [{
        "sand_worm": {
            "NAME": "Gusano de Arena",
            "HP_M": 110,
            "DMG": [20, 0, 25, 0, 0],
            "DMG_min": [10, 0, 12, 0],
            "MP_M": 30,
            "EXP_TO_PLAYER": 85,
            "DEF": [15, 10, 25, 5, 5],
            "LS": 2,
            "AGI": 12,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 100,
            "loot_tables": {"25": 0.5, "12": 0.3}
        },
        "glass_golem": {
            "NAME": "Gólem de Cristal",
            "HP_M": 180,
            "DMG": [15, 20, 0, 15, 0],
            "DMG_min": [8, 10, 0, 8],
            "MP_M": 80,
            "EXP_TO_PLAYER": 140,
            "DEF": [30, 15, 10, 25, 10],
            "LS": 0,
            "AGI": 8,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 200,
            "loot_tables": {"23": 0.1, "25": 0.8, "47": 0.05}
        },
        "Strings": {
            "name": "Desierto de Cristal",
            "desc": "Dunas ardientes con formaciones cristalinas",
            "exit": "Saliendo del Desierto",
            "color": "bright_yellow"
        },
        "Gathering": {
            "Materials": ["7_G", "14_G", "25_G", "17_G"]
        }
    }],
    "ToxicSwamp": [{
        "swamp_slime": {
            "NAME": "Slime del Pantano",
            "HP_M": 90,
            "DMG": [5, 0, 15, 0, 15],
            "DMG_min": [2, 0, 8, 0],
            "MP_M": 20,
            "EXP_TO_PLAYER": 75,
            "DEF": [5, 5, 20, 5, 15],
            "LS": 1,
            "AGI": 5,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 80,
            "loot_tables": {"26": 0.6, "16": 0.4}
        },
        "plague_bringer": {
            "NAME": "Portador de la Plaga",
            "HP_M": 220,
            "DMG": [20, 0, 30, 0, 25],
            "DMG_min": [10, 0, 15, 0],
            "MP_M": 150,
            "EXP_TO_PLAYER": 190,
            "DEF": [20, 15, 30, 10, 25],
            "LS": 5,
            "AGI": 10,
            "DBUFF_TO_PLAYER": [],
            "BUFF_RECEIVED": [],
            "GOLD": 280,
            "IS_BOSS": True,
            "SPAWN_CHANCE": 0.05,
            "loot_tables": {"91": 0.2, "26": 0.9, "43": 0.1}
        },
        "Strings": {
            "name": "Pantano Tóxico",
            "desc": "Aguas pútridas y neblina venenosa",
            "exit": "Saliendo del Pantano",
            "color": "magenta"
        },
        "Gathering": {
            "Materials": ["16_G", "26_G", "4_G", "18_G"]
        }
    }]
}

data.update(new_zones)

with open("Data/DataStats.json", "w") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

