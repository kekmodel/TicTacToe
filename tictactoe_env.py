# -*- coding: utf-8 -*-
import logging  # 로그 제공 모듈
import gym   # 환경 제공 모듈
from gym import spaces   # 공간 정의 클래스
from gym.utils import seeding   # 시드 제공 클래스
import numpy as np   # 배열 제공 모듈


logger = logging.getLogger(__name__)   # 실행 로그 남기기, 생략해도 됨
''' 소개 -----------------------------------------------------------
# 규칙: O, X 를 번갈아 가면서 표시하고 3개 연속으로 한줄을 채우면 승리, 무승부 있음
# state: (3, 3, 3) 넘파이 배열: 3*3 평면 3장
 0번 평면: 나의 표시만 1로 체크
 1번 평면: 상대 표시만 1로 체크 (현재 셀프 플레이만 지원)
 2번 평면: O표시만 1로 체크 (누가 OX인지 구별 용)
# action: [피아식별, 좌표행, 좌표열]
 ex) [0, 1, 1] -> step(action) -> state[0][1][1] = 1
* 0번 평면을 기준으로 승패체크. 보상 (승:1, 무:0, 패:-1)
* 최초 입력된 액션의 주체를 O표시로 인식하여 2번 평면에 동기화 함
[
[[0., 0., 0.]
 [0., 0., 0.]
 [0., 0., 0.]]  0번 평면

[[0., 0., 0.]
 [0., 0., 0.]
 [0., 0., 0.]]  1번 평면

[[0., 0., 0.]
 [0., 0., 0.]
 [0., 0., 0.]]  2번 평면
 ]
--------------------------------------------------------------- '''

PLAYER = 0  # 플레이어 식별 변수
OPPONENT = 1  # 상대 식별 변수


class TicTacToeEnv(gym.Env):
    """gym.Env를 상속하여 틱택토 게임 환경 클래스 정의
        gym.Env: OpenAI Gym의 주요 클래스, 환경 뒤에서 이루어지는 동작 캡슐화
        (gym/core.py 참조)
    """
    # _render()의 리턴 타입 구분
    metadata = {'render.modes': ['human', 'rgb_array']}
    reward_range = (-1, 0, 1)  # 보상의 범위 참고: 패배:-1, 무승부:0, 승리:1

    def __init__(self):
        self.mark_O = None  # O가 누군지 매칭, _reset()에서 설정
        self.mark_X = None  # X가 누군지 매칭
        self.board_size = 3  # 3x3 보드 사이즈
        self.board_n = 3  # 보드 개수 3개: 0.플레이어보드, 1.상대보드, 2.O구별 보드
        # 관찰 공간: 3*3개짜리 3장, 허용 범위 [0,1] 있으면 1, 없으면 0
        self.observation_space = spaces.Box(low=0,
                                            high=1,
                                            shape=(self.board_size,
                                                   self.board_size,
                                                   self.board_n))
        # 액션 공간: (player ,opponent 구분 | 행, 열)
        self.action_space = spaces.MultiDiscrete([[0, 1], [0, 2], [0, 2]])
        self.step_count = None  # 액션 진행 횟수 초기화
        self.viewer = None  # 뷰어 초기화
        self.state = None  # 상태 초기화
        self._seed()  # 랜덤 시드 설정하는 함수 호출

    # 랜덤 시드 생성 및 설정 함수
    # 인스턴스 생성시 새로운 시드 생성 및 반환, 소멸전까지 일관된 난수 생성
    def _seed(self, seed=None):
        # 인스턴스가 사용할 np_random 변수 설정
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def _reset(self):  # 상태 리셋 함수
        # 상태 초기화 (3*3 개짜리배열 3장) 2진으로만 해결하기 위해!
        self.state = np.zeros(
            (self.board_size, self.board_size, self.board_n))
        self.step_count = 0  # 액션 진행 횟수 0
        self.viewer = None   # 뷰어 리셋
        self.mark_O = None  # O 주체 리셋
        self.mark_X = None  # X 주체 리셋
        return self.state  # 상태 리턴

    def _step(self, action):
        """한번의 행동에 상태가 어떻게 변하는지 정하는 함수
            승부가 나면 reset()을 호출(메소드 내부 또는 에이전트)하여 환경을 초기화 해야 함
            action을 받아서 (state, reward, done, info)인 튜플 리턴해야 함
        """
        # step count에 1을 더함
        self.step_count += 1
        # 규칙 위반 필터링: 액션 자리에 이미 자리가 차있음
        for i in range(2):
            if self.state[i][action[1]][action[2]] == 1:
                if action[0] == PLAYER:  # 근데 그게 플레이어가 한 짓이면 반칙패
                    reward = -1
                    done = True  # 게임 종료
                    info = {'steps': self.step_count}  # 액션 1회로 인정
                    print('Illegal Lose!')  # 출력
                    return self.state, reward, done, info  # 필수 요소 리턴
                elif action[0] == OPPONENT:  # 상대가 한짓이면 반대
                    reward = 1
                    done = True
                    info = {'steps': self.step_count}
                    print('Illegal Win!')
                    return self.state, reward, done, info
        # 반칙이 아니면 진행
        # step_count 1, 3, 5 같은 홀수번째 액션은 O표시니까
        if self.step_count % 2 == 1:
            # 첫 action엔 action주체를 불러와서 O표시가 누군지 매칭해주고
            if self.step_count == 1:
                self.mark_O = action[0]
            self.state[2][action[1]][action[2]] = 1  # O표시용 2번보드에 동기화
            # 주체를 식별해서 해당 보드에도 적용
            self.state[action[0]][action[1]][action[2]] = 1
        else:  # 짝수번 째 액션은  X니까 해당 보드에만 적용
            self.state[action[0]][action[1]][action[2]] = 1
        return self.__check_win()  # 승패 체크해서 리턴

    def __check_win(self):  # state 승패체크용 내부 함수
        # 승리패턴 8가지 구성 (1:돌이 있는 곳, 0: 돌이 없는 곳)
        win_pattern = np.array([[[1, 1, 1], [0, 0, 0], [0, 0, 0]],
                                [[0, 0, 0], [1, 1, 1], [0, 0, 0]],
                                [[0, 0, 0], [0, 0, 0], [1, 1, 1]],
                                [[1, 0, 0], [1, 0, 0], [1, 0, 0]],
                                [[0, 0, 1], [0, 0, 1], [0, 0, 1]],
                                [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                                [[0, 0, 1], [0, 1, 0], [1, 0, 0]],
                                [[1, 0, 0], [0, 1, 0], [0, 0, 1]]])
        for i in range(2):
            for k in range(8):  # 0,1번 보드가 승리패턴과 일치하면
                # 바이너리 배열은 패턴을 포함할때 서로 곱(행렬곱아님)하면 패턴 자신이 나옴;
                # 고민하다 발견
                if np.array_equal(
                        self.state[i] * win_pattern[k], win_pattern[k]):
                    if i == PLAYER:  # 주체인 i가 플레이어면 승리
                        reward = 1  # 보상 1
                        done = True  # 게임 끝
                        info = {'steps': self.step_count}  # step 수 기록
                        print('You Win!', info)  # 승리 메세지 출력
                        return self.state, reward, done, info  # 필수 값 리턴!
                    else:  # 주체가 상대면 패배
                        reward = -1  # 보상 -1
                        done = True  # 게임 끝
                        info = {'steps': self.step_count}  # step 수 기록
                        print('You Lose!', info)  # 너 짐
                        return self.state, reward, done, info  # 필수 값 리턴!
        # 다 돌려봤는데 승부난게 없더라 근데 O식별용 2번보드에 들어있는게 5개면? 비김
        if np.count_nonzero(self.state[2]) == 5:
            reward = 0  # 보상 0
            done = True  # 게임 끝
            info = {'steps': self.step_count}
            print('Draw!', info)  # 비김
            return self.state, reward, done, info
        else:  # 이거 다~~~ 아니면 다음 수 둬야지
            reward = 0
            done = False  # 안 끝남!
            info = {'steps': self.step_count}
            return self.state, reward, done, info

    def _render(self, mode='human', close=False):  # 현재 상태를 그려주는 함수
        if close:   # 클로즈값이 참인데
            if self.viewer is not None:  # 뷰어가 비어있지 않으면
                self.viewer.close()   # 뷰어를 닫고
                self.viewer = None   # 뷰어 초기화
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
            # 위치 컨트롤 하는 객체
            trans_O1 = rendering.Transform(render_loc[0])
            # 이놈을 이미지에 장착 (이미지를 뷰어에 붙이기 전까진 렌더링 안됨)
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

        # ------------ 상태 정보에 맞는 이미지를 뷰어에 붙이는 과정 -------------- #
        self.mark_X = abs(self.mark_O - 1)  # O가 0이면 X는 1, 1이면 0으로 세팅
        # 좌표번호마다 O,X가 있는지 확인하여 해당하는 이미지를 뷰어에 붙임 (렌더링 때 보임)
        if self.state[self.mark_O][0][0] == 1:
            self.viewer.add_geom(self.image_O1)
        elif self.state[self.mark_X][0][0] == 1:
            self.viewer.add_geom(self.image_X1)

        if self.state[self.mark_O][0][1] == 1:
            self.viewer.add_geom(self.image_O2)
        elif self.state[self.mark_X][0][1] == 1:
            self.viewer.add_geom(self.image_X2)

        if self.state[self.mark_O][0][2] == 1:
            self.viewer.add_geom(self.image_O3)
        elif self.state[self.mark_X][0][2] == 1:
            self.viewer.add_geom(self.image_X3)

        if self.state[self.mark_O][1][0] == 1:
            self.viewer.add_geom(self.image_O4)
        elif self.state[self.mark_X][1][0] == 1:
            self.viewer.add_geom(self.image_X4)

        if self.state[self.mark_O][1][1] == 1:
            self.viewer.add_geom(self.image_O5)
        elif self.state[self.mark_X][1][1] == 1:
            self.viewer.add_geom(self.image_X5)

        if self.state[self.mark_O][1][2] == 1:
            self.viewer.add_geom(self.image_O6)
        elif self.state[self.mark_X][1][2] == 1:
            self.viewer.add_geom(self.image_X6)

        if self.state[self.mark_O][2][0] == 1:
            self.viewer.add_geom(self.image_O7)
        elif self.state[self.mark_X][2][0] == 1:
            self.viewer.add_geom(self.image_X7)

        if self.state[self.mark_O][2][1] == 1:
            self.viewer.add_geom(self.image_O8)
        elif self.state[self.mark_X][2][1] == 1:
            self.viewer.add_geom(self.image_X8)

        if self.state[self.mark_O][2][2] == 1:
            self.viewer.add_geom(self.image_O9)
        elif self.state[self.mark_X][2][2] == 1:
            self.viewer.add_geom(self.image_X9)
        # rgb 모드면 뷰어를 렌더링해서 리턴해라
        return self.viewer.render(return_rgb_array=mode == 'rgb_array')


# 테스트용 지워도 무방
if __name__ == "__main__":
    import time
    env = TicTacToeEnv()
    state = env.reset()
    print(state)
    print('Start!')

    action = [0, 1, 1]
    state, reward, done, info = env.step(action)
    print('reward: %d' % reward)
    print(info)
    print(state)
    env.render()
    time.sleep(0.4)

    action = [1, 1, 2]
    state, reward, done, info = env.step(action)
    print('reward: %d' % reward)
    print(info)
    print(state)
    env.render()
    time.sleep(0.4)

    action = [0, 1, 0]
    state, reward, done, info = env.step(action)
    print('reward: %d' % reward)
    print(info)
    print(state)
    env.render()
    time.sleep(0.4)

    action = [1, 2, 2]
    state, reward, done, info = env.step(action)
    print('reward: %d' % reward)
    print(info)
    print(state)
    env.render()
    time.sleep(0.4)

    action = [0, 0, 2]
    state, reward, done, info = env.step(action)
    print('reward: %d' % reward)
    print(info)
    print(state)
    env.render()
    time.sleep(0.4)

    action = [1, 2, 1]
    state, reward, done, info = env.step(action)
    print('reward: %d' % reward)
    print(info)
    print(state)
    env.render()
    time.sleep(0.4)

    action = [0, 2, 0]
    state, reward, done, info = env.step(action)
    print('reward: %d' % reward)
    print(info)
    print(state)
    env.render()
    time.sleep(0.4)
    if done:
        time.sleep(0.2)

    env.close()
