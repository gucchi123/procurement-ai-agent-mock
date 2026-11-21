"""取引先の文書・ニュースの中の「指示らしき文」を見つけて伏せる (条件 C の渡さない層)。

取引先の見積・手紙・ニュースは「データ」であって「指示」ではない。【…AI…】の札や「〜するAIへ」の呼びかけで始まる文を伏せ、伏せたことを記録に残す。
"""
import re

MASK = "[取引先の文書の中の指示らしき文を伏せた]"
RX = re.compile(r"【[^】]*(?:AI|ＡＩ)[^】]*】[^\n]*")


def find(text):
    return [m.group(0) for m in RX.finditer(text or "")]


def mask(text):
    hits = find(text)
    return RX.sub(MASK, text or ""), hits
