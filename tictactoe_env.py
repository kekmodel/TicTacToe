# -*- coding: utf-8 -*-
import gym   # 환경 제공 모듈

import numpy as np   # 배열 제공 모듈


PLAYER = 0  # 플레이어 식별 상수
OPPONENT = 1  # 상대 식별 상수
USER_TYPE = 0  # action index 0
MARK_O = 0
MARK_X = 1


class TicTacToeEnv(gym.Env):
    """
    TicTacToe 환경 제공 클래스
    =============================================================

    규칙
    ---------------
    O, X 를 번갈아 가면서 표시하고 3개 연속으로 한줄을 채우면 승리, 무승부 있음.

        0번 평면을 기준으로 승패체크. 보상 (승:1, 무:0, 패:-1)
        "O"인 주체를 정보를 받아 2번 평면에 동기화 함
        현재 self-play만 지원


    state
    ---------------
    3x3x3 numpy 배열: 3x3 평면 3장.

        0번 평면: 나의 표시만 1로 체크
        1번 평면: 상대 표시만 1로 체크
        2번 평면: "O"만 1로 체크 (누가 "OX"인지 구별 용)

    example:
        [
        [[0, 0, 0]
         [0, 0, 0]
         [0, 0, 0]]  0번 평면

        [[0, 0, 0]
         [0, 0, 0]
         [0, 0, 0]]  1번 평면

        [[0, 0, 0]
         [0, 0, 0]
         [0, 0, 0]]  2번 평면
        ]


    action
    ---------------
    tuple(피아식별, 좌표행, 좌표열).

        action = (0, 1, 1) -> step(action) -> state[0][1][1] = 1


    Warning
    --------
    plyer_color 를 반드시 설정해야 함: reset()하면 재설정 필요함.
        >> env = TicTacToeEnv()
        >> state = env.reset()
        >> env.player_color = MARK_O


    gym.Env
    -------
    gym/core.py 참조.

    =============================================================
    """
    # _render()의 리턴 타입 구분
    metadata = {'render.modes': ['human', 'rgb_array']}
    reward = (-1, 0, 1)  # 보상의 범위 참고: 패배:-1, 무승부:0, 승리:1

    def __init__(self):
        self.state = None
        self.viewer = None  # 뷰어
        self.player_color = None  # 나의 "OX"
        self._reset()

    def _reset(self):
        """state 리셋 함수.

        state 초기화: 3x3 배열 3장: 2진으로만 해결하기 위함.
        """
        self.state = np.zeros((3, 3, 3), 'int')
        self.viewer = None   # 뷰어 리셋
        self.step_count = 0  # action 진행 횟수
        self.player_color = None
        return self.state  # state 리턴

    def _step(self, action):
        """한번의 action에 state가 어떻게 변하는지 정하는 메소드.

        승부가 나면 에이전트가 reset()을 호출하여 환경을 초기화 해야 함.
        action을 받아서 (state, reward, done, info)인 튜플 리턴 함.
        """
        # 규칙 위반 필터링: 착수 금지: action 자리에 이미 자리가 차있으면
        if self.state[action] == 1:
            if action[USER_TYPE] == PLAYER:  # 근데 그게 플레이어가 한 짓이면 반칙패
                reward = -1
                done = True  # 게임 종료
                info = {'steps': self.step_count}  # action 1회로 인정
                print('Illegal Lose!')  # 출력
                return self.state, reward, done, info  # 필수 요소 리턴
            elif action[USER_TYPE] == OPPONENT:  # 상대가 한 짓이면 반대
                reward = 1
                done = True
                info = {'steps': self.step_count}
                print('Illegal Win!')
                return self.state, reward, done, info

        # action 적용
        self.state[action] = 1

        # 연속 두번 하기, player_color 비설정 시 오류 발생시키기
        redupl = np.sum(self.state[PLAYER]) - np.sum(self.state[OPPONENT])
        if abs(redupl) > 1 or self.player_color is None:
            raise NotImplementedError
        # "O"가 아닌데 처음에 하면 오류 발생시키기
        if self.player_color != MARK_O:
            if np.sum(self.state) == 1 and action[USER_TYPE] == PLAYER:
                raise NotImplementedError
        else:
            if np.sum(self.state) == 1 and action[USER_TYPE] == OPPONENT:
                raise NotImplementedError

        # 2번 보드("O") 동기화
        if self.player_color == MARK_O:
            self.state[2] = self.state[PLAYER]
        else:
            self.state[2] = self.state[OPPONENT]

        return self.__check_win()  # 승패 체크해서 리턴

    def __check_win(self):
        """state 승패체크용 내부 함수."""
        # 승리패턴 8가지 구성 (1:돌이 있는 곳, 0: 돌이 없는 곳)
        win_pattern = np.array([[[1, 1, 1], [0, 0, 0], [0, 0, 0]],
                                [[0, 0, 0], [1, 1, 1], [0, 0, 0]],
                                [[0, 0, 0], [0, 0, 0], [1, 1, 1]],
                                [[1, 0, 0], [1, 0, 0], [1, 0, 0]],
                                [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                                [[0, 0, 1], [0, 0, 1], [0, 0, 1]],
                                [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                                [[0, 0, 1], [0, 1, 0], [1, 0, 0]]])
        # 0,1번 보드가 승리패턴과 일치하면
        for i in range(2):
            for k in range(8):
                # 2진 배열은 패턴을 포함할때 서로 곱(행렬곱 아님)하면 패턴 자신이 나옴
                if np.array_equal(
                        self.state[i] * win_pattern[k], win_pattern[k]):
                    if i == PLAYER:  # i가 플레이어면 승리
                        reward = 1  # 보상 1
                        done = True  # 게임 끝
                        info = {'steps': self.step_count}  # step 수 기록
                        print('You Win!', info)  # 승리 메세지 출력
                        return self.state, reward, done, info  # 필수 요소 리턴!
                    else:  # i가 상대면 패배
                        reward = -1  # 보상 -1
                        done = True  # 게임 끝
                        info = {'steps': self.step_count}  # step 수 기록
                        print('You Lose!', info)  # 너 짐
                        return self.state, reward, done, info  # 필수 요소 리턴!
        # 다 돌려봤는데 승부난게 없더라 근데 "O"식별용 2번보드에 들어있는게 5개면? 비김
        if np.count_nonzero(self.state[2]) == 5:
            reward = 0  # 보상 0
            done = True  # 게임 끝
            info = {'steps': self.step_count}
            print('Draw!', info)  # 비김
            return self.state, reward, done, info
        # 이거 다~~~ 아니면 다음 수 둬야지
        else:
            reward = 0
            done = False  # 안 끝남!
            info = {'steps': self.step_count}
            return self.state, reward, done, info

    def _render(self, mode='human', close=False):
        """현재 state를 그려주는 함수."""
        if close:  # 클로즈값이 참인데
            if self.viewer is not None:  # 뷰어가 비어있지 않으면
                self.viewer.close()   # 뷰어를 닫고
                self.viewer = None   # 뷰어 지우기
            return

        if self.viewer is None:
            from gym.envs.classic_control import rendering  # 렌더링 모듈 임포트
            # 뷰어의 좌표 딕트로 구성
            render_loc = {0: (50, 250), 1: (150, 250), 2: (250, 250),
                          3: (50, 150), 4: (150, 150), 5: (250, 150),
                          6: (50, 50), 7: (150, 50), 8: (250, 50)}

            # -------------------- 뷰어 생성 --------------------- #
            # 캔버스 역할의 뷰어 초기화 가로 세로 300
            self.viewer = rendering.Viewer(300, 300)
            # 가로 세로 선 생성 (시작점좌표, 끝점좌표), 색정하기 (r, g, b)
            line_1 = rendering.Line((0, 100), (300, 100))
            line_1.set_color(0, 0, 0)
            line_2 = rendering.Line((0, 200), (300, 200))
            line_2.set_color(0, 0, 0)
            line_a = rendering.Line((100, 0), (100, 300))
            line_a.set_color(0, 0, 0)
            line_b = rendering.Line((200, 0), (200, 300))
            line_b.set_color(0, 0, 0)
            # 뷰어에 선 붙이기
            self.viewer.add_geom(line_1)
            self.viewer.add_geom(line_2)
            self.viewer.add_geom(line_a)
            self.viewer.add_geom(line_b)

            # ----------- OX 마크 이미지 생성 및 위치 지정 -------------- #
            # 9개의 위치에 O,X 모두 위치지정해 놓음 (18장)
            # 그림파일 위치는 이 파일이 있는 폴더 내부의 img 폴더

            # 그림 객체 생성
            self.image_O1 = rendering.Image("img/O.png", 96, 96)
            # 위치 컨트롤 하는 객체 생성
            trans_O1 = rendering.Transform(render_loc[0])
            # 이놈을 이미지에 붙혀서 위치 지정
            # (이미지를 뷰어에 붙이기 전까진 렌더링 안됨)
            self.image_O1.add_attr(trans_O1)

            self.image_O2 = rendering.Image("img/O.png", 96, 96)
            trans_O2 = rendering.Transform(render_loc[1])
            self.image_O2.add_attr(trans_O2)

            self.image_O3 = rendering.Image("img/O.png", 96, 96)
            trans_O3 = rendering.Transform(render_loc[2])
            self.image_O3.add_attr(trans_O3)

            self.image_O4 = rendering.Image("img/O.png", 96, 96)
            trans_O4 = rendering.Transform(render_loc[3])
            self.image_O4.add_attr(trans_O4)

            self.image_O5 = rendering.Image("img/O.png", 96, 96)
            trans_O5 = rendering.Transform(render_loc[4])
            self.image_O5.add_attr(trans_O5)

            self.image_O6 = rendering.Image("img/O.png", 96, 96)
            trans_O6 = rendering.Transform(render_loc[5])
            self.image_O6.add_attr(trans_O6)

            self.image_O7 = rendering.Image("img/O.png", 96, 96)
            trans_O7 = rendering.Transform(render_loc[6])
            self.image_O7.add_attr(trans_O7)

            self.image_O8 = rendering.Image("img/O.png", 96, 96)
            trans_O8 = rendering.Transform(render_loc[7])
            self.image_O8.add_attr(trans_O8)

            self.image_O9 = rendering.Image("img/O.png", 96, 96)
            trans_O9 = rendering.Transform(render_loc[8])
            self.image_O9.add_attr(trans_O9)

            self.image_X1 = rendering.Image("img/X.png", 96, 96)
            trans_X1 = rendering.Transform(render_loc[0])
            self.image_X1.add_attr(trans_X1)

            self.image_X2 = rendering.Image("img/X.png", 96, 96)
            trans_X2 = rendering.Transform(render_loc[1])
            self.image_X2.add_attr(trans_X2)

            self.image_X3 = rendering.Image("img/X.png", 96, 96)
            trans_X3 = rendering.Transform(render_loc[2])
            self.image_X3.add_attr(trans_X3)

            self.image_X4 = rendering.Image("img/X.png", 96, 96)
            trans_X4 = rendering.Transform(render_loc[3])
            self.image_X4.add_attr(trans_X4)

            self.image_X5 = rendering.Image("img/X.png", 96, 96)
            trans_X5 = rendering.Transform(render_loc[4])
            self.image_X5.add_attr(trans_X5)

            self.image_X6 = rendering.Image("img/X.png", 96, 96)
            trans_X6 = rendering.Transform(render_loc[5])
            self.image_X6.add_attr(trans_X6)

            self.image_X7 = rendering.Image("img/X.png", 96, 96)
            trans_X7 = rendering.Transform(render_loc[6])
            self.image_X7.add_attr(trans_X7)

            self.image_X8 = rendering.Image("img/X.png", 96, 96)
            trans_X8 = rendering.Transform(render_loc[7])
            self.image_X8.add_attr(trans_X8)

            self.image_X9 = rendering.Image("img/X.png", 96, 96)
            trans_X9 = rendering.Transform(render_loc[8])
            self.image_X9.add_attr(trans_X9)

        # ------------ state 정보에 맞는 이미지를 뷰어에 붙이는 과정 ------------- #
        # 좌표번호마다 "OX"가 있는지 확인하여 해당하는 이미지를 뷰어에 붙임 (렌더링 때 보임)
        # "OX"의 정체성 설정!
        render_O = None
        render_X = None
        if self.player_color == MARK_O:
            render_O = PLAYER
            render_X = OPPONENT
        else:
            render_O = OPPONENT
            render_X = PLAYER

        if self.state[render_O][0][0] == 1:
            self.viewer.add_geom(self.image_O1)
        elif self.state[render_X][0][0] == 1:
            self.viewer.add_geom(self.image_X1)

        if self.state[render_O][0][1] == 1:
            self.viewer.add_geom(self.image_O2)
        elif self.state[render_X][0][1] == 1:
            self.viewer.add_geom(self.image_X2)

        if self.state[render_O][0][2] == 1:
            self.viewer.add_geom(self.image_O3)
        elif self.state[render_X][0][2] == 1:
            self.viewer.add_geom(self.image_X3)

        if self.state[render_O][1][0] == 1:
            self.viewer.add_geom(self.image_O4)
        elif self.state[render_X][1][0] == 1:
            self.viewer.add_geom(self.image_X4)

        if self.state[render_O][1][1] == 1:
            self.viewer.add_geom(self.image_O5)
        elif self.state[render_X][1][1] == 1:
            self.viewer.add_geom(self.image_X5)

        if self.state[render_O][1][2] == 1:
            self.viewer.add_geom(self.image_O6)
        elif self.state[render_X][1][2] == 1:
            self.viewer.add_geom(self.image_X6)

        if self.state[render_O][2][0] == 1:
            self.viewer.add_geom(self.image_O7)
        elif self.state[render_X][2][0] == 1:
            self.viewer.add_geom(self.image_X7)

        if self.state[render_O][2][1] == 1:
            self.viewer.add_geom(self.image_O8)
        elif self.state[render_X][2][1] == 1:
            self.viewer.add_geom(self.image_X8)

        if self.state[render_O][2][2] == 1:
            self.viewer.add_geom(self.image_O9)
        elif self.state[render_X][2][2] == 1:
            self.viewer.add_geom(self.image_X9)

        # rgb 모드면 뷰어를 렌더링해서 리턴
        return self.viewer.render(return_rgb_array=mode == 'rgb_array')
