# /// script
# dependencies = [
#   "numpy",
#   "pytmx",
#   "pyscroll",
#   "pygame",
#   "time"
# ]
# ///

!pip install numpy pytmx pyscroll pygame

from os import listdir, path
from numpy import array, dtype
from collections import deque
from threading import Thread
import pyscroll
import asyncio
import time
import pygame
from sys import exit
import pytmx

from gui.input_box import InputBox
from gui.text_button import TextButton
from gui.text_image_button import TextImageButton

class CodeRunner:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.Font(None, 36)

        self.custom_globals = globals().copy()

        self.custom_globals['print'] = self.custom_print
        self.custom_globals['input'] = self.custom_input

        self.print_queue = deque()

        self.input_box = None
        self.typing = False
        

    def custom_print(self, text):
        print("custom print: " + text)
        self.print_queue.append({'text': text, 'timestamp': pygame.time.get_ticks()})
    
    def custom_input(self, data):
        self.input_box = InputBox(self.screen, (100,100), (300, 50))

    def update(self):
        if self.input_box:
            self.input_box.update()
            self.typing = self.input_box.active

        print_queue_copy = self.print_queue.copy()
        for i, item in enumerate(print_queue_copy):
            if pygame.time.get_ticks() - Config.PRINT_TIMEOUT > item['timestamp']:
                self.print_queue.popleft()
            else:
                text = self.font.render(item['text'], True, (0, 0, 0))
                self.screen.blit(text, (0, i*50))

    def custom_exec(self, code):
        exec(code, self.custom_globals)

    def run_user_code(self, code):
        #exec(code, self.custom_globals)
        thread = Thread(target=self.custom_exec, args=(code, ))
        thread.start()

class Tilemap:
    def __init__(self, screen, player):
        self.screen = screen
        self.player = player

        self.tmx_data = pytmx.load_pygame('assets/levels/level1.tmx')  # Change to your TMX file
        map_layer = pyscroll.BufferedRenderer(
            data=pyscroll.TiledMapData(self.tmx_data),
            size=self.screen.get_size(),
        )
        self.player_group = pyscroll.PyscrollGroup(map_layer=map_layer)
        self.player_group.add(self.player)

    def update(self):
        self.player_group.center(self.player.rect.center)
        self.player_group.draw(self.screen)

    def get_collidable_tiles(self):
        collidable_tiles = []
        collision_layer = self.tmx_data.get_layer_by_name("Collision")

        # Loop through each tile in the collision layer
        for x, y, gid in collision_layer:
            if gid:  # gid == 0 means there's no tile at this location
                # Create a pygame.Rect for each collidable tile
                rect = pygame.Rect(
                    x * self.tmx_data.tilewidth,
                    y * self.tmx_data.tileheight,
                    self.tmx_data.tilewidth,
                    self.tmx_data.tileheight
                )
                collidable_tiles.append(rect)
        return collidable_tiles

class StartMenu:
    def __init__(self, screen):
        self.state = "START"
        self.start_state = "MAIN"
        self.screen = screen
        self.selected_character = Config.DEFAULT_CHARACTER

        self.scene_change()

    
    def scene_change(self):
        self.screen.fill((65,65,65))
        if self.start_state == "MAIN":
            pygame.display.set_caption("Start Menu")
            self.start_button = TextButton(self.screen, position=(150, 50), size=(200, 100), text="Start Game", bg_colour=(40, 40, 40), fg_colour=(192,192,192))  
            self.character_select_button = TextButton(self.screen, position=(150, 200), size=(200, 100), text="Character Select", bg_colour=(40, 40, 40), fg_colour=(192,192,192))
            self.quit_button = TextButton(self.screen, position=(150, 350), size=(200, 100), text="Quit Game", bg_colour=(40, 40, 40), fg_colour=(192,192,192))
        elif self.start_state == "CHARACTER_SELECT":
            pygame.display.set_caption("Character Select")

            self.back_button = TextButton(self.screen, position=(10, 10), size=(100, 50), text="Back", bg_colour=(40, 40, 40), fg_colour=(192,192,192))
            self.select_character_buttons = [TextImageButton(self.screen, position=((i+1)*self.screen.get_size()[0]/5, 150), size=(150, 300), text=("Character " + str(i+1)), bg_colour=(40, 40, 40), fg_colour=(192,192,192), image_path="assets/player/player_" + str(i+1) + ".png") for i in range(Config.NUMBER_OF_CHARACTERS)]

    def update(self):
        self.scene_change()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            
            elif event.type == pygame.VIDEORESIZE:
                self.scene_change()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.start_state == "MAIN":
                    if self.start_button.collidepoint(event.pos):
                        self.state = "GAME"
                    if self.character_select_button.collidepoint(event.pos):
                        self.start_state = "CHARACTER_SELECT"
                        self.scene_change()
                    elif self.quit_button.collidepoint(event.pos):
                        pygame.quit()
                        exit()
                elif self.start_state == "CHARACTER_SELECT":
                    if self.back_button.collidepoint(event.pos):
                        self.start_state = "MAIN"
                        self.scene_change()
                    for i, button in enumerate(self.select_character_buttons):
                        if button.collidepoint(event.pos):
                            self.selected_character = i
                            self.scene_change()

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

class Player(pygame.sprite.Sprite):
    def __init__(self, window, character, code_runner):
        super().__init__()
        self.image = pygame.image.load("assets/player/player_" + str(character+1) + ".png") 
        self.window = window

        self.position = self.get_initial_position()
        self.rect = self.image.get_rect()
        self.rect.center = self.get_initial_position()
        self.player_group = pygame.sprite.Group()
        self.player_group.add(self)

        self.code_runner = code_runner

    def get_initial_position(self):
        return array([self.window.get_size()[0]/2 - self.image.get_size()[0]/2, self.window.get_size()[1]/2 - self.image.get_size()[1]/2])

    def move(self, movement_vector):
        # block movement if player typing
        if self.code_runner.typing:
            return
        
        # move player
        self.rect.x += int(movement_vector[0])
        self.rect.y += int(movement_vector[1])

        # check collision
        if self.check_collision(self.rect):
            self.rect.x -= int(movement_vector[0])
            self.rect.y -= int(movement_vector[1])

    def check_collision(self, player_rect):
        map_width_in_pixels = self.tilemap.tmx_data.width * self.tilemap.tmx_data.tilewidth  - self.rect.width
        map_height_in_pixels = self.tilemap.tmx_data.height * self.tilemap.tmx_data.tileheight - self.rect.height

        if self.rect.x <= 0 or self.rect.x >= map_width_in_pixels:
                return True
        if self.rect.y <= 0 or self.rect.y >= map_height_in_pixels:
            return True

        for tile in self.tilemap.get_collidable_tiles():
            
            if player_rect.colliderect(tile):
                return True
            
        return False
    
    def parse_tilemap(self, tilemap):
        self.tilemap = tilemap

class Controls:
    MOVEMENT = [pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s]

    MOVEMENT_VECTORS = {
        pygame.K_a: array([-1, 0]),  # Move left
        pygame.K_d: array([1, 0]),   # Move right
        pygame.K_w: array([0, -1]),  # Move up
        pygame.K_s: array([0, 1]),   # Move down
    }

class Config:
    DEFAULT_WIN_WIDTH = 1280
    DEFAULT_WIN_HEIGHT = 720
    FPS = 60

    MOVEMENT_SPEED = array([4, 4]) # a <-> d, w <-> s directional movement speed
    MOVEMENT_RESRICTIONS = [0.2, 0.2] # percentage of [width, height] the player cannot physically move to.#

    DEFAULT_CHARACTER = 1
    NUMBER_OF_CHARACTERS = 3 # number of character imgs in "assets\player\"
    GAME_PLAYING_CAPTION = "goblin shooter"

    PRINT_TIMEOUT = 2000 # time to display print statements on-screen (ms)

class App:
    def __init__(self):       
        pygame.init()
        icon = pygame.image.load('icon.png')  # Make sure 'icon.png' exists in your working directory

        # Set the window icon
        pygame.display.set_icon(icon)

        self.screen = pygame.display.set_mode((Config.DEFAULT_WIN_WIDTH, Config.DEFAULT_WIN_HEIGHT)) # config.py
        self.clock = pygame.time.Clock()

        self.movement_vector = []
        self.menu_button = None

        self.setup_start() # show start menu first

        self.gameloop()

    def setup_start(self):
        self.state = "START"
        self.start = StartMenu(self.screen)

    def reset_game(self):
        pygame.display.set_caption(Config.GAME_PLAYING_CAPTION) 

        self.code_runner = CodeRunner(self.screen)
      
        self.player = Player(self.screen, self.start.selected_character, self.code_runner)
        self.tilemap = Tilemap(self.screen, self.player)

        self.player.parse_tilemap(self.tilemap)

        self.state = "GAME"
        self.code_runner.run_user_code("print(\"morning \") \ntime.sleep(1) \nprint(\"goodnight \")")
        #self.code_runner.run_user_code("print(\"morning goblin\") \nprint(\"goodnight goblin\")")
        #self.code_runner.run_user_code("input(\"brrr\")")
        
    def gameloop(self):
        while True:
            self.events()
            self.draw()

            pygame.display.update()
        

    def events(self): 
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.menu_button.collidepoint(event.pos):
                    print("clic")
                    self.start_state = "START"
                    self.state = "START"
                    self.setup_start()
                    
        
        keys = pygame.key.get_pressed()
        self.movement_vector = array([0, 0], dtype='f')

        if self.state == "GAME":
            y_movement = False
            for control_key in Controls.MOVEMENT:
                if keys[control_key]:
                    if control_key == pygame.K_w:
                        y_movement = True
                    
                    self.movement_vector += Controls.MOVEMENT_VECTORS[control_key]

            self.movement_vector *= Config.MOVEMENT_SPEED
            self.player.move(self.movement_vector)

    def draw(self):
        self.clock.tick(Config.FPS) # changes with the FPS in config.py

        if self.state == "START":
            self.start.update()
            self.state = self.start.state
            if self.state == "GAME":
                self.reset_game()
        elif self.state == "GAME":
            self.tilemap.update()
            self.code_runner.update()
            self.menu_button = TextButton(self.screen, position=(self.screen.get_size()[0] - 10 - 100, 10), size=(100, 50), text="Menu", bg_colour=(40, 40, 40), fg_colour=(192,192,192))

    async def run(self):
        while True:
            self.events()
            self.draw()
            await asyncio.sleep(0)


        


if __name__ == "__main__":
    app = App()
    asyncio.run(app.run())
