import copy
from datetime import datetime
from wookitem import AlgorithmItem
from wookdata import *
from wookalgorithm.algorithmbase import AlgorithmBase

'''
QuantumJump algorithm (2021, 03, 06), revision(2021, 04, 06)

Discrete price algorithm using inverse only
1. Overlapping interval
2. Correct order price when stock price get out of interval range
3. purchase, sale dictionaries
4. No limit on minimum transaction amount
'''

class QAlgorithm2(AlgorithmBase):
    def __init__(self, log):
        super().__init__(log)
        self.inverse = None

    def start(self, broker, capital, interval, loss_cut, fee, minimum_transaction_amount):
        self.inverse = AlgorithmItem('252670')
        self.add_item(self.inverse)
        self.initialize(broker, capital, interval, loss_cut, fee, minimum_transaction_amount)
        self.shift_interval = loss_cut

        # Open Orders cancellation
        self.clear_open_orders()

        # Charting & Monitoring
        broker.go_chart(self.inverse.item_code)
        broker.demand_monitoring_items_info(self.inverse)

        self.is_running = True
        self.post('STARTED')

    def update_transaction_info(self, item):
        # First time work
        if not self.start_price:
            self.start_time_text = datetime.now().strftime('%H:%M')
            self.start_time = self.to_min_count(self.start_time_text)
            self.start_price = item.current_price
            reference_price = item.current_price + self.loss_cut
            self.set_reference(reference_price)
            self.inverse.buy(self.buy_limit, self.capital // item.current_price)
            return

        # Block during situation processing
        if self.shift_in_progress:
            return

        # Trade according to current price
        if item.current_price > self.reference_price:
            self.post('Situation 1')
            self.shift_in_progress = True
            self.shift_reference_up()
            self.inverse.correct_purchases(self.buy_limit)
            self.inverse.init_sale()
        elif item.current_price < self.buy_limit:
            self.post('Situation 4')
            self.shift_in_progress = True
            self.shift_reference_down()
            self.inverse.correct_sales(self.reference_price)
            self.inverse.init_purchase()

    def update_execution_info(self, order):
        # Inverse update execution
        self.inverse.update_execution_info(order)

        # Order processing
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.update_episode_purchase(order)
            if order.executed_amount:
                self.inverse.sell(self.reference_price, order.executed_amount)
        elif order.order_position in (SELL, CORRECT_SELL):
            self.update_episode_sale(order)
            if order.executed_amount:
                self.inverse.buy(self.buy_limit, order.executed_amount)
                self.total_profit += order.profit
                self.total_fee += order.transaction_fee
                self.net_profit += order.net_profit
        # elif order.order_position == CANCEL_PURCHASE and order.order_state == CONFIRMED:
        #     if not self.inverse.purchases:
        #         order_amount = self.capital // order.current_price - self.inverse.holding_amount
        #         self.inverse.buy(self.buy_limit, order_amount)
        #         self.situation_processing = False
        # elif order.order_position == CANCEL_SELL and order.order_state == CONFIRMED:
        #     if not self.inverse.sales:
        #         self.inverse.sell(self.reference_price, self.inverse.holding_amount)
        #         self.situation_processing = False

        self.signal('algorithm_update')
        self.broker.draw_chart.start()

    def update_episode_purchase(self, order):
        executed_amount = abs(order.executed_amount)
        if self.episode_purchase.order_price != order.order_price:
            self.episode_purchase = copy.deepcopy(order)
            self.episode_purchase_number = self.get_episode_purchase_number()
            self.episode_purchase.episode_number = self.episode_purchase_number
            self.episode_purchase.order_amount = 0
            self.episode_purchase.open_amount = 0
        self.episode_purchase.executed_time = order.executed_time
        self.episode_purchase.order_number = order.order_number
        self.episode_purchase.order_state = order.order_state
        self.episode_purchase.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT:
            self.episode_purchase.order_amount += order.order_amount
            self.episode_purchase.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.episode_purchase.open_amount -= executed_amount
            self.episode_purchase.executed_amount_sum += executed_amount
        self.orders[self.episode_purchase_number] = self.episode_purchase

    def update_episode_sale(self, order):
        executed_amount = abs(order.executed_amount)
        if self.episode_sale.order_price != order.order_price:
            self.episode_sale = copy.deepcopy(order)
            self.episode_sale_number = self.get_episode_sale_number()
            self.episode_sale.episode_number = self.episode_sale_number
            self.episode_sale.order_amount = 0
            self.episode_sale.open_amount = 0
        self.episode_sale.executed_time = order.executed_time
        self.episode_sale.order_number = order.order_number
        self.episode_sale.order_state = order.order_state
        self.episode_sale.executed_price_avg = order.executed_price_avg
        self.episode_sale.profit += order.profit
        if order.order_state == RECEIPT:
            self.episode_sale.order_amount += order.order_amount
            self.episode_sale.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.episode_sale.open_amount -= executed_amount
            self.episode_sale.executed_amount_sum += executed_amount
        self.orders[self.episode_sale_number] = self.episode_sale