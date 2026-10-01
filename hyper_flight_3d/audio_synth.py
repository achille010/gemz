import pygame
import numpy as np
import math
import random

class AudioSynth:
    def __init__(self):
        self.initialized = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self.initialized = True
        except Exception as e:
            print(f"[AudioSynth] Mixer initialization warning: {e}")
            return

        self.sounds = {}
        self.engine_channel = None
        self.generate_sound_effects()

    def generate_sound_effects(self):
        if not self.initialized:
            return

        sample_rate = 44100

        # 1. Laser sound (descending chirp)
        duration = 0.15
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        freq = np.linspace(1200, 300, len(t))
        laser_wave = np.sin(2 * np.pi * freq * t) * np.exp(-t * 15)
        laser_stereo = np.column_stack((laser_wave, laser_wave))
        laser_int16 = (laser_stereo * 32767 * 0.4).astype(np.int16)
        self.sounds['laser'] = pygame.sndarray.make_sound(laser_int16)

        # 2. Missile Launch sound (whoosh + rocket swell)
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        noise = np.random.uniform(-1, 1, len(t))
        sweep = np.sin(2 * np.pi * np.linspace(150, 800, len(t)) * t)
        missile_wave = (noise * 0.6 + sweep * 0.4) * (1 - np.exp(-t * 20)) * np.exp(-t * 4)
        missile_stereo = np.column_stack((missile_wave, missile_wave))
        missile_int16 = (missile_stereo * 32767 * 0.5).astype(np.int16)
        self.sounds['missile'] = pygame.sndarray.make_sound(missile_int16)

        # 3. Explosion sound (deep low frequency boom + noise burst)
        duration = 0.8
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        noise = np.random.uniform(-1, 1, len(t))
        boom = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 5)
        crack = noise * np.exp(-t * 12)
        explosion_wave = (boom * 0.6 + crack * 0.4)
        explosion_stereo = np.column_stack((explosion_wave, explosion_wave))
        explosion_int16 = (explosion_stereo * 32767 * 0.7).astype(np.int16)
        self.sounds['explosion'] = pygame.sndarray.make_sound(explosion_int16)

        # 4. Ring Chime (bright double harmonic ding)
        duration = 0.3
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        ring_wave = (np.sin(2 * np.pi * 880 * t) * 0.6 + np.sin(2 * np.pi * 1760 * t) * 0.4) * np.exp(-t * 10)
        ring_stereo = np.column_stack((ring_wave, ring_wave))
        ring_int16 = (ring_stereo * 32767 * 0.5).astype(np.int16)
        self.sounds['ring'] = pygame.sndarray.make_sound(ring_int16)

        # 5. Lock-On Beep (high pulse)
        duration = 0.08
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        beep_wave = np.sin(2 * np.pi * 1500 * t)
        beep_stereo = np.column_stack((beep_wave, beep_wave))
        beep_int16 = (beep_stereo * 32767 * 0.3).astype(np.int16)
        self.sounds['lock'] = pygame.sndarray.make_sound(beep_int16)

        # 6. Jet Engine Continuous Roar (Low filtered pink noise + rumble)
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        noise = np.random.uniform(-1, 1, len(t))
        # Simple smoothing filter for low rumble
        rumble = np.sin(2 * np.pi * 70 * t) * 0.3 + np.sin(2 * np.pi * 120 * t) * 0.2
        engine_wave = noise * 0.4 + rumble
        engine_stereo = np.column_stack((engine_wave, engine_wave))
        engine_int16 = (engine_stereo * 32767 * 0.35).astype(np.int16)
        self.sounds['engine'] = pygame.sndarray.make_sound(engine_int16)

    def play(self, sound_name, volume=1.0):
        if not self.initialized or sound_name not in self.sounds:
            return
        snd = self.sounds[sound_name]
        snd.set_volume(volume)
        snd.play()

    def start_engine_sound(self):
        if not self.initialized or 'engine' not in self.sounds:
            return
        if self.engine_channel is None or not self.engine_channel.get_busy():
            self.engine_channel = self.sounds['engine'].play(loops=-1)
            if self.engine_channel:
                self.engine_channel.set_volume(0.2)

    def update_engine(self, throttle, boost):
        if self.engine_channel and self.initialized:
            target_vol = 0.2 + throttle * 0.4 + (0.3 if boost else 0.0)
            self.engine_channel.set_volume(min(1.0, max(0.1, target_vol)))

    def stop_engine(self):
        if self.engine_channel:
            self.engine_channel.stop()
