from dataclasses import dataclass, field
from random import randint

from torch import Tensor, min
from torch.nn.functional import pad

from .option import TransformOption
from .typing import Transform


@dataclass
class RandomShift2dOption(TransformOption):
    max_shifts: list[int] = field(default_factory=lambda: [10, 10])


@dataclass
class RandomShift3dOption(TransformOption):
    max_shifts: list[int] = field(default_factory=lambda: [5, 30, 30])


def create_random_shift2d(opt: RandomShift2dOption) -> Transform:
    return RandomShift2d(opt.max_shifts)


def create_random_shift3d(opt: RandomShift3dOption) -> Transform:
    return RandomShift3d(opt.max_shifts)


class RandomShift2d:
    def __init__(
        self,
        ds: list[int],
    ) -> None:
        self.dx, self.dy = ds

    def __call__(
        self,
        x: Tensor,
    ) -> Tensor:
        min_val = float(min(x))

        # W dimension (dx)
        dx = randint(-self.dx, self.dx)
        if dx != 0:
            if dx > 0:
                x = pad(x, (dx, 0, 0, 0), value=min_val)
                x = x[:, :, :, dx:]
            else:
                x = pad(x, (0, -dx, 0, 0), value=min_val)
                x = x[:, :, :, :dx]

        # H dimension (dy)
        dy = randint(-self.dy, self.dy)
        if dy != 0:
            if dy > 0:
                x = pad(x, (0, 0, dy, 0), value=min_val)
                x = x[:, :, dy:, :]
            else:
                x = pad(x, (0, 0, 0, -dy), value=min_val)
                x = x[:, :, :dy, :]

        return x


class RandomShift3d:
    def __init__(
        self,
        ds: list[int],
    ) -> None:
        self.dz, self.dx, self.dy = ds

    def __call__(
        self,
        x: Tensor,
    ) -> Tensor:
        min_val = float(min(x))

        # N dimension (dz)
        dz = randint(-self.dz, self.dz)
        if dz != 0:
            if dz > 0:
                x = pad(x, (0, 0, 0, 0, dz, 0), value=min_val)
                x = x[:, dz:, :, :]
            else:
                x = pad(x, (0, 0, 0, 0, 0, -dz), value=min_val)
                x = x[:, :dz, :, :]

        # H dimension (dy)
        dy = randint(-self.dy, self.dy)
        if dy != 0:
            if dy > 0:
                x = pad(x, (0, 0, dy, 0, 0, 0), value=min_val)
                x = x[:, :, dy:, :]
            else:
                x = pad(x, (0, 0, 0, -dy, 0, 0), value=min_val)
                x = x[:, :, :dy, :]

        # W dimension (dx)
        dx = randint(-self.dx, self.dx)
        if dx != 0:
            if dx > 0:
                x = pad(x, (dx, 0, 0, 0, 0, 0), value=min_val)
                x = x[:, :, :, dx:]
            else:
                x = pad(x, (0, -dx, 0, 0, 0, 0), value=min_val)
                x = x[:, :, :, :dx]

        return x
