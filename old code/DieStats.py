from enum import StrEnum
import numpy as np
import warnings

class Mode(StrEnum):
    TIMES = "times"
    SCALE = "scale"

class DieStats:
    # _avg: float = 0
    # _dice: dict[int, int] = {1: 0}
    # _mass: int = 1
    # _min: int = 0
    # _mod: bool = False
    # _mode: Mode = Mode.TIMES | Mode.SCALE
    # _pmf: np.ndarray = np.ones(1, dtype=int)
    # _var: int = 0

    def __init__(self, *args, **kwargs):
        """
        Initialize a DieStats object to represent a probability distribution of dice rolls.
        
        Args:
            *args: Variable-length argument list. Each argument can be:
                - int: Number of sides for a single die (count defaults to 1)
                - int, int: Count and sides (e.g., 2, 6 for two d6s)
                - dict: Mapping of sides to count (e.g., {6: 2} for two d6s)
                - tuple: (count, sides) pair (e.g., (2, 6) for two d6s)
            **kwargs: Keyword arguments for internal state:
                - avg (int): Average value of the distribution (default: 0)
                - dice (dict): Dictionary mapping sides to count (default: {1:0})
                - mass (int): Total probability mass (default: 1)
                - min (int): Minimum possible roll value (default: 0)
                - mod (bool): Modified flag, if set then the dice dict is not accurate (default: False)
                - mode (Mode): Multiplication mode (Mode.TIMES or Mode.SCALE, default: Mode.TIMES)
                - pmf (np.ndarray): Probability mass function (default: [1])
                - var (int): Variance of the distribution (default: 0)
        """
        self._avg  = kwargs.get("avg",  0)
        self._dice = kwargs.get("dice", {1:0})
        self._mass = kwargs.get("mass", 1)
        self._min  = kwargs.get("min",  0)
        self._mod  = kwargs.get("mod",  False)
        self._mode = kwargs.get("mode", Mode.TIMES)
        self._pmf  = kwargs.get("pmf",  np.ones(1, dtype=int))
        self._var  = kwargs.get("var",  0)
        if len(args) == 0: return

        self.add_dice(*args)

    @staticmethod
    def parse_dice(*args: DieStats | dict | tuple | list | int):
        """
        Generator that parses and standardizes die inputs, yielding DieStats objects or standardized dicts.
        
        Accepts multiple arguments, each can be:
        - DieStats: yields the DieStats object as-is
        - dict: validates {sides: count} pair and yields standardized result
        - tuple: (count, sides) pair validated and standardized
        - list: recursively processes each element
        - int: flat value treated as {1: count}
        - consecutive ints: treated as (count, sides) pair
        
        Yields:
            DieStats or dict: Standardized die specifications
        """
        def _standardize(die: dict[int, int]) -> dict[int, int]:
            (sides, count), = die.items()  # Unpack single item; raises error if dict length != 1
            if sides == 0 or count == 0:
                warnings.warn(f"Rolling 0 dice or a die with 0 sides does nothing. Ignoring {count}d{sides}.")
                return {1: 0}
            # If subtracting dice (not flat value), negate both sides and count
            if sides != 1 and (count < 0 or sides == -1):
                return {-sides: -count}
            return die

        args_list = list(args)
        i = 0

        while i < len(args_list):
            arg = args_list[i]
            i += 1

            match arg:
                case DieStats():
                    yield arg

                case dict():
                    for sides, count in arg.items():
                        if not isinstance(sides, int) or not isinstance(count, int):
                            warnings.warn(f"{{{sides}: {count}}} of type {{{type(sides).__name__}: {type(count).__name__}}} is not valid (must be {{int: int}}). Ignoring this entry.")
                        else:
                            yield _standardize({sides: count})

                case tuple():
                    if len(arg) != 2:
                        warnings.warn(f"Tuple {arg} has length {len(arg)}, but must be (count, sides). Ignoring.")
                    elif not isinstance(arg[0], int) or not isinstance(arg[1], int):
                        warnings.warn(f"Tuple {arg} of type ({type(arg[0]).__name__}, {type(arg[1]).__name__}) is not valid (must be (int, int)). Ignoring.")
                    else:
                        count, sides = arg
                        yield _standardize({sides: count})
                case list():
                    yield from DieStats.parse_dice(*arg)

                case int():
                    # Check if next item is also an int (pair handling)
                    if i < len(args_list) and isinstance(args_list[i], int):
                        count, sides = arg, args_list[i]
                        i += 1  # Skip next item since it's part of the pair
                        yield _standardize({sides: count})
                    else:
                        yield {1: arg}

                case _:
                    warnings.warn(f"Argument of type {type(arg).__name__} is not valid die input. Ignoring.")

    def copy(self): return DieStats(**self._get())

    def _set(self, **kwargs):
        self._avg  = kwargs.get('avg',  self._avg)
        self._dice = kwargs.get('dice', self._dice)
        self._mass = kwargs.get('mass', self._mass)
        self._min  = kwargs.get('min',  self._min)
        self._mod  = kwargs.get('mod',  True)
        self.set_mode(kwargs.get('mode', self._mode))
        self._pmf  = kwargs.get('pmf',  self._pmf)
        self._var  = kwargs.get('var',  self._var)
        return self

    def set_mode(self, mode: str | Mode):
        if mode not in Mode:
            warnings.warn(f"Invalid mode '{mode}' provided. Mode must be 'times' or 'scale'. Keeping current mode '{self._mode}'.")
        else: self._mode = Mode(mode)
        return self

    def _get(self, default: bool = True, **kwargs):
        send = {}
        if kwargs.get('avg')  or (default and 'avg'  not in kwargs): send["avg"]  = self.get_avg()
        if kwargs.get('dice') or (default and 'dice' not in kwargs): send["dice"] = self.get_dice()
        if kwargs.get('mass') or (default and 'mass' not in kwargs): send["mass"] = self.get_mass()
        if kwargs.get('min')  or (default and 'min'  not in kwargs): send["min"]  = self.get_min()
        if kwargs.get('mod')  or (default and 'mod'  not in kwargs): send["mod"]  = self.get_mod()
        if kwargs.get('mode') or (default and 'mode' not in kwargs): send["mode"] = self.get_mode()
        if kwargs.get('pmf')  or (default and 'pmf'  not in kwargs): send["pmf"]  = self.get_pmf()
        if kwargs.get('var')  or (default and 'var'  not in kwargs): send["var"]  = self.get_var()
        return send

    # Getters for internal state
    def get_avg(self):     return self._avg
    def get_dice(self):    return self._dice.copy()
    def get_mass(self):    return self._mass
    def get_max(self):     return self._min + len(self._pmf) - 1
    def get_min(self):     return self._min
    def get_mod(self):     return self._mod
    def get_mode(self):    return self._mode
    def get_pmf(self):     return self._pmf.copy()
    def get_pmfnorm(self): return self._pmf/self._mass
    def get_sigma(self):   return np.sqrt(self._var)
    def get_var(self):     return self._var

    # Adding and combining dice
    def add_dice(self, *args: DieStats | dict | tuple | list | int):
        """
        Add or subtract dice from the distribution using flexible input formats.
        
        Accepts multiple arguments in various formats:
        - (count, sides): Tuple pair
        - {sides: count}: Dictionary format
        - DieStats: Copy dice from another DieStats object
        - list: Process list elements recursively
        - int: Flat value (treated as count of 1-sided dice)
        - consecutive ints: Treated as (count, sides) pair
        
        Pass negative count or sides to subtract. Negative sides are stored
        in the dice dict to distinguish added from subtracted dice.
        
        Returns:
            self (modifies distribution in-place)
        """
        for parsed in DieStats.parse_dice(*args):
            if isinstance(parsed, DieStats):
                # Handle DieStats objects
                self._avg += parsed.get_avg()
                for key, value in parsed.get_dice().items():
                    self._dice[key] = self._dice.get(key, 0) + value
                self._mass *= parsed.get_mass()
                self._min += parsed.get_min()
                self._mod = self._mod or parsed.get_mod()
                self._pmf = np.convolve(self._pmf, parsed.get_pmf())
                self._var += parsed.get_var()
            else:
                # Handle standardized dice dicts
                (sides, count), = parsed.items()
                self._avg += np.sign(sides) * count * (abs(sides) + 1) / 2
                self._dice[sides] = self._dice.get(sides, 0) + count
                if sides < 0:  # Min decreases by side count per negative die
                    self._min += count * sides
                else:  # Min increases by 1 per positive die
                    self._min += count
                self._mass *= abs(sides) ** count
                self._var += count * (sides ** 2 - 1) / 12

                # Build PMF by repeated convolution
                new_pmf = np.ones(abs(sides), dtype=int)  # PMF for a single die
                for _ in range(count):
                    self._pmf = np.convolve(self._pmf, new_pmf)

        return self

    @staticmethod
    def sum(*args: DieStats | dict | tuple | list | int):
        """
        Create and return a new DieStats representing the sum of all given dice specifications.
        
        Flexible input handling via parse_dice and add_dice. Accepts multiple arguments:
        - DieStats: Includes the distribution from another DieStats object
        - dict {sides: count}: Dictionary format
        - tuple (count, sides): Tuple pairs
        - list: Recursively processes each element
        - int: Flat value or paired with next int as (count, sides)
        
        Returns:
            DieStats: New object representing the combined distribution
        """
        return DieStats().add_dice(*args)

    # Operator overloads for arithmetic operations and comparisons
    def __add__( self, other): return DieStats.sum(self, other)
    def __radd__(self, other): return self.__add__(other)
    def __iadd__(self, other): return self.add_dice(other)
    def __sub__( self, other): return DieStats.sum(self, -other)
    def __rsub__(self, other): return self.__sub__(other)
    def __isub__(self, other): return self.add_dice(-other)

    # Scalar multiplication and repeated addition
    def i_scalar_multiply(self, scalar: int):
        if scalar == 0: return DieStats()
        if scalar < 0: self, scalar = -self, -scalar

        avg = self.get_avg() * scalar
        min = self.get_min() * scalar
        pmf = np.zeros(scalar*(len(self)-1) + 1, dtype=int)
        for i in range(len(self)):
            pmf[scalar*i] = self._pmf[i]
        var = self.get_var() * scalar**2

        return self._set(avg=avg, min=min, pmf=pmf, var=var) # mod = True
    @staticmethod
    def scalar_multiply(roll: DieStats, scalar: int):
        return roll.copy().i_scalar_multiply(scalar)

    def i_times(self, count: int):
        if count == 0: return self._set(**DieStats()._get())
        if count < 0: old, count = -self, -count
        else: old = self.copy()
        for _ in range(count-1):
            self = self.add_dice(old)
        return self
    @staticmethod
    def times(roll: DieStats, count: int):
        if count == 0: return DieStats()
        return roll.copy().i_times(count)

    def __mul__( self, other):
        if not isinstance(other, int): return NotImplemented
        if self.get_mode() == Mode.TIMES: return DieStats.times(self, other)
        if self.get_mode() == Mode.SCALE: return DieStats.scalar_multiply(self, other)
    def __rmul__(self, other): return self.__mul__(other)
    def __imul__(self, other):
        if not isinstance(other, int): return NotImplemented
        if self.get_mode() == Mode.TIMES: return self.i_times(other)
        if self.get_mode() == Mode.SCALE: return self.i_scalar_multiply(other)

    def roll(self, count: int = 1):
        if not isinstance(count, int): return NotImplemented
        rng = np.random.default_rng()
        return rng.choice(np.arange(self._min, self._min+len(self._pmf)), count, p=self.get_pmfnorm())
    def __matmul__( self, count): return self.roll(count)
    def __rmatmul__(self, count): return self.__matmul__(count)
    def __imatmul__(self, other): return NotImplemented

    def __truediv__(self, other): return NotImplemented
    def __floordiv__(self, other): return NotImplemented
        # self = self.copy()
        # self._min //= other


    def __mod__(self, other): return self == other # odds of rolling a specific number
    # def __divmod__(self, other): return NotImplemented
    # def __pow__(self, other, modulo): return NotImplemented
    # def __lshift__(self, other): return NotImplemented
    # def __rshift__(self, other): return NotImplemented
    # def __and__(self, other): return NotImplemented
    # def __xor__(self, other): return NotImplemented
    # def __or__(self, other): return NotImplemented

    def __neg__(self):
        dice = {1: -self.get_dice()[1]}
        for key in self.get_dice(): dice[-key] = self.get_dice()[key]
        del dice[-1]

        min = -self.get_max()
        pmf=self.get_pmf()[::-1]

        return self.copy()._set(dice=dice, min=min, pmf=pmf)
    def __pos__(self): return self

    def __len__(self): return len(self.get_pmf())

    def __int__(self): return int(np.ceil(self.__float__()))
    def __float__(self): return self.get_avg()

    def __round__(self, direction="down"):
        if isinstance(direction, str):
            if   direction[0] == 'd': direction = -1
            elif direction[0] == 'u': direction = 1
            elif not isinstance(direction, int): direction = 0
        if direction < 0: return self.__trunc__()
        if direction > 0: return self.__int__()
        return self.__float__() # direction == 0
    def __trunc__(self): return int(self.__float__())
    def __floor__(self): return self.get_min()
    def __ceil__(self):  return self.get_max()

    def __lt__(self, other):
        if isinstance(other, int):
            if self.get_max() <  other: return 1
            if self.get_min() >= other: return 0

            pmf = self.get_pmf()
            chances = 0
            for i in range(other - self.__floor__()):
                chances += pmf[i]
            return chances/self.get_mass()

        elif isinstance(other, DieStats):
            if self.get_max() <  other.get_min(): return 1
            if self.get_min() >= other.get_max(): return 0

            return NotImplemented
        else:
            return NotImplemented
    def __le__(self, other):
        if isinstance(other, int):
            return self.__lt__(other + 1)
        return NotImplemented
    def __gt__(self, other):
        if isinstance(other, int):
            return 1 - self.__lt__(other + 1)
        return NotImplemented
    def __ge__(self, other):
        if isinstance(other, int):
            return 1 - self.__lt__(other)
        return NotImplemented
    def __eq__(self, other):
        if isinstance(other, int):
            if other < self.get_min(): return 0
            if other > self.get_max(): return 0
            return self.get_pmf()[other - self.get_min()] / self.get_mass()
        return NotImplemented
    def __ne__(self, other): # type: ignore
        return 1 - self.__eq__(other)

    def conditional_roll(self, checks: list[tuple]):
        """
        Build a new distribution by selecting one output distribution per roll outcome.

        Args:
            checks: A list of tuples `(output, threshold)` in ascending threshold order.
                For each roll outcome, the output whose threshold is the highest one <= that
                outcome is used. Tuple `(output,)` with no threshold defaults to -inf.
                If out of order, will be sorted with a warning.

        Returns:
            DieStats: The weighted mixture of branch output distributions.
        """

        # Convert checks to (DieStats, threshold) pairs.
        outputs = []
        thresholds = []
        for output_spec, *threshold_spec in checks:
            dist = output_spec if isinstance(output_spec, DieStats) else DieStats(output_spec)
            thresh = float(threshold_spec[0]) if threshold_spec else -np.inf
            outputs.append(dist)
            thresholds.append(thresh)

        # Sort checks if out of order.
        thresholds_arr = np.asarray(thresholds, dtype=float)
        if not np.all(thresholds_arr[:-1] <= thresholds_arr[1:]):
            warnings.warn("checks not in ascending threshold order; sorting.")
            sort_idx = np.argsort(thresholds_arr)
            outputs = [outputs[i] for i in sort_idx]
            thresholds_arr = thresholds_arr[sort_idx]

        # Map roll values to output checks using highest qualifying threshold.
        roll_values = np.arange(self.get_min(), self.get_max() + 1)
        branch_idx = np.searchsorted(thresholds_arr, roll_values, side='right') - 1
        branch_weights = np.bincount(branch_idx, weights=self._pmf, minlength=len(outputs)).astype(np.int64)

        # Find active checks and their bounds.
        active = np.flatnonzero(branch_weights)
        if active.size == 0:
            return DieStats()

        min_val = min(outputs[i].get_min() for i in active)
        max_val = max(outputs[i].get_max() for i in active)

        # Combine PMFs from active checks weighted by their counts.
        pmf = np.zeros(max_val - min_val + 1, dtype=np.int64)
        for i in active:
            offset = outputs[i].get_min() - min_val
            pmf[offset:offset + len(outputs[i])] += outputs[i]._pmf * branch_weights[i]

        # Compute statistics.
        mass = int(pmf.sum())
        support = np.arange(min_val, max_val + 1)
        avg = float(np.dot(pmf, support) / mass)
        var = float(np.dot(pmf, (support - avg) ** 2) / mass)

        return DieStats(avg=avg, mass=mass, min=min_val, mod=True, pmf=pmf, var=var)

    def __str__(self):  return NotImplemented
    def __repr__(self): return f"DieStats(avg={self._avg}, dice={self._dice}, mass={self._mass}, min={self._min}, pmf={self._pmf}, var={self._var})"
    def text(self):     return f"{self.min_txt()}\n> {self.max_txt()}\n> {self.mean_txt()}\n> {self.std_txt()}"
    def print(self, before: str="", after: str=""): print(before + self.text() + after)
    def min_txt(self):  return f"Minimum: {self.get_min()}"
    def max_txt(self):  return f"Maximum: {self.get_max()}"
    def mean_txt(self): return f"Average: {self.get_avg()}"
    def var_txt(self):  return f"Variance: {self.get_var()}"
    def std_txt(self):  return f"Standard deviation: {self.get_sigma()}"
    def dice_txt(self): return f"Dice: {self.get_dice()}"
    def pmf_txt(self):  return f"PMF of possible values (bounds: [{self.get_min()}, {self.get_max()}]):/n{self.get_pmf()}"
    def pdf_txt(self):  return f"PDF of possible values, 1st element is P(min):\n{self.get_pmfnorm()}"
    def mass_txt(self): return f"Number of possibilities: {self.get_mass()}"
