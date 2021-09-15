import copy
from datetime import datetime
from PyQt5.QtCore import QEventLoop
from wookutil import WookUtil, WookLog, wmath
from wookitem import Item, BalanceItem, Order, AlgorithmItem
from wookdata import *


class Algorithm1(WookUtil, WookLog):
    def __init__(self, log):
        WookLog.custom_init(self, log)

        self.leverage = None
        self.balance_item = None
        self.broker = None
        self.signal = None
        self.orders = dict()
        self.log = log

        self.is_running = False
        self.capital = 0
        self.interval = 0
        self.loss_cut = 0
        self.start_time_text = ''
        self.start_time = 0
        self.start_price = 0
        self.reference_price = 0
        self.buy_limit = 0
        self.loss_limit = 0
        self.sell_off_ordered = False

        self.previous_situation = ''
        self.previous_msg = ()

    def start(self, broker, capital, interval, loss_cut):
        # self.leverage = AlgorithmItem('122630')
        self.leverage = AlgorithmItem('252670')
        self.leverage.set_broker(broker)
        self.leverage.set_log(self.log)
        self.balance_item = BalanceItem()
        self.broker = broker
        self.capital = capital
        self.interval = interval
        self.loss_cut = loss_cut
        self.is_running = True

        # Charting & Monitoring
        broker.go_chart(self.leverage.item_code)
        broker.demand_monitoring_items_info(self.leverage)

        # Open Orders cancellation
        for order in broker.open_orders.values():
            self.broker.cancel(order)

    def stop(self):
        if not self.is_running:
            return

        # Open Orders cancellation
        for order in self.broker.open_orders.values():
            self.broker.cancel(order)

        # Init Fields
        self.orders.clear()
        self.broker = None
        self.leverage = None
        self.balance_item = None
        self.is_running = False
        self.capital = 0
        self.interval = 0
        self.loss_cut = 0
        self.start_time_text = ''
        self.start_time = 0
        self.start_price = 0
        self.reference_price = 0
        self.buy_limit = 0
        self.loss_limit = 0
        self.sell_off_ordered = False
        self.previous_situation = ''
        self.previous_msg = ()

    def resume(self):
        self.is_running = True

    def halt(self):
        self.is_running = False

    def set_reference(self, price):
        self.reference_price = price
        self.buy_limit = self.reference_price - self.interval
        self.loss_limit = self.buy_limit - self.loss_cut

    def shift_reference_up(self):
        self.set_reference(self.reference_price + self.interval)

    def shift_reference_down(self):
        self.set_reference(self.reference_price - self.interval)

    def update_transaction_info(self, item):
        # First time work
        if not self.start_price:
            self.start_time_text = datetime.now().strftime('%H:%M')
            self.start_time = self.to_min_count(self.start_time_text)
            self.start_price = item.current_price
            reference_price = wmath.get_bottom(item.current_price, self.interval)
            self.set_reference(reference_price)
            self.leverage.buy(self.buy_limit, self.capital // item.current_price)
            return

        # Trade
        if self.sell_off_ordered:
            msg = ('sale.ordered:' + str(self.leverage.episode_sale.ordered), 'open_amount:' + str(self.leverage.episode_sale.open_amount))
            self.post('(SELL_OFF)', *msg)
            if self.leverage.episode_sale.ordered or self.leverage.episode_sale.open_amount:
                return
            self.sell_off_ordered = False

        if item.current_price >= self.reference_price + self.interval:
            self.display_situation('Situation 1')
            self.shift_reference_up()
            self.leverage.correct_purchase(self.buy_limit)
        elif item.current_price >= self.buy_limit + self.loss_cut:
            self.display_situation('Situation 2')
            self.leverage.sell_out(self.reference_price)
        elif item.current_price <= self.loss_limit:
            self.display_situation('Situation 4')
            self.sell_off_ordered = True
            self.leverage.sell_off_deprecated()
            self.shift_reference_down()
        elif item.current_price <= self.reference_price - self.loss_cut:
            self.display_situation('Situation 3')
            self.leverage.buy_up()

    def update_execution_info(self, order):
        # Leverage update execution
        self.leverage.update_execution_info(order)

        # Buy after sale completed
        if order.order_position in (SELL, CORRECT_SELL) and order.order_state == ORDER_EXECUTED:
            self.signal('total_profit')
            if not order.open_amount and not self.leverage.episode_purchase.open_amount:
                self.leverage.buy_over(self.buy_limit, self.capital // order.current_price)

        # Order history
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.orders[order.order_number] = order
        elif order.order_position in (SELL, CORRECT_SELL):
            self.orders[order.order_number] = order

        if order.order_position in (CORRECT_PURCHASE, CORRECT_SELL) and order.order_state == CONFIRMED:
            del self.orders[order.original_order_number]
        elif order.order_position in (CANCEL_PURCHASE, CANCEL_SELL) and order.order_state == CONFIRMED:
            original_order = self.orders[order.original_order_number]
            if not original_order.executed_amount_sum:
                del self.orders[order.original_order_number]

    def update_balance_info(self, item):
        self.balance_item = item

    def display_situation(self, current_situation):
        if current_situation != self.previous_situation:
            self.post(current_situation)
            self.previous_situation = current_situation

    def post(self, *args):
        if args != self.previous_msg:
            self.debug('\033[93mALGORITHM', *args, '\033[97m')
            self.previous_msg = args
