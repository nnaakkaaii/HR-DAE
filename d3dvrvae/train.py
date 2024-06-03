from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.utils.data import random_split

from .dataloaders import create_dataloader
from .datasets import create_dataset, Data
from .losses import create_loss
from .networks import create_network
from .optimizers import create_optimizer
from .option import TrainExpOption
from .schedulers import create_scheduler
from .transforms import create_transform


def train(opt: TrainExpOption):
    if torch.cuda.is_available():
        print("GPU is enabled")
        device = torch.device("cuda:0")
    else:
        print("GPU is not enabled")
        device = torch.device("cpu")

    transform = create_transform(opt.transform)
    dataset = create_dataset(
        opt.dataset,
        transform,
        is_train=True,
    )

    train_size = int(opt.train_val_ratio * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(
        dataset,
        [train_size, val_size],
    )

    train_loader = create_dataloader(
        opt.dataloader,
        train_dataset,
        is_train=True,
    )
    val_loader = create_dataloader(
        opt.dataloader,
        val_dataset,
        is_train=False,
    )

    model = create_network(opt.network)

    optimizer = create_optimizer(
        opt.optimizer,
        model.parameters(),
    )
    scheduler = create_scheduler(
        opt.scheduler,
        optimizer,
        opt.n_epoch,
        len(train_loader),
    )
    criterion = create_loss(opt.loss)

    max_iter = 5 if opt.debug else None

    x: Data
    y: Data
    t: Data
    model.to(device)
    for epoch in range(opt.n_epoch):
        model.train()
        running_loss = 0.0
        for idx, (x, t) in enumerate(train_loader):
            if max_iter and max_iter <= idx:
                break

            x = x.to(device)
            t = t.to(device)

            optimizer.zero_grad()
            y = model(x)
            loss = criterion(t, y)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

            if idx % 100 == 0:
                print(f"Epoch: {epoch+1}, Batch: {idx} Loss: {loss.item():.6f}")

        running_loss /= len(train_loader)
        print(f"Epoch: {epoch+1}, Average Loss: {running_loss:.6f}")

        scheduler.step()

        model.eval()
        with torch.no_grad():
            total_val_loss = 0.0
            for idx, (x, t) in enumerate(val_loader):
                if max_iter and max_iter <= idx:
                    break

                x = x.to(device)
                t = t.to(device)

                y = model(x)
                loss = criterion(t, y)
                total_val_loss += loss.item()

            avg_val_loss = total_val_loss / len(val_loader)
            print(f"Epoch: {epoch+1}, Val Loss: {avg_val_loss:.6f}")

        if epoch % 10 == 0:
            x, t = next(iter(val_loader))

            x = x.to(device)
            t = t.to(device)

            y = model(x)

            save_reconstructed_images(
                t.data.cpu().clone().detach().numpy()[:10],
                y.data.cpu().clone().detach().numpy()[:10],
                epoch,
                opt.result_dir / "logs" / "reconstructed",
            )


def save_reconstructed_images(
    original: np.ndarray, reconstructed: np.ndarray, epoch: int, save_dir: Path
):
    save_dir.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(20, 4))

    # Original Images
    for i in range(10):
        plt.subplot(2, 10, i + 1)
        plt.imshow(original[i].reshape(28, 28), cmap="gray")
        plt.title("Original")
        plt.axis("off")

    # Reconstructed Images
    for i in range(10):
        plt.subplot(2, 10, i + 11)
        plt.imshow(reconstructed[i].reshape(28, 28), cmap="gray")
        plt.title("Reconstructed")
        plt.axis("off")

    # 保存するファイル名を設定
    plt.savefig(save_dir / f"original_epoch_{epoch}.png")
    plt.close()
