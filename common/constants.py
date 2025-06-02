# 連線設定
SERVER_HOST = "192.168.143.126"
SERVER_PORT = 12345

# 玩家 1（上半）
P1_ID = 1
P1_SETUP_ROWS = [0, 1]  # 棋盤最上面兩列
P1_GOOD_CHAR = "g"  # 好鬼
P1_BAD_CHAR = "b"  # 壞鬼
P1_ESCAPE_CORNERS = [(5, 0), (5, 5)]  # 逃脫點

# 玩家 2（下半）
P2_ID = 2
P2_SETUP_ROWS = [4, 5]  # 棋盤最下面兩列
P2_GOOD_CHAR = "G"  # 好鬼
P2_BAD_CHAR = "B"  # 壞鬼
P2_ESCAPE_CORNERS = [(0, 0), (0, 5)]  # 逃脫點

# Client 顯示的對手棋子
OPPONENT_GHOST_CHAR = "X"  # 未現形
EMPTY_SQUARE_CHAR = "."  # 空格

# 訊息類型
MSG_TYPE_ASSIGN_ID = "assign_id"
MSG_TYPE_WAIT_OPPONENT = "wait_opponent"
MSG_TYPE_START_SETUP = "start_setup"
MSG_TYPE_SETUP_DATA = "setup_data"
MSG_TYPE_SETUP_INVALID = "setup_invalid"
MSG_TYPE_YOUR_TURN = "your_turn"
MSG_TYPE_OPPONENT_TURN = "opponent_turn"
MSG_TYPE_MOVE = "move"
MSG_TYPE_INVALID_MOVE = "invalid_move"
MSG_TYPE_UPDATE_STATE = "update_state"
MSG_TYPE_GAME_OVER = "game_over"
MSG_TYPE_ERROR = "error"
MSG_TYPE_INFO = "info"
