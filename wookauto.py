from PyQt5.QtCore import QEventLoop, QThread
import warnings, sys, time
warnings.simplefilter('ignore', UserWarning)
sys.coinit_flags = 2
import pywinauto
from pywinauto.application import Application

class LoginPasswordThread(QThread):
    def __init__(self, event_loop, login_id, login_password, certificate_password):
        super().__init__()
        self.event_loop = event_loop
        self.login_id = login_id
        self.login_password = login_password
        self.certificate_password = certificate_password

    def login_app_connectable(self):
        app = Application(backend='win32')
        count = 0
        while count < 10:
            try:
                app.connect(title='Open API Login')
                print('Login app is connected')
                return True
            except:
                count += 1
                print('Login app is not yet connectable ... trial({})'.format(count))
                time.sleep(1)

        print('Login app connection failed')
        return False

    def run(self):
        app = Application(backend='win32')
        if not self.login_app_connectable():
            sys.exit()

        app.connect(title='Open API Login')
        dlg = app.window(title='Open API Login')

        # dlg.Edit1.get_focus()
        # dlg.Edit1.type_keys(self.login_id)
        dlg.Edit2.get_focus()
        dlg.Edit2.type_keys(self.login_password)
        # dlg.Edit3.get_focus()
        # dlg.Edit3.type_keys(self.certificate_password)

        dlg.Button1.click_input()
        self.event_loop.exit()

class AccountPasswordThread(QThread):
    def __init__(self, event_loop, account_password):
        super().__init__()
        self.event_loop = event_loop
        self.account_password = account_password

    def run(self):
        tool_app = Application(backend='uia')
        tool_app.connect(class_name='Shell_TrayWnd')
        tool_dlg = tool_app.window(class_name='Shell_TrayWnd')
        notify_dlg = tool_dlg.window(title='알림 펼침')
        notify_dlg.click_input()
        notify_dlg.click_input()
        notify_dlg.click_input()
        popup_dlg = tool_app.top_window()
        rect = popup_dlg.rectangle()
        row = int(rect.height() / 40)
        column = int(rect.width() / 40)
        ox = rect.left + 20
        oy = rect.top + 20
        for y in range(row):
            for x in range(column):
                pywinauto.mouse.move((ox + x * 40, oy + y * 40))

        kiwoom_dlg = popup_dlg.window(title='서버와 통신이 연결 되었습니다..')
        kiwoom_dlg.right_click_input()

        pywinauto.keyboard.send_keys('{DOWN}')
        pywinauto.keyboard.send_keys('{ENTER}')

        password_app = Application(backend='win32')
        password_app.connect(title_re='계좌비밀번호.*')
        password_dlg = password_app.window(title_re='계좌비밀번호.*')
        password_edit_dlg = password_dlg.window(class_name='Edit')
        password_edit_dlg.set_focus()
        password_edit_dlg.type_keys(self.account_password)
        password_reg_dlg = password_dlg.window(title='등록')
        password_reg_dlg.click_input()
        password_dlg.window(title='닫기').click_input()
        self.event_loop.exit()