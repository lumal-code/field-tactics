import numpy as np

class Vec2:
    def __init__(self, x, y):
        self.array = np.array([x, y], dtype=float)
        if not np.isfinite(self.array).all():
            raise ValueError("vector components must be finite")

    @property
    def x(self):
        return self.array[0]

    @x.setter
    def x(self, value):
        self.array[0] = value

    @property
    def y(self):
        return self.array[1]

    @y.setter
    def y(self, value):
        self.array[1] = value

    def magnitude(self):
        return np.linalg.norm(self.array)

    def normalize(self):
        length = self.magnitude()
        if length == 0:
            return Vec2(0, 0)
        return Vec2(*(self.array / length))

    def distance(self, b):
        return np.linalg.norm(self.array - b.array)

    def dot(self, other):
        return float(np.dot(self.array, other.array))

    def copy(self):
        return Vec2(self.x, self.y)

    def limit(self, max_magnitude):
        if not np.isfinite(max_magnitude) or max_magnitude < 0:
            raise ValueError("Maximum magnitude must be finite and nonnegative")

        length = self.magnitude()
        if length > max_magnitude:
            return Vec2(*(self.array * (max_magnitude / length)))
        return Vec2(*self.array)

    def __add__(self, other):
        return Vec2(*(self.array + other.array))

    def __sub__(self, other):
        return Vec2(*(self.array - other.array))

    def __mul__(self, scalar):
        return Vec2(*(self.array * scalar))

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        if not np.isfinite(scalar) or scalar == 0:
            raise ValueError("divisor must be finite and nonzero")
        return Vec2(*(self.array / scalar))

    def __repr__(self):
        return f"Vec2({self.x}, {self.y})"
