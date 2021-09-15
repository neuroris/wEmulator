import copy
import pandas
from PyQt5.QtCore import QTimer
from matplotlib import ticker
from mplfinance.original_flavor import candlestick2_ohlc
from datetime import datetime
from PyQt5.QtCore import QEventLoop
from wookutil import WookUtil, WookLog, ChartDrawer, wmath
from wookitem import Item, BalanceItem, Order, Episode, AlgorithmItem
from wookdata import *
import math

class FuturesAlgorithmBase(WookUtil, WookLog):
    def __init__(self, trader, log):
        WookLog.custom_init(self, log)
        self.trader = trader
        self.log = log
        self.broker = None

        self.is_running = False
        self.episode_in_progress = False
        self.stop_loss_ordered = False
        self.settle_up_in_progress = False
        self.finish_up_in_progress = False
        self.time_off_in_progress = False
        self.trade_position = ''

        self.open_orders = 0
        self.open_correct_orders = 0
        self.open_cancel_orders = 0
        self.open_purchase_orders = 0
        self.open_sale_orders = 0
        self.open_purchase_correct_orders = 0
        self.open_sale_correct_orders = 0
        self.open_purchase_cancel_orders = 0
        self.open_sale_cancel_orders = 0
        self.cancel_purchases_ordered = False
        self.cancel_sales_ordered = False

        self.previous_situation = ''
        self.previous_msg = ()

        self.draw_chart = ChartDrawer(self.display_chart)
        self.timer = QTimer()
        self.timer.setInterval(60000)
        self.timer.timeout.connect(self.on_every_minute)
        self.chart_locator = list()
        self.chart_formatter = list()
        self.interval_prices = list()
        self.loss_cut_prices = list()
        self.top_price = 0
        self.bottom_price = 0
        self.chart_scope = 90

        self.relax_timer = QTimer()
        self.relax_time = 30000

        self.items = dict()
        self.orders = dict()
        self.open_position = Episode()
        self.close_position = Episode()
        self.long_position = Episode()
        self.short_position = Episode()
        self.episode_count = 0
        self.episode_amount = 0

        self.capital = 0
        self.interval = 0
        self.loss_cut = 0
        self.shift_interval = 0
        self.reference_price = 0.0
        self.trade_limit = 0.0
        self.loss_limit = 0
        self.minimum_transaction_amount = 0
        self.start_time_text = ''
        self.start_comment = ''
        self.start_time = 0
        self.start_price = 0
        self.total_profit = 0
        self.total_fee = 0
        self.net_profit = 0
        self.fee = 0
        self.futures_fee_ratio = 0.0
        self.futures_tax_ratio = 0.0

    def stop(self):
        if not self.is_running:
            return
        self.post('STOPPED')

        # Open Orders cancellation
        self.clear_open_orders()

        # Init Fields
        # self.broker = None
        self.is_running = False
        self.episode_in_progress = False
        self.stop_loss_ordered = False
        self.settle_up_in_progress = False
        self.finish_up_in_progress = False
        self.time_off_in_progress = False
        self.trade_position = ''

        self.open_orders = 0
        self.open_correct_orders = 0
        self.open_cancel_orders = 0
        self.open_purchase_correct_orders = 0
        self.open_purchase_cancel_orders = 0
        self.open_sale_correct_orders = 0
        self.open_sale_cancel_orders = 0

        self.previous_situation = ''
        self.previous_msg = ()

        self.timer.stop()
        self.chart_locator = list()
        self.chart_formatter = list()
        self.interval_prices = list()
        self.loss_cut_prices = list()
        self.top_price = 0
        self.bottom_price = 0
        self.chart_scope = 90

        self.relax_timer.stop()

        self.orders.clear()
        self.open_position = Episode()
        self.close_position = Episode()
        self.episode_count = 0
        self.episode_amount = 0

        self.capital = 0
        self.interval = 0
        self.loss_cut = 0
        self.shift_interval = 0
        self.reference_price = 0
        self.trade_limit = 0
        self.loss_limit = 0
        self.minimum_transaction_amount = 0
        self.start_time_text = ''
        self.start_time = 0
        self.start_price = 0
        self.total_profit = 0
        self.total_fee = 0
        self.net_profit = 0
        self.fee = 0
        self.futures_fee_ratio = 0.0
        self.futures_tax_ratio = 0.0

        # Continue Charting
        # self.trader.go_chart()

    def initialize(self, broker, capital, interval, loss_cut, fee, minimum_transaction_amount):
        for item in self.items.values():
            item.set_broker(broker)
            item.set_log(self.log)
            item.fee_ratio = fee

        self.broker = broker
        self.capital = capital
        self.interval = interval
        self.loss_cut = loss_cut
        self.shift_interval = interval
        self.fee = fee
        self.minimum_transaction_amount = minimum_transaction_amount
        self.futures_fee_ratio = self.broker.futures_fee_ratio
        self.futures_tax_ratio = self.broker.futures_tax_ratio

    def resume(self):
        self.is_running = True

    def halt(self):
        self.is_running = False

    def set_reference(self, current_price):
        if self.trade_position == LONG_POSITION:
            self.reference_price = wmath.get_top(current_price, self.interval)
            self.trade_limit = self.reference_price - self.interval
            self.loss_limit = self.trade_limit - self.loss_cut
            self.episode_amount = int(self.capital // (self.trade_limit * MULTIPLIER))
        elif self.trade_position == SHORT_POSITION:
            self.reference_price = wmath.get_bottom(current_price, self.interval)
            self.trade_limit = self.reference_price + self.interval
            self.loss_limit = self.trade_limit + self.loss_cut
            self.episode_amount = int(self.capital // (self.trade_limit * MULTIPLIER))

    def shift_reference_up(self):
        self.set_reference(self.reference_price + self.shift_interval)

    def shift_reference_down(self):
        self.set_reference(self.reference_price - self.shift_interval)

    def clear_open_orders(self):
        self.open_orders = len(self.broker.open_orders)
        open_orders = list(self.broker.open_orders.values())
        for order in open_orders:
            self.broker.cancel(order)

    def settle_up(self):
        self.post('(SETTLE UP) STARTED')
        self.settle_up_in_progress = True
        if len(self.broker.open_orders):
            self.clear_open_orders()
        else:
            self.settle_up_proper()

    def settle_up_proper(self):
        for item in self.items.values():
            if item.holding_amount:
                # self.broker.sell(item.item_code, 0, item.holding_amount, 'PRIMARY PEG')
                # self.broker.sell(item.item_code, item.ask_price, item.holding_amount, 'CONDITIONAL')
                ask_price = self.broker.monitoring_items[item.item_code].ask_price
                self.broker.sell(item.item_code, ask_price, item.holding_amount, 'MARKET')

    def finish_up(self):
        self.finish_up_in_progress = True
        if len(self.broker.open_orders):
            self.clear_open_orders()
        else:
            self.finish_up_proper()

    def finish_up_proper(self):
        for item in self.items.values():
            if item.holding_amount:
                self.broker.sell(item.item_code, 0, item.holding_amount, 'MARKET')
        self.stop()

    def add_item(self, *items):
        for item in items:
            self.items[item.item_code] = item

    def normalize_number(self, number):
        number = str(number)
        if len(number) == 1:
            number = '00' + number
        elif len(number) == 2:
            number = '0' + number
        return number

    def get_episode_number(self):
        normalized_count = self.normalize_number(self.episode_count)
        return normalized_count

    def switch_position(self):
        if self.trade_position == LONG_POSITION:
            self.trade_position = SHORT_POSITION
        elif self.trade_position == SHORT_POSITION:
            self.trade_position = LONG_POSITION

    def set_position_by(self, item):
        if item.holding_amount > 0:
            self.trade_position = LONG_POSITION
        elif item.holding_amount < 0:
            self.trade_position = SHORT_POSITION
        else:
            self.trade_position = NEUTRAL_POSITION

    def get_opposite_position(self, order_position):
        if order_position == LONG_POSITION:
            return SHORT_POSITION
        elif order_position == SHORT_POSITION:
            return LONG_POSITION
        else:
            return NEUTRAL_POSITION

    def switch_order_position(self, order):
        if order.order_position == PURCHASE:
            order.order_position = SELL
        elif order.order_position == SELL:
            order.order_position = PURCHASE

    def process_past_chart_prices(self, item_code, chart_prices):
        columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        past_chart = pandas.DataFrame(chart_prices, columns=columns)
        past_chart.Time = pandas.to_datetime(past_chart.Time)
        past_chart.set_index('Time', inplace=True)

        item = self.items[item_code]
        # item.chart = past_chart.append(item.chart)
        item.chart = past_chart

        self.customize_past_chart(item)
        self.draw_chart.start()

    def update_chart_prices(self, item_code, price, volume):
        current_time = datetime.now().replace(second=0, microsecond=0)
        item = self.items[item_code]
        chart = item.chart
        if not len(chart):
            chart.loc[current_time] = price
            chart.loc[current_time, 'Volume'] = volume
        elif current_time > chart.index[-1]:
            chart.loc[current_time] = price
            chart.loc[current_time, 'Volume'] = volume
        else:
            if price > chart.High[-1]:
                chart.loc[current_time, 'High'] = price
            elif price < chart.Low[-1]:
                chart.loc[current_time, 'Low'] = price
            last_price = chart.Close[-1]
            chart.loc[current_time, 'Close'] = price
            chart.loc[current_time, 'Volume'] += volume
            if last_price == price:
                return

        self.update_custom_chart(item)
        self.draw_chart.start()

    def on_every_minute(self):
        current_time = datetime.now().replace(second=0, microsecond=0)
        for item in self.items.values():
            if not len(item.chart):
                continue
            if current_time > item.chart.index[-1]:
                price = item.chart.Close[-1]
                item.chart.loc[current_time] = price
                item.chart.loc[current_time, 'Volume'] = 0
                self.update_custom_chart(item)
        self.draw_chart.start()

    def time_off(self):
        self.time_off_in_progress = True
        self.relax_timer.setInterval(self.relax_time)
        self.relax_timer.setSingleShot(True)
        self.relax_timer.timeout.connect(self.time_up)
        self.relax_timer.start()

    def time_up(self):
        self.time_off_in_progress = False

    def customize_past_chart(self, item):
        # Override virtual function
        pass

    def update_custom_chart(self, item):
        # Override virtual function
        pass

    def display_chart(self):
        # Override virtual function
        pass

    def post(self, *args):
        self.debug('\033[93mALGORITHM', *args, '\033[97m')

    def post_cyan(self, *args):
        if args != self.previous_msg:
            self.debug('\033[96mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_green(self, *args):
        if args != self.previous_msg:
            self.debug('\033[92mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_blue(self, *args):
        if args != self.previous_msg:
            self.debug('\033[94mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_red(self, *args):
        if args != self.previous_msg:
            self.debug('\033[91mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_magenta(self, *args):
        if args != self.previous_msg:
            self.debug('\033[95mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_white(self, *args):
        if args != self.previous_msg:
            self.debug('\033[97mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def display_situation(self, current_situation):
        if current_situation != self.previous_situation:
            self.post_without_repetition(current_situation)
            self.previous_situation = current_situation

    def post_without_repetition(self, *args):
        if args != self.previous_msg:
            self.debug('\033[93mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_white_without_repetition(self, *args):
        if args != self.previous_msg:
            self.debug('\033[97m', *args, '\033[97m')
            self.previous_msg = args
