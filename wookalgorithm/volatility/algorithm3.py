from datetime import datetime
from wookitem import Order, AlgorithmItem
from wookutil import wmath
from deprecated.wookdata_deprecated import *
from wookalgorithm.algorithmbase import AlgorithmBase

'''
Original Algorithm (2021, 04, 06)
1. Non overlapping interval
2. Correct order price when stock price get out of interval range
3. Using multi-order purchases, sales
4. Only trade over threshold amount (min_amount)
5. No sell off, just shift reference
'''

class VAlgorithm3(AlgorithmBase):
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
            self.leverage.buy(self.buy_limit, self.episode_amount)
            return

        # Block during situation processing
        if self.finish_up_in_progress:
            return

        if self.open_correct_orders:
            return

        # Trade according to current price
        if item.current_price > (self.reference_price + self.loss_cut):
            self.post('Situation 1')
            self.open_correct_orders = len(self.leverage.purchases)
            self.shift_reference_up()
            self.leverage.correct_purchases(self.buy_limit)
            self.leverage.init_sale()
        elif item.current_price < self.loss_limit:
            self.post('Situation 4')
            self.open_correct_orders = len(self.leverage.sales)
            self.shift_reference_down()
            self.leverage.correct_sales(self.reference_price)
            self.leverage.init_purchase()

    def update_execution_info(self, order):
        # Inverse update execution
        self.leverage.update_execution_info(order)

        # Order processing
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

        # Confirm exclusive situation processing
        if order.order_position in (CORRECT_PURCHASE, CORRECT_SELL) and order.order_state == CONFIRMED:
            self.open_correct_orders -= 1
        elif order.order_state in (CANCEL_PURCHASE, CANCEL_SELL) and order.order_state == CONFIRMED:
            self.open_orders -= 1
            if not self.open_orders:
                if self.settle_up_in_progress:
                    self.settle_up_proper()
                elif self.finish_up_in_progress:
                    self.finish_up_proper()

        self.signal('algorithm_update')
        self.broker.draw_chart.start()

    def update_episode_purchase(self, order):
        executed_amount = abs(order.executed_amount)
        if self.episode_purchase.order_price != order.order_price:
            old_purchase = self.episode_purchase
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
        if self.episode_sale.order_price != order.order_price:
            old_sale = self.episode_sale
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
        self.orders[self.episode_sale_number] = self.episode_sale