import hashlib
import hmac
import secrets
from typing import Dict, Tuple


def generate_server_seed() -> str:
    """Tạo server seed ngẫu nhiên bảo mật cao (64 ký tự hex)."""
    return secrets.token_hex(32)


def hash_server_seed(server_seed: str) -> str:
    """Băm server seed bằng SHA-256 để công khai trước khi phiên bắt đầu."""
    return hashlib.sha256(server_seed.encode("utf-8")).hexdigest()


def generate_dice(server_seed: str, client_seed: str, nonce: int | str) -> Tuple[int, int, int]:
    """
    Sinh 3 mặt xúc xắc theo thuật toán Provably Fair (HMAC-SHA256).
    Hoàn toàn tất định (deterministic), không thể gian lận hoặc sửa đổi kết quả.
    """
    message = f"{client_seed}:{nonce}".encode("utf-8")
    key = server_seed.encode("utf-8")
    hmac_digest = hmac.new(key, message, hashlib.sha256).digest()

    # Lấy 4 bytes cho mỗi viên xí ngầu và modulo 6 + 1
    d1 = (int.from_bytes(hmac_digest[0:4], "big") % 6) + 1
    d2 = (int.from_bytes(hmac_digest[4:8], "big") % 6) + 1
    d3 = (int.from_bytes(hmac_digest[8:12], "big") % 6) + 1

    return d1, d2, d3


def verify_round_fairness(
    server_seed: str, server_seed_hash: str, client_seed: str, nonce: int | str
) -> Dict:
    """Kiểm tra tính minh bạch của một phiên đã kết thúc."""
    computed_hash = hash_server_seed(server_seed)
    is_hash_valid = computed_hash.lower() == server_seed_hash.lower()

    d1, d2, d3 = generate_dice(server_seed, client_seed, nonce)
    total = d1 + d2 + d3

    # Xác định kết quả
    is_triple = (d1 == d2 == d3)
    if is_triple:
        result_type = "TRIPLE"
    elif total >= 11:
        result_type = "TAI"
    else:
        result_type = "XIU"

    return {
        "is_valid": is_hash_valid,
        "computed_hash": computed_hash,
        "expected_hash": server_seed_hash,
        "dice": [d1, d2, d3],
        "total": total,
        "result_type": result_type,
        "is_triple": is_triple,
    }

