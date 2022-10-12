import sys
import socket
import threading
import string
import ctypes
import hashlib
from turtle import st
import pygame
import numpy as np
import pygame_gui
from enum import IntEnum

from pygame_gui.ui_manager import UIManager
from pygame_gui.elements import *

SERVER_ACTION_FINISHED = pygame.event.custom_type()

class RequestType(IntEnum):
    REGISTER = 0
    LOGIN = 1
    RIVALS_LIST = 2
    SUBMIT = 3
    FIGHT = 4
    LOGOUT = 5

def post_action_finished(action_type: RequestType, response_code, response):
    event_data = {
        'action_type': action_type,
        'response_code': response_code,
        'response': response,
        }
    pygame.event.post(pygame.event.Event(SERVER_ACTION_FINISHED, event_data))

class ServerComm:

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
        if not ServerComm.connected:
            connection_thread = threading.Thread(target=ServerComm._connect)
            connection_thread.start()
    
    def _authenticate(username, password, action_type):
        sha_encryption = hashlib.new('sha256')
        sha_encryption.update(password.encode())
        ServerComm.client_socket.send(bytes([action_type.value]))
        ServerComm.client_socket.send(f'{username} {sha_encryption.hexdigest()}'.encode())
        response_code = ServerComm.client_socket.recv(1)[0]
        response_msg = ServerComm.client_socket.recv(1024).decode()
        print(f'Server sent response code {response_code} with response message: {response_msg}')
        post_action_finished(action_type, response_code, response_msg)

    def login(username, password):
        login_thread = threading.Thread(target=ServerComm._authenticate, args=(username, password, RequestType.LOGIN))
        login_thread.start()

    def register(username, password):
        register_thread = threading.Thread(target=ServerComm._authenticate, args=(username, password, RequestType.REGISTER))
        register_thread.start()

    def _get_rivals_list():
        ServerComm.client_socket.send(bytes([RequestType.RIVALS_LIST.value]))
        response_code = ServerComm.client_socket.recv(1)[0]
        response_msg = ServerComm.client_socket.recv(2048).decode()
        print(f'Server sent response code {response_code} with response message: {response_msg}')
        post_action_finished(RequestType.RIVALS_LIST, response_code, response_msg)

    def get_rivals_list():
        get_rivals_list_thread = threading.Thread(target=ServerComm._get_rivals_list)
        get_rivals_list_thread.start()

ServerComm.connected = False

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
        game_surface_size = self.get_container().get_size()
        
        self.username_label = UILabel(pygame.Rect((30, 40), (-1, -1)),
                                      'Username',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self)

        self.username_et_size = (game_surface_size[0]-60,40)
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
        
        self.password_et_size = (game_surface_size[0]-60,40)
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
        self.login_button_pos = np.divide(np.subtract(game_surface_size, self.login_button_size), (2, 1.1))
        self.login_button = UIButton(pygame.Rect(self.login_button_pos, self.login_button_size),
                                     'Login',
                                     manager=ui_manager,
                                     container=self,
                                     parent_element=self,
                                     object_id="#login_button")

        self.register_now_rect = pygame.Rect((0, 0), (-1, -1))
        self.register_now_rect.bottomright = (-140, -50)
        self.register_now_button = UIButton(self.register_now_rect,
                                            "Register Now",
                                            manager=ui_manager,
                                            container=self,
                                            parent_element=self,
                                            anchors={
                                                'top': 'top',
                                                'left': 'left',
                                                'bottom': 'top',
                                                'right': 'left',
                                                'top_target': self,
                                                'left_target': self
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
        game_surface_size = self.get_container().get_size()
        
        self.username_label = UILabel(pygame.Rect((30, 40), (-1, -1)),
                                      'Username',
                                      manager=ui_manager,
                                      container=self,
                                      parent_element=self)

        self.username_et_size = (game_surface_size[0]-60,40)
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
        
        self.password_et_size = (game_surface_size[0]-60,40)
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
        
        self.confirm_password_et_size = (game_surface_size[0]-60,40)
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
        
        
        self.register_button_size = (100,40)
        self.register_button_pos = np.divide(np.subtract(game_surface_size, self.register_button_size), (2, 1.1))
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
        self.login_rect.bottomright = (-150, -50)
        self.login_button = UIButton(self.login_rect,
                                            "Login Instead",
                                            manager=ui_manager,
                                            container=self,
                                            parent_element=self,
                                            anchors={
                                                'top': 'top',
                                                'left': 'left',
                                                'bottom': 'top',
                                                'right': 'left',
                                                'top_target': self,
                                                'left_target': self
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
    pass

class SubmissionPanel(UIPanel):
    pass

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
        
        self.game_panel = GamePanel()

        self.login_window = LoginWindow(self.window_size, self.ui_manager)
    
    def auto_login(self):
        ServerComm.login("yoav", "shifman")

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
    app.run()
