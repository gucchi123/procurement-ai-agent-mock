"""引用の照合: AI が「資料のこの文に基づく」と書いた引用が、資料に一字一句あるか (NFKC・空白だけ吸収)。"""
import re
import unicodedata

MIN_LEN = 3


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"\s+", "", s)


def verify_quote(quote, source):
    q = norm(quote)
    if len(q) < MIN_LEN:
        return False
    return q in norm(source)


def kata(s):
    """ひらがなをカタカナに (名前の照合で表記の揺れを吸収するため)。"""
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in str(s or ""))
