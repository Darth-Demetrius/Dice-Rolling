import numpy as np
from roll import *
from DieStats import DieStats

a = DieStats(1, 6, name='1d6')
b = -DieStats(1, 6, name='1d6')
print(f"\n{(a + 1).text()}")
print(f"\n{(1 + a).text()}")
print(f"\n{(a - 1).text()}")
print(f"\n{(1 - a).text()}")
# a += b
# print("\n", a)
# d = DieStats((5, 10), name='5d8')
# print("\n", d)
# e = DieStats.sum(a,b,d)
# print("\n", e)

# def warhammer_damage(magic: int = 0, str_mod: int = 0, hands: int = 1):
# 	return

# char_AC = 24
# char_conS = 9
# char_atk = 16
# def char_melee_dmg():
# 	return {'bludgeoning': '1d8+9', 'necrotic': 4, 'fire': 6}
# char_boom_dmg = ()

# drag_AC = 20
# drag_atk = 14
