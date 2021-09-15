from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import QObject, QThread
import pandas
from datetime import datetime
import time, math
from bankisbase import BankisBase
from wookauto import LoginPasswordThread, AccountPasswordThread
from wookitem import Item, BalanceItem, Order
from wookdata import *

class Bankis(BankisBase):
    def __init__(self, log, key):
        super().__init__(log, key)
        self.info('Bankis initializing...')

        # Connect slots
        self.OnEventConnect.connect(self.on_login)
        self.OnReceiveTrData.connect(self.on_receive_tr_data)
        self.OnReceiveRealData.connect(self.on_receive_real_data)
        self.OnReceiveChejanData.connect(self.on_receive_chejan_data)
        self.OnReceiveMsg.connect(self.on_receive_msg)
        self.OnReceiveConditionVer.connect(self.on_receive_condition_ver)

        self.demand_market_state_info()

    def auto_login(self):
        self.dynamicCall('CommConnect()')
        self.login_event_loop.exec()

    def login(self):
        self.dynamicCall("CommConnect()")
        log_passwd_thread = LoginPasswordThread(self.event_loop, self.login_id, self.login_password, self.certificate_password)
        log_passwd_thread.start()
        self.event_loop.exec()
        self.login_event_loop.exec()

    def set_account_password(self):
        acc_psword_thread = AccountPasswordThread(self.event_loop, self.account_password)
        acc_psword_thread.start()
        self.event_loop.exec()
        # self.KOA_Functions('ShowAccountWindow', '')

    def get_account_list(self):
        account_list = self.dynamic_call('GetLoginInfo()', 'ACCLIST')
        self.account_list = account_list.split(';')
        self.account_list.pop()
        if self.account_list is None:
            self.info('Failed to get account information')
        else:
            self.info('Account information')
        return self.account_list

    def request_deposit_info(self, sPrevNext='0'):
        self.check_request_time()
        self.set_input_value(ACCOUNT_NUMBER, self.account_number)
        self.set_input_value(PASSWORD, self.account_password)
        self.set_input_value(PASSWORD_MEDIA_TYPE, '00')
        self.set_input_value(INQUIRY_TYPE, '1')
        self.comm_rq_data('deposit', REQUEST_DEPOSIT_INFO, sPrevNext, self.screen_account)

    def request_portfolio_info(self, sPrevNext='0'):
        self.check_request_time()
        self.set_input_value(ACCOUNT_NUMBER, self.account_number)
        self.set_input_value(PASSWORD, self.account_password)
        self.set_input_value(PASSWORD_MEDIA_TYPE, '00')
        self.set_input_value(INQUIRY_TYPE, '1')
        self.comm_rq_data('portfolio', REQUEST_PORTFOLIO_INFO, sPrevNext, self.screen_portfolio)

    def request_order_history(self, item_code='', sPrevNext='0'):
        self.check_request_time()
        self.set_input_value(ACCOUNT_NUMBER, self.account_number)
        self.set_input_value(ALL_OR_INDIVIDUAL, ALL)
        self.set_input_value(TRADE_POSITION, POSITION.ALL)
        self.set_input_value(ITEM_CODE, item_code)
        self.set_input_value(ORDER_EXECUTION_TYPE, ORDER.ALL)
        self.comm_rq_data('order history', REQUEST_OPEN_ORDER, sPrevNext, self.screen_open_order)

    def request_stock_price_min(self, item_code, sPrevNext='0'):
        self.check_request_time()
        self.set_input_value(ITEM_CODE, item_code)
        self.set_input_value(TICK_RANGE, MIN_1)
        self.set_input_value(CORRECTED_PRICE_TYPE, '1')
        self.comm_rq_data('stock price min', REQUEST_MINUTE_PRICE, sPrevNext, self.screen_stock_price)

    def request_futures_stock_price_min(self, item_code, sPrevNext='0'):
        self.set_input_value(ITEM_CODE, item_code)
        self.set_input_value(TIME_UNIT, MIN_1)
        self.comm_rq_data('future min', REQUEST_FUTURE_MIN, sPrevNext, self.screen_futures_stock_price)

    def demand_market_state_info(self):
        self.set_real_reg(self.screen_operation_state, ' ', FID.MARKET_OPERATION_STATE, '0')

    def demand_monitoring_items_info(self, item):
        self.monitoring_items[item.item_code] = item
        self.set_real_reg(item.item_code, item.item_code, FID.TRANSACTION_TIME, '1')

    def order(self, item_code, price, amount, order_position, order_type, order_number=''):
        if order_type == 'MARKET':
            price = 0
        self.order_position = order_position
        order_position_code = ORDER_POSITION_DICT[order_position]
        order_type_code = ORDER_TYPE[order_type]
        if item_code[:3] == FUTURES_CODE:
            trade_position = FUTURES_TRADE_POSITION[order_position]
            send_order = self.new_send_order_fo('order', self.screen_send_order, self.account_number)
            send_order(item_code, order_position_code, trade_position, order_type_code, amount, price, order_number)
        else:
            send_order = self.new_send_order('order', self.screen_send_order, self.account_number)
            send_order(order_position_code, item_code, amount, price, order_type_code, order_number)

    def on_login(self, err_code):
        if err_code == 0:
            self.log('Bankis log in success')
        else:
            self.log('Something is wrong during log-in')
            self.error('Login error', err_code)

        self.login_event_loop.exit()

    def on_receive_msg(self, sScrNo, sRQName, sTrCode, sMsg):
        self.inquiry_count += 1
        current_time = datetime.now().strftime('%H:%M:%S')
        self.status(sMsg, sRQName, current_time, '('+str(self.inquiry_count)+')')

    def on_receive_tr_data(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):
        # self.debug('tr_data', sScrNo, sRQName, sTrCode)
        if sRQName == 'deposit':
            self.get_deposit_info(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'portfolio':
            self.get_portfolio_info(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'order':
            self.get_order_state(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'order history':
            self.get_order_history(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'stock price min':
            self.get_stock_price_min(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'future min':
            self.get_futures_stock_price_min(sTrCode, sRecordName, sScrNo, sPrevNext)

    def on_receive_real_data(self, sCode, sRealType, sRealData):
        # self.debug('real_data', sCode, sRealType, sRealData)
        if sRealType == REAL_TYPE_MARKET_OPENING_TIME:
            self.update_market_state(sCode)
        elif sRealType == REAL_TYPE_STOCK_TRADED:
            self.update_monitoring_items(sCode)
        elif sRealType == REAL_TYPE_FUTURES_TRADED:
            self.update_futures_trading_items(sCode)

    def on_receive_chejan_data(self, sGubun, nItemCnt, nFidList):
        # self.debug('chejan', sGubun, nItemCnt, nFidList)
        if sGubun == CHEJAN_EXECUTED_ORDER:
            self.obtain_executed_order_info()
        elif sGubun == CHEJAN_BALANCE:
            self.obtain_balance_info()

    def get_deposit_info(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, 0)
        self.deposit = get_comm_data(DEPOSIT)
        self.withdrawable = get_comm_data(WITHDRAWABLE)
        self.orderable_money = get_comm_data(ORDERABLE)

        self.signal('deposit')
        self.info('Deposit information')
        self.init_screen(sScrNo)
        # self.deposit_requester.quit()

    def get_portfolio_info(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        number_of_item = self.get_repeat_count(sTrCode, sRecordName)
        for count in range(number_of_item):
            get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, count)

            item = Item()
            item.item_code = get_comm_data(ITEM_NUMBER)[1:]
            item.item_name = get_comm_data(ITEM_NAME)
            item.current_price = get_comm_data(CURRENT_PRICE)
            item.purchase_price = get_comm_data(PURCHASE_PRICE)
            item.holding_amount = get_comm_data(HOLDING_AMOUNT)
            item.purchase_sum = get_comm_data(PURCHASE_SUM)
            item.evaluation_sum = get_comm_data(EVALUATION_SUM)
            item.total_fee = get_comm_data(TOTAL_FEE)
            item.tax = get_comm_data(TAX)
            item.profit = get_comm_data(PROFIT)
            item.profit_rate = get_comm_data(PROFIT_RATE)
            self.portfolio[item.item_code] = item

        if sPrevNext == '2':
            self.request_portfolio_info(sPrevNext)
        else:
            # portfolio_sum = Item()
            # portfolio_sum.item_code = '000000'
            # portfolio_sum.item_name = 'Account Total'
            # self.portfolio[portfolio_sum.item_code] = portfolio_sum
            # self.update_portfolio_sum()
            self.signal('portfolio')
            self.signal('portfolio_table')
            self.info('Portfolio information')
            self.init_screen(sScrNo)
            # self.portfolio_requester.quit()

    def get_order_history(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        number_of_order = self.get_repeat_count(sTrCode, sRecordName)
        for count in range(number_of_order):
            get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, count)

            order = Order()
            order.item_code = str(get_comm_data(ITEM_CODE))
            order.item_name = get_comm_data(ITEM_NAME)
            order.executed_time = get_comm_data(TIME)
            order.order_amount = get_comm_data(ORDER_AMOUNT)
            order.executed_amount_sum = get_comm_data(EXECUTED_ORDER_AMOUNT)
            order.open_amount = get_comm_data(OPEN_AMOUNT)
            order.order_number = get_comm_data(ORDER_NUMBER)
            order.original_order_number = get_comm_data(ORIGINAL_ORDER_NUMBER)
            order.order_price = get_comm_data(ORDER_PRICE)
            order.executed_price_avg = get_comm_data(EXECUTED_ORDER_PRICE)
            order.order_position = get_comm_data(ORDER_POSITION)
            order.order_state = get_comm_data(ORDER_STATE)
            # order.trade_position = get_comm_data(TRADE_POSITION)
            # order.executed_order_number = get_comm_data(EXECUTED_ORDER_NUMBER)

            self.order_history[order.order_number] = order
            if order.open_amount != 0:
                self.open_orders[order.order_number] = order

        if sPrevNext == '2':
            self.request_order_history(sPrevNext)
        else:
            self.signal('order_history_table')
            self.signal('open_orders_table')
            self.info('Order history information')
            self.init_screen(sScrNo)
            # self.order_history_requester.quit()

    def get_stock_price_min(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        number_of_item = self.get_repeat_count(sTrCode, sRecordName)
        today = int(datetime.today().strftime('%Y%m%d'))
        item_code = self.get_comm_data(sTrCode, sRecordName, 0, ITEM_CODE)
        self.chart_prices.clear()

        for count in range(number_of_item):
            get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, count)
            transaction_time = str(get_comm_data(TRANSACTION_TIME))
            current_date = int(transaction_time[:8])

            if current_date < today:
                self.chart_prices.reverse()
                self.draw_chart.start()
                self.init_screen(sScrNo)
                return

            open_price = int(abs(get_comm_data(OPEN_PRICE)))
            high_price = int(abs(get_comm_data(HIGH_PRICE)))
            low_price = int(abs(get_comm_data(LOW_PRICE)))
            current_price = int(abs(get_comm_data(CURRENT_PRICE)))
            volume = int(abs(get_comm_data(VOLUME)))

            data = [transaction_time, open_price, high_price, low_price, current_price, volume]
            self.chart_prices.append(data)

        if sPrevNext == '2':
            self.request_stock_price_min(item_code, sPrevNext)

    def get_futures_stock_price_min(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        number_of_item = self.get_repeat_count(sTrCode, sRecordName)
        today = int(datetime.today().strftime('%Y%m%d'))
        item_code = self.get_comm_data(sTrCode, sRecordName, 0, ITEM_CODE)
        self.chart_prices.clear()

        for count in range(number_of_item):
            get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, count)
            transaction_time = str(get_comm_data(TRANSACTION_TIME))
            current_date = int(transaction_time[:8])

            if current_date < today:
                self.chart_prices.reverse()
                self.draw_chart.start()
                self.init_screen(sScrNo)
                return

            open_price = float(abs(get_comm_data(OPEN_PRICE)))
            high_price = float(abs(get_comm_data(HIGH_PRICE)))
            low_price = float(abs(get_comm_data(LOW_PRICE)))
            current_price = float(abs(get_comm_data(CURRENT_PRICE)))
            volume = int(abs(get_comm_data(VOLUME)))

            data = [transaction_time, open_price, high_price, low_price, current_price, volume]
            self.chart_prices.append(data)

        if sPrevNext == '2':
            self.request_futures_stock_price_min(item_code, sPrevNext)

    def get_order_state(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        get_comm_data = self.new_get_comm_data(sTrCode, sRecordName)
        order_number = get_comm_data(0, ORDER_NUMBER)
        if order_number:
            self.info('Send order ({}) command committed successfully'.format(self.order_position), sTrCode)
        else:
            self.info('Send order failed.', 'Please check order variables')

    def update_market_state(self, sCode):
        operation_state = self.get_comm_real_data(sCode, FID.MARKET_OPERATION_STATE)
        present_time = self.get_comm_real_data(sCode, FID.TRANSACTION_TIME, time=True)
        remaining_time = self.get_comm_real_data(sCode, FID.MARKET_OPERATION_REMAINING_TIME, time=True)
        self.info('market operation state', operation_state, present_time, remaining_time)

    def update_monitoring_items(self, item_code):
        item = self.monitoring_items[item_code]
        get_comm_real_data = self.new_get_comm_real_data(item_code)

        item.transaction_time = get_comm_real_data(FID.TRANSACTION_TIME)
        item.current_price = abs(get_comm_real_data(FID.CURRENT_PRICE))
        item.price_increase_amount = get_comm_real_data(FID.PRICE_INCREASE_AMOUNT)
        item.ask_price = get_comm_real_data(FID.ASK_PRICE)
        item.bid_price = get_comm_real_data(FID.BID_PRICE)
        item.volume = get_comm_real_data(FID.VOLUME)
        item.accumulated_volume = get_comm_real_data(FID.ACCUMULATED_VOLUME)
        item.high_price = get_comm_real_data(FID.HIGH_PRICE)
        item.low_price = get_comm_real_data(FID.LOW_PRICE)
        item.open_price = get_comm_real_data(FID.OPEN_PRICE)
        # item.price_increase_ratio = get_comm_real_data(FID.PRICE_INCREASE_RATIO)
        self.signal('monitoring_items_table')

        if self.algorithm.is_running:
            self.algorithm.market_status(item)

        if item_code in self.portfolio:
            portfolio_item = self.portfolio[item_code]
            if portfolio_item.current_price != item.current_price:
                self.update_portfolio_info(item)

        if item_code == self.draw_chart.item_code:
            self.update_chart_prices(item.current_price, item.volume)

    def update_futures_trading_items(self, item_code):
        item = self.monitoring_items[item_code]
        get_comm_real_data = self.new_get_comm_real_data(item_code)

        item.transaction_time = get_comm_real_data(FID.TRANSACTION_TIME)
        item.current_price = get_comm_real_data(FID.CURRENT_PRICE)
        item.price_increase_amount = get_comm_real_data(FID.PRICE_INCREASE_AMOUNT)
        item.ask_price = get_comm_real_data(FID.ASK_PRICE)
        item.bid_price = get_comm_real_data(FID.BID_PRICE)
        item.volume = get_comm_real_data(FID.VOLUME)
        item.accumulated_volume = get_comm_real_data(FID.ACCUMULATED_VOLUME)
        item.high_price = get_comm_real_data(FID.HIGH_PRICE)
        item.low_price = get_comm_real_data(FID.LOW_PRICE)
        item.open_price = get_comm_real_data(FID.OPEN_PRICE)
        # item.price_increase_ratio = get_comm_real_data(FID.PRICE_INCREASE_RATIO)

        self.signal('monitoring_items_table')

        if item.current_price < 0:
            item.current_price = item.current_price * -1

        if item_code in self.portfolio:
            portfolio_item = self.portfolio[item_code]
            if portfolio_item.current_price != item.current_price:
                self.update_portfolio_info(item)

        if item_code == self.draw_chart.item_code:
            self.update_chart_prices(item.current_price, item.volume)

    def update_deposit_info(self, order):
        orderable_increment = abs(order.executed_price * order.executed_amount)
        if order.order_position == SELL:
            sell_cost = math.ceil(orderable_increment * (self.fee_ratio + self.tax_ratio))
            self.orderable_money += orderable_increment - sell_cost
        else:
            self.orderable_money -= orderable_increment

        self.signal('deposit')

    # def update_portfolio_sum(self):
    #     portfolio_sum = self.portfolio['000000']
    #     portfolio_sum.purchase_sum = 0
    #     portfolio_sum.evaluation_sum = 0
    #     portfolio_sum.total_fee = 0
    #     portfolio_sum.tax = 0
    #     portfolio_sum.profit = 0
    #
    #     for item in self.portfolio.values():
    #         if item.item_code == '000000':
    #             continue
    #         portfolio_sum.purchase_sum += item.purchase_sum
    #         portfolio_sum.evaluation_sum += item.evaluation_sum
    #         portfolio_sum.total_fee += item.total_fee
    #         portfolio_sum.tax += item.tax
    #         portfolio_sum.profit += item.profit
    #
    #     portfolio_sum.profit_rate = round(portfolio_sum.profit / portfolio_sum.purchase_sum * 100, 2)

    def update_portfolio_info(self, updated_item):
        item = self.portfolio[updated_item.item_code]

        item.current_price = updated_item.current_price
        item.evaluation_sum = item.current_price * item.holding_amount
        item.purchase_fee = int(item.purchase_sum * self.fee_ratio / 10) * 10
        item.evaluation_fee = int(item.evaluation_sum * self.fee_ratio / 10) * 10
        item.total_fee = item.purchase_fee + item.evaluation_fee
        item.tax = int(item.evaluation_sum * self.tax_ratio)
        calculated_purchase_sum = item.purchase_price * item.holding_amount
        item.profit = item.evaluation_sum - calculated_purchase_sum - item.total_fee - item.tax
        item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)

        self.signal('portfolio_table')

    def update_portfolio(self, order):
        if order.item_code not in self.portfolio:
            self.portfolio[order.item_code] = order
        item = self.portfolio[order.item_code]

        order_position = order.order_position
        if order_position == SELL:
            order.executed_amount = -abs(order.executed_amount)

        purchase_price = item.purchase_sum / item.holding_amount
        item.current_price = order.current_price
        item.holding_amount += order.executed_amount
        item.evaluation_sum = order.current_price * item.holding_amount

        if order_position == PURCHASE:
            item.purchase_sum += order.executed_price * order.executed_amount
            item.purchase_price = int(item.purchase_sum / item.holding_amount)
        else:
            item.purchase_sum += int(purchase_price * order.executed_amount)

        item.purchase_fee = int(item.purchase_sum * self.fee_ratio / 10) * 10
        item.evaluation_fee = int(item.evaluation_sum * self.fee_ratio / 10) * 10
        item.total_fee = item.purchase_fee + item.evaluation_fee
        item.tax = int(item.evaluation_sum * self.tax_ratio)
        calculated_purchase_sum = item.purchase_price * item.holding_amount
        item.profit = item.evaluation_sum - calculated_purchase_sum - item.total_fee - item.tax
        item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)

        self.signal('portfolio_table')

    def update_chart_prices(self, price, volume):
        current_time = datetime.now().strftime('%Y%m%d%H%M')
        if not self.chart_prices:
            price_data = [current_time, price, price, price, price, volume]
            self.chart_prices.append(price_data)
        elif current_time != self.chart_prices[-1][TIME_]:
            price_data = [current_time, price, price, price, price, volume]
            self.chart_prices.append(price_data)
        else:
            if price > self.chart_prices[-1][HIGH]:
                self.chart_prices[-1][HIGH] = price
            elif price < self.chart_prices[-1][LOW]:
                self.chart_prices[-1][LOW] = price
            last_price = self.chart_prices[-1][CLOSE]
            self.chart_prices[-1][CLOSE] = price
            self.chart_prices[-1][VOLUME_] += volume
            if last_price == price:
                return

        self.draw_chart.start()

    def obtain_executed_order_info(self):
        order = Order()
        order.item_code = self.get_chejan_data(FID.ITEM_CODE)[1:]
        order.item_name = self.get_item_name(order.item_code)
        order.executed_time = self.get_chejan_data(FID.ORDER_EXECUTED_TIME)
        order.order_amount = self.get_chejan_data(FID.ORDER_AMOUNT, number=True)
        order.executed_amount = self.get_chejan_data(FID.UNIT_EXECUTED_AMOUNT, number=True)
        order.executed_amount_sum = self.get_chejan_data(FID.EXECUTED_AMOUNT, number=True)
        order.open_amount = self.get_chejan_data(FID.OPEN_AMOUNT, number=True)
        order.order_number = self.get_chejan_data(FID.ORDER_NUMBER)
        order.original_order_number = self.get_chejan_data(FID.ORIGINAL_ORDER_NUMBER)
        order.executed_order_number = self.get_chejan_data(FID.EXECUTED_ORDER_NUMBER)
        order.order_price = self.get_chejan_data(FID.ORDER_PRICE, number=True)
        order.executed_price = self.get_chejan_data(FID.UNIT_EXECUTED_PRICE, number=True)
        order.executed_price_avg = self.get_chejan_data(FID.EXECUTED_PRICE, number=True)
        # order.order_position = self.get_chejan_data(FID.ORDER_POSITION)[-2:]
        order.order_position = self.get_chejan_data(FID.ORDER_POSITION)
        order.current_price = abs(self.get_chejan_data(FID.CURRENT_PRICE, number=True))

        order.order_state = self.get_chejan_data(FID.ORDER_STATE)
        order.order_type = self.get_chejan_data(FID.ORDER_POSITION)
        order.transaction_type = self.get_chejan_data(FID.TRANSACTION_TYPE)
        order.transaction_price = self.get_chejan_data(FID.EXECUTED_PRICE, number=True)
        # order.volume = self.get_chejan_data(FID.VOLUME, number=True)
        # order.transaction_fee = self.get_chejan_data(FID.TRANSACTION_FEE, number=True)
        # order.tax = self.get_chejan_data(FID.TRANSACTION_TAX, number=True)

        self.update_execution_info(order)

    def update_execution_info(self, order):
        # Algorithm Trading Update
        if self.algorithm.is_running:
            self.algorithm.update_execution_info(order)
            self.signal('algorithm_trading_table')

        # Order History Update
        self.order_history[order.order_number] = order
        self.signal('order_history_table')

        # Open Orders Update
        self.open_orders[order.order_number] = order
        if (order.order_number in self.open_orders) and (order.open_amount == 0):
            del self.open_orders[order.order_number]
        self.signal('open_orders_table')

        # Portfolio, Deposit Update
        if order.order_state == ORDER_EXECUTED:
            if order.order_position[-2:] in (PURCHASE, SELL):
                self.update_portfolio(order)
                self.update_deposit_info(order)

        # Log messege
        message = 'Order execution({}) {}({}), '.format(order.order_position, order.item_name, order.order_state)
        message += 'order:{}, executed:{}, '.format(order.order_amount, order.executed_amount_sum)
        message += 'order number:{}, original number:{}'.format(order.order_number, order.original_order_number)

        message += order.order_position + str(order.open_amount)

        self.log(message)

        # Pending order
        if self.pending_order:
            if order.order_position[-2:] == CANCEL and order.order_state == CONFIRMED:
                self.cancel_confirmed = True
            if order.order_number == self.cancel_order_number and self.cancel_confirmed:
                self.pending_order()
                self.pending_order = None
                self.cancel_confirmed = False

    def obtain_balance_info(self):
        item = BalanceItem()
        item.item_code = self.get_chejan_data(FID.ITEM_CODE)[1:]
        item.item_name = self.get_chejan_data(FID.ITEM_NAME)
        item.current_price = self.get_chejan_data(FID.CURRENT_PRICE)
        item.reference_price = self.get_chejan_data(FID.REFERENCE_PRICE)
        item.purchase_price_avg = self.get_chejan_data(FID.PURCHASE_PRICE_AVG)
        item.holding_amount = self.get_chejan_data(FID.HOLDING_AMOUNT)
        item.purchase_amount_net_today = self.get_chejan_data(FID.PURCHASE_AMOUNT_NET_TODAY)
        item.purchase_sum = self.get_chejan_data(FID.PURCHASE_SUM)
        BalanceItem.balance_profit_net_today = self.get_chejan_data(FID.PROFIT_NET_TODAY)
        BalanceItem.balance_profit_rate = self.get_chejan_data(FID.PROFIT_RATE)
        BalanceItem.balance_profit_realization = self.get_chejan_data(FID.PROFIT_REALIZATION)
        # item.balance_profit_realization_rate = self.get_chejan_data(FID.PROFIT_REALIZATION_RATE)
        # item.buy_or_sell = self.get_chejan_data(FID.BUY_OR_SELL)
        # item.deposit = self.get_chejan_data(FID.DEPOSIT)

        if self.algorithm.is_running:
            self.algorithm.update_balance_info(item)

        self.balance[item.item_code] = item
        self.signal('balance_table')
        self.info('Balance information')

    def go_chart(self, item_code):
        self.draw_chart.item_code = item_code
        if item_code[:3] == FUTURES_CODE:
            self.request_futures_stock_price_min(item_code)
        else:
            self.request_stock_price_min(item_code)
        self.min_timer.start()

    def stop_chart(self):
        item_name = CODES[self.draw_chart.item_code]
        self.draw_chart.item_code = ''
        self.min_timer.stop()
        self.info('Stop Charting', item_name)

    def buy(self, item_code, price, amount, order_type='LIMIT', order_number=''):
        order_position = 'BUY'
        self.order(item_code, price, amount, order_position, order_type, order_number)

    def sell(self, item_code, price, amount, order_type='LIMIT', order_number=''):
        order_position = 'SELL'
        self.order(item_code, price, amount, order_position, order_type, order_number)

    def correct(self, order, price, amount=None):
        order_position = 'CORRECT BUY'
        if order.order_position == SELL:
            order_position = 'CORRECT SELL'
        order_type = 'LIMIT'
        if amount is None:
            amount = order.open_amount
        self.order(order.item_code, price, amount, order_position, order_type, order.order_number)

    def cancel(self, order, amount=None):
        order_position = 'CANCEL BUY'
        if order.order_position == SELL:
            order_position = 'CANCEL SELL'
        order_type = 'LIMIT'
        if amount is None:
            amount = order.open_amount
        self.cancel_order_number = order.order_number
        self.order(order.item_code, order.order_price, amount, order_position, order_type, order.order_number)

    def cancel_and_buy(self, order, price, amount, order_type='LIMIT'):
        item_code = order.item_code
        order_position = 'BUY'
        self.cancel(order)
        self.pending_order = self.new_order(item_code, price, amount, order_position, order_type)

    def cancel_and_sell(self, order, price, amount, order_type='LIMIT'):
        item_code = order.item_code
        order_position = 'SELL'
        self.cancel(order)
        self.pending_order = self.new_order(item_code, price, amount, order_position, order_type)

    def new_order(self, item_code, price, amount, order_position, order_type, order_number=''):
        def custom_order():
            self.order(item_code, price, amount, order_position, order_type, order_number)
        return custom_order

    def on_every_min(self):
        current_time = datetime.now().strftime('%Y%m%d%H%M')
        if not self.chart_prices:
            return
        if current_time != self.chart_prices[-1][TIME_]:
            price = self.chart_prices[-1][CLOSE]
            data = [current_time, price, price, price, price, 0]
            self.chart_prices.append(data)
            self.draw_chart.start()

    def check_request_time(self):
        current_time = time.time()
        interval = current_time - self.request_time
        waiting_time = self.request_interval_limit - interval
        if interval < self.request_interval_limit:
            time.sleep(waiting_time)
        self.request_time = time.time()

    def init_screen(self, sScrNo):
        self.dynamic_call('DisconnectRealData', sScrNo)
        # self.debug('Screen reset', sScrNo)

    def on_receive_condition_ver(self, IRet, sMsg):
        self.debug('receive condition ver', IRet, sMsg)

    def close_process(self):
        self.dynamic_call('SetRealRemove', 'ALL', 'ALL')
        self.log('All screens are disconnected')