# -*- coding: utf-8 -*-
import tictactoe_env
import neural_net_5block

import time
from collections import deque, defaultdict

import torch
from torch.autograd import Variable

import slackweb
import xxhash
import pickle
import numpy as np
np.set_printoptions(suppress=True)

PLAYER, OPPONENT = 0, 1
MARK_O, MARK_X = 0, 1
N, W, Q, P = 0, 1, 2, 3
PLANE = np.zeros((3, 3), 'int').flatten()

CHANNEL = 128

GAMES = 1
SIMULATION = 800


class MCTS(object):
    """몬테카를로 트리 탐색 클래스.

    셀프플레이를 통해 train 데이터 생성 (s, pi, z)

    state
    ------
    각 주체당 4수까지 저장한 8장, OX 구분 1장 총 9장.

        9x3x3 numpy array -> 1x81 numpy array

    edge
    -----
    현재 state의 현재 보드에서 착수 가능한 모든 action자리에 4개의 정보 저장.

    type: 3x3x4 numpy array

        9개 좌표에 4개의 정보 N, W, Q, P 매칭
        N: edge 방문횟수, W: 보상누적값, Q: 보상평균값(W/N), P: 선택 확률 추정치
        edge[좌표행][좌표열][번호]로 접근

    Warning: action의 현재 주체인 current_user를 reset_step()에서 제공해야 함.

    """

    def __init__(self, model_path=None):
        # tree
        self.tree = defaultdict(lambda: np.zeros((3, 3, 4), 'float'))

        # model
        self.pv_net = neural_net_5block.PolicyValueNet(CHANNEL)
        if model_path is not None:
            print('#######  Model is loaded  #######')
            self.pv_net.load_state_dict(torch.load(model_path))

        # hyperparameter
        self.c_puct = 5
        self.epsilon = 0.25
        self.alpha = 0.7

        # loop controller
        self.done = False

        # reset_step member
        self.edge = None
        self.total_visit = None
        self.legal_move = None
        self.no_legal_move = None
        self.state = None
        self.prob = None
        self.value = None
        self.current_user = None

        # reset_episode member
        self.node_memory = None
        self.edge_memory = None
        self.action_memory = None
        self.action_count = None

        # init
        self.reset_step()
        self._reset_episode()

    def reset_step(self, current_user=None):
        self.edge = np.zeros((3, 3, 4), 'float')
        self.total_visit = 0
        self.legal_move = None
        self.no_legal_move = None
        self.state = None
        self.prob = np.zeros((3, 3), 'float')
        self.value = None
        self.current_user = current_user

    def _reset_episode(self):
        self.node_memory = deque(maxlen=9)
        self.edge_memory = deque(maxlen=9)
        self.action_memory = deque(maxlen=9)
        self.action_count = 0

    def select_action(self, state):
        """state을 받아 변환 및 저장 후 action을 리턴하는 외부 메소드.

        state 변환
        ----------
        state --> node & state_variable

            state: 1x81 numpy array.

            state_variable: 1x9x3x3 torch.autograd.Variable.
                신경망의 인수로 넣을 수 있게 조정. (학습용)

            node: string. (xxhash)
                state를 string으로 바꾼 후 hash 생성. (탐색용)

        action 선택
        -----------
        puct 값이 가장 높은 곳을 선택함, 동점이면 랜덤 선택.

            action: 1x3 tuple.
            action = (현재 유저 타입, 보드의 좌표행, 보드의 좌표열)

        """
        # 현재 주체 설정 여부 필터링
        if self.current_user is None:
            raise NotImplementedError("Set Current User!")

        self.action_count += 1

        if self.action_count == 1:
            self.root = state

        self.state = state

        # state -> 문자열 -> hash로 변환 (state 대신 tree dict의 key로 사용)
        node = xxhash.xxh64(self.state.tostring()).hexdigest()

        self.node_memory.appendleft(node)

        # 현재 보드에서 착수가능한 곳 검색
        origin_state = state.reshape(9, 3, 3)
        board_fill = origin_state[0] + origin_state[4]
        self.legal_move = np.argwhere(board_fill == 0)
        self.no_legal_move = np.argwhere(board_fill != 0)

        # tree 탐색 -> edge 호출 or 생성
        self._tree_search(node)

        # edge의 puct 계산
        puct = self._puct(self.edge)

        # PUCT가 최댓값인 곳 찾기
        puct_max = np.argwhere(puct == puct.max())

        # 동점 처리
        move_target = puct_max[np.random.choice(len(puct_max))]

        # 최종 action 구성 (현재 행동주체 + 좌표) 접붙히기
        action = np.r_[self.current_user, move_target]

        # action 저장
        self.action_memory.appendleft(action)

        # tuple로 action 리턴
        return tuple(action)

    def _tree_search(self, node):
        """tree search를 통해 선택, 확장을 진행하는 메소드.

        {node: edge}인 Tree 구성
        edge에 있는 Q, P를 이용하여 PUCT값을 계산한 뒤 모든 좌표에 매칭.

            puct: 3x3 numpy array. (float)

        """
        # tree에서 현재 node를 검색하여 존재하면 해당 edge 불러오기
        if node in self.tree:
            self.edge = self.tree[node]

            print('"Select"\n')

            edge_n = np.zeros((3, 3), 'float')

            for i in range(3):
                for j in range(3):
                    self.prob[i, j] = self.edge[i, j][P]
                    edge_n[i, j] = self.edge[i, j][N]
            self.total_visit = np.sum(edge_n)
            # 계속 진행
            self.done = False

        else:  # 없으면 child node 이므로 edge 초기화하여 달아 주기
            self._expand(node)

        # edge의 총 방문횟수 출력
        print('(visit count: {:0.0f})\n'.format(self.total_visit))

        # root node면 edge의 P에 노이즈
        if self.action_count == 1:
            print('(root node noise)\n')

            for i, move in enumerate(self.legal_move):
                self.edge[tuple(move)][P] = (1 - self.epsilon) * self.prob[tuple(move)] + \
                    self.epsilon * np.random.dirichlet(
                        self.alpha * np.ones(len(self.legal_move)))[i]
        else:
            for move in self.legal_move:
                self.edge[tuple(move)][P] = self.prob[tuple(move)]

        print('###  Piror Prob  ###\n', self.prob.round(decimals=2), '\n')

        # Q, P값을 배치한 edge를 담아둠. 백업할 때 사용
        self.edge_memory.appendleft(self.edge)

    def _puct(self, edge):
        # 모든 edge의 PUCT 계산
        puct = np.zeros((3, 3), 'float')
        for move in self.legal_move:
            puct[tuple(move)] = edge[tuple(move)][Q] + \
                self.c_puct * edge[tuple(move)][P] * \
                np.sqrt(self.total_visit) / (1 + edge[tuple(move)][N])

        # 착수 불가능한 곳엔 PUCT에 -inf를 넣어 최댓값 되는 것 방지
        for move in self.no_legal_move:
            puct[tuple(move)] = -np.inf

        # 보정한 PUCT 점수 출력
        print('***  PUCT SCORE  ***')
        print(puct.round(decimals=2), '\n')

        return puct

    def _expand(self, node):
        """ 기존 tree에 없는 노드가 선택됐을때 사용되는 메소드.

        모든 좌표의 edge를 생성.
        state 텐서화 하여 신경망에 넣고 p_theta, v_theta 얻음.
        edge의 P에 p_theta를 넣어 초기화.
        select에서 edge 중 하나를 선택한 후 v로 백업하도록 알림.

        """
        # edge를 생성
        self.edge = self.tree[node]

        print('"Expand"')

        # state에 Variable 씌워서 신경망에 넣기
        state_tensor = torch.from_numpy(self.state).float()
        state_variable = Variable(state_tensor.view(9, 3, 3).unsqueeze(0))
        p_theta, v_theta = self.pv_net(state_variable)
        self.prob = p_theta.data.numpy()[0].reshape(3, 3)
        self.value = v_theta.data.numpy()[0]

        print('"Evaluate"\n')

        # 이번 액션 후 백업할 것 알림
        self.done = True

    def backup(self, reward):
        """search가 끝나면 지나온 edge의 N, W, Q를 업데이트."""

        steps = self.action_count
        for i in range(steps):

            # W 배치
            # 내가 지나온 edge에는 v 로
            if self.action_memory[i][0] == PLAYER:
                self.edge_memory[i][tuple(
                    self.action_memory[i][1:])][
                    W] += reward

            # 상대가 지나온 edge는 -v 로
            else:
                self.edge_memory[i][tuple(
                    self.action_memory[i][1:])][
                    W] -= reward

            # N 배치 후 Q 배치
            self.edge_memory[i][tuple(self.action_memory[i][1:])][N] += 1
            self.edge_memory[i][tuple(
                self.action_memory[i][1:])][Q] = self.edge_memory[i][tuple(
                    self.action_memory[i][1:])][W] / self.edge_memory[i][tuple(
                        self.action_memory[i][1:])][N]

            # N, W, Q 배치한 edge 트리에 최종 업데이트
            self.tree[self.node_memory[i]] = self.edge_memory[i]

        print('"Backup"\n\n')

        self._reset_episode()

    def play(self, tau):
        """root node의 pi를 계산하고 최댓값을 찾아 action을 return함."""
        root_node = xxhash.xxh64(self.root.tostring()).hexdigest()
        edge = self.tree[root_node]

        pi = np.zeros((3, 3), 'float')
        total_visit = 0
        action_space = []

        for i in range(3):
            for j in range(3):
                total_visit += edge[i, j][N]
                action_space.append([i, j])

        for i in range(3):
            for j in range(3):
                pi[i, j] = edge[i, j][N] / total_visit
        if tau == 0:
            deterministic = np.argwhere(pi == pi.max())
            final_move = deterministic[np.random.choice(len(deterministic))]
        else:
            stochactic = np.random.choice(9, p=pi.flatten())
            final_move = action_space[stochactic]
        action = np.r_[self.current_user, final_move]

        print('=*=*=*=   Pi   =*=*=*=')
        print(pi.round(decimals=2), '\n')

        state_memory.appendleft(self.root)
        pi_memory.appendleft(pi.flatten())

        return tuple(action)


if __name__ == '__main__':
    start = time.time()

    train_dataset_store = []
    state_memory = deque(maxlen=102400)
    pi_memory = deque(maxlen=102400)
    z_memory = deque(maxlen=102400)

    env_game = tictactoe_env.TicTacToeEnv()
    env_simul = tictactoe_env.TicTacToeEnv()

    result_game = {-1: 0, 0: 0, 1: 0}
    win_mark_o = 0
    step_game = 0
    step_total_simul = 0

    print("=" * 30, " Game Start ", "=" * 30, '\n')

    for game in range(GAMES):
        player_color = (MARK_O + game) % 2
        state_game = env_game.reset(player_color=player_color)
        mcts = MCTS()
        done_game = False
        step_play = 0

        while not done_game:
            print("=" * 27, " Simulation Start ", "=" * 27, '\n')

            current_user_play = ((PLAYER if player_color == MARK_O else OPPONENT) + step_play) % 2
            result_simul = {-1: 0, 0: 0, 1: 0}
            terminal_n = 0
            backup_n = 0
            step_simul = 0

            for simul in range(SIMULATION):
                print('#######   Simulation: {}   #######\n'.format(simul + 1))

                state_simul = env_simul.reset(
                    state_game.copy(), player_color=player_color)
                done_simul = False
                step_mcts = 0

                while not done_simul:
                    print('---- BOARD ----')
                    print(env_simul.board[PLAYER] + env_simul.board[OPPONENT] * 2.0, '\n')

                    current_user_mcts = (current_user_play + step_mcts) % 2
                    mcts.reset_step(current_user_mcts)
                    action_simul = mcts.select_action(state_simul)
                    state_simul, z_env, done_env, _ = env_simul.step(action_simul)
                    step_mcts += 1
                    step_simul += 1
                    step_total_simul += 1
                    done_mcts = mcts.done
                    v = mcts.value
                    done_simul = done_mcts or done_env

                if done_simul:
                    if done_mcts:
                        print('==== BACKUP ====')
                        print(env_simul.board[PLAYER] + env_simul.board[OPPONENT] * 2.0, '\n')
                        print('(v: {:0.4f})\n'.format(v[0]))

                        mcts.backup(v[0])
                        backup_n += 1

                    else:
                        print('=== TERMINAL ===')
                        print(env_simul.board[PLAYER] + env_simul.board[OPPONENT] * 2.0, '\n')
                        print("(z': {})\n".format(z_env))

                        mcts.backup(z_env)
                        result_simul[z_env] += 1
                        terminal_n += 1

            print("=" * 25, " {} Simulations End ".format(simul + 1), "=" * 25)
            print('Win: {}  Lose: {}  Draw: {}  Backup: {}  Terminal: {}  Step: {}\n'.format(
                result_simul[1], result_simul[-1], result_simul[0], backup_n, terminal_n,
                step_simul))
            print('##########    Game: {}    ##########\n'.format(game + 1))
            print('`*`*` ROOT `*`*`')
            print(env_game.board[PLAYER] + env_game.board[OPPONENT] * 2.0, '\n')

            mcts.reset_step(current_user_play)

            if step_play < 2:
                tau = 1
            else:
                tau = 0

            action_game = mcts.play(tau)
            state_game, z, done_game, _ = env_game.step(action_game)
            step_play += 1
            step_game += 1

            print('`*`*` PLAY `*`*`')
            print(env_game.board[PLAYER] + env_game.board[OPPONENT] * 2.0, '\n')
            print('tau: {}\n'.format(tau))

        if done_game:
            print("(z: {})\n".format(z))
            result_game[z] += 1

            for i in range(step_play):
                z_memory.appendleft(z)

            if z == 1:
                if env_game.player_color == MARK_O:
                    win_mark_o += 1

    train_dataset_store = list(zip(state_memory, pi_memory, z_memory))
    with open('data/train_dataset_s{}_g{}.pickle'.format(simul + 1, game + 1), 'wb') as f:
        pickle.dump(train_dataset_store, f, pickle.HIGHEST_PROTOCOL)

    finish_game = round(float(time.time() - start))

    print("=" * 27, " {}  Game End  ".format(game + 1), "=" * 27)
    stat_game = ('[GAME] Win: {}  Lose: {}  Draw: {}  Winrate: {:0.1f}%  WinMarkO: {}'.format(
        result_game[1], result_game[-1], result_game[0],
        1 / (1 + np.exp(result_game[-1] / (game + 1)) / np.exp(result_game[1] / (game + 1))) * 100,
        win_mark_o))
    print(stat_game)

    slack = slackweb.Slack(
        url="https://hooks.slack.com/services/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")
    slack.notify(
        text="Finished: [{} Game/{} Step] in {}s [Mac]".format(
            game + 1, step_game + step_total_simul, finish_game))
    slack.notify(text=stat_game)
