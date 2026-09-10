from pathlib import Path
import math
import random

import pygame
from pygame import mixer


WIDTH = 800
HEIGHT = 600
FPS = 60
HUD_HEIGHT = 68
NUM_ENEMIES = 6

ROOT = Path(__file__).resolve().parent
FONT_PATH = ROOT / "assets" / "fonts" / "PixelifySans.ttf"

WHITE = (245, 245, 255)
GREEN = (108, 255, 107)
CYAN = (76, 226, 255)
YELLOW = (255, 215, 77)
RED = (255, 62, 89)
PURPLE = (181, 94, 255)
DARK = (10, 3, 28)


def resource(name):
    return str(ROOT / name)


def pixel_font(size):
    if FONT_PATH.exists():
        return pygame.font.Font(str(FONT_PATH), size)

    return pygame.font.Font(None, size)


pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Invaders - Pixel Edition")
clock = pygame.time.Clock()


# Fondo recortado sin deformación, escalado ni zoom.
background_source = pygame.image.load(
    resource("background.jpg")
).convert()

crop_width = min(WIDTH, background_source.get_width())
crop_height = min(HEIGHT, background_source.get_height())

crop_x = (
    background_source.get_width() - crop_width
) // 2

crop_y = (
    background_source.get_height() - crop_height
) // 2

background_crop = background_source.subsurface(
    pygame.Rect(
        crop_x,
        crop_y,
        crop_width,
        crop_height
    )
).copy()

background = pygame.Surface((WIDTH, HEIGHT))
background.fill(DARK)

background.blit(
    background_crop,
    (
        (WIDTH - crop_width) // 2,
        (HEIGHT - crop_height) // 2
    )
)


# Recursos gráficos
icon = pygame.image.load(
    resource("ufo.png")
).convert_alpha()

pygame.display.set_icon(icon)

player_img = pygame.image.load(
    resource("player.png")
).convert_alpha()

enemy_img = pygame.image.load(
    resource("enemy.png")
).convert_alpha()

enemy_hud_img = pygame.transform.smoothscale(
    enemy_img,
    (30, 30)
)

bullet_img = pygame.image.load(
    resource("bullet.png")
).convert_alpha()


# Música y sonidos
mixer.music.load(
    resource("background.wav")
)

mixer.music.set_volume(0.32)
mixer.music.play(-1)

laser_sound = mixer.Sound(
    resource("laser.wav")
)

explosion_sound = mixer.Sound(
    resource("explosion.wav")
)

laser_sound.set_volume(0.45)
explosion_sound.set_volume(0.45)


# Fuente pixelada
font_small = pixel_font(20)
font_hud = pixel_font(30)
font_title = pixel_font(70)
font_subtitle = pixel_font(30)


# Jugador
player_x = 368
player_y = 500
player_speed = 5


# Enemigos
enemy_x = []
enemy_y = []
enemy_x_change = []
enemy_y_change = []

enemy_speed = 3


# Bala
bullet_x = 0
bullet_y = 480
bullet_speed = 10
bullet_state = "ready"


# Estado
score = 0
lives = 3
game_over = False


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

        enemy_x.append(
            start_x + column * gap_x
        )

        enemy_y.append(
            105 + row * 82
        )

        enemy_x_change.append(
            enemy_speed
        )

        enemy_y_change.append(34)


def reset_game():
    global player_x
    global bullet_x
    global bullet_y
    global bullet_state
    global score
    global lives
    global game_over

    player_x = 368

    bullet_x = 0
    bullet_y = 480
    bullet_state = "ready"

    score = 0
    lives = 3
    game_over = False

    reset_enemy_formation()


def draw_heart(x, y, filled):
    if filled:
        color = RED
        highlight = (255, 150, 163)
    else:
        color = (76, 37, 65)
        highlight = (108, 55, 89)

    pygame.draw.circle(
        screen,
        color,
        (x + 7, y + 7),
        7
    )

    pygame.draw.circle(
        screen,
        color,
        (x + 19, y + 7),
        7
    )

    pygame.draw.polygon(
        screen,
        color,
        [
            (x + 1, y + 9),
            (x + 25, y + 9),
            (x + 13, y + 24)
        ]
    )

    pygame.draw.rect(
        screen,
        highlight,
        (x + 5, y + 4, 4, 4)
    )


def draw_hud():
    hud = pygame.Surface(
        (WIDTH, HUD_HEIGHT),
        pygame.SRCALPHA
    )

    hud.fill((9, 2, 27, 226))
    screen.blit(hud, (0, 0))

    pygame.draw.line(
        screen,
        (80, 38, 121),
        (0, HUD_HEIGHT - 1),
        (WIDTH, HUD_HEIGHT - 1),
        2
    )

    for index in range(3):
        draw_heart(
            16 + index * 34,
            20,
            index < lives
        )

    screen.blit(
        enemy_hud_img,
        (337, 18)
    )

    enemy_count = font_hud.render(
        f"x{NUM_ENEMIES:02d}",
        True,
        GREEN
    )

    screen.blit(
        enemy_count,
        (374, 17)
    )

    pygame.draw.circle(
        screen,
        YELLOW,
        (665, 34),
        11
    )

    pygame.draw.circle(
        screen,
        (255, 238, 137),
        (662, 30),
        3
    )

    score_text = font_hud.render(
        f"{score:04d}",
        True,
        YELLOW
    )

    screen.blit(
        score_text,
        (688, 16)
    )


def draw_footer():
    footer = pygame.Surface(
        (WIDTH, 30),
        pygame.SRCALPHA
    )

    footer.fill((9, 2, 27, 205))

    screen.blit(
        footer,
        (0, HEIGHT - 30)
    )

    controls = font_small.render(
        "FLECHAS: MOVER   ESPACIO: DISPARAR   ESC: SALIR",
        True,
        WHITE
    )

    screen.blit(
        controls,
        controls.get_rect(
            center=(WIDTH // 2, HEIGHT - 16)
        )
    )


def draw_player():
    screen.blit(
        player_img,
        (player_x, player_y)
    )


def draw_enemy(index):
    screen.blit(
        enemy_img,
        (
            enemy_x[index],
            enemy_y[index]
        )
    )


def draw_bullet():
    screen.blit(
        bullet_img,
        (
            bullet_x + 16,
            bullet_y + 10
        )
    )

    center_x = int(
        bullet_x + 32
    )

    for offset, size in (
        (38, 5),
        (50, 4),
        (61, 3),
        (71, 2)
    ):
        pygame.draw.rect(
            screen,
            CYAN,
            (
                center_x - size // 2,
                int(bullet_y + offset),
                size,
                size
            )
        )


def is_collision(ex, ey, bx, by):
    distance = math.hypot(
        ex - bx,
        ey - by
    )

    return distance < 28


def draw_game_over():
    panel = pygame.Surface(
        (560, 210),
        pygame.SRCALPHA
    )

    panel.fill((12, 3, 34, 238))

    pygame.draw.rect(
        panel,
        PURPLE,
        panel.get_rect(),
        4
    )

    screen.blit(
        panel,
        (120, 190)
    )

    title = font_title.render(
        "GAME OVER",
        True,
        RED
    )

    subtitle = font_subtitle.render(
        "PRESIONA R PARA REINICIAR",
        True,
        WHITE
    )

    screen.blit(
        title,
        title.get_rect(
            center=(WIDTH // 2, 265)
        )
    )

    screen.blit(
        subtitle,
        subtitle.get_rect(
            center=(WIDTH // 2, 345)
        )
    )


def lose_life():
    global lives
    global bullet_y
    global bullet_state
    global game_over

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

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            elif (
                event.key == pygame.K_r
                and game_over
            ):
                reset_game()

            elif (
                event.key == pygame.K_SPACE
                and bullet_state == "ready"
                and not game_over
            ):
                bullet_x = player_x
                bullet_y = 480
                bullet_state = "fire"

                laser_sound.play()


    screen.blit(
        background,
        (0, 0)
    )


    if not game_over:
        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT]:
            player_x -= player_speed

        if keys[pygame.K_RIGHT]:
            player_x += player_speed

        player_x = max(
            0,
            min(
                player_x,
                WIDTH - player_img.get_width()
            )
        )


        life_was_lost = False

        for i in range(NUM_ENEMIES):
            enemy_x[i] += enemy_x_change[i]

            if enemy_x[i] <= 0:
                enemy_x[i] = 0
                enemy_x_change[i] = enemy_speed
                enemy_y[i] += enemy_y_change[i]

            elif (
                enemy_x[i]
                >= WIDTH - enemy_img.get_width()
            ):
                enemy_x[i] = (
                    WIDTH - enemy_img.get_width()
                )

                enemy_x_change[i] = -enemy_speed
                enemy_y[i] += enemy_y_change[i]


            if enemy_y[i] > 435:
                lose_life()
                life_was_lost = True
                break


            if (
                bullet_state == "fire"
                and is_collision(
                    enemy_x[i],
                    enemy_y[i],
                    bullet_x,
                    bullet_y
                )
            ):
                explosion_sound.play()

                bullet_y = 480
                bullet_state = "ready"

                score += 10

                enemy_x[i] = random.randint(
                    40,
                    WIDTH - 104
                )

                enemy_y[i] = random.randint(
                    90,
                    160
                )


            draw_enemy(i)


        if (
            not life_was_lost
            and bullet_state == "fire"
        ):
            draw_bullet()

            bullet_y -= bullet_speed

            if (
                bullet_y
                <= -bullet_img.get_height()
            ):
                bullet_y = 480
                bullet_state = "ready"


        draw_player()


    else:
        for i in range(NUM_ENEMIES):
            if enemy_y[i] < HEIGHT:
                draw_enemy(i)

        draw_player()
        draw_game_over()


    draw_hud()
    draw_footer()

    pygame.display.flip()


pygame.quit()
