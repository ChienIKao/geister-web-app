import eventlet

eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from threading import Lock
from collections import deque
from common import constants
import random
import os


app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
# socketio = SocketIO(app)
socketio = SocketIO(app, async_mode="eventlet")


# 房間與配對管理
waiting_queue = deque()
rooms = {}
room_id_counter = 1
queue_lock = Lock()


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("join_game")
def handle_join_game(data):
    sid = request.sid
    nickname = data.get("nickname", f"玩家")
    room_code = data.get("room_code")
    if not room_code or not room_code.isdigit() or len(room_code) != 4:
        emit("waiting", {"message": "請輸入正確的 4 位數房號"}, room=sid)
        return
    with queue_lock:
        if room_code not in rooms:
            # 創建新房間
            rooms[room_code] = {
                "players": [{"sid": sid, "nickname": nickname}],
                "setups": {},
                "board": None,
                "captured": None,
                "turn": None,
            }
            join_room(room_code, sid=sid)
            emit(
                "waiting",
                {"message": f"房號 {room_code} 已建立，請等待對手加入..."},
                room=sid,
            )
            return
        # 加入已存在房間
        if len(rooms[room_code]["players"]) >= 2:
            emit("waiting", {"message": "此房間人數已滿，請換一個房號"}, room=sid)
            return
        rooms[room_code]["players"].append({"sid": sid, "nickname": nickname})
        join_room(room_code, sid=sid)
        p1 = rooms[room_code]["players"][0]
        p2 = rooms[room_code]["players"][1]
        # 通知兩位玩家配對成功
        emit(
            "matched",
            {"room_id": room_code, "player": 1, "opponent_nickname": p2["nickname"]},
            room=p1["sid"],
        )
        emit(
            "matched",
            {"room_id": room_code, "player": 2, "opponent_nickname": p1["nickname"]},
            room=p2["sid"],
        )


# --- 遊戲流程：開始佈局 ---
@socketio.on("start_setup")
def handle_start_setup(data):
    room_id = data["room_id"]
    player = data["player"]
    # 廣播給房間內所有人，通知進入佈局階段
    emit("start_setup", {}, room=room_id)


# --- 玩家送出佈局資料 ---
@socketio.on("setup_data")
def handle_setup_data(data):
    room_id = data["room_id"]
    player = data["player"]
    placements = data["placements"]
    room = rooms.get(room_id)
    if not room:
        return
    # 確保 setups 已初始化且不會殘留
    if "setups" not in room or not isinstance(room["setups"], dict):
        room["setups"] = {}
    room["setups"][player] = placements
    # 等待兩位都送出
    if len(room["setups"]) == 2 and 1 in room["setups"] and 2 in room["setups"]:
        # 隨機決定先手
        first = random.choice([1, 2])
        room["turn"] = first
        # 初始化棋盤
        board = [[None for _ in range(6)] for _ in range(6)]
        for pid in (1, 2):
            for p in room["setups"][pid]:
                board[p["row"]][p["col"]] = (pid, p["ghost_type"])
        room["board"] = board
        room["captured"] = {1: {"good": 0, "bad": 0}, 2: {"good": 0, "bad": 0}}
        # 通知雙方遊戲開始
        for pid in (1, 2):
            emit(
                "game_start",
                {
                    "your_player": pid,
                    "turn": first,
                    "board": get_board_view(board, pid),
                    "my_good_captured_by_opponent": 0,
                    "my_bad_captured_by_opponent": 0,
                    "opponent_good_captured_by_me": 0,
                    "opponent_bad_captured_by_me": 0,
                },
                room=room["players"][pid - 1]["sid"],
            )


# --- 幫助函式：產生玩家視角棋盤 ---
def get_board_view(board, player_id):
    view = [[constants.EMPTY_SQUARE_CHAR for _ in range(6)] for _ in range(6)]
    for r in range(6):
        for c in range(6):
            piece = board[r][c]
            if piece:
                owner, t = piece
                if owner == player_id:
                    if player_id == 1:
                        view[r][c] = (
                            constants.P1_GOOD_CHAR
                            if t == "G"
                            else constants.P1_BAD_CHAR
                        )
                    else:
                        view[r][c] = (
                            constants.P2_GOOD_CHAR
                            if t == "G"
                            else constants.P2_BAD_CHAR
                        )
                else:
                    view[r][c] = constants.OPPONENT_GHOST_CHAR
    return view


# --- 玩家移動 ---
@socketio.on("move")
def handle_move(data):
    room_id = data["room_id"]
    player = data["player"]
    from_sq = data["from_sq"]  # [r, c]
    to_sq = data["to_sq"]  # [r, c]
    room = rooms.get(room_id)
    if not room or room.get("turn") != player:
        return
    board = room["board"]
    captured = room["captured"]
    # 驗證移動
    from_r, from_c = from_sq
    to_r, to_c = to_sq
    if not (0 <= from_r < 6 and 0 <= from_c < 6 and 0 <= to_r < 6 and 0 <= to_c < 6):
        emit("invalid_move", {"message": "無效的座標。"}, room=request.sid)
        return
    moving_piece = board[from_r][from_c]
    if not moving_piece or moving_piece[0] != player:
        emit("invalid_move", {"message": "你不能移動該位置的棋子。"}, room=request.sid)
        return
    if not (
        (abs(from_r - to_r) == 1 and from_c == to_c)
        or (abs(from_c - to_c) == 1 and from_r == to_r)
    ):
        emit("invalid_move", {"message": "只能前後左右移動一格。"}, room=request.sid)
        return
    target = board[to_r][to_c]
    if target and target[0] == player:
        emit("invalid_move", {"message": "目標位置有你自己的棋子。"}, room=request.sid)
        return
    # 執行移動
    board[to_r][to_c] = moving_piece
    board[from_r][from_c] = None
    action_desc = f"玩家{player} 從({from_r},{from_c})移動到({to_r},{to_c})"
    if target:
        opp_id, captured_type = target
        if captured_type == "G":
            captured[player]["good"] += 1
        else:
            captured[player]["bad"] += 1
        action_desc += f"，吃掉了對手的{'好鬼' if captured_type == 'G' else '壞鬼'}！"
    # 勝負判斷
    winner, reason = check_win(room, player, moving_piece[1], (to_r, to_c))
    if winner:
        for pid in (1, 2):
            emit(
                "update_state",
                {
                    "board": get_board_view(board, pid),
                    "turn": None,
                    "last_action_desc": action_desc,
                    "my_good_captured_by_opponent": captured[3 - pid]["good"],
                    "my_bad_captured_by_opponent": captured[3 - pid]["bad"],
                    "opponent_good_captured_by_me": captured[pid]["good"],
                    "opponent_bad_captured_by_me": captured[pid]["bad"],
                },
                room=room["players"][pid - 1]["sid"],
            )
        for pid in (1, 2):
            emit(
                "game_over",
                {"winner": winner, "reason": reason},
                room=room["players"][pid - 1]["sid"],
            )
        room["turn"] = None
        # 清除房間，讓同一房號可再次使用
        if room_id in rooms:
            del rooms[room_id]
        return
    # 換手
    room["turn"] = 2 if player == 1 else 1
    for pid in (1, 2):
        emit(
            "update_state",
            {
                "board": get_board_view(board, pid),
                "turn": room["turn"],
                "last_action_desc": action_desc,
                "my_good_captured_by_opponent": captured[3 - pid]["good"],
                "my_bad_captured_by_opponent": captured[3 - pid]["bad"],
                "opponent_good_captured_by_me": captured[pid]["good"],
                "opponent_bad_captured_by_me": captured[pid]["bad"],
            },
            room=room["players"][pid - 1]["sid"],
        )


# --- 勝負判斷 ---
def check_win(room, player_id, moved_type, to_pos):
    captured = room["captured"]
    opp = 2 if player_id == 1 else 1
    if captured[player_id]["good"] >= 4:
        return player_id, f"玩家{player_id} 吃掉了對手所有好鬼！"
    if captured[opp]["bad"] >= 4:
        return (
            player_id,
            f"玩家{player_id} 的所有壞鬼被對手吃掉，玩家{player_id} 獲勝！",
        )
    if captured[player_id]["bad"] >= 4:
        return opp, f"玩家{opp} 的所有壞鬼被對手吃掉，玩家{opp} 獲勝！"
    if moved_type == "G":
        corners = (
            constants.P1_ESCAPE_CORNERS
            if player_id == 1
            else constants.P2_ESCAPE_CORNERS
        )
        if tuple(to_pos) in corners:
            return player_id, f"玩家{player_id} 的好鬼成功逃脫！"
    return None, ""


# 這裡可以加入遊戲邏輯的 SocketIO 事件
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
