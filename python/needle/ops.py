"""Operatpr table."""
# Global operator table.
from numbers import Number
from typing import Optional, List
from .autograd import NDArray
from .autograd import Op, Tensor, Value, TensorOp
from .autograd import TensorTuple, TensorTupleOp
from . import init
import numpy

from .backend_selection import array_api, NDArray


class MakeTensorTuple(TensorTupleOp):
    def compute(self, *args) -> tuple:
        return tuple(args)

    def gradient(self, out_grad, node):
        assert isinstance(out_grad, TensorTuple)
        return tuple([out_grad[i] for i in range(len(out_grad))])


def make_tuple(*args):
    return MakeTensorTuple()(*args)


class TupleGetItem(TensorOp):
    def __init__(self, index):
        self.index = index

    def __call__(self, a: TensorTuple, fold_const=True) -> Value:
        assert isinstance(a, TensorTuple)
        # constant folding
        if fold_const and isinstance(a.op, MakeTensorTuple):
            return a.inputs[self.index]
        return Tensor.make_from_op(self, [a])

    def compute(self, a):
        return a[self.index]

    def gradient(self, out_grad, node):
        index = self.index
        in_grad = []
        for i, value in enumerate(node.inputs[0]):
            if i != index:
                in_grad.append(init.zeros_like(value, device=value.device))
            else:
                in_grad.append(out_grad)
        return MakeTensorTuple()(*in_grad)


def tuple_get_item(value, index):
    return TupleGetItem(index)(value)


class FusedAddScalars(TensorTupleOp):
    def __init__(self, c0: float, c1: float):
        self.c0 = c0
        self.c1 = c1

    def compute(self, a):
        return a + self.c0, a + self.c1

    def gradient(self, out_grad, node):
        return out_grad[0] + out_grad[1]


def fused_add_scalars(x, c0, c1):
    return FusedAddScalars(c0, c1)(x)


class EWiseAdd(TensorOp):
    def compute(self, a: NDArray, b: NDArray):
        return a + b

    def gradient(self, out_grad: Tensor, node: Tensor):
        return out_grad, out_grad


def add(a, b):
    return EWiseAdd()(a, b)


class AddScalar(TensorOp):
    def __init__(self, scalar):
        self.scalar = scalar

    def compute(self, a: NDArray):
        return a + numpy.float32(self.scalar)

    def gradient(self, out_grad: Tensor, node: Tensor):
        return out_grad


def add_scalar(a, scalar):
    return AddScalar(scalar)(a)


class EWiseMul(TensorOp):
    def compute(self, a: NDArray, b: NDArray):
        return a * b

    def gradient(self, out_grad: Tensor, node: Tensor):
        lhs, rhs = node.inputs
        return out_grad * rhs, out_grad * lhs


def multiply(a, b):
    return EWiseMul()(a, b)


class MulScalar(TensorOp):
    def __init__(self, scalar):
        self.scalar = scalar

    def compute(self, a: NDArray):
        return a * numpy.float32(self.scalar)

    def gradient(self, out_grad: Tensor, node: Tensor):
        return (out_grad * self.scalar,)


def mul_scalar(a, scalar):
    return MulScalar(scalar)(a)


class PowerScalar(TensorOp):
    """Op raise a tensor to an (integer) power."""

    def __init__(self, scalar: int):
        self.scalar = scalar

    def compute(self, a: NDArray) -> NDArray:
        # BEGIN YOUR SOLUTION
        return a ** self.scalar
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return out_grad * self.scalar * power_scalar(node.inputs[0], self.scalar-1)
        # END YOUR SOLUTION


def power_scalar(a, scalar):
    return PowerScalar(scalar)(a)


class EWiseDiv(TensorOp):
    """Op to element-wise divide two nodes."""

    def compute(self, a, b):
        # BEGIN YOUR SOLUTION
        return a / b
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        lhs, rhs = node.inputs
        grad_a = out_grad / rhs
        grad_b = -out_grad * lhs / rhs / rhs
        return grad_a, grad_b
        # END YOUR SOLUTION


def divide(a, b):
    return EWiseDiv()(a, b)


class DivScalar(TensorOp):
    def __init__(self, scalar):
        self.scalar = scalar

    def compute(self, a):
        # BEGIN YOUR SOLUTION
        return a / self.scalar
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return out_grad / self.scalar
        # END YOUR SOLUTION


def divide_scalar(a, scalar):
    return DivScalar(scalar)(a)


class Transpose(TensorOp):
    def __init__(self, axes: Optional[tuple] = None):
        self.axes = axes

    def compute(self, a):
        # BEGIN YOUR SOLUTION
        index = list(range(len(a.shape)))
        if self.axes is None:
            index[-1], index[-2] = index[-2], index[-1]
        else:
            axis1 = self.axes[0]
            axis2 = self.axes[1]
            index[axis1], index[axis2] = index[axis2], index[axis1]
        return a.permute(tuple(index))
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return transpose(out_grad, axes=self.axes)
        # END YOUR SOLUTION


def transpose(a, axes=None):
    return Transpose(axes)(a)


class Reshape(TensorOp):
    def __init__(self, shape):
        self.shape = shape

    def compute(self, a):
        # BEGIN YOUR SOLUTION
        return array_api.reshape(a, self.shape)
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return reshape(out_grad, node.inputs[0].shape)
        # END YOUR SOLUTION


def reshape(a, shape):
    return Reshape(shape)(a)


class BroadcastTo(TensorOp):
    def __init__(self, shape):
        self.shape = shape

    def compute(self, a):
        return array_api.broadcast_to(a, self.shape).compact()

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        input_shape = node.inputs[0].shape
        extra_len = len(out_grad.shape)-len(input_shape)
        index = tuple([i for i in reversed(range(len(out_grad.shape))) if (i < extra_len
                                                                           or out_grad.shape[i] != input_shape[i-extra_len])])
        return summation(out_grad, axes=index).reshape(input_shape)
        # END YOUR SOLUTION


def broadcast_to(a, shape):
    return BroadcastTo(shape)(a)


class Summation(TensorOp):
    def __init__(self, axes: Optional[tuple] = None):
        self.axes = axes

    def compute(self, a):
        # BEGIN YOUR SOLUTION
        if isinstance(self.axes, (tuple, list)):
            for i in self.axes:
                a = a.sum(i)
            return a
        else:
            return a.sum(self.axes)
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        shape = list(node.inputs[0].shape)
        if self.axes is None:
            shape = [1 for i in range(len(shape))]
        elif isinstance(self.axes, int):
            shape[self.axes] = 1
        else:
            for axis in self.axes:
                shape[axis] = 1
        return broadcast_to(reshape(out_grad, shape), node.inputs[0].shape)
        # END YOUR SOLUTION


def summation(a, axes=None):
    return Summation(axes)(a)


class MatMul(TensorOp):
    def compute(self, a, b):
        # BEGIN YOUR SOLUTION
        return a @ b
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        lhs, rhs = node.inputs
        grad_a = out_grad @ transpose(rhs)
        grad_b = transpose(lhs) @ out_grad
        if grad_a.shape != lhs.shape:
            grad_a = summation(grad_a, tuple(
                range(len(grad_a.shape)-len(lhs.shape))))
        if grad_b.shape != rhs.shape:
            grad_b = summation(grad_b, tuple(
                range(len(grad_b.shape)-len(rhs.shape))))
        return grad_a, grad_b
        # END YOUR SOLUTION


def matmul(a, b):
    return MatMul()(a, b)


class Negate(TensorOp):
    def compute(self, a):
        # BEGIN YOUR SOLUTION
        return -a
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return -out_grad
        # END YOUR SOLUTION


def negate(a):
    return Negate()(a)


class Log(TensorOp):
    def compute(self, a):
        # BEGIN YOUR SOLUTION
        return array_api.log(a)
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return out_grad / node.inputs[0]
        # END YOUR SOLUTION


def log(a):
    return Log()(a)


class Exp(TensorOp):
    def compute(self, a):
        # BEGIN YOUR SOLUTION
        return array_api.exp(a)
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return out_grad * exp(node.inputs[0])
        # END YOUR SOLUTION


def exp(a):
    return Exp()(a)


class ReLU(TensorOp):
    def compute(self, a):
        # BEGIN YOUR SOLUTION
        return array_api.maximum(a, 0)
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        input = node.inputs[0].cached_data
        hot = input >= 0
        return out_grad * Tensor(hot, device=out_grad.device, dtype=out_grad.dtype)
        # END YOUR SOLUTION


def relu(a):
    return ReLU()(a)


class LogSumExp(TensorOp):
    def __init__(self, axes: Optional[tuple] = None):
        self.axes = axes

    def compute(self, Z):
        # BEGIN YOUR SOLUTION
        Z_max = Z.max(self.axes)
        s = list(Z.shape)
        if self.axes is None:
            s = [1 for _ in range(len(Z.shape))]
        elif isinstance(self.axes, int):
            s[self.axes] = 1
        else:
            for i in self.axes:
                s[i] = 1
        Z = Z - array_api.broadcast_to(array_api.reshape(Z_max, s), Z.shape)
        Z = array_api.exp(Z).sum(self.axes)
        Z = array_api.log(Z)
        return Z + Z_max
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        input = node.inputs[0].cached_data
        Z_max = input.max(self.axes)
        s = list(input.shape)
        if self.axes is None:
            s = [1 for _ in range(len(input.shape))]
        else:
            for i in self.axes:
                s[i] = 1
        g = broadcast_to(reshape(out_grad, s), input.shape)
        input = input - \
            array_api.broadcast_to(array_api.reshape(Z_max, s), input.shape)
        expz = array_api.exp(input)
        expzsum = array_api.exp(input).sum(self.axes)
        logz = array_api.broadcast_to(
            array_api.reshape(expzsum, s), input.shape)
        return g / Tensor(logz, device=out_grad.device) * Tensor(expz, device=out_grad.device)
        # END YOUR SOLUTION


def logsumexp(a, axes=None):
    return LogSumExp(axes=axes)(a)


class Tanh(TensorOp):
    def compute(self, a):
        # BEGIN YOUR SOLUTION
        return a.tanh()
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return out_grad * (1.0 - tanh(node.inputs[0]) ** 2)
        # END YOUR SOLUTION


def tanh(a):
    return Tanh()(a)


class Stack(TensorOp):
    def __init__(self, axis: int):
        """
        Concatenates a sequence of arrays along a new dimension.
        Parameters:
        axis - dimension to concatenate along
        All arrays need to be of the same size.
        """
        self.axis = axis

    def compute(self, args):
        # BEGIN YOUR SOLUTION
        stack_dim = len(args)
        out = array_api.empty(
            (stack_dim, args[0].size), dtype=args[0].dtype, device=args[0].device)
        for i in range(stack_dim):
            out[i, :] = args[i].reshape((1, args[0].size))
        new_shape = (stack_dim,) + args[0].shape
        new_axes = [i for i in range(1, len(args[0].shape)+1)]
        new_axes.insert(self.axis, 0)
        out = out.reshape(new_shape).permute(new_axes)
        return out
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return split(out_grad, axis=self.axis)
        # END YOUR SOLUTION


def stack(args, axis):
    return Stack(axis)(make_tuple(*args))


class Split(TensorTupleOp):
    def __init__(self, axis: int):
        """
        Splits a tensor along an axis into a tuple of tensors.
        (The "inverse" of Stack)
        Parameters:
        axis - dimension to split
        """
        self.axis = axis

    def compute(self, A):
        # BEGIN YOUR SOLUTION
        stack_dim = A.shape[self.axis]
        new_axes = list(range(len(A.shape)))
        new_axes[0], new_axes[self.axis] = new_axes[self.axis], new_axes[0]
        new_shape = list(A.shape)
        new_shape.pop(self.axis)
        A = A.permute(tuple(new_axes)).reshape(
            (stack_dim, A.size // stack_dim))
        out = []
        for i in range(stack_dim):
            out.append(A[i, :].reshape(tuple(new_shape)))
        return out
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return stack(out_grad, axis=self.axis)
        # END YOUR SOLUTION


def split(a, axis):
    return Split(axis)(a)


class Flip(TensorOp):
    def __init__(self, axes: Optional[tuple] = None):
        self.axes = axes

    def compute(self, a):
        # BEGIN YOUR SOLUTION
        if self.axes == None:
            self.axes = tuple(range(len(a.shape)))
        return a.flip(self.axes)
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return flip(out_grad, self.axes)
        # END YOUR SOLUTION


def flip(a, axes):
    return Flip(axes)(a)


class Dilate(TensorOp):
    def __init__(self, axes: tuple, dilation: int):
        self.axes = axes
        self.dilation = dilation

    def compute(self, a):
        # BEGIN YOUR SOLUTION
        new_shape = list(a.shape)
        ndim = len(new_shape)
        for i in range(ndim):
            new_shape[i] = a.shape[i] * \
                ((1 + self.dilation) if i in self.axes else 1)
        out = array_api.full(tuple(new_shape), 0, device=a._device)
        sl = [slice(None), ] * ndim
        for i in range(ndim):
            if i in self.axes:
                sl[i] = slice(0, new_shape[i], self.dilation + 1)
        out[tuple(sl)] = a
        return out
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return undilate(out_grad, self.axes, self.dilation)
        # END YOUR SOLUTION


def dilate(a, axes, dilation):
    return Dilate(axes, dilation)(a)


class UnDilate(TensorOp):
    def __init__(self, axes: tuple, dilation: int):
        self.axes = axes
        self.dilation = dilation

    def compute(self, a):
        # BEGIN YOUR SOLUTION
        ndim = len(a.shape)
        sl = [slice(None), ] * ndim
        for i in range(ndim):
            if i in self.axes:
                sl[i] = slice(0, a.shape[i], self.dilation + 1)
        out = a[tuple(sl)]
        return out
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        return dilate(out_grad, self.axes, self.dilation)
        # END YOUR SOLUTION


def undilate(a, axes, dilation):
    return UnDilate(axes, dilation)(a)


class Conv(TensorOp):
    def __init__(self, stride: Optional[int] = 1, padding: Optional[int] = 0):
        self.stride = stride
        self.padding = padding

    def compute(self, A, B):
        # BEGIN YOUR SOLUTION
        A_pad = A.pad(((0, 0),) + ((self.padding, self.padding),)
                      * 2 + ((0, 0),))
        N, H, W, C_in = A_pad.shape
        K, _, _, C_out = B.shape
        Ns, Hs, Ws, Cs = A_pad.strides

        inner_dim = K * K * C_in
        new_h = (H-K) // self.stride + 1
        new_w = (W-K) // self.stride + 1
        A2col = A_pad.as_strided(shape=(N, new_h, new_w, K, K, C_in),
                                 strides=(Ns, Hs * self.stride, Ws * self.stride, Hs, Ws, Cs)).compact().reshape((N * new_h * new_w, inner_dim))
        out = A2col @ B.reshape((K*K*C_in, C_out))
        return out.reshape((N, new_h, new_w, C_out))
        # END YOUR SOLUTION

    def gradient(self, out_grad, node):
        # BEGIN YOUR SOLUTION
        # out_grad   (N, (H-K+2P)//S+1, (W-K+2P)//S+1, C_out)
        # x_grad    (N, H, W, C_in)
        # w_grad    (K, K, C_in, C_out)
        X, W = node.inputs
        K, _, _, C_out = W.shape
        # (H+2P-K+1)-K+1+2X = H-2K+2+2P+2X = H, X = K-P-1
        # n,nh,nw,cout conv k,k,cout,cin -> n,h,w,cin
        W = transpose(flip(W, (0, 1)), (2, 3))
        if (self.stride > 1):
            out_grad = dilate(out_grad, (1, 2), self.stride-1)
        x_grad = conv(out_grad, W, 1, K-self.padding-1)
        # H-(H-K+1+2P)+1+2X=K-2P+2X=K, X=P
        # cin,w,h,n conv nw,nh,n,cout -> cin,kw,kh,cout
        X = transpose(transpose(X, (1, 2)), (0, 3))
        out_grad = transpose(out_grad, (0, 2))
        w_grad = conv(X, out_grad, 1, self.padding)
        w_grad = transpose(w_grad, (0, 2))
        return x_grad, w_grad
        # END YOUR SOLUTION


def conv(a, b, stride=1, padding=1):
    return Conv(stride, padding)(a, b)
