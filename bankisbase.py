from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop, QThread, QTimer
from queue import Queue
import time
from wookutil import WookCipher, WookLog, WookTimer, WookUtil, ChartDrawer
from wookdata import *

class BankisBase(QAxWidget, WookLog, WookUtil):
    def __init__(self, log, key):
        super().__init__('KHOPENAPI.KHOpenAPICtrl.1')
        WookLog.custom_init(self, log)
        WookUtil.__init__(self)

        # Password
        wc = WookCipher(key)
        wc.decrypt_data()
        self.login_id = wc.login_id
        self.login_password = wc.login_password
        self.account_password = wc.account_password
        self.certificate_password = wc.certificate_password

        # Eventloop
        self.login_event_loop = QEventLoop()
        self.event_loop = QEventLoop()
        self.timer_event_loop = QEventLoop()
        self.wook_timer = WookTimer(self.timer_event_loop)

        # Chart
        self.draw_chart = ChartDrawer()
        self.chart_prices = list()
        self.min_timer = QTimer()
        self.min_timer.setInterval(60000)
        self.min_timer.timeout.connect(self.on_every_min)

        # Requesters
        self.deposit_requester = QThread()
        self.moveToThread(self.deposit_requester)
        self.deposit_requester.started.connect(self.request_deposit_info)
        self.portfolio_requester = QThread()
        self.moveToThread(self.portfolio_requester)
        self.portfolio_requester.started.connect(self.request_portfolio_info)
        self.order_history_requester = QThread()
        self.moveToThread(self.order_history_requester)
        self.order_history_requester.started.connect(self.request_order_history)

        self.request_time = 0
        self.request_interval_limit = 0.5
        self.order_position = ''

        # Signals
        self.log = None
        self.signal = None
        self.status = None

        # Deposit
        self.account_list = None
        self.account_number = 0
        self.deposit = 0
        self.withdrawable_money = 0
        self.orderable_money = 0

        # Items and Orders
        self.portfolio = dict()
        self.monitoring_items = dict()
        self.balance = dict()
        self.open_orders = dict()
        self.order_history = dict()
        self.algorithm = None

        # Pending order
        self.pending_order = None
        self.cancel_confirmed = False
        self.cancel_order_number = 0

        # Request limit
        self.inquiry_count = 0
        self.previous_time = 0.0
        self.reference_time = Queue()
        self.reference_time_interval_limit = 20
        self.consecutive_interval_limit = 0.25
        self.request_block_time_limit = 5
        self.request_block_size = 10
        self.request_count = 0
        self.request_count_threshold = 90
        self.request_count_interval = 60
        self.request_count_waiting = 30

        # Fee and Tax
        self.fee_ratio = 0.0035
        self.tax_ratio = 0.0023

        # Screen numbers
        self.screen_account = '0010'
        self.screen_open_order = '0020'
        self.screen_operation_state = '0040'
        self.screen_portfolio = '0060'
        self.screen_send_order = '0080'
        self.screen_stock_price = '0120'
        self.screen_futures_stock_price = '0140'
        self.screen_test = '9999'

    def dynamic_call(self, function_name, *args):
        function_spec = '('
        for order in range(len(args)):
            parameter = 'parameter_' + str(order)
            function_spec += parameter
            if order < len(args) - 1:
                function_spec += ', '
        function_spec += ')'
        function_spec = function_name + function_spec
        args = list(args)
        result = self.dynamicCall(function_spec, args)
        return result

    def set_input_value(self, item, value):
        self.dynamicCall('SetInputValue(str, str)', item, value)

    def comm_rq_data(self, sRQName, sTrCode, sPrevNext, sScreenNo):
        # self.check_time_rule()
        result = self.dynamicCall('CommRqData(str, str, int, str)', sRQName, sTrCode, sPrevNext, sScreenNo)
        if result != 0:
            print('Something is wrong during request : {}, Error code : {}'.format(sRQName, result))

    def get_comm_data(self, sTrCode, sRQName, nIndex, strItemName):
        result = self.dynamicCall('GetCommData(str, str, int, str)', sTrCode, sRQName, nIndex, strItemName)
        processed_result = self.process_type(result)
        return processed_result

    def get_comm_data_ex(self, sTrCode, sRQName):
        result = self.dynamic_call('GetCommDataEx', sTrCode, sRQName)
        return result

    def new_get_comm_data(self, *precedent_args):
        def custom_get_comm_data(*args):
            new_args = precedent_args + args
            result = self.get_comm_data(*new_args)
            return result
        return custom_get_comm_data

    def get_repeat_count(self, sTrCode, sRQName):
        repeat_count = self.dynamic_call('GetRepeatCnt', sTrCode, sRQName)
        return repeat_count

    def set_real_reg(self, strScreenNo, strCodeList, strFidList, strOptType='1'):
        self.dynamic_call('SetRealReg', strScreenNo, strCodeList, strFidList, strOptType)

    def get_comm_real_data(self, sCode, fid, time=False):
        result = self.dynamic_call('GetCommRealData', sCode, fid)
        processed_result = self.process_type(result, time)
        return processed_result

    def new_get_comm_real_data(self, *precedent_args):
        def custom_get_comm_real_data(*args):
            new_args = precedent_args + args
            result = self.get_comm_real_data(*new_args)
            return result
        return custom_get_comm_real_data

    def send_order(self, sRQName, sScreenNo, sAccNo, nOrderType, sCode, nQty, nPrice, sHogaGb, sOrgOrderNo=''):
        self.check_time_rule()
        result = self.dynamic_call('SendOrder', sRQName, sScreenNo, sAccNo, nOrderType, sCode, nQty, nPrice, sHogaGb, sOrgOrderNo)
        return result

    def new_send_order(self, *precedent_args):
        def custom_send_order(*args):
            new_args = precedent_args + args
            result = self.send_order(*new_args)
            return result
        return custom_send_order

    def send_order_fo(self, sRQName, sScreenNo, sAccNo, sCode, IOrdKind, sSlbyTp, sOrdTp, IQty, sPrice, sOrgOrderNo=''):
        self.check_time_rule()
        result = self.dynamic_call('SendOrderFO', sRQName, sScreenNo, sAccNo, sCode, IOrdKind, sSlbyTp, sOrdTp, IQty, sPrice, sOrgOrderNo)
        return result

    def new_send_order_fo(self, *precedent_args):
        def custom_send_order(*args):
            new_args = precedent_args + args
            result = self.send_order_fo(*new_args)
            return result

        return custom_send_order

    def get_chejan_data(self, nFid, number=False):
        result = self.dynamic_call('GetChejanData', nFid)
        processed_result = self.process_type(result, number)
        return processed_result

    def get_item_name(self, item_code):
        item_name = self.dynamic_call('GetMasterCodeName()', str(item_code))
        return item_name

    def get_item_code(self, item_name):
        item_code = ''
        for key, value in CODES.items():
            if item_name == value:
                item_code = key
        return item_code

    def check_time_rule(self):
        # consecutive 28 request is blocked in 5 times a sec
        # consecutive 100 request is blocked in 4 times a sec
        # every 25 request, 10 sec waiting is required optimally
        time_interval = time.time() - self.previous_time
        if time_interval < self.consecutive_interval_limit:
            waiting_time = self.consecutive_interval_limit - time_interval
            time.sleep(waiting_time)

        if self.reference_time.qsize() == self.request_block_size:
            reference_time = self.reference_time.get()
        else:
            reference_time = 0
        reference_time_interval = time.time() - reference_time

        if reference_time_interval < self.request_block_time_limit:
            waiting_time = self.request_block_time_limit - reference_time_interval
            self.info('now waiting {}s... for request block interval'.format(waiting_time))
            time.sleep(waiting_time)

        if self.request_count >= self.request_count_threshold:
            if reference_time_interval < self.reference_time_interval_limit:
                if (self.request_count - self.request_count_threshold) % self.request_count_interval == 0:
                    print('now waiting {}s... for request count over {}'.format(self.request_count_waiting,
                                                                                self.request_count))
                    # self.sleep(self.request_count_waiting)

        self.request_count += 1
        current_time = time.time()
        self.previous_time = current_time
        self.reference_time.put(current_time)

    def sleep(self, time):
        self.wook_timer.sleep(time)
        self.wook_timer.start()
        self.timer_event_loop.exec()