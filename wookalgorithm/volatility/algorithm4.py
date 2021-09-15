from datetime import datetime
from wookitem import Order, AlgorithmItem
from wookutil import wmath
from wookdata import *
from wookalgorithm.algorithmbase import AlgorithmBase

'''
Original Algorithm (2021, 04, 08)
1. Non overlapping interval
2. Correct order price when stock price get out of interval range
3. Using multi-order purchases, sales
4. Only trade over threshold amount (min_amount)
5. Sell off under the loss limit
'''

class VAlgorithm4(AlgorithmBase):
    def __init__(self, log):
        super().__init__(log)
        self.leverage = None

    def start(self, broker, capital, interval, loss_cut, fee, minimum_transaction_amount):
        self.leverage = AlgorithmItem('122630')
        self.add_item(self.leverage)
        self.initialize(broker, capital, interval, loss_cut, fee, minimum_transaction_amount)

        # Open Orders cancellation
        self.clear_open_orders()

        # Charting & Monitoring
        broker.go_chart(self.leverage.item_code)
        broker.demand_monitoring_items_info(self.leverage)

        self.is_running = True
        self.post('STARTED')

    def update_transaction_info(self, item):
        # First time work
        if not self.start_price:
            self.start_time_text = datetime.now().strftime('%H:%M')
            self.start_time = self.to_min_count(self.start_time_text)
            self.start_price = item.current_price
            reference_price = wmath.get_top(item.current_price, self.interval)
            self.set_reference(reference_price)
            self.episode_purchase.virtual_open_amount = self.episode_amount
            self.purchase_episode_shifted = True
            self.sale_episode_shifted = True
            self.leverage.buy(self.buy_limit, self.episode_amount)
            return

        # Update ask price
        self.items[item.item_code].ask_price = item.ask_price

        # Block during situation processing
        if self.open_correct_orders:
            self.post('(BLOCK)', 'open correct orders', self.open_correct_orders)
            return
        elif self.open_cancel_orders:
            self.post('(BLOCK)', 'open cancel orders', self.open_cancel_orders)
            return
        elif self.sell_off_ordered:
            self.post('(BLOCK)', 'sell off ordered')
            return
        elif self.settle_up_in_progress:
            self.post('(BLOCK)', 'settle up in progress')
            return
        elif self.finish_up_in_progress:
            self.post('(BLOCK)', 'finish in progress')
            return

        # Trade according to current price
        if item.current_price >= (self.reference_price + self.loss_cut):
            self.post('Situation 1')
            self.open_correct_orders = len(self.leverage.purchases)
            self.shift_reference_up()
            self.purchase_episode_shifted = True
            self.sale_episode_shifted = True
            self.leverage.correct_purchases(self.buy_limit)
        elif item.current_price <= self.loss_limit:
            self.post('Situation 4')
            self.open_cancel_orders = len(self.leverage.sales)
            self.shift_reference_down()
            self.purchase_episode_shifted = True
            self.leverage.cancel_sales()

    def update_execution_info(self, order):
        # Inverse update execution
        self.leverage.update_execution_info(order)

        # Order processing
        self.process_subsequent_order(order)
        self.process_synchronization(order)

        self.signal('algorithm_update')
        self.broker.draw_chart.start()

    def process_subsequent_order(self, order):
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.update_episode_purchase(order)
            if order.executed_amount:
                order_amount = self.leverage.holding_amount - self.episode_sale.virtual_open_amount
                if order_amount >= self.minimum_transaction_amount:
                    self.episode_sale.virtual_open_amount += order_amount
                    self.leverage.sell(self.reference_price, order_amount)
        elif order.order_position in (SELL, CORRECT_SELL):
            self.update_episode_sale(order)
            if order.executed_amount:
                order_amount = self.episode_amount - self.episode_purchase.virtual_open_amount - self.leverage.holding_amount
                if order_amount >= self.minimum_transaction_amount:
                    self.episode_purchase.virtual_open_amount += order_amount
                    self.leverage.buy(self.buy_limit, order_amount)
                self.total_profit += order.profit
                self.total_fee += order.transaction_fee
                self.net_profit += order.net_profit

    def process_synchronization(self, order):
        if order.order_position in (CORRECT_PURCHASE, CORRECT_SELL) and order.order_state == CONFIRMED:
            self.open_correct_orders -= 1
        elif order.order_position in (CANCEL_PURCHASE, CANCEL_SELL) and order.order_state == CONFIRMED:
            if self.open_cancel_orders:
                self.open_cancel_orders -= 1
                if not self.open_cancel_orders:
                    self.sell_off_ordered = True
                    self.leverage.sell_off()
            if self.settle_up_in_progress:
                self.open_orders -= 1
                self.debug('%%%%%%%% (SETTLE UP) OPEN ORDER', self.open_orders)
                if not self.open_orders:
                    self.settle_up_proper()
            elif self.finish_up_in_progress:
                self.open_orders -= 1
                if not self.open_orders:
                    self.finish_up_proper()

    def update_episode_purchase(self, order):
        executed_amount = abs(order.executed_amount)
        if self.purchase_episode_shifted:
            old_purchase = self.episode_purchase
            self.purchase_episode_shifted = False
            self.episode_purchase = Order()
            self.episode_purchase_number = self.get_episode_purchase_number()
            self.episode_purchase.episode_number = self.episode_purchase_number
            self.episode_purchase.item_name = order.item_name
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
        if self.sale_episode_shifted:
            old_sale = self.episode_sale
            self.sale_episode_shifted = False
            self.episode_sale = Order()
            self.episode_sale_number = self.get_episode_sale_number()
            self.episode_sale.episode_number = self.episode_sale_number
            self.episode_sale.item_name = order.item_name
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
            self.episode_sale.net_profit += order.net_profit
        self.orders[self.episode_sale_number] = self.episode_sale

        if self.sell_off_ordered and not order.open_amount:
            self.sale_episode_shifted = True
            self.sell_off_ordered = False