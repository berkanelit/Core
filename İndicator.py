import pygame
import random

# Ekran boyutları
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Renkler
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
BROWN = (153, 76, 0)

# Oyun başlatılıyor
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Basit Minecraft Oyunu")

clock = pygame.time.Clock()
running = True

# Karakterin özellikleri
character_x = 50
character_y = 50
character_width = 50
character_height = 50

# Ağaçların özellikleri
tree_x = 300
tree_y = 300
tree_width = 100
tree_height = 150

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Tuş kontrolü
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        character_x -= 5
    if keys[pygame.K_RIGHT]:
        character_x += 5
    if keys[pygame.K_UP]:
        character_y -= 5
    if keys[pygame.K_DOWN]:
        character_y += 5

    # Çizim işlemleri
    screen.fill(WHITE)
    pygame.draw.rect(screen, GREEN, (character_x, character_y, character_width, character_height))
    pygame.draw.rect(screen, BROWN, (tree_x, tree_y, tree_width, tree_height))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
