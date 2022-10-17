import os
import sys
import socket
import threading
import string
import ctypes
import hashlib
from time import sleep
import pygame
import numpy as np
import pygame_gui
from enum import IntEnum

from pygame_gui.ui_manager import UIManager
from pygame_gui.elements import *
from pygame_gui.windows import *
from pygame_gui._constants import UI_FILE_DIALOG_PATH_PICKED
import pyperclip

SERVER_ACTION_FINISHED = pygame.event.custom_type()

class RequestType(IntEnum):
    REGISTER = 0
    LOGIN = 1
    RIVALS_LIST = 2
    GET_DEFAULT_PATH = 3
    SET_DEFAULT_PATH = 4
    SUBMIT = 5
    FIGHT = 6
    LOGOUT = 7
    LOAD_LAST_SUBMISSION = 8

def post_action_finished(action_type: RequestType, response_code, response):
    event_data = {
        'action_type': action_type,
        'response_code': response_code,
        'response': response,
        }
    pygame.event.post(pygame.event.Event(SERVER_ACTION_FINISHED, event_data))

class ServerComm:

    def _recv_exact(socket, no_bytes):
        # Helper function to recv no_bytes bytes or return None if EOF is hit
        data = bytearray()
        while len(data) < no_bytes:
            packet = socket.recv(no_bytes - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def _perform_actions():
        while len(ServerComm.actions_queue) > 0:
            action_fp, args = ServerComm.actions_queue[0]
            action_fp(*args)
            ServerComm.actions_queue.pop(0)

    def _add_action(action_fp, args=()):
        ServerComm.actions_queue.append((action_fp, args))
        if len(ServerComm.actions_queue) == 1:
            ServerComm.actions_thread = threading.Thread(target=ServerComm._perform_actions)
            ServerComm.actions_thread.start()

    def _connect():
        ServerComm.connected = False
        ServerComm.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if len(sys.argv) >= 2:
            ServerComm.host, ServerComm.port = sys.argv[1].split(':')
            ServerComm.port = int(ServerComm.port)
        else:
            ServerComm.host, ServerComm.port = ('16.170.245.99', 6666)
            print(f'No target host and port is specified for the server, taking default host: {ServerComm.host} and port: {ServerComm.port}')

        print(f'Trying connection to {ServerComm.host} on port {ServerComm.port}')
        try:
            ServerComm.client_socket.connect((ServerComm.host, ServerComm.port))
            ServerComm.connected = True
            print('Connected')
        except socket.error as e:
            print(str(e))
    
    def connect():
        ServerComm._add_action(ServerComm._connect)
    
    def _authenticate(username, password, action_type):
        sha_encryption = hashlib.new('sha256')
        sha_encryption.update(password.encode())
        ServerComm.client_socket.send(bytes([action_type.value]))
        ServerComm.client_socket.send(f'{username} {sha_encryption.hexdigest()}'.encode())
        response_code = ServerComm._recv_exact(ServerComm.client_socket, 1)[0]
        response_msg = ServerComm.client_socket.recv(1024).decode()
        print(f'Server sent response code {response_code} with response message: {response_msg}')
        post_action_finished(action_type, response_code, response_msg)

    def login(username, password):
        ServerComm._add_action(ServerComm._authenticate, args=(username, password, RequestType.LOGIN))

    def register(username, password):
        ServerComm._add_action(ServerComm._authenticate, args=(username, password, RequestType.REGISTER))

    def _get_rivals_list():
        ServerComm.client_socket.send(bytes([RequestType.RIVALS_LIST.value]))
        response_code = ServerComm._recv_exact(ServerComm.client_socket, 1)[0]
        response_msg = ServerComm.client_socket.recv(2048).decode()
        print(f'Server sent response code {response_code} with response message: {response_msg}')
        post_action_finished(RequestType.RIVALS_LIST, response_code, response_msg)

    def get_rivals_list():
        ServerComm._add_action(ServerComm._get_rivals_list)

    def _get_default_path():
        ServerComm.client_socket.send(bytes([RequestType.GET_DEFAULT_PATH.value]))
        response_code = ServerComm._recv_exact(ServerComm.client_socket, 1)[0]
        response_msg = ServerComm.client_socket.recv(2048).decode()
        print(f'Server sent response code {response_code} with response message: {response_msg}')
        post_action_finished(RequestType.GET_DEFAULT_PATH, response_code, response_msg)

    def get_default_path():
        ServerComm._add_action(ServerComm._get_default_path)

    def _set_default_path(new_path):
        ServerComm.client_socket.send(bytes([RequestType.SET_DEFAULT_PATH.value]))
        ServerComm.client_socket.send(new_path.encode())
        response_code = ServerComm._recv_exact(ServerComm.client_socket, 1)[0]
        response_msg = ServerComm.client_socket.recv(2048).decode()
        print(f'Server sent response code {response_code} with response message: {response_msg}')
        post_action_finished(RequestType.SET_DEFAULT_PATH, response_code, response_msg)

    def set_default_path(new_path):
        ServerComm._add_action(ServerComm._set_default_path, args=[new_path])

    def _submit(file_contents):
        ServerComm.client_socket.send(bytes([RequestType.SUBMIT.value]))
        ServerComm.client_socket.send(len(file_contents).to_bytes(4,'little'))
        ServerComm.client_socket.send(file_contents.encode())
        response_code = ServerComm._recv_exact(ServerComm.client_socket, 1)[0]
        response_msg = ServerComm.client_socket.recv(2048).decode()
        print(f'Server sent response code {response_code} with response message: {response_msg}')
        post_action_finished(RequestType.SUBMIT, response_code, response_msg)

    def submit(file_contents):
        ServerComm._add_action(ServerComm._submit, args=[file_contents])

    def _load_last_submission():
        ServerComm.client_socket.send(bytes([RequestType.LOAD_LAST_SUBMISSION.value]))
        response_code = ServerComm._recv_exact(ServerComm.client_socket, 1)[0]
        size = int.from_bytes(ServerComm._recv_exact(ServerComm.client_socket, 4), 'little')
        data = ServerComm._recv_exact(ServerComm.client_socket, size)
        response_msg = data.decode()
        post_action_finished(RequestType.LOAD_LAST_SUBMISSION, response_code, response_msg)

    def load_last_submission():
        ServerComm._add_action(ServerComm._load_last_submission)

ServerComm.connected = False
ServerComm.actions_queue = []

def validate_cradentials(username, password, confirm_password=None):
    username_charset = list(string.ascii_letters + string.digits + '_')
    password_charset = list(string.ascii_letters + string.digits + string.punctuation)
    size_rng = (4, 30)

    if len(username) < size_rng[0] or len(username) > size_rng[1]:
        return f'Username length should be between [{size_rng[0]}, {size_rng[1]}]'

    if len(password) < size_rng[0] or len(password) > size_rng[1]:
        return f'Password length should be between [{size_rng[0]}, {size_rng[1]}]'

    for ch in username:
        if ch not in username_charset:
            return 'Username should contain letters, digits and _ only'
    
    for ch in password:
        if ch not in password_charset:
            return f'Password should contain letters, digits and any of {string.punctuation} only'
    
    if confirm_password is not None and password != confirm_password:
        return 'Passwords do not match'

    return None

class LoginWindow(UIWindow):
    def __init__(self, app_window_size, ui_manager):
        self.app_window_size = app_window_size
        self.window_size = (480, 360)
        self.window_position = np.divide(np.subtract(app_window_size, self.window_size), 2)
        super().__init__(pygame.Rect(self.window_position, self.window_size), ui_manager,
                         window_display_title='Login',
                         object_id='#login_window')
        
        self.register_window_created = False
        self.set_blocking(True)
        self.close_window_button.is_enabled = False
        self.title_bar.is_enabled = False
        self.game_surface_size = self.get_container().get_size()
        
        self.username_label = UILabel(pygame.Rect((30, 40), (-1, -1)),
                                      'Username',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self)

        self.username_et_size = (self.game_surface_size[0]-60,40)
        self.username_et = UITextEntryLine(pygame.Rect((0, 5), self.username_et_size),
                                           manager=ui_manager,
                                           container=self,
                                           parent_element=self,
                                           anchors={
                                               'top': 'top',
                                               'left': 'right',
                                               'bottom': 'top',
                                               'right': 'right',
                                               'top_target': self.username_label,
                                               'right_target': self.username_label
                                           })
        
        self.password_label = UILabel(pygame.Rect((30, 130), (-1, -1)),
                                      'Password',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self)
        
        self.password_et_size = (self.game_surface_size[0]-60,40)
        self.password_et = UITextEntryLine(pygame.Rect((0, 0), self.password_et_size),
                                           manager=ui_manager,
                                           container=self,
                                           parent_element=self,
                                           anchors={
                                               'top': 'top',
                                               'left': 'right',
                                               'bottom': 'top',
                                               'right': 'right',
                                               'top_target': self.password_label,
                                               'right_target': self.password_label
                                           })
        self.password_et.set_text_hidden()
        
        self.login_button_size = (100,40)
        self.login_button_pos = np.divide(np.subtract(self.game_surface_size, self.login_button_size), (2, 1.1))
        self.login_button = UIButton(pygame.Rect(self.login_button_pos, self.login_button_size),
                                     'Login',
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     object_id="#login_button")

        self.register_now_rect = pygame.Rect((0, 0), (-1, -1))
        self.register_now_rect.bottomright = (-10, -10)
        self.register_now_button = UIButton(self.register_now_rect,
                                            "Register Now",
                                            manager=ui_manager,
                                            container=self,
                                            parent_element=self,
                                            anchors={
                                                'left': 'right',
                                                'top': 'bottom',
                                                'right': 'right',
                                                'bottom': 'bottom',
                                            },
                                            object_id="#register_now_button")

        self.message_label = UILabel(pygame.Rect((-self.password_et_size[0], 15), (-1, -1)),
                                     '',
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     anchors={
                                        'top': 'top',
                                        'left': 'left',
                                        'bottom': 'top',
                                        'right': 'left',
                                        'top_target': self.password_et,
                                        'left_target': self.password_et
                                     })

    def switch_to_register_window(self):
        if not self.register_window_created:
            self.register_window = RegisterWindow(self.app_window_size, self.ui_manager)
            self.register_window.login_window = self
            self.register_window_created = True
        self.register_window.show()
        self.hide()

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#login_window.#login_button" and \
            event.ui_element == self.login_button:
            self.message_label.set_text('')
            response = validate_cradentials(self.username_et.text, self.password_et.text)
            if response is None:
                self.login_button.disable()
                ServerComm.login(self.username_et.text, self.password_et.text)
            else:
                self.message_label.set_text(response)
        elif event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#login_window.#register_now_button" and \
            event.ui_element == self.register_now_button:
            self.switch_to_register_window()
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.LOGIN:
            self.login_button.enable()
            self.message_label.set_text(event.response)
            if event.response_code == 0:
                self.hide()

        
    def update(self, time_delta):
        super().update(time_delta)

class RegisterWindow(UIWindow):
    def __init__(self, app_window_size, ui_manager):
        self.window_size = (480, 455)
        self.window_position = np.divide(np.subtract(app_window_size, self.window_size), 2)
        super().__init__(pygame.Rect(self.window_position, self.window_size), ui_manager,
                         window_display_title='Register',
                         object_id='#register_window')
        
        self.set_blocking(True)
        self.close_window_button.is_enabled = False
        self.title_bar.is_enabled = False
        self.game_surface_size = self.get_container().get_size()
        
        self.username_label = UILabel(pygame.Rect((30, 40), (-1, -1)),
                                      'Username',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self)

        self.username_et_size = (self.game_surface_size[0]-60,40)
        self.username_et = UITextEntryLine(pygame.Rect((0, 5), self.username_et_size),
                                           manager=ui_manager,
                                           container=self,
                                           parent_element=self,
                                           anchors={
                                               'top': 'top',
                                               'left': 'right',
                                               'bottom': 'top',
                                               'right': 'right',
                                               'top_target': self.username_label,
                                               'right_target': self.username_label
                                           })
        
        self.password_label = UILabel(pygame.Rect((30, 130), (-1, -1)),
                                      'Password',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self)
        
        self.password_et_size = (self.game_surface_size[0]-60,40)
        self.password_et = UITextEntryLine(pygame.Rect((0, 0), self.password_et_size),
                                           manager=ui_manager,
                                           container=self,
                                           parent_element=self,
                                           anchors={
                                               'top': 'top',
                                               'left': 'right',
                                               'bottom': 'top',
                                               'right': 'right',
                                               'top_target': self.password_label,
                                               'right_target': self.password_label
                                           })
        self.password_et.set_text_hidden()
        
        self.confirm_password_label = UILabel(pygame.Rect((30, 220), (-1, -1)),
                                      'Confirm Password',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self)
        
        self.confirm_password_et_size = (self.game_surface_size[0]-60,40)
        self.confirm_password_et = UITextEntryLine(pygame.Rect((0, 0), self.confirm_password_et_size),
                                                   manager=ui_manager,
                                                   container=self,
                                                   parent_element=self,
                                                   anchors={
                                                       'top': 'top',
                                                       'left': 'right',
                                                       'bottom': 'top',
                                                       'right': 'right',
                                                       'top_target': self.confirm_password_label,
                                                       'right_target': self.confirm_password_label
                                                   })
        self.confirm_password_et.set_text_hidden()
        
        
        self.register_button_size = (100, 40)
        self.register_button_pos = np.divide(np.subtract(self.game_surface_size, self.register_button_size), (2, 1.1))
        self.register_button = UIButton(pygame.Rect(self.register_button_pos, self.register_button_size),
                                        'Register',
                                        manager=ui_manager,
                                        container=self,
                                        parent_element=self,
                                        object_id="#register_button")

        self.message_label = UILabel(pygame.Rect((-self.confirm_password_et_size[0], 12), (-1, -1)),
                                     '',
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     anchors={
                                        'top': 'top',
                                        'left': 'left',
                                        'bottom': 'top',
                                        'right': 'left',
                                        'top_target': self.confirm_password_et,
                                        'left_target': self.confirm_password_et
                                     })

        self.login_rect = pygame.Rect((0, 0), (-1, -1))
        self.login_rect.bottomright = (-10, -10)
        self.login_button = UIButton(self.login_rect,
                                     "Login Instead",
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     anchors={
                                        'left': 'right',
                                        'top': 'bottom',
                                        'right': 'right',
                                        'bottom': 'bottom',
                                     },
                                     object_id="#login_button")

    def switch_to_login_window(self):
        self.hide()
        self.login_window.show()

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#register_window.#register_button" and \
            event.ui_element == self.register_button:
            self.message_label.set_text('')
            response = validate_cradentials(self.username_et.text, self.password_et.text, self.confirm_password_et.text)
            if response is None:
                self.register_button.disable()
                ServerComm.register(self.username_et.text, self.password_et.text)
            else:
                self.message_label.set_text(response)
        if event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#register_window.#login_button" and \
            event.ui_element == self.login_button:
            self.switch_to_login_window()
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.REGISTER:
            self.register_button.enable()
            self.message_label.set_text(event.response)
        
    def update(self, time_delta):
        super().update(time_delta)

class GamePanel(UIPanel):
    def __init__(self, app_window_size, ui_manager, bottom, centerx):
        self.window_rect = pygame.Rect((0, 0), (bottom-100, bottom-100))
        self.window_rect.centerx = centerx
        self.window_rect.top = 75

        super().__init__(self.window_rect,
                         0,
                         ui_manager,
                         object_id='#game_panel')
        
        

class FightPanel(UIPanel):
    def __init__(self, app_window_size, ui_manager):
        self.window_rect = pygame.Rect((0, 0), (app_window_size[0] / 2, app_window_size[1]))
        super().__init__(self.window_rect,
                         0,
                         ui_manager, 
                         object_id='#fight_panel')
        
        self.game_surface_size = self.get_container().get_size()

        
        self.fight_button_horizontal_margin = 200
        self.fight_button_vertical_margin = 75
        self.fight_button_rect = pygame.Rect((0, 0), (self.window_rect.width / 2, 200))
        self.fight_button_rect.bottomright = self.window_rect.bottomright
        self.fight_button_center = self.fight_button_rect.center # save center
        self.fight_button_rect.width -= self.fight_button_horizontal_margin
        self.fight_button_rect.height -= self.fight_button_vertical_margin
        self.fight_button_rect.center = self.fight_button_center # reset center to saved

        self.fight_button = UIButton(self.fight_button_rect,
                                     'Fight',
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     object_id="#fight_button")
        self.fight_button.disable()
        
        self.select_enemy_label_rect = pygame.Rect((0, 0), (self.window_rect.width / 2, 40))
        self.select_enemy_label_rect.bottomleft = self.window_rect.bottomleft
        self.select_enemy_label_rect.y -= 160
        self.select_enemy_label = UILabel(self.select_enemy_label_rect,
                                     'Select Enemy:',
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     object_id="#select_enemy_label")

        self.enemy_selector_rect = pygame.Rect((0, 0), self.fight_button_rect.size)
        self.enemy_selector_rect.centery = self.fight_button_rect.centery
        self.enemy_selector_rect.centerx = self.select_enemy_label_rect.centerx
        self.enemy_selector = UISelectionList(self.enemy_selector_rect,
                                     [],
                                     allow_double_clicks=False,
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     object_id="#enemy_selector")

        self.game_panel = GamePanel(app_window_size, ui_manager, self.select_enemy_label_rect.top, self.window_rect.centerx)
        
    def process_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#fight_panel.#fight_button" and \
            event.ui_element == self.fight_button:
            pass
        elif event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            self.fight_button.enable()
            self.fight_button.set_text(f"Fight {event.text}")
            self.current_enemy = event.text
        elif event.type == pygame_gui.UI_SELECTION_LIST_DROPPED_SELECTION and \
            event.ui_object_id == "#fight_panel.#enemy_selector" and \
            event.ui_element == self.enemy_selector:
            if self.current_enemy == event.text:
                self.fight_button.text = "Fight"
                self.fight_button.disable()
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.LOGIN and \
            event.response_code == 0:
            ServerComm.get_rivals_list()
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.RIVALS_LIST and \
            event.response_code == 0:
            self.enemy_selector.set_item_list(event.response.split(','))


class SubmissionPanel(UIPanel):
    def __init__(self, app_window_size, ui_manager):
        self.ui_manager = ui_manager
        self.app_window_size = app_window_size
        self.window_rect = pygame.Rect((self.app_window_size[0] / 2, 0), (self.app_window_size[0] / 2, self.app_window_size[1]))
        super().__init__(self.window_rect,
                         0,
                         ui_manager, 
                         object_id='#submission_panel')
        
        self.game_surface_size = self.get_container().get_size()

        self.open_file_button_rect = pygame.Rect(np.divide(np.subtract(self.game_surface_size, (100, 40)), (7, 1)), (100, 40))
        self.open_file_button = UIButton(self.open_file_button_rect,
                                         'Open File',
                                         manager=ui_manager,
                                         container=self,
                                         parent_element=self,
                                         object_id="#open_file_button")
        
        self.submit_button_rect = pygame.Rect(np.divide(np.subtract(self.game_surface_size, (100, 40)), (3, 1)), (100, 40))
        self.submit_button = UIButton(self.submit_button_rect,
                                      'Submit',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self,
                                      object_id="#submit_button")

        self.load_last_submit_button_rect = pygame.Rect(np.divide(np.subtract(self.game_surface_size, (200, 40)), (1.65, 1)), (200, 40))
        self.load_last_submit_button = UIButton(self.load_last_submit_button_rect,
                                                'Load Last Submission',
                                                manager=ui_manager,
                                                container=self,
                                                parent_element=self,
                                                object_id="#load_last_submission_button")
        
        self.copy_contents_button_rect = pygame.Rect(np.divide(np.subtract(self.game_surface_size, (150, 40)), (1.1, 1)), (150, 40))
        self.copy_contents_button = UIButton(self.copy_contents_button_rect,
                                             'Copy Contents',
                                             manager=ui_manager,
                                             container=self,
                                             parent_element=self,
                                             object_id="#copy_contents_button")
        
        self.submission_text_rect = pygame.Rect((50, 30), (self.window_rect.width - 100, self.window_rect.height - 100))
        self.submission_text = UITextBox('', 
                                         self.submission_text_rect,
                                         manager=ui_manager,
                                         container=self,
                                         parent_element=self,
                                         object_id="submission_text")


        self.message_label_rect = pygame.Rect((0, 0), (-1, -1))
        self.message_label_rect.centerx = self.submission_text_rect.centerx
        self.message_label_rect.top = self.submission_text_rect.bottom
        self.message_label = UILabel(self.message_label_rect,
                                     '',
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     )
        

    def _show_message(self, txt):
        self.message_label.set_relative_position((self.message_label_rect.left - len(txt)*4, self.message_label_rect.top)) # 4 is the magic number
        self.message_label.set_text(txt)
        sleep(2)
        self.message_label.set_text('')
    
    def validate_submission(self, contents) -> int:
        if contents == '':
            message_thread = threading.Thread(target=self._show_message, args=['Your algorithm is empty!'])
            message_thread.start()
            return False
        
        return True

    def validate_path(self, path: str) :
        if not path.endswith('.py'):
            message_thread = threading.Thread(target=self._show_message, args=['You algorithm has to be a python file (.py)'])
            message_thread.start()
            return False
        return True

    def create_file_dialog(self, inital_path=''):
        self.file_dialog_rect = pygame.Rect((0, 0), (self.app_window_size[0]/2, 800))
        self.file_dialog_rect.topleft = (self.app_window_size[0]/4, 100)
        if inital_path != '':
            self.file_dialog = UIFileDialog(self.file_dialog_rect,
                                            manager=self.ui_manager,
                                            initial_file_path=inital_path,
                                            allow_existing_files_only=True,
                                            object_id="file_dialog")
        else:
            self.file_dialog = UIFileDialog(self.file_dialog_rect,
                                            manager=self.ui_manager,
                                            allow_existing_files_only=True,
                                            object_id="file_dialog")

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#submission_panel.#open_file_button" and \
            event.ui_element == self.open_file_button:
            self.open_file_button.disable()
            ServerComm.get_default_path()
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.GET_DEFAULT_PATH:
            default_path = event.response
            if event.response_code != 0 or not os.path.exists(default_path):
                self.create_file_dialog()
            else:
                self.create_file_dialog(inital_path=default_path)
            
            self.open_file_button.enable()
        elif event.type == UI_FILE_DIALOG_PATH_PICKED:
            path = event.text.replace('\\','/')
            if self.validate_path(path):
                with open(path, "r") as subb:
                    text = subb.read()
                    text = text.replace('\n', '<br>')
                    self.submission_text.set_text(text)
                ServerComm.set_default_path(path)
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.LOGIN and \
            event.response_code == 0:
            ServerComm.load_last_submission()
        elif event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#submission_panel.#submit_button" and \
            event.ui_element == self.submit_button:
            submission = self.submission_text.html_text.replace('<br>','\n')
            if self.validate_submission(submission) :
                ServerComm.submit(submission)
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.SUBMIT:
            message_thread = threading.Thread(target=self._show_message, args=[event.response])
            message_thread.start()
        elif event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#submission_panel.#load_last_submission_button" and \
            event.ui_element == self.load_last_submit_button:
            self.load_last_submit_button.disable()
            ServerComm.load_last_submission()
        elif event.type == SERVER_ACTION_FINISHED and \
            event.action_type == RequestType.LOAD_LAST_SUBMISSION:
            self.submission_text.set_text(event.response.replace('\n','<br>'))
            self.load_last_submit_button.enable()
        elif event.type == pygame_gui.UI_BUTTON_PRESSED and \
            event.ui_object_id == "#submission_panel.#copy_contents_button" and \
            event.ui_element == self.copy_contents_button:
            pyperclip.copy(self.submission_text.html_text.replace('<br>','\n'))
            message_thread = threading.Thread(target=self._show_message, args=['Copied!'])
            message_thread.start()

class BorgleApp:
    def __init__(self):
        pygame.init()

        self.root_window_surface = pygame.display.set_mode((0, 0), pygame.RESIZABLE)
        
        if sys.platform == "win32":
            HWND = pygame.display.get_wm_info()['window']
            SW_MAXIMIZE = 3
            ctypes.windll.user32.ShowWindow(HWND, SW_MAXIMIZE)
            
        self.window_size = pygame.display.get_surface().get_size()
        
        pygame.display.set_caption("Borgle")

        self.background_surface = pygame.Surface(self.window_size).convert()
        self.background_surface.fill(pygame.Color('#505050')) 
        
        self.ui_manager = UIManager(self.window_size)#, 'data/themes/theme_3.json')
        self.clock = pygame.time.Clock()
        self.is_running = True
        
        self.fight_panel = FightPanel(self.window_size, self.ui_manager)
        self.submission_panel = SubmissionPanel(self.window_size, self.ui_manager)

        self.login_window = LoginWindow(self.window_size, self.ui_manager)
    
    def _auto_login(self):
        ServerComm.login("yoav", "shifman")

    def auto_login(self):
        auto_login_thread = threading.Thread(target=self._auto_login)
        auto_login_thread.start()
        

    def run(self):
        while self.is_running:
            time_delta = self.clock.tick(60)/1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_running = False
                
                self.ui_manager.process_events(event)
                    
            self.ui_manager.update(time_delta)

            self.root_window_surface.blit(self.background_surface, (0, 0))
            self.ui_manager.draw_ui(self.root_window_surface)

            pygame.display.update()

                    
        pygame.quit()


# TITLE OF CANVAS

if __name__ == '__main__':
    ServerComm.connect()
    app = BorgleApp()
    # app.auto_login()
    app.run()
