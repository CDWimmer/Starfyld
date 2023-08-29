from random import randint

from pyglet import shapes


def rand_color() -> tuple:
    return randint(0, 255), randint(0, 255), randint(0, 255), randint(150, 255)


def make_random_circle(left, right, top, bottom, segments, batch_name):
    """Return a random circle within the bounds given"""
    # print(left, right, top, bottom)
    return shapes.Circle(
        x=randint(*sorted([left, right])),
        y=randint(*sorted([bottom, top])),
        radius=randint(1, 10),
        segments=segments,
        color=rand_color(),
        batch=batch_name
    )
