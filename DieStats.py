import numpy as np

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

		def add_dice(count:int, sides:int=1):
			if count == 0 or sides == 0: return # Rolling 0 dice does nothing
			if count < 0: sides, count = -sides, -count # If subtracting dice, use -sides and abs(count)
			self._avg += count * (sides+1) / 2
			self._dice[sides] = self._dice.get(sides, 0) + count # Add dice to dict
			if sides < 0:
				self._min += count*sides # Subtract from minimum
				sides = -sides
			else:
				self._min += count # Add count to minimum
			self._mass *= sides**count
			self._var += count * (sides**2 - 1) / 12

			if count >= 2: # Double pmf to reduce convolutions by 1/2
				pmf_2 = np.arange(1, 2*sides, dtype=int) # Create array of correct size
				pmf_2[sides:] = pmf_2[sides-2::-1] # Array values should look like [1,2,3...x...3,2,1]
			if count%2 == 1: # odd
				pmf = np.ones(sides, dtype=int) # Base pmf of [1,1...1]
				count -= 1
			else: # even
				pmf = pmf_2.copy() # Base pmf of [1,2,3...n...3,2,1]
				count -=2
			while count >= 2:
				pmf = np.convolve(pmf, pmf_2)
				count -= 2
			self._pmf = np.convolve(self._pmf, pmf)
		# end add_dice
		args = list(args)
		while len(args) > 0:
			x = args.pop(0)

			if isinstance(x, str):
				if self._name is not None: raise ValueError("You cannot set the name more than once.")
				x = x.strip()
				if x == "": raise ValueError("You cannot set a blank name.")
				self._name = x
				continue
			if isinstance(x, int):
				if len(args) > 0 and isinstance(args[0], int): add_dice(x, args.pop(0))
				else: add_dice(x)
				continue
			if isinstance(x, dict):
				for key in x:
					if isinstance(key, int) and isinstance(x[key], int):
						add_dice(x[key], key)
						continue
					raise TypeError("Dict arguments must be in to form of {die1: count1, ...}")
				continue
			if isinstance(x, tuple):
				if len(x) == 2 and isinstance(x[0], int) and isinstance(x[1], int):
					add_dice(x[0], x[1])
					continue
				raise TypeError("Tuple arguments must be in to form of (die, count)")
			raise TypeError("Arguments must be integers, dictionaries, tuples, or a string.")
		if self._name is None: raise ValueError("You must name a new roll.")
	#	end __init__

	def copy(self):
		return DieStats(**self._get(default=1))

	def set(self, avg: int=None, dice: dict=None, mass: int=None, min: int=None, pmf: np.array=None, var: float=None):
		if avg  is not None: self._avg  = avg
		if dice is not None: self._dice = dice
		if mass is not None: self._mass = mass
		if min  is not None: self._min  = min
		if pmf  is not None: self._pmf  = pmf
		if var  is not None: self._var  = var
		return self	#End set
	def _get(self, default: bool=None, avg: bool=None, dice: bool=None, mass: bool=None, min: bool=None, pmf: bool=None, var: bool=None):
		if None is default is avg is dice is mass is min is pmf is var:
			avg, dice, mass, min, pmf, var = 1,1,1,1,1,1
		send = {}
		if avg  or (avg  is None and default): send["avg"]  = self._avg
		if dice or (dice is None and default): send["dice"] = self._dice.copy()
		if mass or (mass is None and default): send["mass"] = self._mass
		if min  or (min  is None and default): send["min"]  = self._min
		if pmf  or (pmf  is None and default): send["pmf"]  = self._pmf.copy()
		if var  or (var  is None and default): send["var"]  = self._var
		return send

	def get_avg(self):
		return self._avg
	def get_dice(self):
		return self._dice.copy()
	def get_mass(self):
		return self._mass
	def get_max(self):
		return self._min + len(self._pmf) - 1
	def get_min(self):
		return self._min
	def get_pmf(self):
		return self._pmf.copy()
	def get_pmfnorm(self):
		return self._pmf/self.get_mass()
	def get_sigma(self):
		return np.sqrt(self.get_var())
	def get_var(self):
		return self._var


	def sum(*args):
		avg = 0
		dice = {1:0}
		mass = 1
		min = 0
		pmf  = np.ones(1, dtype=int)
		var  = 0

		roll_count = 0
		for arg in args:
			if isinstance(arg, int):
				avg += arg
				min += arg
				dice[1] += arg
			else:
				avg += arg.get_avg()
				for key in arg._dice: dice[key] = dice.get(key, 0) + arg._dice[key]
				mass *= arg.get_mass()
				min += arg.get_min()
				pmf = np.convolve(pmf, arg._pmf)
				var += arg.get_var()
				roll_count += 1
		return DieStats(avg=avg, dice=dice, mass=mass, min=min, pmf=pmf, var=var)	#End sum
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

	def scalar_multiply(self, count:int, mult_const:bool=None, roll_new:bool=None):
		if mult_const is None: mult_const = True
		if roll_new is None: roll_new = True
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
		
		
	 def __mod__(self, other): return self == other		#odds of rolling a specific number
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
	def __pos__(self): return NotImplemented


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
	def __trunc__(self):
		return int(self.__float__())
	def __floor__(self):
		return self.get_min()
	def __ceil__(self):
		self.get_max()

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
			
			return: NotImplemented
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
	def __ne__(self, other):
		return 1 - self.__eq__(other)


	def conditional_roll(in_check, output:list, condition:list=None, name:str=None):
		"""
		in_check: A roll object to be compared against the condition list.
		output: A list of resulting roll (or roll-like) objects to be rolled if the corresponding condition is met or exeeded.
		condition [optional]: A list of strictly decreasing integers.
		name [optional]: A string to name the resulting roll object.

		The output list must be the same length as the condition list or exactly 1 longer. If they are the same length and all conditions are evaluated as false the return will 0, otherwise the final element of output will be returned.

		If output is given but not condition, it should instead be in the form of a list of (output, condition) tuples; again, with the conditions in strictly decreasing order. If all tuples contain 2 elements, then the all false condition output will default to 0, otherwise, if the final tuple only contains 1 element (output,), this final value will be used.
		"""

		self = in_check.copy(name)
		if condition is None:
			if len(output[-1]) == 1: output[-1] += (np.NINF,)
			output, condition = map(list, zip(*output))
		if condition[-1] != np.NINF:
			condition.append(np.NINF)
		if len(condition) > len(output):
			output.append(0)
		cond_cnt = len(output)
		for c in range(cond_cnt): # Ensure all outputs are DieStats
			if not isinstance(output[c], DieStats):
				output[c] = DieStats("temp", output[c])

		# for c in range(cond_cnt): # Normalize conditions by effectively setting _min to 0
		# 	condition[c] = condition[c] - self.get_min()
		counts = np.zeros(cond_cnt, dtype=int) # Keep track of how many ways to get each output

		c = 0 # Current condition evluation
		for i in range(len(self)-1, -1, -1): # Iterate through possible rolls high->low
			while i + self.get_min() < condition[c]: c += 1 # If fails condition: check next condition
			counts[c] += self._pmf[i] # Add pmf to counts
		del c

		# weights = np.ones(cond_cnt, dtype=int) # The multiplier for each output's pmf
		# for c in range(cond_cnt):
		# 	weights[c] = output[c].get_mass() # Set weights to the total mass of each output
		# lcm = np.lcm.reduce(weights) # Find lcm of all weights
		# weights = lcm // weights * counts
		# weights //= np.gcd.reduce(weights)

		max_, min_ = np.NINF, np.inf
		for c in range(cond_cnt):
			if counts[c] > 0: # If there is at least one case this condition was met
				max_ = max(max_, output[c].get_max())
				min_ = min(min_, output[c].get_min())

		if max_ == np.NINF:# If no conditions were met: return blank roll
			return DieStats(name = name)
			
		pmf = np.zeros(max_ - min_ + 1, dtype=int)
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

		return DieStats(avg=avg, mass=mass, min=min_, name=name, pmf=pmf, var=var)


	def __str__(self): return self._name
	def text(self):
		return f"{self.name_txt()}\n> {self.min_txt()}\n> {self.max_txt()}\n> {self.mean_txt()}\n> {self.std_txt()}"
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
	def name_txt(self): return f"{self._name}:"
