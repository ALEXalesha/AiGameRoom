"""Ход ИИ фиксируется до хода человека: показывается хэш, после раунда - ход и ключ.

commit = SHA-256 строки "rockpaperai:<k>:<раунд>:<ход>:<ключ>". Ключ - 16 случайных байт:
без него перебором трёх или пяти ходов хэш раскрылся бы сразу. Номер раунда и вариант в
строке - чтобы старое раскрытие нельзя было выдать за новое.
"""
import hashlib
import secrets


def make_nonce():
    return secrets.token_hex(16)


def digest(k, round_no, move, nonce):
    text = f"rockpaperai:{int(k)}:{int(round_no)}:{int(move)}:{nonce}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def commit(k, round_no, move, nonce=None):
    """(хэш, ключ)."""
    nonce = nonce or make_nonce()
    return digest(k, round_no, move, nonce), nonce


def verify(commit_hash, k, round_no, move, nonce):
    return digest(k, round_no, move, nonce) == commit_hash
