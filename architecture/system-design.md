# Kiến Trúc Microservices Ứng Dụng Game Tài Xỉu

Hệ thống được thiết kế theo mô hình **Microservices hướng sự kiện (Event-Driven Microservices Architecture)**, đảm bảo khả năng mở rộng (high scalability), độ trễ thấp (low latency cho game thời gian thực) và tính toàn vẹn dữ liệu tài chính (ACID ledger).

---

## 1. Sơ Đồ Kiến Trúc Tổng Thể

```mermaid
flowchart TD
    subgraph Clients["Clients"]
        Web["Web Browser (React/Vue/Phaser)"]
        Mobile["Mobile App (Flutter/React Native)"]
    end

    subgraph Gateway["API Gateway & Reverse Proxy"]
        Nginx["Nginx / Traefik / Envoy Gateway"]
    end

    subgraph CoreServices["Microservices Ecosystem"]
        AuthSvc["Auth Service (Port 8001)\n- Đăng ký / Đăng nhập\n- Cấp phát JWT & Quản lý người chơi"]
        WalletSvc["Wallet Service (Port 8002)\n- Ví người chơi (Số dư, Nạp, Rút)\n- Khóa số dư đặt cược (Hold)\n- Trả thưởng (Settlement)"]
        GameSvc["Game Engine Service (Port 8003)\n- Vòng quay Tài Xỉu (30s cược, 10s lắc, 5s kết quả)\n- Thuật toán Provably Fair (SHA-256)\n- Tính toán thắng/thua"]
        RealtimeSvc["Realtime Gateway (Port 8004)\n- Quản lý hàng chục ngàn kết nối WebSocket\n- Broadcast nhịp đếm ngược, tổng tiền cược, kết quả xí ngầu"]
        HistorySvc["History & Analytics Service (Port 8005)\n- Soi cầu (Bệt, 1-1, Cầu Nghiêng)\n- Bảng xếp hạng & Thống kê phiên"]
    end

    subgraph DataBroker["Data & Event Infrastructure"]
        RedisBus[("Redis Cluster\n(Pub/Sub, Caching, Redlock)")]
        KafkaOrRabbit[("RabbitMQ / Kafka\n(Event Streams)")]
        AuthDB[("Auth DB\n(PostgreSQL)")]
        WalletDB[("Wallet DB\n(PostgreSQL - ACID)")]
        GameDB[("Game DB\n(PostgreSQL / ClickHouse)")]
    end

    Web -->|HTTP / WebSocket| Nginx
    Mobile -->|HTTP / WebSocket| Nginx

    Nginx -->|/api/v1/auth| AuthSvc
    Nginx -->|/api/v1/wallet| WalletSvc
    Nginx -->|/api/v1/game| GameSvc
    Nginx -->|/ws| RealtimeSvc

    AuthSvc --> AuthDB
    WalletSvc --> WalletDB
    GameSvc --> GameDB

    GameSvc -->|Publish Ticks & Results| RedisBus
    RedisBus -->|Subscribe & Broadcast| RealtimeSvc

    GameSvc -->|Event: BetPlaced, RoundFinished| KafkaOrRabbit
    KafkaOrRabbit -->|Event Consumer: Settle Balance| WalletSvc
    KafkaOrRabbit -->|Event Consumer: Store History| HistorySvc
```

---

## 2. Vòng Đời Của Một Phiên Game Tài Xỉu (Game Cycle State Machine)

Mỗi phiên Tài Xỉu vận hành tự động theo chu kỳ tuần hoàn khép kín:

```mermaid
stateDiagram-v2
    [*] --> PREPARATION: Khởi tạo phiên mới (Tạo Server Seed bí mật)
    PREPARATION --> BETTING: Mở cược (35 giây)
    
    state BETTING {
        [*] --> ReceivingBets: Người chơi đặt cược Tài / Xỉu / Bộ Ba / Cặp số
        ReceivingBets --> ValidateAndHold: Wallet kiểm tra và tạm giữ số dư
        ValidateAndHold --> BroadcastStats: Cập nhật tổng tiền & số người theo cửa
    }

    BETTING --> SHAKING: Đóng cược & Lắc đĩa (10 giây)
    
    state SHAKING {
        [*] --> GenerateDice: Sinh 3 xúc xắc (Provably Fair RNG)
        GenerateDice --> ShakeAnimation: Phát hoạt họa lắc bát úp
    }

    SHAKING --> REVEAL_RESULT: Mở bát & Trả thưởng (5 giây)
    
    state REVEAL_RESULT {
        [*] --> AnnounceWinner: Công bố điểm số & cửa thắng
        AnnounceWinner --> SettlePayouts: Wallet cộng thưởng cho người thắng
        SettlePayouts --> RecordHistory: Lưu cầu & kết quả phiên
    }

    REVEAL_RESULT --> PREPARATION: Chuyển sang phiên kế tiếp
```

---

## 3. Quy Ước Luật Chơi Tài Xỉu

1. **Dụng cụ**: 3 viên xúc xắc (xí ngầu), mỗi viên có 6 mặt (1 đến 6 điểm).
2. **Tổng điểm**: Từ 3 đến 18.
   - **Xỉu**: Tổng điểm từ 4 đến 10 (Tỷ lệ 1 : 1).
   - **Tài**: Tổng điểm từ 11 đến 17 (Tỷ lệ 1 : 1).
   - **Bão (Triple)**: 3 mặt xúc xắc ra cùng 1 số (ví dụ: 1-1-1, 6-6-6). Khi ra bão, cả cửa Tài và Xỉu đều **thua** (nhà cái giữ lợi thế House Edge), người đặt đúng cửa Bão ăn tỷ lệ cao (ví dụ: 1 : 30 hoặc 1 : 180 cho bộ ba cụ thể).
3. **Tính minh bạch (Provably Fair)**:
   - Trước khi bắt đầu phiên, server băm SHA-256 chuỗi `ServerSeed + RoundID` và công khai mã băm (`HashCommitment`).
   - Sau khi kết thúc phiên, công khai `ServerSeed`. Người chơi có thể tự hash lại để kiểm chứng kết quả không hề bị thay đổi hay can thiệp giữa chừng.

---

## 4. Danh Sách Các Microservices Chi Tiết

| Service | Công nghệ | Trách nhiệm chính |
| :--- | :--- | :--- |
| **Auth Service** | FastAPI, SQLAlchemy, JWT, Bcrypt | Đăng ký, đăng nhập, cấp Access/Refresh Token, xác thực người dùng. |
| **Wallet Service** | FastAPI, PostgreSQL (Ledger) | Quản lý ví, nạp/rút tiền, hold số dư khi cược, credit tiền khi thắng. |
| **Game Service** | FastAPI / Python Asyncio Worker | Quản lý logic phiên, thuật toán xúc xắc, nhận cược, tính tiền thắng. |
| **Realtime Service**| FastAPI WebSocket / Node.js WebSocket | Nhận kết nối người chơi, broadcast countdown, tiền cược live, kết quả. |
| **History Service** | FastAPI, Redis, ClickHouse/PostgreSQL | Cung cấp dữ liệu soi cầu (chuỗi bệt, tài xỉu xen kẽ), lịch sử cược cá nhân. |

