import random

import torch
import torch.nn as nn


class RNNEncoder(nn.Module):
    def __init__(self, vocab_size, embeb_dim, hidden_size, num_layers,
                 dropout):
        super().__init__()

        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.embedding = nn.Embedding(vocab_size, embeb_dim)

        # no dropout as only one layer!
        self.rnn = nn.GRU(input_size=embeb_dim,
                          hidden_size=hidden_size,
                          num_layers=num_layers,
                          dropout=dropout if num_layers > 1 else 0.)

        self.dropout = nn.Dropout(dropout)

    def forward(self, src):

        # src = [src len, batch size]

        embedded = self.dropout(self.embedding(src))

        # embedded = [src len, batch size, emb dim]

        # no cell state!
        outputs, hidden = self.rnn(embedded)

        # outputs = [src len, batch size, hid dim * n directions]
        # hidden = [n layers * n directions, batch size, hid dim]

        # outputs are always from the top hidden layer

        return outputs, hidden


class RNNDecoder(nn.Module):
    def __init__(self,
                 vocab_size,
                 embed_dim,
                 hidden_size,
                 num_layers,
                 dropout=0.):
        super().__init__()

        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.embedding = nn.Embedding(vocab_size, embed_dim)

        self.rnn = nn.GRU(embed_dim + hidden_size,
                          hidden_size,
                          num_layers,
                          dropout=dropout if num_layers > 1 else 0.)

        self.fc_out = nn.Linear(embed_dim + hidden_size * 2, vocab_size)

        self.dropout = nn.Dropout(dropout)

    def forward(self, input, hidden, context):

        # input = [batch size]
        # hidden = [n layers * n directions, batch size, hid dim]
        # context = [n layers * n directions, batch size, hid dim]

        # n layers and n directions in the decoder will both always be 1, therefore:
        # hidden = [1, batch size, hid dim]
        # context = [1, batch size, hid dim]

        input = input.unsqueeze(0)

        # input = [1, batch size]

        embedded = self.dropout(self.embedding(input))

        # embedded = [1, batch size, emb dim]

        emb_con = torch.cat((embedded, context), dim=2)

        # emb_con = [1, batch size, emb dim + hid dim]

        output, hidden = self.rnn(emb_con, hidden)

        # output = [seq len, batch size, hid dim * n directions]
        # hidden = [n layers * n directions, batch size, hid dim]

        # seq len, n layers and n directions will always be 1 in the decoder, therefore:
        # output = [1, batch size, hid dim]
        # hidden = [1, batch size, hid dim]

        output = torch.cat(
            (embedded.squeeze(0), hidden.squeeze(0), context.squeeze(0)),
            dim=1)

        # output = [batch size, emb dim + hid dim * 2]

        prediction = self.fc_out(output)

        # prediction = [batch size, output dim]

        return prediction, hidden


class RNNSeq2Seq(nn.Module):
    def __init__(self,
                 src_vocab_size,
                 trg_vocab_size,
                 embed_dim,
                 hidden_size,
                 num_layers,
                 dropout=0.,
                 device='cpu'):
        super().__init__()

        self.src_vocab_size = src_vocab_size
        self.trg_vocab_size = trg_vocab_size

        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.device = device

        self.encoder = RNNEncoder(src_vocab_size, embed_dim, hidden_size,
                                  num_layers, dropout)
        self.decoder = RNNDecoder(trg_vocab_size, embed_dim, hidden_size,
                                  num_layers, dropout)

    def forward(self, src, trg, teacher_forcing_ratio=0.5):

        # src = [src len, batch size]
        # trg = [trg len, batch size]
        # teacher_forcing_ratio is probability to use teacher forcing
        # e.g. if teacher_forcing_ratio is 0.75 we use ground-truth inputs 75% of the time

        batch_size = trg.shape[1]
        trg_len = trg.shape[0]
        trg_vocab_size = self.trg_vocab_size

        # tensor to store decoder outputs
        outputs = torch.zeros(trg_len, batch_size,
                              trg_vocab_size).to(self.device)

        # last hidden state of the encoder is the context
        _, context = self.encoder(src)

        # context also used as the initial hidden state of the decoder
        hidden = context

        # first input to the decoder is the <sos> tokens
        input = trg[0, :]

        for t in range(1, trg_len):

            # insert input token embedding, previous hidden state and the context state
            # receive output tensor (predictions) and new hidden state
            output, hidden = self.decoder(input, hidden, context)

            # place predictions in a tensor holding predictions for each token
            outputs[t] = output

            # decide if we are going to use teacher forcing or not
            teacher_force = random.random() < teacher_forcing_ratio

            # get the highest predicted token from our predictions
            top1 = output.argmax(1)

            # if teacher forcing, use actual next token as next input
            # if not, use predicted token
            input = trg[t] if teacher_force else top1

        return outputs

    def init_weights(self):
        for name, param in self.named_parameters():
            if 'weight' in name:
                nn.init.normal_(param.data, mean=0, std=0.01)
            else:
                nn.init.constant_(param.data, 0)
