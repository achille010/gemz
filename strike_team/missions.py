"""Mission generator: map x task x time of day x modifiers -> endless unique, hard missions.

Campaign mission N always produces the same mission (seeded), getting harder every 3 missions.
Random ops use a random seed. Every mission has ONE specific task - clearing the map never wins.
"""
import random

TASKS = {
    "defuse": ("Defuse the Bomb",
               "A device is armed somewhere in the {map}. Reach it and hold position next to it until "
               "it's disarmed - before the clock runs out."),
    "hack": ("Hack the Terminal",
             "Find the enemy terminal and stay next to it while the upload runs. They will send "
             "everything they have at you."),
    "destroy": ("Sabotage",
                "Plant charges on all {targets} targets (radars and fuel tanks), then get both of "
                "you to the extraction zone."),
    "intel": ("Steal the Intel",
              "A laptop with enemy plans is guarded in the {map}. Grab it and carry it to extraction. "
              "If the carrier goes down, the intel drops."),
    "rescue": ("Hostage Rescue",
               "A hostage (orange) is held somewhere in the {map}. Find them - they will follow you - "
               "and bring them to extraction alive."),
    "assassinate": ("High Value Target",
                    "An enemy commander (gold uniform) is inspecting the {map} with bodyguards. "
                    "Take him out, then extract."),
    "survive": ("Hold the Line",
                "Occupy the marked zone and keep at least one of you inside it for {hold} seconds. "
                "Then extract."),
    "collect": ("Supply Run",
                "{cases} supply cases were lost across the {map}. Recover every one of them, then extract."),
}

BIOMES = {
    "urban": "city district", "base": "military base", "desert": "desert village",
    "snow": "frozen outpost", "forest": "forest camp", "docks": "harbour docks",
}

MODS = {
    "fog": "Thick fog - enemies (and you) see less",
    "heavy": "Armoured heavies reinforce the enemy",
    "scarce": "Ammo is scarce - you start with 6 reloads and fewer crates",
    "sharpshooters": "Enemy marksmen - they hit more often",
    "reinforcements": "Enemy reinforcements arrive throughout the mission",
    "no_regen": "No health regeneration",
    "timed": "Strict time limit",
}

ADJ = ["Iron", "Silent", "Crimson", "Black", "Broken", "Frozen", "Burning", "Hidden", "Last", "Shattered",
       "Hollow", "Steel", "Midnight", "Desert", "Northern", "Savage", "Ghost", "Thunder", "Red", "Final"]
NOUN = ["Dawn", "Viper", "Anvil", "Harbor", "Echo", "Spear", "Lantern", "Falcon", "Tide", "Hammer",
        "Serpent", "Shield", "Storm", "Reaper", "Gate", "Wolf", "Ember", "Raven", "Horizon", "Fortress"]


def generate(seed=None, campaign_no=None, solo=False):
    if seed is None:
        seed = random.randrange(1, 10 ** 6) if campaign_no is None else 1000 + campaign_no * 7919
    rng = random.Random(seed)
    if campaign_no is not None:
        diff = min(10, 2 + (campaign_no - 1) // 3)
    else:
        diff = rng.randint(3, 8)
    task = rng.choice(list(TASKS))
    biome = rng.choice(list(BIOMES))
    tod = rng.choices(["day", "dusk", "night"], weights=[5, 3, 2])[0]
    n_mods = min(4, diff // 3 + rng.randint(0, 1))
    mods = rng.sample(list(MODS), n_mods)
    params = {
        "targets": 3 + diff // 4,
        "cases": 4 + diff // 3,
        "hold_time": 75 + diff * 8,
        "hack_time": 40 + diff * 4,
        "defuse_time": 8 + diff // 2,
    }
    time_limit = 0
    if task == "defuse":
        time_limit = 300 - diff * 12
    elif "timed" in mods:
        time_limit = 660 - diff * 25
    tname, brief = TASKS[task]
    brief = brief.format(map=BIOMES[biome], targets=params["targets"], hold=params["hold_time"], cases=params["cases"])
    if solo:
        diff = max(1, diff - 2)              # one player: a little more forgiving
    return {
        "solo": solo,
        "name": f"Operation {rng.choice(ADJ)} {rng.choice(NOUN)}",
        "code": f"OP-{seed:06d}",
        "campaign_no": campaign_no,
        "task": task,
        "task_name": tname,
        "brief": brief,
        "biome": biome,
        "biome_name": BIOMES[biome],
        "time": tod,
        "seed": seed,
        "difficulty": diff,
        "mods": mods,
        "mod_text": [MODS[m] for m in mods],
        "time_limit": time_limit,
        "params": params,
    }


if __name__ == "__main__":
    for n in range(1, 13):
        m = generate(campaign_no=n)
        print(f"{n:2}  {m['name']:<28} {m['task_name']:<18} {m['biome_name']:<16} {m['time']:<5} "
              f"diff {m['difficulty']}  {', '.join(m['mods'])}")
