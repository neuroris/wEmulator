from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import Qt, QThread
from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Util import Padding, strxor
from PyQt5.QtCore import QThread
import time, re

class WookCipher:
    def __init__(self, key=None):
        self.file_name = 'D:/Project/Data/data.bin'
        self.login_id = None
        self.login_password = None
        self.account_password = None
        self.certificate_password = None
        self.raw_key = key

    def set_key(self, key):
        key_len = len(key)
        set_key = None

        if 0 < key_len < 16:
            portion = 16 // key_len
            remainder = 16 % key_len
            set_key = key * portion + key[:remainder]
        elif key_len >= 16:
            set_key = key[:16]

        return set_key

    def encrypt_data(self, login_id, login_password, account_password, certificate_password, given_key=None, file_name=None):
        plain_data = ';'.join((login_id, login_password, account_password, certificate_password))
        if file_name is not None:
            self.file_name = file_name

        # key setting
        random = Random.new()
        raw_key = given_key
        if raw_key is None:
            raw_key = self.raw_key
        set_key = self.set_key(raw_key)
        iv = random.read(AES.block_size)
        encoded_key = set_key.encode()
        key = strxor.strxor(encoded_key, iv)

        # Encryption
        encoded_data = plain_data.encode()
        padded_data = Padding.pad(encoded_data, AES.block_size)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(padded_data)

        # File writing
        with open(self.file_name, 'wb') as file:
            file.write(iv)
            file.write(encrypted_data)

    def decrypt_data(self, given_key=None, file_name=None):
        # data parsing
        if file_name is not None:
            self.file_name = file_name
        with open(self.file_name, 'rb') as file:
            iv = file.read(AES.block_size)
            encrypted_data = file.read()

        # key setting
        raw_key = given_key
        if raw_key is None:
            raw_key = self.raw_key
        set_key = self.set_key(raw_key)
        encoded_key = set_key.encode()
        key = strxor.strxor(encoded_key, iv)

        # decrypt data
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(encrypted_data)
        unpadded_data = Padding.unpad(decrypted_data, AES.block_size)
        plain_data = unpadded_data.decode()
        parsed_data = plain_data.split(';')
        self.login_id = parsed_data[0]
        self.login_password = parsed_data[1]
        self.account_password = parsed_data[2]
        self.certificate_password = parsed_data[3]

        return parsed_data

class WookLog:
    def __init__(self):
        pass

    def custom_init(self, log):
        self.debug = self.get_logger(log.debug)
        self.info = self.get_logger(log.info)
        self.warning = self.get_logger(log.warning)
        self.error = self.get_logger(log.error)
        self.critical = self.get_logger(log.critical)

    def get_logger(self, logger):
        def custom_logger(message, *args):
            message = str(message)
            message += ' %s'*len(args)
            logger(message, *args)
        return custom_logger

class WookTimer(QThread):
    def __init__(self, event_loop):
        super().__init__()
        self.time = 0
        self.event_loop = event_loop

    def sleep(self, time):
        self.time = time

    def run(self):
        for i in range(self.time):
            print('\r{}s remaining '.format(self.time-i)+'='*(self.time-i), end='')
            time.sleep(1)
        self.event_loop.exit()

class WookThreadCollector(QThread, WookLog):
    def __init__(self, kiwoom, log):
        super().__init__()
        WookLog.custom_init(self, log)
        self.kiwoom = kiwoom

    def run(self):
        while True:
            time.sleep(30)
            self.debug('~~~~~~~~~~ Inspecting threads ~~~~~~~~~~')
            if self.kiwoom.portfolio_requester.isRunning():
                self.debug('Portfolio requester is running. Collecting threads...')
                self.kiwoom.portfolio_requester.quit()

class ChartDrawer(QThread):
    def __init__(self, display_chart=None):
        super().__init__()
        self.item_code = ''
        self.display_chart = display_chart

    def set(self, display_chart):
        self.display_chart = display_chart

    def run(self):
        self.display_chart()

class wmath:
    def __init__(self):
        pass

    @classmethod
    def get_top(cls, price, interval):
        bottom = (price // interval) * interval
        top = bottom + interval
        return top

    @classmethod
    def get_bottom(cls, price, interval):
        bottom = (price // interval) * interval
        return bottom

    @classmethod
    def get_nearest_top(cls, price):
        top_price = round(cls.get_top(price, 0.05), 2)
        bottom_price = round(cls.get_bottom(price, 0.05), 2)
        if (top_price - price) <= (price - bottom_price):
            return top_price
        else:
            return bottom_price

    @classmethod
    def get_nearest_bottom(cls, price):
        top_price = round(cls.get_top(price, 0.05), 2)
        bottom_price = round(cls.get_bottom(price, 0.05), 2)
        if (top_price - price) < (price - bottom_price):
            return top_price
        else:
            return bottom_price

    @classmethod
    def get_loss_cut(cls, price, interval, loss_cut):
        cut_value = interval - loss_cut
        quotient, remainder = divmod(price - 1, interval)
        fraction = remainder / cut_value
        factor = int(fraction)
        if factor:
            factor = cut_value
        processed_price = quotient * interval + factor

        return processed_price

    @classmethod
    def custom_get_loss_cut(cls, interval, loss_cut):
        def new_get_floor(price):
            result = cls.get_floor(price, interval, loss_cut)
            return result

        return new_get_floor

    @classmethod
    def at_cut_price(cls, interval, price):
        check_result = False
        if price % interval:
            check_result = True
        return check_result

    @classmethod
    def custom_at_cut_price(cls, interval):
        def new_at_cut_price(price):
            result = cls.at_cut_price(interval, price)
            return result
        return new_at_cut_price

class WookUtil:
    def __init__(self):
        pass

    def to_min_count(self, time_text):
        time_text = time_text.replace(':', '')
        hour = int(time_text[:2])
        minute = int(time_text[2:])
        time_count = (hour - 9) * 60 + minute
        return time_count

    def to_min_count2(self, time_text):
        time_text = str(time_text)
        hour = int(time_text[:2])
        minute = int(time_text[2:4])
        time_count = (hour - 9) * 60 + minute
        return time_count

    def process_type(self, raw_data, number=False, time=False):
        data = str(raw_data)
        data = data.strip()
        data = data.replace(',', '')

        if data == '':
            if number:
                data = 0
            return data

        if time:
            time_format = data[:2] + ':' + data[2:4] + ':' + data[4:]
            return time_format

        if data[0] == '0' and len(data) == 6:
            if data[1] != '.':
                return data

        int_criteria = re.compile('([+]{0,1}|[-]{0,1})\d+$')
        if int_criteria.match(data):
            return int(data)

        float_criteria = re.compile('([+]{0,1}|[-]{0,1})\d+[.]\d+$')
        if float_criteria.match(data):
            return float(data)

        return data

    def to_time(self, data):
        time_format = data[:2] + ':' + data[2:4] + ':' + data[4:]
        return time_format

    def formalize_int(self, str_data):
        int_data = int(str_data)
        formalized_data = format(int_data, ',')
        return formalized_data

    def formalize_float(self, str_data):
        float_data = float(str_data)
        formalized_data = format(float_data, ',')
        return formalized_data

    def formalize(self, data):
        processed_data = self.process_type(data)

        try:
            formalized_data = format(processed_data, ',')
        except Exception as e:
            print('Error occurs during formalizing data', e)
            formalized_data = ''

        return formalized_data

    def to_item(self, data):
        if type(data) != str:
            item_data = self.formalize(data)
            table_item = QTableWidgetItem(item_data)
            table_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if item_data[0] == '-':
                table_item.setText(item_data[1:])
                table_item.setForeground(Qt.blue)
            else:
                table_item.setForeground(Qt.red)
        else:
            table_item = QTableWidgetItem(data)
            if data:
                if (data[0] == '-') or (data[0] == '+'):
                    table_item.setText(data[1:])
        return table_item

    def to_item_float2(self, data):
        processed_data = self.process_type(data)
        if not processed_data:
            return QTableWidgetItem(processed_data)
        elif type(processed_data) == float:
            item_data = format(processed_data, ',.2f')
        else:
            item_data = format(processed_data, ',')
        table_item = QTableWidgetItem(item_data)
        table_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if item_data[0] == '-':
            table_item.setText(item_data[1:])
            table_item.setForeground(Qt.blue)
        else:
            table_item.setForeground(Qt.red)
        return table_item

    def to_item_float3(self, data):
        processed_data = self.process_type(data)
        if not processed_data:
            return QTableWidgetItem(processed_data)
        elif type(processed_data) == float:
            item_data = format(processed_data, ',.3f')
        else:
            item_data = format(processed_data, ',')
        table_item = QTableWidgetItem(item_data)
        table_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if item_data[0] == '-':
            table_item.setText(item_data[1:])
            table_item.setForeground(Qt.blue)
        else:
            table_item.setForeground(Qt.red)
        return table_item

    def to_item_plain(self, data):
        item_data = str(data)
        table_item = QTableWidgetItem(item_data)
        table_item.setTextAlignment((Qt.AlignRight | Qt.AlignVCenter))
        return table_item

    def to_item_center(self, data):
        item_data = str(data)
        table_item = QTableWidgetItem(item_data)
        table_item.setTextAlignment((Qt.AlignCenter))
        if data == '':
            return table_item
        if (data[0] == '-') or (data[0] == '+'):
            table_item.setText(data[1:])
        return table_item

    def to_item_time(self, data):
        data = str(data)
        time_format = data[:2] + ':' + data[2:4] + ':' + data[4:]
        table_item = self.to_item(time_format)
        table_item.setTextAlignment(Qt.AlignCenter)
        return table_item

    def to_item_sign(self, data):
        item_data = data
        if type(data) != str:
            item_data = self.formalize(data)
        table_item = QTableWidgetItem(item_data)
        table_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if not item_data:
            return table_item
        elif item_data[0] == '-':
            table_item.setForeground(Qt.blue)
        else:
            table_item.setForeground(Qt.red)
        return table_item

    def to_item_gray(self, data):
        table_item = QTableWidgetItem(data)
        table_item.setForeground(Qt.darkGray)

        return table_item