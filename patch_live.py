import os

files = ["Modules/GuildMenu.py", "Modules/GuildSkillTree.py"]

for fname in files:
    with open(fname, "r") as f:
        content = f.read()
    
    content = content.replace("Live(console=con, refresh_per_second=20)", "Live(console=con, screen=True, refresh_per_second=20)")
    content = content.replace("Live(console=console, refresh_per_second=20)", "Live(console=console, screen=True, refresh_per_second=20)")
    
    with open(fname, "w") as f:
        f.write(content)
print("Done")
