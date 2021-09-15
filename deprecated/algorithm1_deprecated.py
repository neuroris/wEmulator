from datetime import datetime
from wookutil import wmath
from wookitem import AlgorithmItem
from wookalgorithm.algorithmbase import AlgorithmBase
from wookdata import *

'''
Original algorithm(2021, 02, 28), revision(2021, 04, 06) 

First algorithm using leverage only
1. Non overlapping interval
2. Discard every holding stock when touching loss cut
3. Only one purchase, sale manager
4. Beyond threashold, cancel purchase or sale and re-order
'''

class Algorithm1(AlgorithmBase):
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
            reference_price = wmath.get_bottom(item.current_price, self.interval)
            self.set_reference(reference_price)
            self.leverage.buy(self.buy_limit, self.capital // item.current_price, 'MARKET')
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
            if self.leverage.holding_amount:
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
            # if not order.open_amount and not self.leverage.purchase.open_amount:
            if not order.open_amount:
                self.leverage.buy_over(self.buy_limit, self.capital // order.current_price)
                self.leverage.buy(self.buy_limit, self.capital // order.current_price)

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