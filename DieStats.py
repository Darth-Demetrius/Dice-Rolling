import numpy as np
import warnings

class DieStats:
    # _avg = 0
    # _dice = {1: 0}
    # _mass = 1
    # _min = 0
    # _pmf = np.ones(1, dtype=int)
    # _var = 0

    def __init__(self, *args, **kwargs):
        self._avg  = kwargs.get("avg",  0)
        self._dice = kwargs.get("dice", {1:0})
        self._mass = kwargs.get("mass", 1)
        self._min  = kwargs.get("min",  0)
        self._pmf  = kwargs.get("pmf",  np.ones(1, dtype=int))
        self._var  = kwargs.get("var",  0)
        if len(args) == 0: return

        args = list(args)
        while len(args) > 0:
            x = args.pop(0)

            if isinstance(x, int):
                if len(args) > 0 and isinstance(args[0], int): self.add_die(x, args.pop(0))
                else: self.add_die(x)
                continue
            if isinstance(x, dict):
                for key in x:
                    if isinstance(key, int) and isinstance(x[key], int):
                        self.add_die(x[key], key)
                        continue
                    raise TypeError("Dict arguments must be in to form of {die1: count1, ...}")
                continue
            if isinstance(x, tuple):
                if len(x) == 2 and isinstance(x[0], int) and isinstance(x[1], int):
                    self.add_die(x[0], x[1])
                    continue
                raise TypeError("Tuple arguments must be in to form of (die, count)")
            raise TypeError("Arguments must be integers, dictionaries, or, tuples.")


    def add_die(self, count: int, sides: int = 1):
        if count == 0 or sides == 0:
            warnings.warn("Rolling 0 dice or a die with 0 sides does nothing.")
            return
        if count < 0: sides, count = -sides, -count # If subtracting dice, use -sides and abs(count)
        self._avg += count * (sides+1) / 2
        self._dice[sides] = self._dice.get(sides, 0) + count # Add dice to dict
        if sides < 0:
            self._min += count*sides # Subtract from minimum
            sides = -sides # Use positive sides for mass and variance calculations
        else:
            self._min += count # Add count to minimum
        self._mass *= abs(sides)**count
        self._var += count * (sides**2 - 1) / 12

        if count >= 2: # Double pmf to reduce convolutions by 1/2
            pmf_2 = np.arange(1, 2*sides, dtype=int) # Create array of correct size
            pmf_2[sides:] = pmf_2[sides-2::-1] # Array values should look like [1,2,3...x...3,2,1]
        if count%2 == 1: # odd
            pmf = np.ones(sides, dtype=int) # Base pmf of [1,1...1]
            count -= 1
        else: # even
            pmf = pmf_2.copy() # Base pmf of [1,2,3...n...3,2,1] # type: ignore
            count -=2
        while count >= 2:
            pmf = np.convolve(pmf, pmf_2) # type: ignore
            count -= 2
        self._pmf = np.convolve(self._pmf, pmf)

    def copy(self): return DieStats(**self._get())

    def set(self, **kwargs):
        self._avg  = kwargs.get('avg',  self._avg)
        self._dice = kwargs.get('dice', self._dice)
        self._mass = kwargs.get('mass', self._mass)
        self._min  = kwargs.get('min',  self._min)
        self._pmf  = kwargs.get('pmf',  self._pmf)
        self._var  = kwargs.get('var',  self._var)
        return self # End set

    def _get(self, default: bool = True, **kwargs):
        send = {}
        if kwargs.get('avg')  or (default and 'avg'  not in kwargs): send["avg"]  = self.get_avg()
        if kwargs.get('dice') or (default and 'dice' not in kwargs): send["dice"] = self.get_dice()
        if kwargs.get('mass') or (default and 'mass' not in kwargs): send["mass"] = self.get_mass()
        if kwargs.get('min')  or (default and 'min'  not in kwargs): send["min"]  = self.get_min()
        if kwargs.get('pmf')  or (default and 'pmf'  not in kwargs): send["pmf"]  = self.get_pmf()
        if kwargs.get('var')  or (default and 'var'  not in kwargs): send["var"]  = self.get_var()
        return send

    def get_avg(self):     return self._avg
    def get_dice(self):    return self._dice.copy()
    def get_mass(self):    return self._mass
    def get_max(self):     return self._min + len(self._pmf) - 1
    def get_min(self):     return self._min
    def get_pmf(self):     return self._pmf.copy()
    def get_pmfnorm(self): return self._pmf/self._mass
    def get_sigma(self):   return np.sqrt(self._var)
    def get_var(self):     return self._var


    def sum(*args: int | DieStats | tuple):
        avg = 0
        dice = {1:0}
        mass = 1
        min = 0
        pmf  = np.ones(1, dtype=int)
        var  = 0

        for arg in args:
            if isinstance(arg, int):
                avg += arg
                min += arg
                dice[1] += arg
            elif isinstance(arg, DieStats):
                avg += arg.get_avg()
                for key, value in arg.get_dice().items():
                    dice[key] = dice.get(key, 0) + value
                mass *= arg.get_mass()
                min += arg.get_min()
                pmf = np.convolve(pmf, arg.get_pmf())
                var += arg.get_var()
            else:
                warnings.warn(f"Argument {arg} of type {type(arg)} is not an int or DieStats and will be ignored.")
        return DieStats(avg=avg, dice=dice, mass=mass, min=min, pmf=pmf, var=var)

    def __add__( self, other): return self.sum(other)
    def __radd__(self, other): return self.sum(other)
    def __iadd__(self, other):
        self = self + other
        return self
    def __sub__( self, other): return self.sum(-other)
    def __rsub__(self, other): return (-self).sum(other)
    def __isub__(self, other):
        self = self - other
        return self

    def scalar_multiply(self, count: int, mult_const: bool = True, roll_new: bool = True):
        if count == 0: return DieStats()
        if count < 0:
            self = -self
            count = -count
        if count == 1: return self

        avg = self.get_avg() * count
        dice = self.get_dice()
        for die in dice:
            if mult_const or die != 1:
                dice[die] *= count
        min = self.get_min()*count
        if not mult_const: min -= dice[1]*(count-1)
        if roll_new:
            mass = self.get_mass()**count
            pmf = self.get_pmf()
            for i in range(1, count):
                pmf = np.convolve(pmf, self._pmf)
            var = self.get_var() * count
        else:
            mass = self.get_mass()
            pmf = np.zeros(count*(len(self)-1) + 1, dtype=int)
            for i in range(len(self)):
                pmf[count*i] = self._pmf[i]
            var = self.get_var() * count**2

        return DieStats(avg=avg, dice=dice, mass=mass, min=min, pmf=pmf, var=var)
    def __mul__( self, other): return self.scalar_multiply(other)
    def __rmul__(self, other): return self.scalar_multiply(other)
    def __imul__(self, other):
        self = self*other
        return self

    def roll(self, count:int):
        if not isinstance(count, int): return NotImplemented
        rng = np.random.default_rng()
        return rng.choice(np.arange(self._min, self._min+len(self._pmf)), count, p=self.get_pmfnorm())
    def __matmul__( self, count): return self.roll(count)
    def __rmatmul__(self, count): return self.roll(count)
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
        dice = {1: -self._dice[1]}
        for key in self._dice: dice[-key] = self._dice[key]
        del dice[-1]

        min = -self.get_max()
        pmf=self._pmf[::-1]

        return self.copy().set(dice=dice, min=min, pmf=pmf)
    def __pos__(self): return self


    def __len__(self): return len(self._pmf)

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
    def __ceil__(self): self.get_max()

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
            other = other - self.__floor__()
            if other < 0: return 0
            if other > self.__len__(): return 0
            return self.get_pmf()[other]/self.get_mass()
        return NotImplemented
    def __ne__(self, other): # type: ignore
        return 1 - self.__eq__(other)


    def conditional_roll(self, output:list, condition:list | None=None):
        """
        output: A list of resulting roll (or roll-like) objects to be rolled if the corresponding condition is met or exeeded.
        condition [optional]: A list of strictly decreasing integers.

        The output list must be the same length as the condition list or exactly 1 longer. If they are the same length and all conditions are evaluated as false the return will 0, otherwise the final element of output will be returned.

        If output is given but not condition, it should instead be in the form of a list of (output, condition) tuples; again, with the conditions in strictly decreasing order. If all tuples contain 2 elements, then the all false condition output will default to 0, otherwise, if the final tuple only contains 1 element (output,), this final value will be used.
        """

        self = self.copy()
        if condition is None:
            if len(output[-1]) == 1:
                output[-1] += (-np.inf,)
            output, condition = map(list, zip(*output))
        if condition[-1] != -np.inf:
            condition.append(-np.inf)
        if len(condition) > len(output):
            output.append(0)
        cond_cnt = len(output)
        for c in range(cond_cnt): # Ensure all outputs are DieStats
            if not isinstance(output[c], DieStats):
                output[c] = DieStats(output[c])

        # for c in range(cond_cnt): # Normalize conditions by effectively setting _min to 0
        #     condition[c] = condition[c] - self.get_min()
        counts = np.zeros(cond_cnt, dtype=int) # Keep track of how many ways to get each output

        c = 0 # Current condition evluation
        for i in range(len(self)-1, -1, -1): # Iterate through possible rolls high->low
            while i + self.get_min() < condition[c]: c += 1 # If fails condition: check next condition
            counts[c] += self._pmf[i] # Add pmf to counts
        del c

        # weights = np.ones(cond_cnt, dtype=int) # The multiplier for each output's pmf
        # for c in range(cond_cnt):
        #     weights[c] = output[c].get_mass() # Set weights to the total mass of each output
        # lcm = np.lcm.reduce(weights) # Find lcm of all weights
        # weights = lcm // weights * counts
        # weights //= np.gcd.reduce(weights)

        max_, min_ = -np.inf, np.inf
        for c in range(cond_cnt):
            if counts[c] > 0: # If there is at least one case this condition was met
                max_ = max(max_, output[c].get_max())
                min_ = min(min_, output[c].get_min())

        if max_ == -np.inf:# If no conditions were met: return blank roll
            return DieStats()

        pmf = np.zeros(int(max_ - min_ + 1), dtype=int)
        mass, avg = 0, 0
        for c in range(cond_cnt):
            if counts[c] == 0: continue # If this condition was never met
            offset = output[c].get_min() - min_
            for i in range(len(output[c])):
                weight = output[c]._pmf[i] #* weights[c]
                pmf[i + offset] += weight
                mass += weight
                avg += weight * (i + offset)
        avg = avg/mass + min_
        var = np.var(pmf)

        return DieStats(avg=avg, mass=mass, min=min_, pmf=pmf, var=var)


    def __str__(self):  return NotImplemented
    def text(self):     return f"{self.min_txt()}\n> {self.max_txt()}\n> {self.mean_txt()}\n> {self.std_txt()}"
    def print(self, before: str="", after: str=""): print(before + self.text() + after)
    def min_txt(self):  return f"Minimum: {self.get_min()}"
    def max_txt(self):  return f"Maximum: {self.get_max()}"
    def mean_txt(self): return f"Average: {self.get_avg()}"
    def var_txt(self):  return f"Variance: {self.get_var()}"
    def std_txt(self):  return f"Standard deviation: {self.get_sigma()}"
    def dice_txt(self): return f"Dice: {self.get_dice()}"
    def pmf_txt(self):
        return f"PMF of possible values (bounds: [{self.get_min()}, {self.get_max()}]):/n{self.get_pmf()}"
    def pdf_txt(self):  return f"PDF of possible values, 1st element is P(min):\n{self.get_pmfnorm()}"
    def mass_txt(self): return f"Number of possibilities: {self.get_mass()}"
