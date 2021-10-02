import pandas
import numpy as np
from datetime import datetime
import time, math, copy
from kiwoombase import KiwoomBase
from wookauto import LoginPasswordThread, AccountPasswordThread
from wookitem import Item, BalanceItem, FuturesItem, Order
from wookdata import *

class Kiwoom(KiwoomBase):
    def __init__(self, trader, log, key):
        super().__init__(trader, log, key)
        self.info('Kiwoom initializing...')

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

    def request_futures_deposit_info(self, sPrevNext='0'):
        self.check_request_time()
        self.set_input_value(ACCOUNT_NUMBER, self.account_number)
        self.set_input_value(PASSWORD, self.account_password)
        self.set_input_value(PASSWORD_MEDIA_TYPE, '00')
        self.comm_rq_data('deposit', REQUEST_FUTURES_DEPOSIT_INFO, sPrevNext, self.screen_account)

    def request_portfolio_info(self, sPrevNext='0'):
        self.check_request_time()
        self.set_input_value(ACCOUNT_NUMBER, self.account_number)
        self.set_input_value(PASSWORD, self.account_password)
        self.set_input_value(PASSWORD_MEDIA_TYPE, '00')
        self.set_input_value(INQUIRY_TYPE, '1')
        self.comm_rq_data('portfolio', REQUEST_PORTFOLIO_INFO, sPrevNext, self.screen_portfolio)

    def request_futures_portfolio_info(self, sPrevNext='0'):
        self.check_request_time()
        self.set_input_value(ACCOUNT_NUMBER, self.account_number)
        self.set_input_value(PASSWORD, self.account_password)
        self.set_input_value(INQUIRY_TYPE, datetime.now().strftime('%Y%m%d'))
        self.set_input_value(PASSWORD_MEDIA_TYPE, '00')
        self.comm_rq_data('futures portfolio', REQUEST_FUTURES_PORTFOLIO_INFO, sPrevNext, self.screen_portfolio)

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
        self.check_request_time()
        self.chart_item_code = item_code
        self.set_input_value(ITEM_CODE, item_code)
        self.set_input_value(TIME_UNIT, MIN_1)
        self.comm_rq_data('futures min', REQUEST_FUTURE_MIN, sPrevNext, self.screen_futures_stock_price)

    def demand_market_state_info(self):
        self.set_real_reg(self.screen_operation_state, ' ', FID.MARKET_OPERATION_STATE, '0')

    def demand_monitoring_items_info(self, item):
        self.monitoring_items[item.item_code] = item
        self.item_code = item.item_code
        # self.set_real_reg(item.item_code, item.item_code, FID.TRANSACTION_TIME, '1')

    def order(self, item_code, price, amount, order_position, order_type, order_number=''):
        if order_type == 'MARKET':
            price = 0
        self.order_position = order_position
        if item_code[:3] == FUTURES_CODE:
            order_position_code = FUTURES_ORDER_POSITION[order_position]
            trade_position = FUTURES_TRADE_POSITION[order_position]
            order_type_code = FUTURES_ORDER_TYPE[order_type]
            send_order = self.new_send_order_fo('order', self.screen_send_order, self.account_number)
            send_order(item_code, order_position_code, trade_position, order_type_code, amount, price, order_number)
        else:
            order_type_code = ORDER_TYPE[order_type]
            order_position_code = ORDER_POSITION_DICT[order_position]
            send_order = self.new_send_order('order', self.screen_send_order, self.account_number)
            send_order(order_position_code, item_code, amount, price, order_type_code, order_number)

        # For debug
        # self.order_variables = (price, amount, order_position, order_type, order_number)
        self.order_report.order_price = price
        self.order_report.order_amount = amount
        self.order_report.order_position = ORDER_POSITION_DICT2[order_position]
        self.order_report.order_type = order_type
        self.order_report.order_number = order_number

    def on_login(self, err_code):
        if err_code == 0:
            self.trader.log('Kiwoom log in success')
        else:
            self.trader.log('Something is wrong during log-in')
            self.error('Login error', err_code)

        self.login_event_loop.exit()

    def on_receive_msg(self, sScrNo, sRQName, sTrCode, sMsg):
        self.inquiry_count += 1
        current_time = datetime.now().strftime('%H:%M:%S')
        self.trader.status(sMsg, sRQName, current_time, '('+str(self.inquiry_count)+')')

    def on_receive_tr_data(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):
        if sRQName == 'deposit':
            self.get_deposit_info(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'portfolio':
            self.get_portfolio_info(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'futures portfolio':
            self.get_futures_portfolio_info(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'order':
            self.get_order_state(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'order history':
            self.get_order_history(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'stock price min':
            self.get_stock_price_min(sTrCode, sRecordName, sScrNo, sPrevNext)
        elif sRQName == 'futures min':
            self.get_futures_stock_price_min(sTrCode, sRecordName, sScrNo, sPrevNext)

    def on_receive_real_data(self, sCode, sRealType, sRealData):
        if sRealType == REAL_TYPE_MARKET_OPENING_TIME:
            self.update_market_state(sCode)
        elif sRealType == REAL_TYPE_STOCK_TRADED:
            self.update_monitoring_items(sCode)
        elif sRealType == REAL_TYPE_FUTURES_TRADED:
            # self.update_futures_trading_items(sCode)
            self.update_monitoring_items(sCode)

    def on_receive_chejan_data(self, sGubun, nItemCnt, nFidList):
        if sGubun == CHEJAN_EXECUTED_ORDER:
            self.obtain_executed_order_info()
        elif sGubun == CHEJAN_BALANCE:
            self.obtain_balance_info()
        elif sGubun == CHEJAN_FUTURES_BALANCE:
            self.obtain_balance_info()

    def get_deposit_info(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, 0)
        if self.trader.running_futures_account():
            self.deposit = get_comm_data(FUTURES_DEPOSIT)
            self.withdrawable = get_comm_data(FUTURES_WITHDRAWABLE)
            self.orderable_money = get_comm_data(FUTURES_ORDERABLE)
            self.info('Deposit information (Futures)')
        else:
            self.deposit = get_comm_data(DEPOSIT)
            self.withdrawable = get_comm_data(WITHDRAWABLE)
            self.orderable_money = get_comm_data(ORDERABLE)
            self.info('Deposit information')

        self.trader.update_deposit_info()
        self.init_screen(sScrNo)

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

            if number_of_item:
                self.trader.update_order_variables()
                self.trader.display_portfolio()
                self.info('Portfolio information')
            else:
                self.info('Portfolio information (No item found)')
            self.init_screen(sScrNo)

    def get_futures_portfolio_info(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        portfolio_copy = copy.deepcopy(self.portfolio)
        for item_code in portfolio_copy:
            if item_code[:3] == FUTURES_CODE:
                del self.portfolio[item_code]

        number_of_item = self.get_repeat_count(sTrCode, sRecordName)
        for count in range(number_of_item):
            get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, count)

            item = Item()
            item.item_code = get_comm_data(ITEM_CODE)
            if not item.item_code:
                self.info('Portfolio information (NO ITEM)')
                return
            # item.item_name = get_comm_data(ITEM_NAME)[9:]
            item.item_name = get_comm_data(ITEM_NAME)
            item.trade_position = get_comm_data(TRADE_POSITION)
            item.holding_amount = get_comm_data(BALANCE_AMOUNT)
            item.purchase_price = get_comm_data(PURCHASE_UNIT_PRICE) / 100
            item.purchase_sum = get_comm_data(TRANSACTION_SUM)
            item.current_price = get_comm_data(CURRENT_PRICE) / 100
            item.profit = get_comm_data(EVALUATION_PROFIT)
            item.profit_rate = get_comm_data(EVALUATION_PROFIT_RATE)
            item.evaluation_sum = get_comm_data(EVALUATION_SUM)
            item.purchase_fee = item.purchase_sum * self.futures_fee_ratio
            item.evaluation_fee = item.evaluation_sum * self.futures_fee_ratio
            item.total_fee = int((item.purchase_fee + item.evaluation_fee) / 10) * 10
            item.tax = self.get_tax(item)
            item.profit -= item.total_fee
            item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)
            # calculated_purchase_sum = int(item.purchase_price * abs(item.holding_amount) * MULTIPLIER)
            # item.profit = item.evaluation_sum - calculated_purchase_sum - item.total_fee - item.tax
            # item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)

            if item.trade_position == SELL[1:]:
                item.holding_amount = -item.holding_amount

            # item_debug = copy.deepcopy(item)
            # item_debug.item_name = str(count)
            # self.portfolio[count] = item_debug

            # Check item is in portfolio
            if item.item_code in self.portfolio:
                futures_item = self.portfolio[item.item_code]
            else:
                futures_item = FuturesItem(item, self)
                self.portfolio[item.item_code] = futures_item
            futures_item.append(item)

        if sPrevNext == '2':
            self.request_portfolio_info(sPrevNext)
        else:
            # portfolio_sum = Item()
            # portfolio_sum.item_code = '000000'
            # portfolio_sum.item_name = 'Account Total'
            # self.portfolio[portfolio_sum.item_code] = portfolio_sum
            # self.update_portfolio_sum()
            if number_of_item:
                self.trader.update_order_variables()
                self.trader.display_portfolio()
                self.info('Portfolio information (Futures)')
            else:
                self.info('Portfolio information (Futures) (No item found)')
            self.init_screen(sScrNo)

    def get_order_history(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        number_of_order = self.get_repeat_count(sTrCode, sRecordName)
        if sPrevNext == '0':
            self.order_history.clear()

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

            self.order_history[order.order_number] = order
            if order.open_amount != 0:
                self.open_orders[order.order_number] = order

        if sPrevNext == '2':
            self.request_order_history('', sPrevNext)
        else:
            self.trader.display_order_history()
            self.trader.display_open_orders()
            self.info('Order history information')
            self.init_screen(sScrNo)

    def get_stock_price_min(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        number_of_item = self.get_repeat_count(sTrCode, sRecordName)
        today = int(datetime.today().strftime('%Y%m%d'))
        item_code = self.get_comm_data(sTrCode, sRecordName, 0, ITEM_CODE)
        for count in range(number_of_item):
            get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, count)
            transaction_time = str(get_comm_data(TRANSACTION_TIME))
            current_date = int(transaction_time[:8])

            if current_date < today:
                self.trader.process_past_chart_prices(str(item_code), self.chart_prices)
                self.init_screen(sScrNo)
                return

            open_price = int(abs(get_comm_data(OPEN_PRICE)))
            high_price = int(abs(get_comm_data(HIGH_PRICE)))
            low_price = int(abs(get_comm_data(LOW_PRICE)))
            current_price = int(abs(get_comm_data(CURRENT_PRICE)))
            volume = int(abs(get_comm_data(VOLUME)))
            data = [transaction_time, open_price, high_price, low_price, current_price, volume]
            self.chart_prices.insert(0, data)

        if sPrevNext == '2':
            self.request_stock_price_min(item_code, sPrevNext)

    def get_futures_stock_price_min(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        number_of_item = self.get_repeat_count(sTrCode, sRecordName)
        today = int(datetime.today().strftime('%Y%m%d'))
        for count in range(number_of_item):
            get_comm_data = self.new_get_comm_data(sTrCode, sRecordName, count)
            transaction_time = str(get_comm_data(TRANSACTION_TIME))
            current_date = int(transaction_time[:8])

            if current_date < today:
                self.trader.process_past_chart_prices(self.chart_item_code, self.chart_prices)
                self.init_screen(sScrNo)
                return

            open_price = float(abs(get_comm_data(OPEN_PRICE)))
            high_price = float(abs(get_comm_data(HIGH_PRICE)))
            low_price = float(abs(get_comm_data(LOW_PRICE)))
            current_price = float(abs(get_comm_data(CURRENT_PRICE)))
            volume = int(abs(get_comm_data(VOLUME)))
            data = [transaction_time, open_price, high_price, low_price, current_price, volume]
            self.chart_prices.insert(0, data)

        if sPrevNext == '2':
            self.request_futures_stock_price_min(self.chart_item_code, sPrevNext)

    def get_order_state(self, sTrCode, sRecordName, sScrNo, sPrevNext):
        get_comm_data = self.new_get_comm_data(sTrCode, sRecordName)
        order_number = get_comm_data(0, ORDER_NUMBER)
        if order_number:
            self.info('Send order ({}) command committed successfully'.format(self.order_position), sTrCode)
            if self.trader.algorithm.is_running:
                self.trader.algorithm.report_success_order(self.order_report)
        else:
            self.report_fail_order()
            if self.trader.algorithm.is_running:
                self.trader.algorithm.report_fail_order(self.order_report)

    def update_market_state(self, sCode):
        operation_state = self.get_comm_real_data(sCode, FID.MARKET_OPERATION_STATE)
        present_time = self.get_comm_real_data(sCode, FID.TRANSACTION_TIME, time=True)
        remaining_time = self.get_comm_real_data(sCode, FID.MARKET_OPERATION_REMAINING_TIME, time=True)
        self.info('market operation state', operation_state, present_time, remaining_time)

    def update_monitoring_items(self, item_code=None):
        item_code = item_code if item_code else self.item_code
        item = self.monitoring_items[item_code]

        item.transaction_time = str(self.prices.Time[self.index])[8:]
        item.current_price = self.prices.Close[self.index]
        item.ask_price = item.current_price + 0.05
        item.bid_price = item.current_price - 0.05
        item.volume = self.prices.Volume[self.index]
        item.high_price = self.prices.High[self.index]
        item.low_price = self.prices.Low[self.index]
        item.open_price = self.prices.Open[self.index]
        item.accumulated_volume += item.volume

        self.index += 1

        self.trader.display_monitoring_items()

        if self.trader.algorithm.is_running:
            self.trader.algorithm.market_status(item)
        elif self.is_running_chart:
            self.trader.update_chart_prices(item.current_price, item.volume, item_code)

        if item_code in self.portfolio:
            portfolio_item = self.portfolio[item_code]
            if portfolio_item.current_price != item.current_price:
                if item_code[:3] == FUTURES_CODE:
                    self.update_futures_portfolio_info(item)
                else:
                    self.update_portfolio_info(item)

    def update_deposit_info(self, order):
        orderable_increment = int(abs(order.executed_price * order.executed_amount))
        if order.order_position == SELL:
            sell_cost = int(math.ceil(orderable_increment * (self.fee_ratio + self.tax_ratio)))
            self.orderable_money += orderable_increment - sell_cost
        else:
            self.orderable_money -= orderable_increment
        self.trader.update_deposit_info()

    def update_portfolio_info(self, updated_item):
        item = self.portfolio[updated_item.item_code]
        item.current_price = updated_item.current_price
        item.evaluation_sum = int(item.current_price * abs(item.holding_amount))
        item.purchase_fee = int((item.purchase_sum * self.fee_ratio) / 10) * 10
        item.evaluation_fee = int((item.evaluation_sum * self.fee_ratio) / 10) * 10
        item.total_fee = item.purchase_fee + item.evaluation_fee
        item.tax = self.get_tax(item)
        calculated_purchase_sum = int(item.purchase_price * abs(item.holding_amount))
        item.profit = item.evaluation_sum - calculated_purchase_sum - item.total_fee - item.tax
        item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)
        self.trader.display_portfolio()

    def update_futures_portfolio_info(self, updated_item):
        futures_item = self.portfolio[updated_item.item_code]
        futures_item.current_price = updated_item.current_price
        futures_item.evaluation_sum = int(futures_item.current_price * abs(futures_item.holding_amount) * MULTIPLIER)
        futures_item.evaluation_fee = futures_item.evaluation_sum * self.futures_fee_ratio
        futures_item.total_fee = int((futures_item.purchase_fee + futures_item.evaluation_fee) / 10) * 10
        futures_item.tax = self.get_tax(futures_item)
        futures_item.profit = (futures_item.evaluation_sum - futures_item.purchase_sum) * np.sign(futures_item.holding_amount)
        futures_item.profit = futures_item.profit - futures_item.total_fee - futures_item.tax
        futures_item.profit_rate = round(futures_item.profit / futures_item.purchase_sum * 100, 2)

        for contract in futures_item.contracts:
            contract.current_price = updated_item.current_price
            contract.evaluation_sum = int(contract.current_price * abs(contract.holding_amount) * MULTIPLIER)
            contract.evaluation_fee = contract.evaluation_sum * self.futures_fee_ratio
            contract.total_fee = int((contract.purchase_fee + contract.evaluation_fee) / 10) * 10
            contract.tax = self.get_tax(contract)
            contract.profit = (contract.evaluation_sum - contract.purchase_sum) * np.sign(contract.holding_amount)
            contract.profit = contract.profit - contract.total_fee - contract.tax
            contract.profit_rate = round(contract.profit / contract.purchase_sum * 100, 2)

        self.trader.display_portfolio()

    def update_portfolio(self, order):
        if order.item_code not in self.portfolio:
            order = copy.deepcopy(order)
            self.portfolio[order.item_code] = order
        item = self.portfolio[order.item_code]

        if order.order_position in (SELL, CORRECT_SELL):
            order.executed_amount = -abs(order.executed_amount)
        item.current_price = order.current_price
        item.holding_amount += order.executed_amount
        item.evaluation_sum = int(order.current_price * abs(item.holding_amount) )

        if not item.holding_amount:
            del self.portfolio[order.item_code]
            self.trader.display_portfolio()
            return

        # Purchase or Sell
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            item.purchase_sum += int(order.executed_price * order.executed_amount)
            item.purchase_price = int(item.purchase_sum / abs(item.holding_amount))
        else:
            purchase_price_exact = item.purchase_sum / abs(item.holding_amount - order.executed_amount)
            item.purchase_sum += int(purchase_price_exact * abs(order.executed_amount))

        item.purchase_fee = int(item.purchase_sum * self.fee_ratio / 10) * 10
        item.evaluation_fee = int(item.evaluation_sum * self.fee_ratio / 10) * 10
        item.total_fee = item.purchase_fee + item.evaluation_fee
        item.tax = self.get_tax(item)
        calculated_purchase_sum = int(item.purchase_price * abs(item.holding_amount))
        item.profit = item.evaluation_sum - calculated_purchase_sum - item.total_fee - item.tax
        item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)
        self.trader.display_portfolio()

    def update_futures_portfolio(self, order):
        if order.item_code not in self.portfolio:
            futures_item = FuturesItem(order, self)
            self.portfolio[order.item_code] = futures_item
        futures_item = self.portfolio[order.item_code]

        holding_amount = futures_item.holding_amount + order.executed_amount
        if not holding_amount:
            del self.portfolio[order.item_code]
            self.trader.display_portfolio()
            return

        # Futures entry or settlement
        if futures_item.holding_amount * order.executed_amount >= 0:
            futures_item.add(order)
        else:
            working_order = copy.deepcopy(order)
            contracts = copy.deepcopy(futures_item.contracts)
            for individual_contract in contracts:
                if abs(individual_contract.holding_amount) <= abs(working_order.executed_amount):
                    futures_item.pop()
                    working_order.executed_amount += individual_contract.holding_amount
                else:
                    futures_item.settle(working_order)
                    working_order.executed_amount = 0
                if not working_order.executed_amount:
                    break
            if working_order.executed_amount:
                futures_item.add(working_order)

        futures_item.update(order.current_price)
        self.trader.display_portfolio()

    def obtain_executed_order_info(self):
        order = Order()
        order.item_code = self.get_chejan_data(FID.ITEM_CODE)
        if order.item_code[0] == 'A':
            order.item_code = order.item_code[1:]
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
        order.order_position = self.get_chejan_data(FID.ORDER_POSITION)
        order.current_price = abs(self.get_chejan_data(FID.CURRENT_PRICE, number=True))
        order.order_state = self.get_chejan_data(FID.ORDER_STATE)
        order.order_type = self.get_chejan_data(FID.ORDER_POSITION)
        order.transaction_type = self.get_chejan_data(FID.TRANSACTION_TYPE)
        order.transaction_price = self.get_chejan_data(FID.EXECUTED_PRICE, number=True)
        # order.volume = self.get_chejan_data(FID.VOLUME, number=True)
        # order.transaction_fee = self.get_chejan_data(FID.TRANSACTION_FEE, number=True)
        # order.tax = self.get_chejan_data(FID.TRANSACTION_TAX, number=True)
        if order.order_position in (SELL, CORRECT_SELL):
            order.executed_amount = -abs(order.executed_amount)

        self.update_execution_info(order)

    def update_execution_info(self, order):
        # Log message
        message = 'Order execution({}) {}({}), '.format(order.order_position, order.item_name, order.order_state)
        message += 'order:{}, executed_sum:{}, '.format(order.order_amount, order.executed_amount_sum)
        message += 'open:{}, price:{}, '.format(order.open_amount, order.order_price)
        message += 'number:{}, original:{}'.format(order.order_number, order.original_order_number)
        self.trader.log(message)

        # Algorithm Trading Update
        if self.trader.algorithm.is_running:
            if order.order_number != self.previous_order.original_order_number:
                self.trader.algorithm.update_execution_info(order)
            self.previous_order = order

        # Pending order
        if self.pending_order:
            if order.order_position[-2:] == CANCEL and order.order_state == CONFIRMED:
                self.cancel_confirmed = True
            if order.order_number == self.cancel_order_number and self.cancel_confirmed:
                self.pending_order()
                self.pending_order = None
                self.cancel_confirmed = False

        # Portfolio, Deposit Update
        # if order.order_state == ORDER_EXECUTED:
        if order.executed_amount:
            if order.order_position in (PURCHASE, CORRECT_PURCHASE, SELL, CORRECT_SELL):
                self.update_deposit_info(order)
                if order.item_code[:3] == FUTURES_CODE:
                    self.update_futures_portfolio(order)
                else:
                    self.update_portfolio(order)

        # Open Orders Update
        self.open_orders[order.order_number] = order
        if (order.order_number in self.open_orders) and (order.open_amount == 0):
            del self.open_orders[order.order_number]
        self.trader.display_open_orders()

        # Order History Update
        self.order_history[order.order_number] = order
        self.trader.display_order_history()

    def obtain_balance_info(self):
        item = BalanceItem()
        item.item_code = self.get_chejan_data(FID.ITEM_CODE)
        item.item_name = self.get_chejan_data(FID.ITEM_NAME)
        item.current_price = self.get_chejan_data(FID.CURRENT_PRICE)
        item.reference_price = self.get_chejan_data(FID.REFERENCE_PRICE)
        item.purchase_price_avg = round(self.get_chejan_data(FID.PURCHASE_PRICE_AVG), 2)
        item.holding_amount = self.get_chejan_data(FID.HOLDING_AMOUNT)
        item.purchase_amount_net_today = self.get_chejan_data(FID.PURCHASE_AMOUNT_NET_TODAY)
        item.purchase_sum = int(self.get_chejan_data(FID.PURCHASE_SUM))
        BalanceItem.balance_profit_net_today = self.get_chejan_data(FID.PROFIT_NET_TODAY)
        BalanceItem.balance_profit_rate = self.get_chejan_data(FID.PROFIT_RATE)
        BalanceItem.balance_profit_realization = self.get_chejan_data(FID.PROFIT_REALIZATION)
        if item.item_code[:3] != FUTURES_CODE:
            item.item_code = item.item_code[1:]

        self.balance[item.item_code] = item
        self.trader.display_balance()
        self.info('Balance information')

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
        if order.order_position in SELL_EQUIVALENT:
            order_position = 'CANCEL SELL'
        order_type = 'LIMIT'
        if amount is None:
            amount = order.open_amount
        self.cancel_order_number = order.order_number
        self.order(order.item_code, order.order_price, amount, order_position, order_type, order.order_number)

    def cancel_and_buy(self, order, price, amount=None, order_type='LIMIT'):
        item_code = order.item_code
        order_position = 'BUY'
        if amount is None:
            amount = order.order_amount
        self.cancel(order)
        self.pending_order = self.new_order(item_code, price, amount, order_position, order_type)

    def cancel_and_sell(self, order, price, amount, order_type='LIMIT'):
        item_code = order.item_code
        order_position = 'SELL'
        self.cancel(order)
        self.pending_order = self.new_order(item_code, price, amount, order_position, order_type)

    def settle_up(self):
        for item in self.portfolio.values():
            if item.holding_amount > 0:
                self.sell(item.item_code, 0, item.holding_amount, 'MARKET')
            elif item.holding_amount < 0:
                self.buy(item.item_code, 0, abs(item.holding_amount), 'MARKET')

    def new_order(self, item_code, price, amount, order_position, order_type, order_number=''):
        def custom_order():
            self.order(item_code, price, amount, order_position, order_type, order_number)
        return custom_order

    def check_request_time(self):
        current_time = time.time()
        interval = current_time - self.request_time
        waiting_time = self.request_interval_limit - interval
        if interval < self.request_interval_limit:
            time.sleep(waiting_time)
        self.request_time = time.time()

    def get_stock_prices(self):
        file_name = './20210813.csv'
        self.prices = pandas.read_csv(file_name)

    def init_screen(self, sScrNo):
        self.dynamic_call('DisconnectRealData', sScrNo)

    def on_receive_condition_ver(self, IRet, sMsg):
        self.debug('receive condition ver', IRet, sMsg)

    def close_process(self):
        self.dynamic_call('SetRealRemove', 'ALL', 'ALL')
        self.trader.log('All screens are disconnected')