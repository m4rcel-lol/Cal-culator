# =============================================================================
# Cal-cu-ator: The RPG Calculator
# Inspired by the Richard Watterson meme from The Amazing World of Gumball
#
# Required dependencies (install before running):
#   pip install pygame pypresence
#
# Run from terminal:
#   python3 calculator_rpg.py
# =============================================================================

import pygame
import sys
import math
import random
import time
import uuid

# Discord Rich Presence — import with graceful fallback if pypresence is missing
try:
    from pypresence import Presence
    PYPRESENCE_AVAILABLE = True
except ImportError:
    PYPRESENCE_AVAILABLE = False

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

WINDOW_WIDTH  = 360
WINDOW_HEIGHT = 540
FPS           = 60
TITLE         = "Calculator"         # Boring calculator window title for cover

# Colour palette (Linux GTK-style calculator inspired)
COLOR_BG         = (42,  42,  42)    # Dark background
COLOR_DISPLAY_BG = (30,  30,  30)    # Display area
COLOR_DISPLAY_FG = (220, 220, 220)   # Display text
COLOR_BTN_NUM    = (70,  70,  70)    # Number button face
COLOR_BTN_OP     = (90,  60,  20)    # Operator button face
COLOR_BTN_EQ     = (30,  100, 30)    # Equals button face
COLOR_BTN_CLEAR  = (120, 30,  30)    # Clear button face
COLOR_BTN_HOVER  = (110, 110, 110)   # Hover highlight
COLOR_BTN_TEXT   = (240, 240, 240)   # Button text
COLOR_BORDER     = (80,  80,  80)    # Button border
COLOR_HP_BAR_BG  = (60,  20,  20)
COLOR_HP_BAR_FG  = (200, 40,  40)
COLOR_ENEMY_HP   = (40,  160, 40)

# RPG Discord application client ID
# Using a placeholder — Discord RPC will simply be skipped if the ID is invalid
# or if Discord is not running on the machine.
DISCORD_CLIENT_ID = "1234567890123456789"   # Replace with your own App ID

# =============================================================================
# ENEMY DATA — progressively harder foes
# =============================================================================

ENEMIES = [
    {"name": "Spam Email",      "hp": 30,  "atk": 5,  "xp": 10},
    {"name": "Tax Return",      "hp": 60,  "atk": 10, "xp": 25},
    {"name": "Monday Morning",  "hp": 90,  "atk": 15, "xp": 50},
    {"name": "The Boss",        "hp": 130, "atk": 22, "xp": 80},
    {"name": "Existential Dread","hp": 200,"atk": 30, "xp": 120},
]

PLAYER_MAX_HP   = 100
PLAYER_START_HP = 100

# =============================================================================
# BUTTON LAYOUT
# Rows of (label, action_key, col_span)
# =============================================================================

BUTTON_ROWS = [
    # row 0
    [("C",   "clear",  1), ("AC",  "allclear", 1), ("%",   "pct",  1), ("/",   "div",  1)],
    # row 1
    [("7",   "7",      1), ("8",   "8",        1), ("9",   "9",    1), ("*",   "mul",  1)],
    # row 2
    [("4",   "4",      1), ("5",   "5",        1), ("6",   "6",    1), ("-",   "sub",  1)],
    # row 3
    [("1",   "1",      1), ("2",   "2",        1), ("3",   "3",    1), ("+",   "add",  1)],
    # row 4
    [("0",   "0",      2), (".",   "dot",      1), ("=",   "eq",   1)],
]

# RPG action mapping (button key → action description)
RPG_ACTIONS = {
    "7": ("Light Attack", 15, 0),   # (name, dmg, heal)
    "8": ("Heavy Attack", 30, 0),
    "9": ("Block",         0, 0),   # Block: no attack, reduces incoming dmg
    "4": ("Jab",          10, 0),
    "5": ("Counter",      20, 0),
    "6": ("Feint",         5, 0),
    "1": ("Poke",          8, 0),
    "2": ("Scratch",      12, 0),
    "3": ("Throw",        18, 0),
    "+": ("Heal",          0, 25),  # Heal player
    "-": ("Quick Strike", 14, 0),
    "*": ("Power Slam",   35, 0),
    "/": ("Dodge",         0, 0),   # Dodge: skip enemy turn
    "0": ("Taunt",         2, 0),
    ".": ("Rest",          0, 10),
    "=": ("Finish Move",  22, 0),
    "eq":("Finish Move",  22, 0),
    "add":  ("Heal",       0, 25),
    "sub":  ("Quick Strike",14,0),
    "mul":  ("Power Slam", 35, 0),
    "div":  ("Dodge",       0, 0),
    "clear":("Retreat",     0, 5),
    "allclear":("Surrender",0, 0),
    "pct":  ("Status",      0, 0),
    "dot":  ("Rest",        0, 10),
}

# Special keys that skip the enemy turn
SKIP_ENEMY_TURN = {"9", "/", "div", "pct"}

# =============================================================================
# DISCORD RICH PRESENCE MANAGER
# =============================================================================

class DiscordRPC:
    """Wraps pypresence Presence with graceful error handling."""

    def __init__(self, client_id: str):
        self.rpc    = None
        self.active = False
        self.started_at = int(time.time())
        self.party_id = uuid.uuid4().hex
        if not PYPRESENCE_AVAILABLE:
            print("[RPC] pypresence not installed — Discord RPC disabled.")
            return
        try:
            self.rpc = Presence(client_id)
            self.rpc.connect()
            self.active = True
            print("[RPC] Discord Rich Presence connected.")
        except Exception as exc:
            print(f"[RPC] Could not connect to Discord: {exc}")
            self.rpc    = None
            self.active = False

    def update(self, state: str, details: str = "Cal-cu-ator"):
        """Update RPC state, silently ignoring any errors."""
        if not self.active or self.rpc is None:
            return
        try:
            self.rpc.update(
                state   = "Playing Duos",
                details = "Survival",
                large_image = "calculator",
                large_text  = "Calculator",
                small_image = "richard",
                small_text  = "In party with: Richard Watterson",
                party_id    = self.party_id,
                party_size  = [2, 2],
                start       = self.started_at,
            )
        except Exception as exc:
            print(f"[RPC] Update failed: {exc}")

    def close(self):
        if self.active and self.rpc is not None:
            try:
                self.rpc.close()
            except Exception:
                pass

# =============================================================================
# EXPLOSION PARTICLE
# =============================================================================

class Particle:
    """A single particle for the explosion effect."""

    def __init__(self, x: float, y: float):
        angle  = random.uniform(0, 2 * math.pi)
        speed  = random.uniform(2, 8)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.radius = random.randint(4, 12)
        self.color  = random.choice([
            (255, 80,   0),
            (255, 160,  0),
            (255, 220,  0),
            (255, 40,   0),
            (200, 200, 200),
        ])
        self.life     = random.uniform(0.6, 1.2)   # seconds
        self.born_at  = time.time()
        self.gravity  = 0.15

    @property
    def alive(self) -> bool:
        return (time.time() - self.born_at) < self.life

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += self.gravity   # gravity pulls particles down
        self.vx *= 0.97           # slight air resistance

    def draw(self, surface: pygame.Surface):
        age_ratio = (time.time() - self.born_at) / self.life
        alpha_r   = max(0, int(255 * (1 - age_ratio)))
        r = max(2, int(self.radius * (1 - age_ratio * 0.6)))
        # Blend colour toward dark based on age
        c = tuple(max(0, int(ch * (1 - age_ratio * 0.8))) for ch in self.color)
        pygame.draw.circle(surface, c, (int(self.x), int(self.y)), r)

# =============================================================================
# BUTTON
# =============================================================================

class Button:
    """A single calculator button."""

    def __init__(self, label: str, key: str, rect: pygame.Rect, style: str = "num"):
        self.label   = label
        self.key     = key
        self.rect    = rect
        self.style   = style     # "num", "op", "eq", "clear"
        self.hovered = False
        self.pressed_at: float | None = None   # timestamp for press animation

    def get_color(self) -> tuple:
        base = {
            "num":   COLOR_BTN_NUM,
            "op":    COLOR_BTN_OP,
            "eq":    COLOR_BTN_EQ,
            "clear": COLOR_BTN_CLEAR,
        }.get(self.style, COLOR_BTN_NUM)

        # Short press flash
        if self.pressed_at and (time.time() - self.pressed_at) < 0.15:
            return COLOR_BTN_HOVER

        if self.hovered:
            return tuple(min(255, c + 30) for c in base)
        return base

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        color = self.get_color()
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, COLOR_BORDER, self.rect, 1, border_radius=6)
        text_surf = font.render(self.label, True, COLOR_BTN_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if this button was clicked."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed_at = time.time()
                return True
        return False

# =============================================================================
# GAME STATE
# =============================================================================

class GameState:
    """Manages all RPG game state."""

    # Possible screens
    SCREEN_MENU    = "menu"
    SCREEN_BATTLE  = "battle"
    SCREEN_VICTORY = "victory"
    SCREEN_GAMEOVER= "gameover"
    SCREEN_EXPLODE = "explode"

    def __init__(self):
        self.reset()

    def reset(self):
        self.screen      = GameState.SCREEN_MENU
        self.player_hp   = PLAYER_START_HP
        self.player_max  = PLAYER_MAX_HP
        self.player_xp   = 0
        self.enemy_index = 0
        self.enemy_hp    = 0
        self.enemy_max   = 0
        self.enemy_name  = ""
        self.log_lines: list[str] = ["Welcome!", "Press any button to begin."]
        self.particles: list[Particle] = []
        self.explode_start: float | None = None
        self.last_action: str = ""
        self.blocking    = False
        self.dodging     = False

    def start_battle(self):
        if self.enemy_index >= len(ENEMIES):
            self.screen = GameState.SCREEN_VICTORY
            return
        enemy = ENEMIES[self.enemy_index]
        self.enemy_name  = enemy["name"]
        self.enemy_hp    = enemy["hp"]
        self.enemy_max   = enemy["hp"]
        self.screen      = GameState.SCREEN_BATTLE
        self.log_lines   = [
            f"A new foe appears:",
            f"  >> {self.enemy_name} <<",
            "Choose your action!",
        ]
        self.blocking = False
        self.dodging  = False

    def current_enemy(self) -> dict:
        return ENEMIES[self.enemy_index]

    def apply_action(self, key: str):
        """Process a button press during battle."""
        if key not in RPG_ACTIONS:
            return

        name, dmg, heal = RPG_ACTIONS[key]
        self.last_action = name
        self.blocking = (key == "9")
        self.dodging  = (key in SKIP_ENEMY_TURN)

        self.log_lines = []  # fresh log each turn

        # --- Player action ---
        if dmg > 0:
            # small variance
            actual_dmg = max(1, dmg + random.randint(-3, 3))
            self.enemy_hp = max(0, self.enemy_hp - actual_dmg)
            self.log_lines.append(f"You use {name}!")
            self.log_lines.append(f"  Dealt {actual_dmg} dmg to {self.enemy_name}.")
        elif heal > 0:
            actual_heal = min(heal, self.player_max - self.player_hp)
            self.player_hp += actual_heal
            self.log_lines.append(f"You use {name}!")
            self.log_lines.append(f"  Restored {actual_heal} HP.")
        elif self.blocking:
            self.log_lines.append(f"You brace for impact! (Block)")
        elif self.dodging:
            self.log_lines.append(f"You dodge — enemy misses!")
        else:
            self.log_lines.append(f"You use {name}. Nothing happens...")

        # --- Check enemy death ---
        if self.enemy_hp <= 0:
            xp = self.current_enemy()["xp"]
            self.player_xp += xp
            self.log_lines.append(f"{self.enemy_name} defeated! +{xp} XP")
            self.enemy_index += 1
            if self.enemy_index >= len(ENEMIES):
                self.screen = GameState.SCREEN_VICTORY
            else:
                self.log_lines.append("Press any button for next battle.")
                self.screen = GameState.SCREEN_MENU   # brief pause before next
            return

        # --- Enemy turn (unless dodged) ---
        if not self.dodging:
            enemy_atk = self.current_enemy()["atk"]
            variance  = random.randint(-3, 5)
            incoming  = max(1, enemy_atk + variance)
            if self.blocking:
                incoming = max(1, incoming // 2)
                self.log_lines.append(f"{self.enemy_name} hits — BLOCKED! -{incoming} HP")
            else:
                self.log_lines.append(f"{self.enemy_name} attacks! -{incoming} HP")
            self.player_hp = max(0, self.player_hp - incoming)

        # --- Check player death ---
        if self.player_hp <= 0:
            self.log_lines.append("You have been defeated...")
            self.screen       = GameState.SCREEN_EXPLODE
            self.explode_start = time.time()
            # Spawn explosion particles at screen centre
            cx = WINDOW_WIDTH  // 2
            cy = WINDOW_HEIGHT // 2
            for _ in range(120):
                self.particles.append(Particle(cx, cy))

    def update_explosion(self) -> bool:
        """Update particles; return True when explosion is done."""
        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update()
        elapsed = time.time() - (self.explode_start or 0)
        if elapsed > 2.5 and not self.particles:
            return True
        return False

# =============================================================================
# MAIN GAME CLASS
# =============================================================================

class CalcRPG:
    """Main application class."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen_surf = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.font.init()
        self.clock       = pygame.time.Clock()

        # Fonts
        self.font_small  = pygame.font.SysFont("DejaVu Sans", 14)
        self.font_mid    = pygame.font.SysFont("DejaVu Sans", 18)
        self.font_large  = pygame.font.SysFont("DejaVu Sans", 28, bold=True)
        self.font_huge   = pygame.font.SysFont("DejaVu Sans", 48, bold=True)

        # Build button grid
        self.buttons: list[Button] = []
        self._build_buttons()

        # Game state
        self.state = GameState()

        # Discord RPC
        self.rpc = DiscordRPC(DISCORD_CLIENT_ID)
        self.rpc.update("Pretending to work", "Main Menu")

        self.running      = True
        self.gameover_shown_at: float | None = None

    # ------------------------------------------------------------------
    # BUTTON LAYOUT BUILDER
    # ------------------------------------------------------------------

    def _build_buttons(self):
        DISPLAY_H  = 160    # height reserved for the display area
        PADDING    = 6
        COLS       = 4
        ROWS       = 5
        avail_w    = WINDOW_WIDTH  - PADDING * (COLS + 1)
        avail_h    = WINDOW_HEIGHT - DISPLAY_H - PADDING * (ROWS + 1)
        cell_w     = avail_w // COLS
        cell_h     = avail_h // ROWS

        for row_idx, row_def in enumerate(BUTTON_ROWS):
            col_cursor = 0
            for label, key, span in row_def:
                x = PADDING + col_cursor * (cell_w + PADDING)
                y = DISPLAY_H + PADDING + row_idx * (cell_h + PADDING)
                w = cell_w * span + PADDING * (span - 1)
                h = cell_h
                rect = pygame.Rect(x, y, w, h)

                # Determine style
                if key in ("clear", "allclear"):
                    style = "clear"
                elif key == "eq":
                    style = "eq"
                elif key in ("add", "sub", "mul", "div", "pct", "+", "-", "*", "/", "="):
                    style = "op"
                else:
                    style = "num"

                self.buttons.append(Button(label, key, rect, style))
                col_cursor += span

    # ------------------------------------------------------------------
    # DRAWING HELPERS
    # ------------------------------------------------------------------

    def _draw_display(self):
        """Render the top display panel with RPG info."""
        disp_rect = pygame.Rect(0, 0, WINDOW_WIDTH, 160)
        pygame.draw.rect(self.screen_surf, COLOR_DISPLAY_BG, disp_rect)

        state = self.state

        if state.screen == GameState.SCREEN_MENU:
            self._blit_centered("CAL-CU-ATOR", self.font_large, COLOR_DISPLAY_FG, 40)
            self._blit_centered("[ The RPG Calculator ]", self.font_small, (160, 160, 80), 75)
            self._blit_centered("Press any button to start", self.font_small, (140, 140, 140), 100)
            self._blit_centered(f"XP: {state.player_xp}", self.font_small, (100, 200, 100), 130)

        elif state.screen == GameState.SCREEN_BATTLE:
            # Enemy HP bar
            self._draw_hp_bar(10, 12, WINDOW_WIDTH - 20, 18,
                              state.enemy_hp, state.enemy_max,
                              COLOR_ENEMY_HP, f"{state.enemy_name}")
            # Player HP bar
            self._draw_hp_bar(10, 48, WINDOW_WIDTH - 20, 18,
                              state.player_hp, state.player_max,
                              COLOR_HP_BAR_FG, "Your HP")
            # XP
            xp_surf = self.font_small.render(f"XP: {state.player_xp}", True, (180, 180, 60))
            self.screen_surf.blit(xp_surf, (10, 78))

            # Action log lines
            y_off = 98
            for line in state.log_lines[-4:]:
                surf = self.font_small.render(line, True, COLOR_DISPLAY_FG)
                self.screen_surf.blit(surf, (10, y_off))
                y_off += 16

        elif state.screen in (GameState.SCREEN_EXPLODE, GameState.SCREEN_GAMEOVER):
            self._blit_centered("GAME OVER", self.font_huge, (220, 30, 30), 60)
            self._blit_centered("You exploded.", self.font_mid, (200, 100, 0), 115)
            self._blit_centered("Press C to restart", self.font_small, (160, 160, 160), 145)

        elif state.screen == GameState.SCREEN_VICTORY:
            self._blit_centered("YOU WIN!", self.font_huge, (50, 220, 50), 50)
            self._blit_centered(f"Total XP: {state.player_xp}", self.font_mid, (200, 200, 60), 105)
            self._blit_centered("Press C to play again", self.font_small, (160, 160, 160), 140)

    def _draw_hp_bar(self, x, y, w, h, current, maximum, color, label):
        ratio  = max(0.0, current / maximum) if maximum else 0.0
        # Background
        pygame.draw.rect(self.screen_surf, COLOR_HP_BAR_BG, (x, y, w, h), border_radius=4)
        # Fill
        fill_w = int(w * ratio)
        if fill_w > 0:
            pygame.draw.rect(self.screen_surf, color, (x, y, fill_w, h), border_radius=4)
        # Border
        pygame.draw.rect(self.screen_surf, COLOR_BORDER, (x, y, w, h), 1, border_radius=4)
        # Label
        text = f"{label}: {current}/{maximum}"
        surf = self.font_small.render(text, True, COLOR_DISPLAY_FG)
        self.screen_surf.blit(surf, (x + 4, y + 2))

    def _blit_centered(self, text: str, font: pygame.font.Font, color: tuple, y: int):
        surf = font.render(text, True, color)
        x    = (WINDOW_WIDTH - surf.get_width()) // 2
        self.screen_surf.blit(surf, (x, y))

    def _draw_explosion(self):
        """Draw all live particles onto the screen."""
        for p in self.state.particles:
            p.draw(self.screen_surf)

        # Expanding shockwave rings
        if self.state.explode_start:
            elapsed = time.time() - self.state.explode_start
            for i in range(3):
                ring_t = (elapsed - i * 0.2)
                if 0 < ring_t < 1.0:
                    radius = int(ring_t * 250)
                    alpha  = max(0, int(255 * (1 - ring_t)))
                    color  = (255, max(0, 200 - i*80), 0)
                    pygame.draw.circle(
                        self.screen_surf,
                        color,
                        (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2),
                        radius, 3,
                    )

    # ------------------------------------------------------------------
    # EVENT HANDLING
    # ------------------------------------------------------------------

    def _handle_button_press(self, key: str):
        """Route a button press to the appropriate game logic."""
        state = self.state

        if state.screen == GameState.SCREEN_MENU:
            # Any button starts/continues to the next battle
            state.start_battle()
            self.rpc.update(
                f"Battling {state.enemy_name} — HP: {state.player_hp}",
                "In Combat",
            )

        elif state.screen == GameState.SCREEN_BATTLE:
            if key in ("clear", "allclear"):
                # Clear is treated as retreat / menu (no RPC change yet)
                pass
            state.apply_action(key)

            if state.screen == GameState.SCREEN_BATTLE:
                self.rpc.update(
                    f"Battling {state.enemy_name} — HP: {state.player_hp}",
                    f"Used: {state.last_action}",
                )
            elif state.screen == GameState.SCREEN_MENU:
                # Defeated an enemy, show brief menu before next fight
                self.rpc.update("Enemy defeated! Preparing...", "Between Battles")
            elif state.screen == GameState.SCREEN_EXPLODE:
                self.rpc.update("Lost the game. Exploded.", "Status: GAME OVER")
            elif state.screen == GameState.SCREEN_VICTORY:
                self.rpc.update("Conquered everything!", "Victory!")

        elif state.screen in (GameState.SCREEN_GAMEOVER, GameState.SCREEN_VICTORY):
            if key in ("clear", "allclear", "c", "C"):
                state.reset()
                self.rpc.update("Pretending to work", "Main Menu")

    # ------------------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------------------

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)

            # --- EVENTS ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                # Keyboard shortcuts (handy for testing)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

                # Button clicks
                for btn in self.buttons:
                    if btn.handle_event(event):
                        self._handle_button_press(btn.key)

            # --- EXPLOSION UPDATE ---
            if self.state.screen == GameState.SCREEN_EXPLODE:
                done = self.state.update_explosion()
                if done:
                    self.state.screen = GameState.SCREEN_GAMEOVER

            # --- DRAWING ---
            self.screen_surf.fill(COLOR_BG)
            self._draw_display()
            for btn in self.buttons:
                btn.draw(self.screen_surf, self.font_mid)
            if self.state.screen in (GameState.SCREEN_EXPLODE, GameState.SCREEN_GAMEOVER):
                self._draw_explosion()

            pygame.display.flip()

        # Cleanup
        self.rpc.close()
        pygame.quit()
        sys.exit(0)

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    game = CalcRPG()
    game.run()
