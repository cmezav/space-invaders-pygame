from pathlib import Path
import random

import pygame
from pygame import mixer


# Configuración general
WIDTH = 800
HEIGHT = 600
FPS = 60
HUD_HEIGHT = 68
NUM_ENEMIES = 6

BASE_PLAYER_SPEED = 5
TURBO_PLAYER_SPEED = 10
TURBO_DURATION_MS = 8000
TRANSFORM_DURATION_MS = 1200
POWERUP_FALL_SPEED = 2
EXPLOSION_FRAME_MS = 85

ROOT = Path(__file__).resolve().parent
FONT_PATH = ROOT / "assets" / "fonts" / "PixelifySans.ttf"
EXTRA_DIR = ROOT / "assets" / "sprites_extra"

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
    if FONT_PATH.exists():
        return pygame.font.Font(str(FONT_PATH), size)
    return pygame.font.Font(None, size)


def scale_to_height(image, height):
    """Cambia el tamaño sin deformar la proporción del sprite."""
    width = round(image.get_width() * height / image.get_height())
    return pygame.transform.scale(image, (width, height))


pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Invaders - Pixel Edition")
clock = pygame.time.Clock()

# Recursos
background_source = pygame.image.load(resource("background.jpg")).convert()

# Recorte central a tamaño original: no estira, no deforma y no hace zoom.
crop_width = min(WIDTH, background_source.get_width())
crop_height = min(HEIGHT, background_source.get_height())
crop_x = (background_source.get_width() - crop_width) // 2
crop_y = (background_source.get_height() - crop_height) // 2
background_crop = background_source.subsurface(
    pygame.Rect(crop_x, crop_y, crop_width, crop_height)
).copy()

background = pygame.Surface((WIDTH, HEIGHT))
background.fill(DARK)
background.blit(
    background_crop,
    ((WIDTH - crop_width) // 2, (HEIGHT - crop_height) // 2),
)

icon = pygame.image.load(resource("ufo.png")).convert_alpha()
pygame.display.set_icon(icon)

# Naves y potenciadores nuevos.
small_player_source = pygame.image.load(
    extra_resource("nave_celeste_pequena.png")
).convert_alpha()
upgraded_player_source = pygame.image.load(
    extra_resource("nave_celeste_grande.png")
).convert_alpha()
small_player_img = scale_to_height(small_player_source, 64)
upgraded_player_img = scale_to_height(upgraded_player_source, 88)

flash_img = pygame.transform.scale(
    pygame.image.load(extra_resource("icono_flash.png")).convert_alpha(), (46, 46)
)
question_img = pygame.transform.scale(
    pygame.image.load(extra_resource("icono_pregunta.png")).convert_alpha(), (46, 46)
)

# El orden pequeña -> mediana -> grande crea la expansión del impacto.
explosion_frames = [
    pygame.image.load(extra_resource("explosion_03_pequena.png")).convert_alpha(),
    pygame.image.load(extra_resource("explosion_02_mediana.png")).convert_alpha(),
    pygame.image.load(extra_resource("explosion_01_grande.png")).convert_alpha(),
]

enemy_img = pygame.image.load(resource("enemy.png")).convert_alpha()
enemy_hud_img = pygame.transform.scale(enemy_img, (30, 30))
bullet_img = pygame.image.load(resource("bullet.png")).convert_alpha()

mixer.music.load(resource("background.wav"))
mixer.music.set_volume(0.32)
mixer.music.play(-1)
laser_sound = mixer.Sound(resource("laser.wav"))
explosion_sound = mixer.Sound(resource("explosion.wav"))
laser_sound.set_volume(0.45)
explosion_sound.set_volume(0.45)

font_small = pixel_font(20)
font_hud = pixel_font(30)
font_title = pixel_font(70)
font_subtitle = pixel_font(30)

# Estado del juego
player_center_x = WIDTH // 2
player_bottom = HEIGHT - 40

enemy_x = []
enemy_y = []
enemy_x_change = []
enemy_y_change = []
enemy_speed = 3

bullet_x = 0
bullet_y = 480
bullet_speed = 10
bullet_state = "ready"

score = 0
lives = 3
game_over = False
turbo_until = 0
player_upgraded = False
transform_start = 0
transform_until = 0
explosions = []
powerups = []


def reset_enemy_formation():
    enemy_x.clear()
    enemy_y.clear()
    enemy_x_change.clear()
    enemy_y_change.clear()

    start_x = 205
    gap_x = 165
    for i in range(NUM_ENEMIES):
        row = i // 3
        column = i % 3
        enemy_x.append(start_x + column * gap_x)
        enemy_y.append(105 + row * 82)
        enemy_x_change.append(enemy_speed)
        enemy_y_change.append(34)


def reset_powerups():
    """Los deja visibles pronto para poder probarlos en la presentación."""
    powerups.clear()
    powerups.extend(
        [
            {"kind": "turbo", "x": 165.0, "y": 112.0, "active": True, "respawn": 0},
            {"kind": "upgrade", "x": 590.0, "y": 152.0, "active": True, "respawn": 0},
        ]
    )


def reset_game():
    global player_center_x, bullet_x, bullet_y, bullet_state
    global score, lives, game_over, turbo_until
    global player_upgraded, transform_start, transform_until

    player_center_x = WIDTH // 2
    bullet_x = 0
    bullet_y = 480
    bullet_state = "ready"
    score = 0
    lives = 3
    game_over = False
    turbo_until = 0
    player_upgraded = False
    transform_start = 0
    transform_until = 0
    explosions.clear()
    reset_enemy_formation()
    reset_powerups()


def current_player_image(now):
    """Alterna ambas naves durante 1.2 s para crear el parpadeo."""
    if now < transform_until:
        phase = (now - transform_start) // 100
        return small_player_img if phase % 2 == 0 else upgraded_player_img
    return upgraded_player_img if player_upgraded else small_player_img


def player_rect(now):
    image = current_player_image(now)
    return image.get_rect(midbottom=(round(player_center_x), player_bottom))


def draw_heart(x, y, filled):
    color = RED if filled else (76, 37, 65)
    pygame.draw.circle(screen, color, (x + 7, y + 7), 7)
    pygame.draw.circle(screen, color, (x + 19, y + 7), 7)
    pygame.draw.polygon(
        screen, color, [(x + 1, y + 9), (x + 25, y + 9), (x + 13, y + 24)]
    )
    highlight = (255, 150, 163) if filled else (108, 55, 89)
    pygame.draw.rect(screen, highlight, (x + 5, y + 4, 4, 4))


def draw_hud(now):
    hud = pygame.Surface((WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
    hud.fill((9, 2, 27, 226))
    screen.blit(hud, (0, 0))
    pygame.draw.line(
        screen, (80, 38, 121), (0, HUD_HEIGHT - 1), (WIDTH, HUD_HEIGHT - 1), 2
    )

    for index in range(3):
        draw_heart(16 + index * 34, 20, index < lives)

    screen.blit(enemy_hud_img, (337, 18))
    enemy_count = font_hud.render(f"x{NUM_ENEMIES:02d}", True, GREEN)
    screen.blit(enemy_count, (374, 17))

    pygame.draw.circle(screen, YELLOW, (665, 34), 11)
    pygame.draw.circle(screen, (255, 238, 137), (662, 30), 3)
    score_text = font_hud.render(f"{score:04d}", True, YELLOW)
    screen.blit(score_text, (688, 16))

    if now < turbo_until:
        seconds = max(1, (turbo_until - now + 999) // 1000)
        badge = pygame.Surface((150, 34), pygame.SRCALPHA)
        badge.fill((9, 2, 27, 215))
        screen.blit(badge, (12, HUD_HEIGHT + 8))
        screen.blit(pygame.transform.scale(flash_img, (28, 28)), (16, HUD_HEIGHT + 11))
        turbo_text = font_small.render(f"TURBO {seconds}s", True, YELLOW)
        screen.blit(turbo_text, (49, HUD_HEIGHT + 13))

    if player_upgraded:
        badge = pygame.Surface((158, 34), pygame.SRCALPHA)
        badge.fill((9, 2, 27, 215))
        screen.blit(badge, (WIDTH - 170, HUD_HEIGHT + 8))
        screen.blit(
            pygame.transform.scale(question_img, (28, 28)),
            (WIDTH - 166, HUD_HEIGHT + 11),
        )
        upgrade_text = font_small.render("NAVE +", True, PURPLE)
        screen.blit(upgrade_text, (WIDTH - 130, HUD_HEIGHT + 13))


def draw_footer():
    footer = pygame.Surface((WIDTH, 30), pygame.SRCALPHA)
    footer.fill((9, 2, 27, 205))
    screen.blit(footer, (0, HEIGHT - 30))
    controls = font_small.render(
        "FLECHAS: MOVER   ESPACIO: DISPARAR   ESC: SALIR", True, WHITE
    )
    screen.blit(controls, controls.get_rect(center=(WIDTH // 2, HEIGHT - 16)))


def draw_player(now):
    image = current_player_image(now)
    rect = image.get_rect(midbottom=(round(player_center_x), player_bottom))

    if now < transform_until and ((now - transform_start) // 70) % 2 == 0:
        glow = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (220, 245, 255, 92), glow.get_rect())
        screen.blit(glow, glow.get_rect(center=rect.center))

    screen.blit(image, rect)


def draw_enemy(index):
    screen.blit(enemy_img, (enemy_x[index], enemy_y[index]))


def draw_bullet():
    shot_rect = bullet_img.get_rect(midbottom=(round(bullet_x), round(bullet_y)))
    screen.blit(bullet_img, shot_rect)
    for offset, size in ((8, 5), (20, 4), (31, 3), (41, 2)):
        pygame.draw.rect(
            screen,
            CYAN,
            (round(bullet_x - size / 2), round(bullet_y + offset), size, size),
        )


def get_bullet_rect():
    return bullet_img.get_rect(midbottom=(round(bullet_x), round(bullet_y)))


def draw_powerups():
    for powerup in powerups:
        if not powerup["active"]:
            continue
        image = flash_img if powerup["kind"] == "turbo" else question_img
        screen.blit(image, (round(powerup["x"]), round(powerup["y"])))


def update_powerups(now, ship_rect):
    global turbo_until, player_upgraded, transform_start, transform_until

    for powerup in powerups:
        if not powerup["active"]:
            if powerup["kind"] == "turbo" and now >= powerup["respawn"]:
                powerup.update(
                    x=float(random.randint(50, WIDTH - 96)),
                    y=float(HUD_HEIGHT + 10),
                    active=True,
                )
            elif (
                powerup["kind"] == "upgrade"
                and not player_upgraded
                and now >= powerup["respawn"]
            ):
                powerup.update(
                    x=float(random.randint(50, WIDTH - 96)),
                    y=float(HUD_HEIGHT + 10),
                    active=True,
                )
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
                transform_start = now
                transform_until = now + TRANSFORM_DURATION_MS
            continue

        if powerup["y"] > HEIGHT:
            powerup["active"] = False
            powerup["respawn"] = now + 1800


def add_explosion(center, now):
    explosions.append({"center": center, "start": now})


def draw_and_update_explosions(now):
    active_explosions = []
    for explosion in explosions:
        frame_index = (now - explosion["start"]) // EXPLOSION_FRAME_MS
        if frame_index < len(explosion_frames):
            frame = explosion_frames[frame_index]
            rect = frame.get_rect(center=explosion["center"])
            screen.blit(frame, rect)
            active_explosions.append(explosion)
    explosions[:] = active_explosions


def draw_game_over():
    panel = pygame.Surface((560, 210), pygame.SRCALPHA)
    panel.fill((12, 3, 34, 238))
    pygame.draw.rect(panel, PURPLE, panel.get_rect(), 4)
    screen.blit(panel, (120, 190))

    title = font_title.render("GAME OVER", True, RED)
    subtitle = font_subtitle.render("PRESIONA R PARA REINICIAR", True, WHITE)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 265)))
    screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 345)))


def lose_life():
    global lives, bullet_y, bullet_state, game_over
    lives -= 1
    bullet_y = 480
    bullet_state = "ready"
    if lives <= 0:
        game_over = True
    else:
        reset_enemy_formation()


reset_game()
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
            elif event.key == pygame.K_r and game_over:
                reset_game()
            elif event.key == pygame.K_SPACE and bullet_state == "ready" and not game_over:
                bullet_x = player_center_x
                bullet_y = player_rect(now).top
                bullet_state = "fire"
                laser_sound.play()

    screen.blit(background, (0, 0))

    if not game_over:
        active_speed = TURBO_PLAYER_SPEED if now < turbo_until else BASE_PLAYER_SPEED
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player_center_x -= active_speed
        if keys[pygame.K_RIGHT]:
            player_center_x += active_speed

        ship_image = current_player_image(now)
        half_width = ship_image.get_width() / 2
        player_center_x = max(half_width, min(player_center_x, WIDTH - half_width))
        ship_rect = player_rect(now)

        update_powerups(now, ship_rect)
        draw_powerups()

        life_was_lost = False
        for i in range(NUM_ENEMIES):
            enemy_x[i] += enemy_x_change[i]

            if enemy_x[i] <= 0:
                enemy_x[i] = 0
                enemy_x_change[i] = enemy_speed
                enemy_y[i] += enemy_y_change[i]
            elif enemy_x[i] >= WIDTH - enemy_img.get_width():
                enemy_x[i] = WIDTH - enemy_img.get_width()
                enemy_x_change[i] = -enemy_speed
                enemy_y[i] += enemy_y_change[i]

            if enemy_y[i] > 435:
                lose_life()
                life_was_lost = True
                break

            enemy_rect = enemy_img.get_rect(
                topleft=(round(enemy_x[i]), round(enemy_y[i]))
            )
            if bullet_state == "fire" and enemy_rect.colliderect(get_bullet_rect()):
                impact_center = enemy_rect.center
                explosion_sound.play()
                add_explosion(impact_center, now)
                bullet_y = 480
                bullet_state = "ready"
                score += 10
                enemy_x[i] = random.randint(40, WIDTH - 104)
                enemy_y[i] = random.randint(105, 175)

            draw_enemy(i)

        if not life_was_lost and bullet_state == "fire":
            draw_bullet()
            bullet_y -= bullet_speed
            if bullet_y <= -bullet_img.get_height():
                bullet_y = 480
                bullet_state = "ready"

        draw_and_update_explosions(now)
        draw_player(now)
    else:
        for i in range(NUM_ENEMIES):
            if enemy_y[i] < HEIGHT:
                draw_enemy(i)
        draw_and_update_explosions(now)
        draw_player(now)
        draw_game_over()

    draw_hud(now)
    draw_footer()
    pygame.display.flip()

pygame.quit()
