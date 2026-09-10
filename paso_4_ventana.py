"""Primera ejecucion correspondiente a los puntos 3 y 4 del laboratorio."""

from pathlib import Path

import pygame


ANCHO = 800
ALTO = 600
RUTA = Path(__file__).resolve().parent

pygame.init()
screen = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Space Invaders - Primera ejecucion")

background = pygame.image.load(str(RUTA / "background.jpg")).convert()
background = pygame.transform.smoothscale(background, (ANCHO, ALTO))

# El enunciado no incluye este bucle en el punto 3, pero es necesario para
# mantener la ventana abierta y poder verificar su funcionamiento.
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.blit(background, (0, 0))
    pygame.display.flip()

pygame.quit()
