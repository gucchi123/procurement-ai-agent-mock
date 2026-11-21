"""置き場所。

- data/         購買システム (AI が道具・貼り付けで見てよい場所)。会社・取引先はすべて架空。
- data/handbook 社内の手引き (条件 A+ の文脈・道具 get_guide)
- scoring/gold/ 正解表 (AI が見る場所の外)
- out/          ラボの出力・承認の列・協議の記録の写し
"""
import os

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(KIT, "data")
HANDBOOK = os.path.join(DATA, "handbook")
GOLD = os.path.join(KIT, "scoring", "gold")
EXPERIMENT = os.path.join(KIT, "experiment")
OUT = os.path.join(KIT, "out")


def data(name):
    return os.path.join(DATA, name)


def gold(name):
    return os.path.join(GOLD, name)
