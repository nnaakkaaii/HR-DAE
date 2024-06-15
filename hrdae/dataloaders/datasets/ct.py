import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from omegaconf import MISSING
from torch import Tensor, from_numpy, gather, int64, tensor, where, cat
from torch.utils.data import Dataset
from tqdm import tqdm

from ..transforms import Transform


@dataclass
class CTDatasetOption:
    root: Path = MISSING
    threshold: float = 0.1
    min_occupancy: float = 0.2
    in_memory: bool = False


class BasicSliceIndexer:
    def __init__(self, threshold: float = 0.1, min_occupancy: float = 0.2) -> None:
        self.threshold = threshold
        self.min_occupancy = min_occupancy

    def __call__(self, x: Tensor) -> Tensor:
        mask = where(x > self.threshold, 1, 0)
        choices = []
        n, d, h, w = x.size()
        for i in range(w):
            if mask[:, :, :, i].sum() < self.min_occupancy * n * d * h:
                continue
            choices.append(i)

        if len(choices) > 0:
            return tensor([random.choice(choices)], dtype=int64)

        return tensor([int(mask.sum(dim=(0, 1)).argmax())], dtype=int64)


def create_ct_dataset(
    opt: CTDatasetOption, transform: Transform, is_train: bool
) -> Dataset:
    return CT(
        root=opt.root,
        slice_indexer=BasicSliceIndexer(opt.threshold, opt.min_occupancy),
        transform=transform,
        in_memory=opt.in_memory,
        is_train=is_train,
    )


class CT(Dataset):
    TRAIN_PER_TEST = 4
    PERIOD = 10

    def __init__(
        self,
        root: Path,
        slice_indexer: Callable[[Tensor], Tensor],
        transform: Transform | None = None,
        in_memory: bool = True,
        is_train: bool = True,
    ) -> None:
        super().__init__()

        self.paths = []
        data_root = root / self.__class__.__name__
        for i, path in enumerate(sorted(data_root.glob("**/*"))):
            if is_train and i % (1 + self.TRAIN_PER_TEST) != 0:
                self.paths.append(path)
            elif not is_train and i % (1 + self.TRAIN_PER_TEST) == 0:
                self.paths.append(path)

        self.data: list[Tensor] = []
        if in_memory:
            for path in tqdm(self.paths, desc="loading datasets..."):
                t = from_numpy(np.load(path)["arr_0"])
                if transform is not None:
                    t = transform(t)
                self.data.append(t)

        self.slice_indexer = slice_indexer
        self.transform = transform
        self.in_memory = in_memory

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index: int) -> dict[str, Tensor]:
        if len(self.data) > 0:
            assert self.in_memory
            x_3d = self.data[index]
        else:  # not in memory
            assert not self.in_memory
            x_3d = from_numpy(np.load(str(self.paths[index]))["arr_0"])
            if self.transform is not None:
                x_3d = self.transform(x_3d)

        n, d, h, w = x_3d.size()
        assert n == self.PERIOD, f"expected {self.PERIOD} but got {n}"

        # (s,)
        slice_idx = self.slice_indexer(x_3d)
        # (n, d, h, s)
        idx_expanded = (
            slice_idx.unsqueeze(0).unsqueeze(1).unsqueeze(2).repeat(n, d, h, 1)
        )

        # (n, d, h, s)
        x_2d = gather(x_3d, -1, idx_expanded)
        # (d, h, s)
        x_2d_0 = x_2d[0]
        x_2d_t = x_2d[self.PERIOD // 2]
        # (d, h, w)
        x_3d_0 = x_3d[0]
        x_3d_t = x_3d[self.PERIOD // 2]

        # (n, d, h, s) -> (b, n, d, h, s) -> (b, n, s, d, h)
        x_2d = x_2d.unsqueeze(0).permute(0, 1, 4, 2, 3)
        # (d, h, s) -> (b, d, h, s) -> (b, s, d, h)
        x_2d_0 = x_2d_0.unsqueeze(0).permute(0, 3, 1, 2)
        x_2d_t = x_2d_t.unsqueeze(0).permute(0, 3, 1, 2)
        # (b, 2 * s, d, h)
        x_2d_all = cat([x_2d_0, x_2d_t], dim=1)
        # (n, d, h, w) -> (b, n, c, d, h, w)
        x_3d = x_3d.unsqueeze(0).unsqueeze(2)
        # (d, h, w) -> (b, c, d, h, w)
        x_3d_0 = x_3d_0.unsqueeze(0).unsqueeze(1)
        x_3d_t = x_3d_t.unsqueeze(0).unsqueeze(1)
        # (b, 2 * c, d, h, w)
        x_3d_all = cat([x_3d_0, x_3d_t], dim=1)
        # (s,) -> (b, s)
        slice_idx = slice_idx.unsqueeze(0)
        # (n, d, h, s) -> (b, n, d, h, s) -> (b, n, s, d, h)
        idx_expanded = idx_expanded.unsqueeze(0).permute(0, 1, 4, 2, 3)

        return {
            "x-": x_2d,  # (b, n, s, d, h)
            "x-_0": x_2d_0,  # (b, s, d, h)
            "x-_t": x_2d_t,  # (b, s, d, h)
            "x-_all": x_2d_all,  # (b, 2 * s, d, h)
            "x+": x_3d,  # (b, n, c, d, h, w)
            "x+_0": x_3d_0,  # (b, c, d, h, w)
            "x+_t": x_3d_t,  # (b, c, d, h, w)
            "x+_all": x_3d_all,  # (b, 2 * c, d, h, w)
            "slice_idx": slice_idx,  # (b, s)
            "idx_expanded": idx_expanded,  # (b, n, s, d, h)
        }


if __name__ == "__main__":

    def test():
        from torchvision import transforms

        from ..transforms import (MinMaxNormalizationOption, Pool3dOption,
                                  UniformShape3dOption, create_transform)

        option = CTDatasetOption(
            root=Path("data"),
        )
        dataset = create_ct_dataset(
            option,
            transform=transforms.Compose(
                [
                    create_transform(MinMaxNormalizationOption()),
                    create_transform(UniformShape3dOption()),
                    create_transform(Pool3dOption()),
                ]
            ),
            is_train=True,
        )
        data = dataset[0]
        for k, v in data.items():
            print(k, v.shape)

    test()