import numpy as np
from numpy.random import randint


def d(count: int = 1, size: int = 20) -> tuple:
	rolls = randint(1, size+1, count)
	return (np.sum(rolls), rolls)

def roll(count: int = 1, size: int = 20, mods: tuple = ()) -> tuple:
	total, rolls = d(count, size)
	total = total + np.sum(mods)
	return (total, rolls, mods)


def d_stats(count: int = 1, size: int = 20) -> tuple:
	# mean(X) = (1/n) * sum(X)
	# sum(X) = X[1] + X[2]... + X[n-1] + X[n]
	# mean(X) = (1/2) * (1 + n): iff X is the consecutive integers from 1 to n
	# mean(X^2) = (1/6) * (n+1)(2n+1): iff X is the consecutive integers from 1 to n
	# variance(X) = mean(X^2) - mean(X)^2 => (1/12) * (n^2 - 1)
	# variance(X1, X2... Xi) = variance(X1) + variance(X2)... variance(Xi): iff independent
	# variance(X1, X2... Xi) = i * variance(X1): iff X1 == X2... == Xi
	# variance = i * (1/12) * (n^2 - 1)
	
	mean = count * (size+1)/2
	var = count * (size^2 - 1) / 12
	prob = np.arange(1, count+1)
	for i in range(count):
		prob[i] = 0
	return (mean, var, prob)
