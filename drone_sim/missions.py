"""Mission generator: course x district x weather x modifiers -> endless unique, hard flight ops.

Campaign mission N always produces the same mission (seeded), getting harder every 3 missions.
Random ops use a random seed. Every mission has ONE specific course, and every number this
file emits drives a real knob in drone_sim.py (gate count and radius, wind and gusts, battery
drain and recharge, the clock), so nothing in a briefing is decoration.
"""
import random

COURSES = {
    "gate_rush": ("Gate Rush",
                  "{gates} gates strung across the {district}, climbing and dropping as they go. "
                  "Fly through every ring in order. Clip an edge and it costs you points and battery."),
    "slalom": ("Slalom Sprint",
               "{gates} poles planted low over the {district}. Pass inside the ground circle of each "
               "one, in order, without climbing out to cheat the line."),
    "altitude": ("Altitude Ace",
                 "{gates} rings stacked over the {district}. Hold the drone inside each one for "
                 "{hold:.1f} s while the air shoves you around."),
    "landing": ("Precision Landing",
                "A pad on the far side of the {district}. Cross to it and set down soft and centred, "
                "in a crosswind that does not want you there."),
    "delivery": ("Delivery Run",
                 "Rooftop courier over the {district}: {parcels} parcels. Land to pick one up, land "
                 "again to drop it. A parcel on board is dead weight and eats the battery."),
    "grand_tour": ("Grand Tour",
                   "The long way round the {district}: {gates} gates, and a landing pad at the end "
                   "you have to touch down on with whatever battery you have left."),
}

# base course in drone_sim.MISSIONS that a generated op borrows its shape from
COURSE_BASE = {"gate_rush": "ring_rush", "slalom": "slalom", "altitude": "altitude_ace",
               "landing": "precision_landing", "delivery": "delivery", "grand_tour": "ring_rush"}

DISTRICTS = {
    "downtown": "downtown towers", "docks": "harbour docks", "industrial": "industrial park",
    "suburbs": "low suburbs", "park": "city park", "ringroad": "ring road",
}

WEATHER = {
    "calm": ("calm air", 0.4, 0.5),
    "breeze": ("a steady breeze", 2.0, 1.0),
    "gusty": ("gusty air", 4.0, 1.8),
    "crosswind": ("a hard crosswind", 5.5, 1.6),
    "gale": ("a gale", 7.5, 2.4),
    "storm": ("a storm", 9.5, 3.2),
}

MODS = {
    "tight": "Undersized gates - half the usual margin",
    "heavy": "Heavy airframe - sluggish to turn, thirsty on the battery",
    "lowbat": "You launch on a part-charged battery",
    "nocharge": "Checkpoints give you no charge back",
    "long": "Extended course - extra checkpoints",
    "strict": "Strict clock",
    "squall": "Squalls - the wind swings and gusts far harder",
}

ADJ = ["Iron", "Silent", "Crimson", "Black", "Broken", "Frozen", "Burning", "Hidden", "Last", "Shattered",
       "Hollow", "Steel", "Midnight", "Desert", "Northern", "Savage", "Ghost", "Thunder", "Red", "Final"]
NOUN = ["Dawn", "Viper", "Anvil", "Harbor", "Echo", "Spear", "Lantern", "Falcon", "Tide", "Hammer",
        "Serpent", "Shield", "Storm", "Reaper", "Gate", "Wolf", "Ember", "Raven", "Horizon", "Fortress"]


def generate(seed=None, campaign_no=None, solo=False):
    """Build one mission. campaign_no pins the seed, so campaign mission N is always the same op."""
    if seed is None:
        seed = random.randrange(1, 10 ** 6) if campaign_no is None else 1000 + campaign_no * 7919
    rng = random.Random(seed)
    if campaign_no is not None:
        diff = min(10, 2 + (campaign_no - 1) // 3)
    else:
        diff = rng.randint(3, 8)
    course = rng.choice(list(COURSES))
    district = rng.choice(list(DISTRICTS))
    # rough weather follows difficulty, with room either side
    wkeys = list(WEATHER)
    wi = min(len(wkeys) - 1, max(0, round(diff / 10 * (len(wkeys) - 1)) + rng.randint(-1, 1)))
    weather = wkeys[wi]
    wname, wind, gust = WEATHER[weather]
    n_mods = min(4, diff // 3 + rng.randint(0, 1))
    mods = rng.sample(list(MODS), n_mods)

    gates = {"gate_rush": 8, "slalom": 12, "altitude": 4, "landing": 1,
             "delivery": 2, "grand_tour": 12}[course] + diff // 3
    if "long" in mods:
        gates += 3
    if course == "landing":
        gates = 1                        # one pad, however long the op is
    base_r = {"gate_rush": 5.5, "slalom": 3.6, "altitude": 4.0, "landing": 4.5,
              "delivery": 4.0, "grand_tour": 5.0}[course]
    gate_r = base_r * (1.0 - 0.035 * diff)
    if "tight" in mods:
        gate_r *= 0.62
    gate_r = max(gate_r, base_r * 0.5)   # never shrink a gate below half size - it stays flyable
    hold = 1.4 + 0.1 * diff if course in ("altitude", "landing") else 0.0

    # clock: enough seconds per checkpoint to be fair, minus difficulty, minus "strict"
    per = {"gate_rush": 7.0, "slalom": 3.4, "altitude": 14.0, "landing": 42.0,
           "delivery": 52.0, "grand_tour": 7.5}[course]
    time_limit = int((gates * per + 14) * (1.0 - 0.025 * diff))
    if "strict" in mods:
        time_limit = int(time_limit * 0.8)
    if "squall" in mods:
        wind *= 1.15
        gust *= 2.0
    drain = 0.75 + 0.07 * diff + (0.25 if "heavy" in mods else 0.0)
    recharge = 0 if "nocharge" in mods else max(3, 11 - diff // 2)
    battery = 70 if "lowbat" in mods else 100

    if solo:
        diff = max(1, diff - 2)              # flying it alone: a little more forgiving
        time_limit = int(time_limit * 1.15)
        wind *= 0.85
        drain *= 0.9

    params = {
        "gates": gates, "gate_r": round(gate_r, 2), "hold": round(hold, 2),
        "wind": round(wind, 2), "gust": round(gust, 2), "drain": round(drain, 3),
        "recharge": recharge, "battery": battery, "parcels": gates if course == "delivery" else 0,
        "heavy": "heavy" in mods, "tour_landing": course == "grand_tour",
    }
    cname, brief = COURSES[course]
    brief = brief.format(district=DISTRICTS[district], gates=gates, hold=params["hold"],
                         parcels=params["parcels"])
    return {
        "solo": solo,
        "name": f"Operation {rng.choice(ADJ)} {rng.choice(NOUN)}",
        "code": f"OP-{seed:06d}",
        "campaign_no": campaign_no,
        "course": course,
        "course_name": cname,
        "base": COURSE_BASE[course],
        "brief": brief,
        "district": district,
        "district_name": DISTRICTS[district],
        "weather": weather,
        "weather_name": wname,
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
        p = m["params"]
        print(f"{n:2}  {m['name']:<26} {m['course_name']:<18} {m['district_name']:<17} "
              f"{m['weather_name']:<18} diff {m['difficulty']:<3} {m['time_limit']:>3}s  "
              f"{p['gates']} cp r={p['gate_r']}  wind {p['wind']}/{p['gust']}  "
              f"{', '.join(m['mods'])}")
