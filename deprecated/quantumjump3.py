from datetime import datetime
from wookitem import Order, AlgorithmItem
from wookdata import *
from wookalgorithm.algorithmbase import AlgorithmBase

'''
Quantum algorithm (2021, 03, 06)

Discrete price algorithm using inverse only
1. Overlapping interval
2. Correct order price when stock price get out of interval range
3. Only trade over threshold amount (min_amount)
3. purchase, sale dictionaries
'''

class QuantumJumpAlgorithm3(AlgorithmBase):
    def __init__(self, log):
        super().__init__(log)
        self.log = log
        self.reference_price = 0
        self.buy_limit = 0
        self.loss_limit = 0
        self.situation_processing = False
        self.inverse = None
        self.episode_purchase = Order()
        self.episode_sale = Order()

    def start(self, broker, capital, interval, loss_cut, fee, minimum_transaction_amount):
        self.inverse = AlgorithmItem('252670')
        self.inverse.set_broker(broker)
        self.inverse.set_log(self.log)
        self.inverse.fee_ratio = fee
        self.broker = broker
        self.capital = capital
        self.interval = interval
        self.loss_cut = loss_cut
        self.fee = fee
        self.minimum_transaction_amount = minimum_transaction_amount
        self.is_running = True

        # Charting & Monitoring
        broker.go_chart(self.inverse.item_code)
        broker.demand_monitoring_items_info(self.inverse)

        # Open Orders cancellation
        open_orders = list(broker.open_orders.values())
        for order in open_orders:
            self.broker.cancel(order)

        self.post('STARTED')

    def stop(self):
        if not self.is_running:
            return

        self.post('STOPPED')

        # Open Orders cancellation
        open_orders = list(self.broker.open_orders.values())
        for order in open_orders:
            self.broker.cancel(order)

        # Init Fields
        self.orders.clear()
        self.broker = None
        self.inverse = None
        self.is_running = False
        self.capital = 0
        self.interval = 0
        self.loss_cut = 0
        self.fee = 0
        self.minimum_transaction_amount = 0
        self.total_profit = 0
        self.net_profit = 0
        self.start_time_text = ''
        self.start_time = 0
        self.start_price = 0
        self.reference_price = 0
        self.buy_limit = 0
        self.loss_limit = 0
        self.situation_processing = False
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
        self.episode_amount = self.capital // self.buy_limit
        self.episode_count += 1
        self.episode_purchase_number = self.get_episode_purchase_number()
        self.episode_sale_number = self.get_episode_sale_number()

    def shift_reference_up(self):
        self.set_reference(self.reference_price + self.loss_cut)

    def shift_reference_down(self):
        self.set_reference(self.reference_price - self.loss_cut)

    def update_transaction_info(self, item):
        # First time work
        if not self.start_price:
            self.start_time_text = datetime.now().strftime('%H:%M')
            self.start_time = self.to_min_count(self.start_time_text)
            self.start_price = item.current_price
            reference_price = item.current_price + self.loss_cut
            self.set_reference(reference_price)
            self.episode_purchase.virtual_open_amount = self.episode_amount
            self.inverse.buy(self.buy_limit, self.episode_amount)

            return

        # Block during situation processing
        # if self.situation_processing:
        #     return

        # Trade according to current price
        if item.current_price > self.reference_price:
            self.post('Situation 1')
            self.shift_reference_up()
            self.inverse.correct_purchases(self.buy_limit)
            self.inverse.init_sale()
        elif item.current_price < self.buy_limit:
            self.post('Situation 4')
            self.shift_reference_down()
            self.inverse.correct_sales(self.reference_price)
            self.inverse.init_purchase()

    def update_execution_info(self, order):
        # Inverse update execution
        self.inverse.update_execution_info(order)

        # Order processing
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.update_episode_purchase(order)

            # Order
            if order.executed_amount:
                order_amount = self.inverse.holding_amount - self.episode_sale.virtual_open_amount
                if order_amount >= self.minimum_transaction_amount:
                    self.episode_sale.virtual_open_amount += order_amount
                    self.inverse.sell(self.reference_price, order_amount)
        elif order.order_position in (SELL, CORRECT_SELL):
            self.update_episode_sale(order)

            # Order
            if order.executed_amount:
                order_amount = self.episode_amount - self.episode_purchase.virtual_open_amount - self.inverse.holding_amount
                if order_amount >= self.minimum_transaction_amount:
                    self.episode_purchase.virtual_open_amount += order_amount
                    self.inverse.buy(self.buy_limit, order_amount)

                self.total_profit += order.profit
                self.total_fee += order.transaction_fee
                self.net_profit += order.net_profit

        self.signal('algorithm_update')
        self.broker.draw_chart.start()

    def update_episode_purchase(self, order):
        executed_amount = abs(order.executed_amount)
        if self.episode_purchase.order_price != order.order_price:
            old_purchase = self.episode_purchase
            self.episode_purchase = Order()
            self.episode_purchase.item_name = order.item_name
            self.episode_purchase.episode_number = self.episode_purchase_number
            self.episode_purchase.order_price = order.order_price
            self.episode_purchase.virtual_open_amount = old_purchase.virtual_open_amount
        self.episode_purchase.executed_time = order.executed_time
        self.episode_purchase.order_number = order.order_number
        self.episode_purchase.order_position = order.order_position
        self.episode_purchase.order_state = order.order_state
        self.episode_purchase.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT:
            self.episode_purchase.order_amount += order.order_amount
            self.episode_purchase.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.episode_purchase.open_amount -= executed_amount
            self.episode_purchase.virtual_open_amount -= executed_amount
            self.episode_purchase.executed_amount_sum += executed_amount
        self.orders[self.episode_purchase_number] = self.episode_purchase

    def update_episode_sale(self, order):
        executed_amount = abs(order.executed_amount)
        if self.episode_sale.order_price != order.order_price:
            old_sale = self.episode_sale
            self.episode_sale = Order()
            self.episode_sale.item_name = order.item_name
            self.episode_sale.episode_number = self.episode_sale_number
            self.episode_sale.order_price = order.order_price
            self.episode_sale.virtual_open_amount = old_sale.virtual_open_amount
        self.episode_sale.executed_time = order.executed_time
        self.episode_sale.order_number = order.order_number
        self.episode_sale.order_position = order.order_position
        self.episode_sale.order_state = order.order_state
        self.episode_sale.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT:
            self.episode_sale.order_amount += order.order_amount
            self.episode_sale.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.episode_sale.open_amount -= executed_amount
            self.episode_sale.virtual_open_amount -= executed_amount
            self.episode_sale.executed_amount_sum += executed_amount
            self.episode_sale.profit += order.profit
        self.orders[self.episode_sale_number] = self.episode_sale

    def display_situation(self, current_situation):
        if current_situation != self.previous_situation:
            self.post(current_situation)
            self.previous_situation = current_situation

    def post(self, *args):
        if args != self.previous_msg:
            self.debug('\033[93mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post(self, *args):
        self.debug('\033[93mALGORITHM', *args, '\033[97m')