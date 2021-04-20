import numpy as np

class DieStats:
	def __init__(self, count: int=0, sides: int=20, const: int=0, name: str=None):
		if count and not sides: raise ValueError("Dice must have sides.")
		if count and sides < 0: raise ValueError("Dice cannot have a negative number of sides.")
		if count and name is None: self._name = f"{count}sides{sides}"
		else: self.set(name=name)

		if sides == 1:
			const += count
			count = 0
		self._dice = {1: const}
		if count: self._dice[sides] = count

		if count%2 == 0:
			pmf = np.ones(1, dtype=int)
		else:
			pmf = np.ones(sides, dtype=int)
			count = count-1
		if count > 2:
			pmf_2 = np.arange(1, 2*sides)
			pmf_2[sides:] = pmf_2[sides-2::-1]
		while count >= 2:
			pmf = np.convolve(pmf, pmf_2)
			count = count-2
		self._pmf = pmf
#	end __init__

	def copy(self, name: str=None):
		new = DieStats().set(**self._get(name=0, default=1))
		if name is not None:
			return new.set(name=name)
		if self._name is not None:
			return new.set(name=f"{self._name} (copy)")
		return new.set(name=None)

	def set(self, dice: dict=None, pmf: np.array=None, name: str=None):
		if dice is not None: self._dice = dice
		if pmf  is not None: self._pmf  = pmf
		if name is not None:
			if len(name) == 0: self._name = None
			else: self._name = name
		return self	#End set
	def _get(self, dice: bool=None, pmf: bool=None, name: bool=None, default: bool=None):
		if None is dice is pmf is name is default: dice, pmf, name = 1, 1, 1
		send = {}
		if dice or (dice is None and default): send["dice"] = self._dice.copy()
		if pmf  or (pmf  is None and default): send["pmf"]  = self._pmf.copy()
		if name or (name is None and default): send["name"] = self._name
		return send
	
	def get_spread(self):
		return len(self._pmf)
	def get_min(self):
		num = self._dice
		min = 0				#if die<0: sub num*die, else: add 1
		for die in num: min += num[die] * (1 + (die<0)*(die-1))
		return min
	def get_max(self): return self.get_min() + self.get_spread() - 1

	def get_mean(self): return self.get_min() + self.get_spread()/2 - 0.5
	def get_var(self):
		num = self._dice
		var = 0
		for die in num: var += num[die] * (die^2 - 1)
		return var/12
	def get_sigma(self): return np.sqrt(self.get_var())

	def get_pmf(self): return self._pmf.copy()
	def get_mass(self):
		num = self._dice
		mass = 1
		for die in num: mass *= pow(abs(die), num[die])
		return mass
	def get_pdf(self): return self._pmf/self.get_mass()


	def __ineg__(self):
		dice = {1: -self._dice[1]}
		for key in self._dice: dice[-key] = self._dice[key]
		del dice[-1]
		return self.set(dice=dice)
	def __neg__(self):
		name = self._name
		if name is None: return self.copy().__ineg__()
		elif name[0] == '-': name = name[1:]	# if name starts with '-': remove it
		else: name = f"-{name}"		# else: add '-'
		return self.copy().__ineg__().set(name=name)

	def __iadd__(self, other):
		if isinstance(other, int):
			self._dice[1] += other
			return self
		if not isinstance(other, DieStats): return NotImplemented
		for key in other._dice: self._dice[key] = self._dice.get(key, 0) + other._dice[key]
		self._pmf = np.convolve(self._pmf, other._pmf)
		return self	#End __iadd__
	def __add__(self, other, name=None):
		new = self.copy().__iadd__(other)
		if name is not None: return new.set(name=name)
		try: name = other._name
		except AttributeError: name = str(other)
		if self._name is None: return new.set(name=name)
		return new.set(name=f"{self._name} + {name}")
	def __radd__(self, other):
		return self.__add__(other)

	def __isub__(self, other):
		return self.__iadd__(-other)
	def __sub__(self, other, name=None):
		return self.__add__(-other, name)
	def __rsub__(self, other):
		return self.__radd__(-other)

#	def __mul__

	def sum(*args, **kwargs):
		arg_num = len(args)
		if arg_num == 0: raise TypeError("sum() missing 2 required arguments")
		if arg_num == 1: raise TypeError("sum() missing 1 required argument")
		try: name = kwargs['name']
		except KeyError: name = None
		if arg_num == 2: return args[0].__add__(args[1], name)
		if name is None: name = f"Sum of {arg_num} vars"
		dice = args[0].get_dice()
		pmf  = args[0].get_pmf()
		for arg in args[1:]:
			for key in arg._dice:
				dice[key] = dice.get(key, 0) + arg._dice[key]
			pmf = np.convolve(pmf, arg._pmf)
		return DieStats().set(dice=dice, pmf=pmf, name=name)	#End sum
	

	def __lt__(self, other):
		if   isinstance(self,  int): return 1 - other.__lt__(self + 1)
		elif isinstance(other, int):
			if self.get_max() <  other: return 1
			if self.get_min() >= other: return 0

			pmf = self.get_pmf()
			chances = 0
			for i in range(other - self.get_min()):
				chances += pmf[i]
			return chances/self.get_mass()
		return NotImplemented
	def __le__(self, other):
		if   isinstance(self,  int): return 1 - other.__lt__(self)
		elif isinstance(other, int): return self.__lt__(other + 1)
		return NotImplemented
	def __gt__(self, other):
		if   isinstance(self,  int): return other.__lt__(self)
		elif isinstance(other, int): return 1 - self.__lt__(other + 1)
		return NotImplemented
	def __ge__(self, other):
		if   isinstance(self,  int): return other.__lt__(self + 1)
		elif isinstance(other, int): return 1 - self.__lt__(other)
		return NotImplemented
	def __eq__(self, other):
		if isinstance(self,  int): self, other = other, self
		if isinstance(other, int):
			other = other - self.get_min()
			if other < 0: return 0
			if other > self.get_spread(): return 0
			return self.get_pmf()[other]/self.get_mass()
		return NotImplemented


	def __str__(self):
		if self._name is None: return "Unnamed DieStats object"
		return self._name
	def text(self):
		return f"{self.name_txt()}\n> {self.dice_txt()}\n> {self.min_txt()}\n> {self.max_txt()}\n> {self.mean_txt()}"
	def print(self, before: str="", after: str=""): print(before + self.text() + after)
	def min_txt(self):  return f"Minimum: {self.get_min()}"
	def max_txt(self):  return f"Maximum: {self.get_max()}"
	def mean_txt(self): return f"Average: {self.get_mean()}"
	def var_txt(self):  return f"Variance: {self.get_var()}"
	def std_txt(self):  return f"Standard deviation: {self.get_sigma()}"
	def dice_txt(self): return f"Dice: {self._get(dice=True)}"
	def pmf_txt(self):  return f"PMF of possible values (bounds: [min, max]):\n{self.get_pmf()}"
	def pdf_txt(self):  return f"PDF of possible values, 1st element is P(min):\n{self.get_pdf()}"
	def mass_txt(self): return f"Number of possibilities: {self.get_mass()}"
	def name_txt(self):
		if self._name: return f"{self._name}:"
		return "Values:"
