'''
Author: jianzhnie
Date: 2021-12-17 16:49:18
LastEditTime: 2022-01-13 12:24:28
LastEditors: jianzhnie
Description:

'''

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from torch.nn import init

from .function import RNNReLUCell, RNNTanhCell


def _get_activation_fn(activation):
    if activation == 'relu':
        return F.relu
    elif activation == 'tanh':
        return F.tanh

    raise RuntimeError(
        'activation should be relu/tanh, not {}'.format(activation))


class NaiveCustomRNN(nn.Module):
    """
    - ππ‘=π(ππ‘ππ₯β+ππ‘β1πββ+πβ).
    - ππ‘=ππ‘πβπ+ππ.

    Reference:
        https://d2l.ai
    """
    def __init__(self, input_size, hidden_size):
        super().__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size

        # ιθε±εζ°
        self.W_xh = nn.Parameter(torch.Tensor(input_size, hidden_size))
        self.W_hh = nn.Parameter(torch.Tensor(hidden_size, hidden_size))
        self.b_h = nn.Parameter(torch.Tensor(hidden_size))

        # θΎεΊε±εζ°
        self.W_hq = nn.Parameter(torch.Tensor(hidden_size, hidden_size))
        self.b_q = nn.Parameter(torch.Tensor(hidden_size))

        self.reset_parameters()

    def reset_parameters(self) -> None:
        stdv = 1.0 / math.sqrt(self.hidden_size)
        for weight in self.parameters():
            init.uniform_(weight, -stdv, stdv)

    def forward(self, input, hx):
        if hx is None:
            hx = Variable(input.new_zeros(input.size(0), self.hidden_size))
        hy = torch.mm(input, self.W_xh) + torch.mm(hx, self.W_hh) + self.b_h
        hy = torch.tanh(hy)
        out = torch.mm(hy, self.W_hq) + self.b_q
        return out, hy


class RNNCellBase(nn.Module):
    def extra_repr(self):
        s = '{input_size}, {hidden_size}'
        if 'bias' in self.__dict__ and self.bias is not True:
            s += ', bias={bias}'
        if 'nonlinearity' in self.__dict__ and self.nonlinearity != 'tanh':
            s += ', nonlinearity={nonlinearity}'
        return s.format(**self.__dict__)

    def check_forward_input(self, input):
        if input.size(1) != self.input_size:
            raise RuntimeError(
                'input has inconsistent input_size: got {}, expected {}'.
                format(input.size(1), self.input_size))

    def check_forward_hidden(self, input, hx, hidden_label=''):
        if input.size(0) != hx.size(0):
            raise RuntimeError(
                "Input batch size {} doesn't match hidden{} batch size {}".
                format(input.size(0), hidden_label, hx.size(0)))

        if hx.size(1) != self.hidden_size:
            raise RuntimeError(
                'hidden{} has inconsistent hidden_size: got {}, expected {}'.
                format(hidden_label, hx.size(1), self.hidden_size))


class RNNCell(RNNCellBase):
    r"""An Elman RNN cell with tanh or ReLU non-linearity.

    .. math::

        h' = \tanh(w_{ih} x + b_{ih}  +  w_{hh} h + b_{hh})

    If :attr:`nonlinearity` is `'relu'`, then ReLU is used in place of tanh.

    Args:
        input_size: The number of expected features in the input `x`
        hidden_size: The number of features in the hidden state `h`
        bias: If ``False``, then the layer does not use bias weights `b_ih` and `b_hh`.
            Default: ``True``
        nonlinearity: The non-linearity to use. Can be either 'tanh' or 'relu'. Default: 'tanh'

    Inputs: input, hidden
        - **input** of shape `(batch, input_size)`: tensor containing input features
        - **hidden** of shape `(batch, hidden_size)`: tensor containing the initial hidden
          state for each element in the batch.
          Defaults to zero if not provided.

    Outputs: h'
        - **h'** of shape `(batch, hidden_size)`: tensor containing the next hidden state
          for each element in the batch

    Attributes:
        weight_ih: the learnable input-hidden weights, of shape
            `(input_size x hidden_size)`
        weight_hh: the learnable hidden-hidden weights, of shape
            `(hidden_size x hidden_size)`
        bias_ih: the learnable input-hidden bias, of shape `(hidden_size)`
        bias_hh: the learnable hidden-hidden bias, of shape `(hidden_size)`

    Examples::

        >>> rnn = nn.RNNCell(10, 20)
        >>> input = torch.randn(6, 3, 10)
        >>> hx = torch.randn(3, 20)
        >>> output = []
        >>> for i in range(6):
                hx = rnn(input[i], hx)
                output.append(hx)
    """
    def __init__(self,
                 input_size,
                 hidden_size,
                 bias=True,
                 nonlinearity='tanh'):
        super(RNNCell, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.bias = bias
        self.nonlinearity = nonlinearity
        self.weight_ih = nn.Parameter(torch.Tensor(hidden_size, input_size))
        self.weight_hh = nn.Parameter(torch.Tensor(hidden_size, hidden_size))
        if bias:
            self.bias_ih = nn.Parameter(torch.Tensor(hidden_size))
            self.bias_hh = nn.Parameter(torch.Tensor(hidden_size))
        else:
            self.register_parameter('bias_ih', None)
            self.register_parameter('bias_hh', None)
        self.reset_parameters()

    def reset_parameters(self):
        stdv = 1.0 / math.sqrt(self.hidden_size)
        for weight in self.parameters():
            weight.data.uniform_(-stdv, stdv)

    def forward(self, input, hx=None):
        self.check_forward_input(input)
        if hx is None:
            hx = input.new_zeros(input.size(0),
                                 self.hidden_size,
                                 requires_grad=False)
        self.check_forward_hidden(input, hx)
        if self.nonlinearity == 'tanh':
            func = RNNTanhCell
        elif self.nonlinearity == 'relu':
            func = RNNReLUCell
        else:
            raise RuntimeError('Unknown nonlinearity: {}'.format(
                self.nonlinearity))

        return func(
            input,
            hx,
            self.weight_ih,
            self.weight_hh,
            self.bias_ih,
            self.bias_hh,
        )
