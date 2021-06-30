from DieStats import DieStats
import matplotlib.pyplot as plt

a_base = DieStats((1, 20), 5, 'attack')
a_sharp = a_base - 5


d_base = DieStats((2,6), (1,8), 3, 'damage')
d_base_2 = d_base.scalar_multiply(2, False, 'crit damage')
d_sharp = d_base + 10
d_sharp_2 = d_sharp.scalar_multiply(2, False, 'crit damage')


print()
c = a_base.if_then([12,25], [0, d_base, d_base_2], "attack c")
c_range = range(c.get_min(), c.get_max()+1)
print(c.text())
#print(c.get_pmf())

print()
d = a_sharp.if_then([12,20], [0, d_sharp, d_sharp_2], "attack d")
d_range = range(d.get_min(), d.get_max()+1)
print(d.text())
#print(d.get_pmf())

print()
e = d-c
e_range = range(e.get_min(), e.get_max()+1)
#print(e.text())
#print(e.get_pmf())

plt.plot(c_range, c.get_pmfnorm(), d_range, d.get_pmfnorm())#, e_range, e.get_pmfnorm())
plt.show()