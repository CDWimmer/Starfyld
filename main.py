import random
from math import atan2, cos, sin
from typing import List  # i love typing

import opensimplex
import pyglet
from pyglet.window import key


from pyglet.gl import *

from utils import make_random_circle

# fix for dpi scaling on UI scaled monitors e.g. laptops.
# todo: Need to revisit this. Does weird things when two monitors are on different DPI scales.
# if sys.platform == 'win32':
#     import ctypes
#     ctypes.windll.user32.SetProcessDPIAware()

opensimplex.random_seed()

WINDOW_WIDTH = 1024  # ignored as set by monitor
WINDOW_HEIGHT = 768

NUM_STARS = 100
MAX_STAR_RADIUS = 10
MIN_STAR_RADIUS = 1
MIN_STAR_SEGMENTS = 3
MAX_STAR_SEGMENTS = 14

DELETE_BOARDER_LIMIT = 50  # pixels?
SPAWN_BOARDER_LIMIT = 30  # pixels?

SPEED_SCALE = 0.4

DISPLAY_FPS = True


class App(pyglet.window.Window):
    def __init__(self, width, height, *args, **kwargs):
        self.render_overlays = True
        conf = Config(sample_buffers=1, samples=4, depth_size=16, double_buffer=True)
        super().__init__(width, height, config=conf, *args, **kwargs)

        self.time = 0

        self.fps_display = pyglet.window.FPSDisplay(window=self)
        self.fps_display.label.font_size = 20
        self.fps_display.label.color = 255, 255, 0, 255
        self.fps_display.label.x = 5
        self.fps_display.label.y = self.height - 30

        self.main_batch = pyglet.graphics.Batch()
        self.overlay1_batch = pyglet.graphics.Batch()
        self.overlay2_batch = pyglet.graphics.Batch()

        self.left = 0
        self.right = width
        self.bottom = 0
        self.top = height
        self.zoom_level = 1
        self.zoomed_width = width
        self.zoomed_height = height

        self.additional_wind_vertical = 0
        self.additional_wind_horizontal = 0
        font_size = 10
        self.additional_wind_label = pyglet.text.Label(
            text="Additional Wind: 0, 0",
            x=self.width / 2,
            y=self.bottom + font_size + 5,
            font_size=font_size,
            anchor_x="center",
            anchor_y="center",
            batch=self.overlay2_batch,
        )

        self.stars: List[pyglet.shapes.Circle] = [
            make_random_circle(
                self.left,
                self.right,
                self.top,
                self.bottom,
                random.randint(MIN_STAR_SEGMENTS, MAX_STAR_SEGMENTS),
                self.main_batch,
            )
            for i in range(NUM_STARS)
        ]

        self.static_grid = []  # strong reference
        NUM_LINES = 12
        GRID_COLOUR = (10, 170, 230, 255)
        separation = self.width / (NUM_LINES + 1)
        for i in range(1, NUM_LINES + 1):
            from_left = self.left + (i * separation)
            self.static_grid.append(
                pyglet.shapes.Line(
                    x=from_left,
                    y=self.bottom,
                    x2=from_left,
                    y2=self.top,
                    width=0.5,
                    color=GRID_COLOUR,
                    batch=self.overlay1_batch,
                )
            )
        for i in range(1, int(self.height / separation) + 1):
            from_bottom = self.bottom + (i * separation)
            self.static_grid.append(
                pyglet.shapes.Line(
                    x=self.left,
                    y=from_bottom,
                    x2=self.right,
                    y2=from_bottom,
                    width=0.5,
                    color=GRID_COLOUR,
                    batch=self.overlay1_batch,
                )
            )

        self.radar_container = pyglet.shapes.BorderedRectangle(
            x=self.left + 5,
            y=self.top - 5,
            width=200,
            height=-200,
            border=1,
            color=(
                int(GRID_COLOUR[0] * 0.3),
                int(GRID_COLOUR[1] * 0.3),
                int(GRID_COLOUR[2] * 0.3),
                int(GRID_COLOUR[3]),
            ),
            border_color=GRID_COLOUR,
            batch=self.overlay1_batch,
        )
        self.radar_center_x = self.radar_container.x + self.radar_container.width / 2
        self.radar_center_y = self.radar_container.y + self.radar_container.height / 2
        self.radar_radius = 0.8 * self.radar_container.width / 2
        # hollow circle == Arc
        self.radar_circle = pyglet.shapes.Arc(
            x=self.radar_center_x,
            y=self.radar_center_y,
            radius=self.radar_radius,
            batch=self.overlay2_batch,
        )
        self.radar_pointer_line = pyglet.shapes.Line(
            x=self.radar_center_x,
            y=self.radar_center_y,
            x2=self.radar_center_x,  # p2 values overwritten by updater
            y2=self.radar_center_y,
            batch=self.overlay2_batch,
        )

    def wind_label_update(self):
        self.additional_wind_label.text = (
            f"Additional wind: {self.additional_wind_horizontal:+},"
            f" {self.additional_wind_vertical:+}"
        )

    def on_key_press(self, symbol, modifiers):
        super().on_key_press(symbol, modifiers)
        if symbol == key.H:
            self.render_overlays = not self.render_overlays
        match symbol:
            case key.UP:
                self.additional_wind_vertical += 1 * (
                    10 if modifiers & key.MOD_SHIFT else 1
                )
                self.wind_label_update()
            case key.DOWN:
                self.additional_wind_vertical -= 1 * (
                    10 if modifiers & key.MOD_SHIFT else 1
                )
                self.wind_label_update()
            case key.LEFT:
                self.additional_wind_horizontal -= 1 * (
                    10 if modifiers & key.MOD_SHIFT else 1
                )
                self.wind_label_update()
            case key.RIGHT:
                self.additional_wind_horizontal += 1 * (
                    10 if modifiers & key.MOD_SHIFT else 1
                )
                self.wind_label_update()
            case _:
                pass

    def generate_new_star(self, heading_horizontal, heading_vertical):
        horizontal_or_vertical = random.choice(
            ["horizontal", "vertical"]
        )  # good enough
        match horizontal_or_vertical:
            case "horizontal":
                lim_top = self.top
                lim_bottom = self.bottom
                if heading_horizontal >= 0:  # stars moving right
                    # print("horizontal ->")
                    lim_left = self.left  # left edge of screen
                    lim_right = (
                        self.left - SPAWN_BOARDER_LIMIT
                    )  # n pixels out of screen on left
                else:  # stars moving left
                    # print("horizontal <-")
                    lim_left = (
                        self.right + SPAWN_BOARDER_LIMIT
                    )  # n pixels out of screen on right
                    lim_right = self.right  # right edge of screen
            case "vertical":
                lim_left = self.left
                lim_right = self.right
                if heading_vertical >= 0:  # stars moving up
                    # print("vertical ^")
                    lim_top = self.bottom  # bottom edge of screen
                    lim_bottom = (
                        self.bottom - SPAWN_BOARDER_LIMIT
                    )  # n pixels out of screen on bottom
                else:
                    # print("vertical v")
                    lim_top = (
                        self.top + SPAWN_BOARDER_LIMIT
                    )  # n pixels out of screen on top
                    lim_bottom = self.top  # top edge of screen
            case _:
                print("????? you shouldn't be reading this")
                lim_left = self.left
                lim_right = self.right
                lim_bottom = self.bottom
                lim_top = self.top
        new_star = make_random_circle(
            lim_left,
            lim_right,
            lim_bottom,
            lim_top,
            random.randint(MIN_STAR_SEGMENTS, MAX_STAR_SEGMENTS),
            self.main_batch,
        )
        # print(new_star.x, new_star.y)
        self.stars.append(new_star)

    def init_gl(self, width, height):
        # Set clear color
        glClearColor(0 / 255, 0 / 255, 0 / 255, 0 / 255)

        # Set antialiasing
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_POLYGON_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        # Set alpha blending
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        self.right = width
        self.top = height
        self.init_gl(width, height)
        self.fps_display.label.y = self.height - 30

    def on_draw(self):
        # Clear window with ClearColor
        glClear(GL_COLOR_BUFFER_BIT)

        self.main_batch.draw()
        if self.render_overlays:
            self.overlay1_batch.draw()
            self.overlay2_batch.draw()
        if DISPLAY_FPS:
            self.fps_display.draw()


canvas = pyglet.canvas.get_display()
monitors = canvas.get_screens()
int_list_of_monitors = [int(i) for i in list(range(len(monitors)))]
target_monitor_number: int = int(
    input(f"Pick a display number: {int_list_of_monitors}: ")
)

app = App(
    width=monitors[target_monitor_number].width,
    height=monitors[target_monitor_number].height,
    caption="StarFyld",
    resizable=True,
    fullscreen=True,
    vsync=True,
    screen=monitors[target_monitor_number],
)

# print(monitors[target_monitor_number].width, "x", monitors[target_monitor_number].height)


def update(dt):
    app.time += dt * 0.1
    travel_vertical_multiplier = opensimplex.noise2(app.time, 0) + (
        app.additional_wind_vertical * 0.1
    )
    travel_horizontal_multiplier = opensimplex.noise2(0, app.time) + (
        app.additional_wind_horizontal * 0.1
    )
    for star in app.stars:
        # check if star needs replacing due to being off-screen
        if (
            star.x < (app.left - DELETE_BOARDER_LIMIT)
            or star.x > (app.right + DELETE_BOARDER_LIMIT)
            or star.y < (app.bottom - DELETE_BOARDER_LIMIT)
            or star.y > (app.top + DELETE_BOARDER_LIMIT)
        ):
            star.delete()
            app.stars.remove(star)
            app.generate_new_star(
                travel_horizontal_multiplier, travel_vertical_multiplier
            )
            continue
        star.x += travel_horizontal_multiplier * star.radius * SPEED_SCALE
        star.y += travel_vertical_multiplier * star.radius * SPEED_SCALE

    # update radar pointer
    angle = atan2(travel_vertical_multiplier, travel_horizontal_multiplier)
    pointer_radius = (
        app.radar_radius
    )  # * abs(travel_vertical_multiplier) * abs(travel_horizontal_multiplier)
    app.radar_pointer_line.x2 = pointer_radius * cos(angle) + app.radar_center_x
    app.radar_pointer_line.y2 = pointer_radius * sin(angle) + app.radar_center_y


pyglet.clock.schedule_interval(update, 1 / 240.0)

pyglet.app.run(1 / 144)
