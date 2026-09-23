The game, manual and launchers are in C:\Users\HP\OneDrive\Documents\code\bots\vault_runner\. I ran it headless and it works, but I couldn't play it with real input or a physical pad.

How to start it

Double-click play.bat, or run python vault_runner.py. Your Python 3.14, pygame-ce and numpy were already installed.

What it is

VAULT RUNNER is a first-person 3D stealth heist. You steal coins, gold bars and gems for cash and score, find the red keycard, and open the vault door before the alarm goes off. Guards patrol with flashlights and chase you through the maze if they spot or hear you.

Between levels there's a black-market shop. Time left on the clock, never being spotted, and collecting every item all pay bonuses, and your best score is saved.

On "hyperrealistic": pygame can't do real photorealism. I got as close as software rendering allows, with:
- generated brick, marble, metal, wood and tile textures
- dynamic lighting from your flashlight, flickering ceiling lamps and the guards' torches
- haze, ambient shading, head-bob, film grain and vignette

The manual offers a port to a real 3D engine if you want it to look better than that.

Input, as you asked

All three work at the same time:
- Keyboard: WASD and mouse.
- Numeric keypad (NumLock on): 8/5 move, 4/6 strafe, 7/9 turn, 0 sprint, . sneak, + torch, - map, Enter to use.
- Two-stick gamepad: left stick moves (tilting further goes faster) and right stick looks. The hat/D-pad, buttons and menus also work.

One thing you need to do: a lab-made pad will probably number its axes and buttons differently from the defaults. Run gamepad_test.bat and move the sticks and press the buttons. Then set the numbers in CONFIG["gamepad"] at the top of vault_runner.py. MANUAL.md walks through it.

What I tested

- Passed in a headless run: title screen, keypad start, movement, pickups, guard catch, vault exit, shop, next level, and all 8 generated levels. A simulated pad axis and button also worked.
- Speed: 7 fps at first, tuned to about 39 fps on this machine. If it's slow on yours, lower render_size in CONFIG.

Your customization list

MANUAL.md has about 100 numbered options across 11 groups:
- Themes: space station, casino, haunted mansion and others.
- Tasks: courier deliveries, hacking terminals, defusing bombs.
- Scoring: combos, contracts, star ratings.
- Gadgets and enemies: smoke bombs, cameras, lasers.
- Graphics: shadows, bloom, your own textures.
- Audio, accessibility and progression.

Tell me the numbers you want (for example "A4, B2, C2, D4, E3") and I'll build them in. Options marked ⚙ are already one-line edits in CONFIG.