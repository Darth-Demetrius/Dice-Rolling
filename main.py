#import matplotlib.pyplot as plt
from DieStats import DieStats

mode = "PF2e"

e_Level = 20
e_Skill = 38
e_AC = 45
e_SaveH = 36
e_SaveM = 33
e_SaveL = 30
e_HP = 470
e_Strike = 38
e_SpellSave = 42
e_SpellStrike = 34

f_Level = 20
f_AC = 44
f_HP = 288
f_Strike = 34
f_StrikeInt = 36
f_SpellSave = 36
f_SpellStrike = 26

compLbow = DieStats((4,8), (5,6), 7)
compLbow_C = DieStats.sum(compLbow*2, DieStats((1,6)))

meteorSwarm_F = DieStats((6,10), (14,6))
meteorSwarm_CF = meteorSwarm_F*2
meteorSwarm_S = meteorSwarm_F//2