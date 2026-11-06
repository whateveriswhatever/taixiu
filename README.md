# Hệ Thống Microservices Game Tài Xỉu (Sic Bo Web Platform)

Hệ thống backend microservices hiệu năng cao phục vụ trò chơi Tài Xỉu trực tuyến, hỗ trợ nhiều người chơi thời gian thực với độ trễ thấp và tính minh bạch công bằng (Provably Fair).

---

## 📁 Cấu Trúc Dự Án

```
taixiu/
├── architecture/
│   └── system-design.md          # Tài liệu thiết kế kiến trúc toàn hệ thống
├── docker-compose.yml             # Docker Compose chạy toàn bộ cụm services
├── README.md                      # Hướng dẫn tổng quan & cài đặt
└── services/
    ├── auth-service/              # [Port 8001] Service Xác thực & Tài khoản (FastAPI)
    │   ├── app/
    │   │   ├── api/               # Router, Endpoints & Dependencies
    │   │   ├── core/              # Config, Security (bcrypt, jwt), Database (Async SQLAlchemy)
    │   │   ├── models/            # SQLAlchemy ORM Models (User)
    │   │   ├── schemas/           # Pydantic v2 validation models
    │   │   ├── services/          # Business logic xác thực
    │   │   └── main.py            # FastAPI Entrypoint
    │   ├── tests/                 # 14 Automated Unit & Integration Tests
    │   ├── Dockerfile
    │   └── requirements.txt
    ├── wallet-service/            # [Port 8002] Service Quản lý Ví, Sổ cái & Cược (FastAPI)
    │   ├── app/
    │   │   ├── api/               # Endpoints: /me, /transactions, /deposit, /withdraw, /hold, /settle
    │   │   ├── core/              # Config, Security (JWT + Service Key), Database
    │   │   ├── models/            # Models: Wallet, WalletTransaction
    │   │   ├── schemas/           # Pydantic Schemas: HoldBet, SettleBet, Deposit, Withdraw
    │   │   ├── services/          # Business logic: Pessimistic Row Locking, Idempotency
    │   │   └── main.py            # FastAPI Entrypoint
    │   ├── tests/                 # 13 Automated Unit & Integration Tests
    │   ├── Dockerfile
    │   └── requirements.txt
    ├── game-service/              # [Port 8003] Game Engine & Thuật Toán Provably Fair (FastAPI)
    │   ├── app/
    │   │   ├── api/               # Endpoints: /current-round, /bet, /my-bets, /rounds/history, /rounds/verify
    │   │   ├── clients/           # Async WalletClient kết nối Wallet Service
    │   │   ├── core/              # Thuật toán Provably Fair HMAC-SHA256, Config, Database
    │   │   ├── models/            # Models: GameRound, Bet
    │   │   ├── schemas/           # Pydantic Schemas: BetRequest, RoundResponse, VerifyFairness
    │   │   ├── services/          # GameEngine: State Machine (BETTING -> SHAKING -> SETTLED), Payouts
    │   │   └── main.py            # FastAPI Entrypoint
    │   ├── tests/                 # 11 Automated Unit & Integration Tests
    │   ├── Dockerfile
    │   └── requirements.txt
    └── realtime-service/          # (Giai đoạn tiếp theo) [Port 8004] WebSocket Hub broadcast nhịp cược
```

---

## 🎲 Quy Tắc Trò Chơi Tài Xỉu & Tỷ Lệ Ăn Thưởng

1. **Dụng cụ**: 3 viên xúc xắc 6 mặt (1 đến 6). Tổng điểm từ 3 đến 18.
2. **Các Cửa Cược Hỗ Trợ**:
   - **TÀI (`TAI`)**: Tổng 11 - 17 (không bão). Tỷ lệ **1 : 1** (cược 10k nhận 20k).
   - **XỈU (`XIU`)**: Tổng 4 - 10 (không bão). Tỷ lệ **1 : 1** (cược 10k nhận 20k).
   - **BÃO BẤT KỲ (`TRIPLE_ANY`)**: 3 mặt xúc xắc ra cùng 1 số bất kỳ. Tỷ lệ **1 : 30** (cược 10k nhận 310k). *(Lưu ý: Khi ra Bão, cả cửa Tài và Xỉu đều thua theo luật nhà cái).*
   - **BÃO CỤ THỂ (`TRIPLE_SPECIFIC`)**: Chọn chính xác bộ ba (ví dụ: 6-6-6). Tỷ lệ **1 : 180** (cược 10k nhận 1,810k).
   - **CẶP SỐ (`PAIR`)**: Xuất hiện ít nhất 2 viên cùng điểm (ví dụ: cặp 4). Tỷ lệ **1 : 10** (cược 10k nhận 110k).
   - **ĐIỂM CHÍNH XÁC (`EXACT_POINT`)**: Đoán đúng tổng điểm từ 4 đến 17 (Tỷ lệ lên tới 1:60 cho điểm 4 hoặc 17).
3. **Thuật Toán Minh Bạch Provably Fair**:
   - Trước khi mở cược: Server sinh `ServerSeed` bí mật và băm SHA-256 thành `server_seed_hash` công khai cho người chơi.
   - Khi lắc xúc xắc: Tính `HMAC-SHA256(ServerSeed, ClientSeed + RoundID)`. Lấy 12 bytes đầu chia làm 3 cụm modulo 6 + 1 để ra 3 mặt xí ngầu.
   - Sau khi kết thúc phiên: `ServerSeed` được công khai. Người chơi gọi API `/rounds/verify` để kiểm chứng kết quả độc lập.

---

## 🚀 Khởi Chạy Các Microservices (FastAPI)

### 1. Khởi Chạy Local Development

```bash
# Auth Service (Port 8001)
cd /home/admin/taixiu/services/auth-service
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Wallet Service (Port 8002)
cd /home/admin/taixiu/services/wallet-service
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

# Game Service (Port 8003)
cd /home/admin/taixiu/services/game-service
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

- **Swagger UI Game Service**: [http://localhost:8003/api/v1/docs](http://localhost:8003/api/v1/docs)

---

### 2. Khởi Chạy Bằng Docker Compose (Toàn bộ Cụm Dịch Vụ)

Chạy đồng thời **Auth Service**, **Wallet Service**, **Game Service**, 3 cơ sở dữ liệu **PostgreSQL** và **Redis**:

```bash
cd /home/admin/taixiu
docker compose up -d --build
```

---

## 🧪 Kiểm Thử Tự Động Toàn Bộ Hệ Thống (38 Test Cases)

Hệ thống có bộ 38 test cases bao phủ toàn bộ luồng nghiệp vụ:

```bash
# Test toàn bộ 3 microservices
PYTHONPATH=/home/admin/taixiu/services/auth-service pytest /home/admin/taixiu/services/auth-service/tests/ -v
PYTHONPATH=/home/admin/taixiu/services/wallet-service pytest /home/admin/taixiu/services/wallet-service/tests/ -v
PYTHONPATH=/home/admin/taixiu/services/game-service pytest /home/admin/taixiu/services/game-service/tests/ -v
```

---

## 🔑 Danh Sách API Endpoints của Game Service (Port 8003)

| Method | Endpoint | Mô tả | Quyền truy cập |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/game/current-round` | Xem phiên cược hiện tại (Countdown & Server Seed Hash) | Công khai |
| `POST` | `/api/v1/game/bet` | Đặt cược vào phiên hiện tại (Khóa số dư qua Wallet Service) | Người chơi (`Bearer Token`) |
| `GET` | `/api/v1/game/my-bets` | Xem lịch sử các vé cược cá nhân | Người chơi (`Bearer Token`) |
| `GET` | `/api/v1/game/rounds/history` | Xem lịch sử các phiên trước (Dữ liệu soi cầu & seed) | Công khai |
| `POST` | `/api/v1/game/rounds/verify` | Công cụ tự kiểm chứng tính minh bạch Provably Fair | Công khai |
| `POST` | `/api/v1/game/admin/advance` | **[Admin/Worker]** Chuyển nhịp game (Đóng cược -> Lắc -> Trả thưởng) | Quản trị viên (`Admin Token`) |
| `GET` | `/api/v1/health` | Kiểm tra sức khỏe dịch vụ | Công khai |
| `GET` | `/api/v1/ready` | Kiểm tra kết nối Database | Công khai |

---

## 📋 Các Bước Tiếp Theo Của Hệ Thống

1. **Realtime Service (Port 8004)**: Quản lý WebSocket kết nối hàng nghìn người chơi đồng thời, đồng bộ đồng hồ đếm ngược và trạng thái cược live.
2. **API Gateway**: Định tuyến toàn bộ lưu lượng qua một cổng duy nhất cho Web/Mobile.
