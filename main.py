from pathlib import Path
import json
import math
import random

import pygame
from pygame import mixer


WIDTH, HEIGHT, FPS = 800, 600, 60
HUD_HEIGHT = 68
BASE_PLAYER_SPEED = 5
TURBO_PLAYER_SPEED = 10
TURBO_DURATION_MS = 8000
UPGRADE_DURATION_MS = 10000
TRANSFORM_DURATION_MS = 1200
POWERUP_FALL_SPEED = 2
EXPLOSION_FRAME_MS = 85
NORMAL_SHOT_COOLDOWN_MS = 240
UPGRADE_SHOT_COOLDOWN_MS = 650
BLAST_RADIUS = 115
PLAYER_INVINCIBILITY_MS = 1500
SHAKE_DURATION_MS = 320
ENEMY_BULLET_SPEED = 5

ROOT = Path(__file__).resolve().parent
FONT_PATH = ROOT / "assets" / "fonts" / "PixelifySans.ttf"
EXTRA_DIR = ROOT / "assets" / "sprites_extra"
HIGH_SCORE_PATH = ROOT / "highscore.json"

DIFFICULTIES = [
    {"name": "FÁCIL", "speed": 0.80, "fire": 1.35},
    {"name": "NORMAL", "speed": 1.00, "fire": 1.00},
    {"name": "DIFÍCIL", "speed": 1.25, "fire": 0.72},
]

WHITE = (245, 245, 255)
GREEN = (108, 255, 107)
CYAN = (76, 226, 255)
YELLOW = (255, 215, 77)
RED = (255, 62, 89)
PURPLE = (181, 94, 255)
DARK = (10, 3, 28)


def resource(name):
    return str(ROOT / name)


def extra_resource(name):
    return str(EXTRA_DIR / name)


def pixel_font(size):
    return pygame.font.Font(str(FONT_PATH), size) if FONT_PATH.exists() else pygame.font.Font(None, size)


def scale_to_height(image, height):
    width = round(image.get_width() * height / image.get_height())
    return pygame.transform.scale(image, (width, height))


pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Invaders - Pixel Edition")
pygame.display.set_icon(pygame.image.load(resource("ufo.png")))
clock = pygame.time.Clock()

# Fondo recortado al centro, sin deformarlo ni ampliarlo.
background_source = pygame.image.load(resource("background.jpg")).convert()
crop_width = min(WIDTH, background_source.get_width())
crop_height = min(HEIGHT, background_source.get_height())
crop_x = (background_source.get_width() - crop_width) // 2
crop_y = (background_source.get_height() - crop_height) // 2
background_crop = background_source.subsurface(
    pygame.Rect(crop_x, crop_y, crop_width, crop_height)
).copy()
background = pygame.Surface((WIDTH, HEIGHT))
background.fill(DARK)
background.blit(background_crop, ((WIDTH - crop_width) // 2, (HEIGHT - crop_height) // 2))

small_player_img = scale_to_height(
    pygame.image.load(extra_resource("nave_celeste_pequena.png")).convert_alpha(), 64
)
upgraded_player_img = scale_to_height(
    pygame.image.load(extra_resource("nave_celeste_grande.png")).convert_alpha(), 88
)
flash_img = pygame.transform.scale(
    pygame.image.load(extra_resource("icono_flash.png")).convert_alpha(), (46, 46)
)
question_img = pygame.transform.scale(
    pygame.image.load(extra_resource("icono_pregunta.png")).convert_alpha(), (46, 46)
)

# Ahora sí se usan los tres enemigos del paquete de sprites.
enemy_images = [
    pygame.image.load(extra_resource("enemigo_01_verde.png")).convert_alpha(),
    pygame.image.load(extra_resource("enemigo_02_celeste.png")).convert_alpha(),
    pygame.image.load(extra_resource("enemigo_03_morado.png")).convert_alpha(),
]
enemy_hud_img = pygame.transform.scale(enemy_images[0], (30, 30))
bullet_img = pygame.image.load(resource("bullet.png")).convert_alpha()
explosion_frames = [
    pygame.image.load(extra_resource("explosion_03_pequena.png")).convert_alpha(),
    pygame.image.load(extra_resource("explosion_02_mediana.png")).convert_alpha(),
    pygame.image.load(extra_resource("explosion_01_grande.png")).convert_alpha(),
]

mixer.music.load(resource("background.wav"))
mixer.music.set_volume(0.32)
mixer.music.play(-1)
laser_sound = mixer.Sound(resource("laser.wav"))
explosion_sound = mixer.Sound(resource("explosion.wav"))
laser_sound.set_volume(0.45)
explosion_sound.set_volume(0.45)
# Pulso muy suave que se repite más rápido cuando quedan pocos invasores.
tension_sound = mixer.Sound(resource("laser.wav"))
tension_sound.set_volume(0.07)

font_small = pixel_font(20)
font_hud = pixel_font(30)
font_title = pixel_font(66)
font_subtitle = pixel_font(30)


def load_high_score():
    try:
        data = json.loads(HIGH_SCORE_PATH.read_text(encoding="utf-8"))
        return max(0, int(data.get("score", 0))), str(data.get("initials", "---"))[:3].upper()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0, "---"


def save_high_score():
    data = {"score": high_score, "initials": high_initials}
    HIGH_SCORE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

player_center_x = WIDTH // 2
player_bottom = HEIGHT - 40
bullet_x, bullet_y = 0, 480
bullet_speed = 10
bullet_state = "ready"
bullet_explosive = False
last_shot_at = -1000

score = 0
lives = 3
level = 1
game_state = "menu"
state_until = 0
difficulty_index = 1
high_score, high_initials = load_high_score()
initials_input = ""
pause_started = 0

enemies = []
wave_enemy_count = 0
formation_direction = 1
enemy_bullets = []
last_enemy_shot_at = 0
next_tension_beat = 0
turbo_until = 0
upgrade_until = 0
player_upgraded = False
transform_start = 0
transform_until = 0
invincible_until = 0
shake_until = 0
explosions = []
blast_effects = []
floating_texts = []
powerups = []


def current_player_image(now):
    if now < transform_until:
        return small_player_img if ((now - transform_start) // 100) % 2 == 0 else upgraded_player_img
    return upgraded_player_img if player_upgraded else small_player_img


def player_rect(now):
    return current_player_image(now).get_rect(midbottom=(round(player_center_x), player_bottom))


def create_wave():
    """Cada nivel agrega enemigos y aumenta 0.5 la velocidad base."""
    global enemies, wave_enemy_count, formation_direction
    global last_enemy_shot_at, next_tension_beat
    count = min(6 + (level - 1) * 2, 18)
    columns = min(6, count)
    rows = (count + columns - 1) // columns
    gap_x, gap_y = 105, 72
    formation_width = (columns - 1) * gap_x + 61
    start_x = (WIDTH - formation_width) // 2

    enemies = []
    for index in range(count):
        row, column = divmod(index, columns)
        image_index = (row + column) % len(enemy_images)
        enemies.append(
            {
                "x": float(start_x + column * gap_x),
                "y": float(105 + row * gap_y),
                "image": image_index,
            }
        )
    wave_enemy_count = len(enemies)
    formation_direction = 1
    enemy_bullets.clear()
    last_enemy_shot_at = pygame.time.get_ticks()
    next_tension_beat = pygame.time.get_ticks()


def reset_powerups():
    powerups.clear()
    powerups.extend(
        [
            {"kind": "turbo", "x": 165.0, "y": 112.0, "active": True, "respawn": 0},
            {"kind": "upgrade", "x": 590.0, "y": 152.0, "active": True, "respawn": 0},
        ]
    )


def reset_game():
    global player_center_x, bullet_x, bullet_y, bullet_state
    global score, lives, level, game_state, state_until
    global turbo_until, upgrade_until, player_upgraded, transform_start, transform_until
    global bullet_explosive, last_shot_at
    global invincible_until, shake_until
    global initials_input, pause_started

    player_center_x = WIDTH // 2
    bullet_x, bullet_y = 0, 480
    bullet_state = "ready"
    score, lives, level = 0, 3, 1
    game_state = "playing"
    state_until = 0
    turbo_until = 0
    upgrade_until = 0
    player_upgraded = False
    transform_start = transform_until = 0
    invincible_until = shake_until = 0
    initials_input = ""
    pause_started = 0
    bullet_explosive = False
    last_shot_at = -1000
    explosions.clear()
    blast_effects.clear()
    floating_texts.clear()
    enemy_bullets.clear()
    create_wave()
    reset_powerups()


def draw_heart(x, y, filled):
    color = RED if filled else (76, 37, 65)
    pygame.draw.circle(screen, color, (x + 7, y + 7), 7)
    pygame.draw.circle(screen, color, (x + 19, y + 7), 7)
    pygame.draw.polygon(screen, color, [(x + 1, y + 9), (x + 25, y + 9), (x + 13, y + 24)])
    pygame.draw.rect(screen, (255, 150, 163) if filled else (108, 55, 89), (x + 5, y + 4, 4, 4))


def draw_hud(now):
    hud = pygame.Surface((WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
    hud.fill((9, 2, 27, 226))
    screen.blit(hud, (0, 0))
    pygame.draw.line(screen, (80, 38, 121), (0, HUD_HEIGHT - 1), (WIDTH, HUD_HEIGHT - 1), 2)
    for index in range(3):
        draw_heart(16 + index * 34, 20, index < lives)

    screen.blit(enemy_hud_img, (315, 18))
    screen.blit(font_hud.render(f"x{len(enemies):02d}", True, GREEN), (351, 17))
    screen.blit(font_small.render(f"NV.{level}", True, CYAN), (433, 24))
    pygame.draw.circle(screen, YELLOW, (665, 34), 11)
    pygame.draw.circle(screen, (255, 238, 137), (662, 30), 3)
    screen.blit(font_hud.render(f"{score:04d}", True, YELLOW), (688, 16))

    if now < turbo_until:
        seconds = max(1, (turbo_until - now + 999) // 1000)
        draw_badge(12, flash_img, f"TURBO {seconds}s", YELLOW)
    if player_upgraded:
        seconds = max(1, (upgrade_until - now + 999) // 1000)
        draw_badge(WIDTH - 182, question_img, f"MEGA {seconds}s", PURPLE)


def draw_badge(x, image, text, color):
    badge = pygame.Surface((158, 34), pygame.SRCALPHA)
    badge.fill((9, 2, 27, 215))
    screen.blit(badge, (x, HUD_HEIGHT + 8))
    screen.blit(pygame.transform.scale(image, (28, 28)), (x + 4, HUD_HEIGHT + 11))
    screen.blit(font_small.render(text, True, color), (x + 37, HUD_HEIGHT + 13))


def draw_footer():
    footer = pygame.Surface((WIDTH, 30), pygame.SRCALPHA)
    footer.fill((9, 2, 27, 205))
    screen.blit(footer, (0, HEIGHT - 30))
    text = font_small.render("FLECHAS: MOVER   ESPACIO: DISPARAR   P: PAUSA   ESC: SALIR", True, WHITE)
    screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT - 16)))


def draw_player(now):
    image = current_player_image(now)
    rect = image.get_rect(midbottom=(round(player_center_x), player_bottom))
    if now < transform_until and ((now - transform_start) // 70) % 2 == 0:
        glow = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (220, 245, 255, 92), glow.get_rect())
        screen.blit(glow, glow.get_rect(center=rect.center))
    # Tras recibir daño parpadea: durante este tiempo no puede perder otra vida.
    if now >= invincible_until or ((now // 90) % 2 == 0):
        screen.blit(image, rect)


def get_bullet_rect():
    return bullet_img.get_rect(midbottom=(round(bullet_x), round(bullet_y)))


def draw_bullet():
    screen.blit(bullet_img, get_bullet_rect())
    trail_color = PURPLE if bullet_explosive else CYAN
    if bullet_explosive:
        pygame.draw.circle(screen, PURPLE, (round(bullet_x), round(bullet_y) - 8), 12, 2)
    for offset, size in ((8, 5), (20, 4), (31, 3), (41, 2)):
        pygame.draw.rect(screen, trail_color, (round(bullet_x - size / 2), round(bullet_y + offset), size, size))


def update_enemies():
    global formation_direction
    if not enemies:
        return False

    remaining_ratio = len(enemies) / max(1, wave_enemy_count)
    base_speed = 2.0 + (level - 1) * 0.5
    speed = base_speed * DIFFICULTIES[difficulty_index]["speed"]
    speed *= 1.0 + (1.0 - remaining_ratio) * 0.85
    movement = speed * formation_direction
    for enemy in enemies:
        enemy["x"] += movement

    left = min(enemy["x"] for enemy in enemies)
    right = max(enemy["x"] + enemy_images[enemy["image"]].get_width() for enemy in enemies)
    if left <= 8 or right >= WIDTH - 8:
        formation_direction *= -1
        for enemy in enemies:
            enemy["x"] = max(8, min(enemy["x"], WIDTH - enemy_images[enemy["image"]].get_width() - 8))
            enemy["y"] += 28

    return any(enemy["y"] > 430 for enemy in enemies)


def draw_enemies():
    for enemy in enemies:
        screen.blit(enemy_images[enemy["image"]], (round(enemy["x"]), round(enemy["y"])))


def enemy_rect(enemy):
    image = enemy_images[enemy["image"]]
    return image.get_rect(topleft=(round(enemy["x"]), round(enemy["y"])))


def update_enemy_attack(now, ship_rect):
    """Un invasor aleatorio dispara hacia abajo y obliga al jugador a esquivar."""
    global last_enemy_shot_at
    if enemies:
        remaining_ratio = len(enemies) / max(1, wave_enemy_count)
        interval = (720 + round(remaining_ratio * 650)) * DIFFICULTIES[difficulty_index]["fire"]
        if now - last_enemy_shot_at >= interval:
            shooter = random.choice(enemies)
            origin = enemy_rect(shooter)
            enemy_bullets.append({"x": float(origin.centerx), "y": float(origin.bottom)})
            last_enemy_shot_at = now + random.randint(-120, 160)

    active = []
    player_was_hit = False
    for shot in enemy_bullets:
        shot["y"] += ENEMY_BULLET_SPEED
        rect = pygame.Rect(round(shot["x"] - 3), round(shot["y"]), 6, 16)
        if rect.colliderect(ship_rect) and now >= invincible_until:
            player_was_hit = True
        elif shot["y"] < HEIGHT - 28:
            active.append(shot)
    enemy_bullets[:] = active
    if player_was_hit:
        hit_player(now, False)


def draw_enemy_bullets():
    for shot in enemy_bullets:
        x, y = round(shot["x"]), round(shot["y"])
        pygame.draw.rect(screen, RED, (x - 3, y, 6, 14))
        pygame.draw.rect(screen, YELLOW, (x - 1, y + 3, 2, 7))


def draw_powerups():
    for powerup in powerups:
        if powerup["active"]:
            image = flash_img if powerup["kind"] == "turbo" else question_img
            screen.blit(image, (round(powerup["x"]), round(powerup["y"])))


def update_powerups(now, ship_rect):
    global turbo_until, upgrade_until, player_upgraded, transform_start, transform_until
    for powerup in powerups:
        if not powerup["active"]:
            if powerup["kind"] == "turbo" and now >= powerup["respawn"]:
                powerup.update(x=float(random.randint(50, WIDTH - 96)), y=float(HUD_HEIGHT + 10), active=True)
            elif (
                powerup["kind"] == "upgrade"
                and not player_upgraded
                and now >= transform_until
                and now >= powerup["respawn"]
            ):
                powerup.update(x=float(random.randint(50, WIDTH - 96)), y=float(HUD_HEIGHT + 10), active=True)
            continue

        powerup["y"] += POWERUP_FALL_SPEED
        image = flash_img if powerup["kind"] == "turbo" else question_img
        item_rect = image.get_rect(topleft=(round(powerup["x"]), round(powerup["y"])))
        if item_rect.colliderect(ship_rect):
            powerup["active"] = False
            if powerup["kind"] == "turbo":
                turbo_until = now + TURBO_DURATION_MS
                powerup["respawn"] = turbo_until + 2500
            else:
                player_upgraded = True
                upgrade_until = now + UPGRADE_DURATION_MS
                transform_start = now
                transform_until = now + TRANSFORM_DURATION_MS
                powerup["respawn"] = upgrade_until + 3500
        elif powerup["y"] > HEIGHT:
            powerup["active"] = False
            powerup["respawn"] = now + 1800


def add_explosion(center, now):
    explosions.append({"center": center, "start": now})


def draw_explosions(now):
    active = []
    for explosion in explosions:
        index = (now - explosion["start"]) // EXPLOSION_FRAME_MS
        if index < len(explosion_frames):
            frame = explosion_frames[index]
            screen.blit(frame, frame.get_rect(center=explosion["center"]))
            active.append(explosion)
    explosions[:] = active


def add_blast(center, now):
    blast_effects.append({"center": center, "start": now})


def draw_blasts(now):
    """Expande un aro que permite entender el alcance del disparo mejorado."""
    active = []
    for blast in blast_effects:
        elapsed = now - blast["start"]
        if elapsed < 360:
            progress = elapsed / 360
            radius = max(8, round(BLAST_RADIUS * progress))
            alpha = round(210 * (1 - progress))
            layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*PURPLE, alpha), blast["center"], radius, 3)
            pygame.draw.circle(layer, (*CYAN, alpha // 2), blast["center"], max(3, radius - 8), 2)
            screen.blit(layer, (0, 0))
            active.append(blast)
    blast_effects[:] = active


def destroy_enemies_at_impact(direct_hit, center, explosive, now):
    """La nave grande daña también a enemigos dentro de 115 píxeles."""
    global score
    defeated = []
    for enemy in enemies:
        target_center = enemy_rect(enemy).center
        in_radius = math.hypot(target_center[0] - center[0], target_center[1] - center[1]) <= BLAST_RADIUS
        if enemy is direct_hit or (explosive and in_radius):
            defeated.append(enemy)

    for enemy in defeated:
        enemies.remove(enemy)
        defeated_center = enemy_rect(enemy).center
        add_explosion(defeated_center, now)
        floating_texts.append({"text": "+10", "center": defeated_center, "start": now})
        score += 10

    if explosive:
        add_blast(center, now)
    return len(defeated)


def draw_floating_texts(now):
    active = []
    for item in floating_texts:
        elapsed = now - item["start"]
        if elapsed < 720:
            progress = elapsed / 720
            label = font_small.render(item["text"], True, YELLOW)
            label.set_alpha(round(255 * (1 - progress)))
            x, y = item["center"]
            screen.blit(label, label.get_rect(center=(x, y - round(progress * 38))))
            active.append(item)
    floating_texts[:] = active


def update_music_tension(now):
    """Añade un pulso al soundtrack cuya frecuencia aumenta al caer enemigos."""
    global next_tension_beat
    if not enemies:
        return
    remaining_ratio = len(enemies) / max(1, wave_enemy_count)
    interval = 180 + round(remaining_ratio * 620)
    if now >= next_tension_beat:
        tension_sound.play()
        next_tension_beat = now + interval


def shift_timers_after_pause(delta):
    """Evita que los potenciadores y animaciones expiren mientras está pausado."""
    global turbo_until, upgrade_until, transform_start, transform_until
    global invincible_until, shake_until, last_shot_at, last_enemy_shot_at
    global next_tension_beat, state_until
    turbo_until += delta
    upgrade_until += delta
    transform_start += delta
    transform_until += delta
    invincible_until += delta
    shake_until += delta
    last_shot_at += delta
    last_enemy_shot_at += delta
    next_tension_beat += delta
    state_until += delta
    for collection in (explosions, blast_effects, floating_texts):
        for item in collection:
            item["start"] += delta
    for powerup in powerups:
        if not powerup["active"]:
            powerup["respawn"] += delta


def finish_game():
    global game_state, initials_input
    if score > high_score:
        initials_input = ""
        game_state = "initials"
    else:
        game_state = "game_over"


def hit_player(now, formation_breached):
    global lives, bullet_state, bullet_y, bullet_explosive, game_state
    global invincible_until, shake_until, player_center_x
    if now < invincible_until:
        return
    lives -= 1
    bullet_state, bullet_y = "ready", 480
    bullet_explosive = False
    enemy_bullets.clear()
    invincible_until = now + PLAYER_INVINCIBILITY_MS
    shake_until = now + SHAKE_DURATION_MS
    player_center_x = WIDTH // 2
    if lives <= 0:
        finish_game()
    elif formation_breached:
        create_wave()


def draw_center_panel(title, subtitle, color):
    panel = pygame.Surface((600, 210), pygame.SRCALPHA)
    panel.fill((12, 3, 34, 238))
    pygame.draw.rect(panel, color, panel.get_rect(), 4)
    screen.blit(panel, (100, 190))
    heading = font_title.render(title, True, color)
    detail = font_subtitle.render(subtitle, True, WHITE)
    screen.blit(heading, heading.get_rect(center=(WIDTH // 2, 265)))
    screen.blit(detail, detail.get_rect(center=(WIDTH // 2, 345)))


def draw_start_screen(real_now):
    offset_y = round(math.sin(real_now / 380) * 8)
    title = font_title.render("SPACE INVADERS", True, CYAN)
    shadow = font_title.render("SPACE INVADERS", True, PURPLE)
    title_rect = title.get_rect(center=(WIDTH // 2, 148 + offset_y))
    screen.blit(shadow, title_rect.move(4, 5))
    screen.blit(title, title_rect)

    for index, image in enumerate(enemy_images):
        screen.blit(image, image.get_rect(center=(320 + index * 80, 235)))

    difficulty = DIFFICULTIES[difficulty_index]["name"]
    box = pygame.Surface((420, 72), pygame.SRCALPHA)
    box.fill((12, 3, 34, 225))
    pygame.draw.rect(box, PURPLE, box.get_rect(), 3)
    screen.blit(box, (190, 285))
    selector = font_subtitle.render(f"<  {difficulty}  >", True, YELLOW)
    screen.blit(selector, selector.get_rect(center=(WIDTH // 2, 321)))

    record = font_small.render(f"RÉCORD: {high_initials}  {high_score:04d}", True, GREEN)
    start = font_subtitle.render("PRESIONA ENTER PARA JUGAR", True, WHITE)
    hint = font_small.render("IZQUIERDA / DERECHA: DIFICULTAD", True, CYAN)
    screen.blit(record, record.get_rect(center=(WIDTH // 2, 397)))
    screen.blit(start, start.get_rect(center=(WIDTH // 2, 455)))
    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 502)))


def draw_initials_screen():
    panel = pygame.Surface((610, 250), pygame.SRCALPHA)
    panel.fill((12, 3, 34, 242))
    pygame.draw.rect(panel, YELLOW, panel.get_rect(), 4)
    screen.blit(panel, (95, 165))
    title = font_title.render("¡NUEVO RÉCORD!", True, YELLOW)
    prompt = font_subtitle.render("ESCRIBE TUS 3 INICIALES", True, WHITE)
    slots = " ".join(list(initials_input.ljust(3, "_")))
    initials = font_title.render(slots, True, CYAN)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 222)))
    screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, 290)))
    screen.blit(initials, initials.get_rect(center=(WIDTH // 2, 360)))


reset_game()
game_state = "menu"
running = True

while running:
    clock.tick(FPS)
    now = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif game_state == "menu":
                if event.key == pygame.K_LEFT:
                    difficulty_index = (difficulty_index - 1) % len(DIFFICULTIES)
                elif event.key == pygame.K_RIGHT:
                    difficulty_index = (difficulty_index + 1) % len(DIFFICULTIES)
                elif event.key == pygame.K_RETURN:
                    reset_game()
            elif game_state == "initials":
                if event.key == pygame.K_BACKSPACE:
                    initials_input = initials_input[:-1]
                elif event.key == pygame.K_RETURN and len(initials_input) == 3:
                    high_score = score
                    high_initials = initials_input
                    save_high_score()
                    game_state = "game_over"
                elif event.unicode and event.unicode.upper() in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    if len(initials_input) < 3:
                        initials_input += event.unicode.upper()
            elif event.key == pygame.K_p and game_state == "playing":
                pause_started = now
                game_state = "paused"
                mixer.music.pause()
            elif event.key == pygame.K_p and game_state == "paused":
                shift_timers_after_pause(now - pause_started)
                game_state = "playing"
                mixer.music.unpause()
            elif event.key == pygame.K_r and game_state == "game_over":
                reset_game()
            elif event.key == pygame.K_SPACE and bullet_state == "ready" and game_state == "playing":
                shot_cooldown = UPGRADE_SHOT_COOLDOWN_MS if player_upgraded else NORMAL_SHOT_COOLDOWN_MS
                if now - last_shot_at >= shot_cooldown:
                    bullet_x = player_center_x
                    bullet_y = player_rect(now).top
                    bullet_state = "fire"
                    bullet_explosive = player_upgraded
                    last_shot_at = now
                    laser_sound.play()

    if game_state == "level_clear" and now >= state_until:
        level += 1
        create_wave()
        game_state = "playing"

    if game_state == "playing" and player_upgraded and now >= upgrade_until:
        player_upgraded = False
        transform_start = now
        transform_until = now + TRANSFORM_DURATION_MS

    screen.blit(background, (0, 0))

    if game_state == "playing":
        active_speed = TURBO_PLAYER_SPEED if now < turbo_until else BASE_PLAYER_SPEED
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player_center_x -= active_speed
        if keys[pygame.K_RIGHT]:
            player_center_x += active_speed
        half_width = current_player_image(now).get_width() / 2
        player_center_x = max(half_width, min(player_center_x, WIDTH - half_width))

        update_powerups(now, player_rect(now))
        if update_enemies():
            hit_player(now, True)

        if game_state == "playing":
            update_enemy_attack(now, player_rect(now))
            update_music_tension(now)

        if bullet_state == "fire":
            bullet_y -= bullet_speed
            shot = get_bullet_rect()
            hit_index = next((i for i, enemy in enumerate(enemies) if shot.colliderect(enemy_rect(enemy))), None)
            if hit_index is not None:
                direct_hit = enemies[hit_index]
                impact_center = enemy_rect(direct_hit).center
                destroy_enemies_at_impact(direct_hit, impact_center, bullet_explosive, now)
                explosion_sound.play()
                bullet_state, bullet_y = "ready", 480
                bullet_explosive = False
                if not enemies:
                    game_state = "level_clear"
                    state_until = now + 1600
            elif bullet_y <= -bullet_img.get_height():
                bullet_state, bullet_y = "ready", 480
                bullet_explosive = False

    if game_state == "menu":
        draw_start_screen(now)
    else:
        display_now = pause_started if game_state == "paused" else now
        draw_powerups()
        draw_enemies()
        draw_enemy_bullets()
        if bullet_state == "fire":
            draw_bullet()
        draw_explosions(display_now)
        draw_blasts(display_now)
        draw_floating_texts(display_now)
        draw_player(display_now)

        if game_state == "level_clear":
            draw_center_panel("¡NIVEL SUPERADO!", f"PREPARANDO OLEADA {level + 1}", GREEN)
        elif game_state == "paused":
            draw_center_panel("PAUSA", "PRESIONA P PARA CONTINUAR", CYAN)
        elif game_state == "initials":
            draw_initials_screen()
        elif game_state == "game_over":
            draw_center_panel("GAME OVER", "PRESIONA R PARA REINICIAR", RED)

        draw_hud(display_now)
        draw_footer()

        if display_now < shake_until:
            snapshot = screen.copy()
            offset = (random.randint(-7, 7), random.randint(-5, 5))
            screen.fill(DARK)
            screen.blit(snapshot, offset)
    pygame.display.flip()

pygame.quit()
