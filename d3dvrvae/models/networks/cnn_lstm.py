import numpy as np
from torch import Tensor, nn, zeros

from .modules import ConvModule2d


class RNNEncoder(nn.Module):
    """encode (batch_size, seq_len, in_channels) into (batch_size, seq_len, hidden_dim)"""

    def __init__(
        self,
        in_channels: int,
        hidden_dim: int,
        num_layers: int,
        bidirectional: bool,
    ):
        super().__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.lstm = nn.LSTM(
            in_channels,
            hidden_dim,
            num_layers,
            batch_first=True,
            dropout=0.2,
            bidirectional=bidirectional,
        )
        self.relu = nn.ReLU()

        nn.init.orthogonal_(self.lstm.weight_ih_l0, gain=np.sqrt(2))
        nn.init.orthogonal_(self.lstm.weight_hh_l0, gain=np.sqrt(2))

    def forward(
        self,
        x: Tensor,
    ) -> Tensor:
        h0 = zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)
        c0 = zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)

        out, _ = self.lstm(x, (h0, c0))

        return out[:, -1, :].unsqueeze(1)


class RNNDecoder(nn.Module):
    def __init__(
        self,
        out_channels: int,
        hidden_dim: int,
        num_layers: int,
        bidirectional: bool,
    ):
        super().__init__()
        self.out_channels = out_channels
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.lstm = nn.LSTM(
            hidden_dim,
            out_channels,
            num_layers,
            batch_first=True,
            dropout=0.2,
            bidirectional=bidirectional,
        )

        # initialize weights
        nn.init.orthogonal_(self.lstm.weight_ih_l0, gain=np.sqrt(2))
        nn.init.orthogonal_(self.lstm.weight_hh_l0, gain=np.sqrt(2))

    def forward(self, x: Tensor) -> Tensor:
        # set initial hidden and cell states
        h0 = zeros(self.num_layers, x.size(0), self.out_channels).to(x.device)
        c0 = zeros(self.num_layers, x.size(0), self.out_channels).to(x.device)

        # forward propagate lstm
        out, _ = self.lstm(x, (h0, c0))

        return out


class CNNLSTM2d(nn.Module):
    def __init__(
        self,
        in_channels: int,
        latent_dim: int,
        sequence_length: int,
        conv_params: list[dict[str, int]],
        rnn_hidden_dim: int,
        rnn_num_layers: int,
        rnn_bidirectional: bool = False,
    ):
        super().__init__()
        self.sequence_length = sequence_length
        self.encoder_conv = ConvModule2d(
            in_channels,
            latent_dim,
            latent_dim,
            conv_params,
            transpose=False,
        )
        self.encoder_rnn = RNNEncoder(
            latent_dim, rnn_hidden_dim, rnn_num_layers, rnn_bidirectional
        )
        self.decoder_rnn = RNNDecoder(
            latent_dim, rnn_hidden_dim, rnn_num_layers, rnn_bidirectional
        )
        self.decoder_conv = ConvModule2d(
            latent_dim,
            in_channels,
            latent_dim,
            conv_params,
            transpose=True,
        )

    def forward(self, x: dict[str, Tensor]) -> dict[str, Tensor]:
        encoded_x = self.encoder(x).expand(-1, ..., -1)  # FIXME: TO BE FIXED
        decoded_x = self.decoder(encoded_x)
        latent = self.encoder(x)
        y = self.decoder(latent)

        return decoded_x
