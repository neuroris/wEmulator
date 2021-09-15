import numpy
from mplfinance.original_flavor import candlestick2_ohlc
from matplotlib import ticker
from datetime import datetime
from wookitem import Order, AlgorithmItem
from wookutil import wmath
from deprecated.wookdata_deprecated import *
from wookalgorithm.algorithmbase import AlgorithmBase
import math, copy

'''
Original Algorithm (2021, 05, 11)
1. Moving average algorithm
2. Moving average is calculated by simple close price 
3. Futures!!
'''

class MAlgorithm3(AlgorithmBase):
    def __init__(self, trader, log):
        super().__init__(trader, log)
        self.futures = None

    def start(self, broker, capital, interval, loss_cut, fee, minimum_transaction_amount):
        self.futures = AlgorithmItem('101R6000')
        self.add_item(self.futures)
        self.initialize(broker, capital, interval, loss_cut, fee, minimum_transaction_amount)

        # Open Orders cancellation
        self.clear_open_orders()

        # Charting & Monitoring
        broker.chart_prices.clear()
        broker.request_futures_stock_price_min(self.futures.item_code)
        broker.demand_monitoring_items_info(self.futures)
        self.timer.start()

        self.is_running = True
        self.post('STARTED')

    def update_transaction_info(self, item):
        # First time work
        if not self.start_price:
            self.start_time_text = datetime.now().strftime('%H:%M')
            self.start_time = self.to_min_count(self.start_time_text)
            self.start_price = item.current_price
            self.start_comment = 'start\n' + self.start_time_text + '\n' + format(self.start_price, ',')
            reference_price = wmath.get_top(item.current_price, self.interval)
            self.set_reference(reference_price)
            return

        # Block during situation processing
        if self.open_purchase_correct_orders or self.open_sale_correct_orders:
            self.post('(BLOCK)', 'open correct orders', self.open_correct_orders)
            return
        elif self.open_purchase_cancel_orders or self.open_sale_cancel_orders:
            self.post('(BLOCK)', 'open cancel orders', self.open_cancel_orders)
            return
        elif self.open_cancel_orders:
            self.post('(BLOCK)', 'open cancel orders', self.open_cancel_orders)
            return
        elif self.sell_off_ordered:
            self.post('(BLOCK)', 'sell off ordered')
            return
        elif self.settle_up_in_progress:
            self.post_without_repetition('(BLOCK)', 'settle up in progress')
            return
        elif self.finish_up_in_progress:
            self.post_without_repetition('(BLOCK)', 'finish in progress')
            return

        # Update ask price
        self.items[item.item_code].ask_price = abs(item.ask_price)

        # Update chart
        self.update_chart_prices(item.item_code, item.current_price, item.volume)

        # Purchase decision
        self.bull_market()
        if not self.futures.purchase.ordered and self.bull_market():
            self.buy(item)
        if not self.futures.purchase.ordered and self.bear_market():
            self.sell(item)

        # Trade according to current price
        if item.current_price >= (self.reference_price + self.loss_cut):
            self.post('Situation 1')
            self.shift_reference_up()
            if self.bull_market():
                self.open_purchase_correct_orders = len(self.futures.purchases)
                if self.open_purchase_correct_orders:
                    self.futures.correct_purchases(self.buy_limit)
                if self.futures.holding_amount:
                    self.loss_limit -= self.loss_cut
            else:
                self.open_purchase_cancel_orders = len(self.futures.purchases)
                if self.open_purchase_cancel_orders:
                    self.futures.cancel_purchases()
        elif item.current_price <= self.loss_limit:
            self.post('Situation 4')
            self.shift_reference_down()
            if self.futures.holding_amount:
                self.open_cancel_orders = len(self.futures.sales)
                self.sell_off_ordered = True
                self.futures.sell_off()

    def bull_market(self):
        chart = self.futures.chart
        self.debug('Diff5: {}, DiffDifff5[-1]:{}, DiffDiff10[-1]: {}, DiffDiff10[-2]: {}'.format(chart.Diff5[-1], chart.DiffDiff5[-1], chart.DiffDiff10[-1], chart.DiffDiff10[-2]))
        # if chart.Diff5[-1] > 0 and chart.DiffDiff10[-1] > 0 and chart.DiffDiff10[-2] > 0:
        # if chart.Diff5[-1] > 0 and chart.DiffDiff10[-1] > 0:
        if chart.DiffDiff5[-1] > 0 and chart.DiffDiff10[-1] > 0:
            return True
        else:
            return False

    def bear_market(self):
        chart = self.futures.chart
        if chart.Diff5[-1] < 0 and chart.Diff10[-1] < 0 and chart.DiffDiff20[-1] < 0:
            return True
        else:
            return False

    def buy(self, item):
        self.episode_purchase.virtual_open_amount += self.episode_amount
        self.episode_count += 1
        self.purchase_episode_shifted = True
        self.sale_episode_shifted = True
        self.futures.buy(0, self.episode_amount, 'MARKET')
        # self.leverage.buy(self.buy_limit, self.episode_amount)

    def sell(self, item):
        self.episode_purchase.virtual_open_amount += self.episode_amount
        self.episode_count += 1
        self.purchase_episode_shifted = True
        self.sale_episode_shifted = True
        self.futures.sell(0, self.episode_amount, 'MARKET')

    def update_execution_info(self, order):
        # Algorithm item update
        self.futures.update_execution_info(order)

        # Order processing
        self.process_subsequent_order(order)
        self.process_synchronization(order)

        # Display
        self.trader.display_algorithm_trading()
        self.trader.display_algorithm_results()
        self.draw_chart.start()

    def process_subsequent_order(self, order):
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.update_episode_purchase(order)
        elif order.order_position in (SELL, CORRECT_SELL):
            self.update_episode_sale(order)
            if order.executed_amount:
                self.total_profit += order.profit
                self.total_fee += order.transaction_fee
                self.net_profit += order.net_profit

    def process_synchronization(self, order):
        if order.order_position == CORRECT_PURCHASE and order.order_state == CONFIRMED:
            self.open_purchase_correct_orders -= 1
        elif order.order_position == CORRECT_SELL and order.order_state == CONFIRMED:
            self.open_sale_correct_orders -= 1
        elif order.order_position == CANCEL_PURCHASE and order.order_state == CONFIRMED:
            if self.open_purchase_cancel_orders:
                self.open_purchase_cancel_orders -= 1
        elif order.order_position == CANCEL_SELL and order.order_state == CONFIRMED:
            if self.open_sale_cancel_orders:
                self.open_sale_cancel_orders -= 1
            if self.settle_up_in_progress:
                self.open_orders -= 1
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
            self.episode_purchase.virtual_open_amount = old_purchase.virtual_open_amount
            self.episode_purchase.order_amount += order.order_amount
            self.episode_purchase.open_amount += order.open_amount
        self.episode_purchase.order_price = order.order_price
        self.episode_purchase.executed_time = order.executed_time
        self.episode_purchase.order_number = order.order_number
        self.episode_purchase.order_position = order.order_position
        self.episode_purchase.order_state = order.order_state
        self.episode_purchase.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT:
            pass
        elif order.order_state == ORDER_EXECUTED:
            self.episode_purchase.open_amount -= executed_amount
            self.episode_purchase.virtual_open_amount -= executed_amount
            self.episode_purchase.executed_amount_sum += executed_amount
        self.orders[self.episode_purchase_number] = self.episode_purchase

    def update_episode_sale(self, order):
        executed_amount = abs(order.executed_amount)
        if self.sale_episode_shifted:
            self.sale_episode_shifted = False
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
            self.episode_sale.net_profit += order.net_profit
        self.orders[self.episode_sale_number] = self.episode_sale

        if self.sell_off_ordered and not order.open_amount:
            self.sell_off_ordered = False

    def customize_past_chart(self, item):
        chart = item.chart
        chart['MA5'] = chart.Close.rolling(5, 1).mean().apply(lambda x:round(x, 2))
        chart['MA10'] = chart.Close.rolling(10, 1).mean().apply(lambda x:round(x, 2))
        chart['MA20'] = chart.Close.rolling(20, 1).mean().apply(lambda x:round(x, 2))
        chart['Diff5'] = chart.MA5.diff().fillna(0).apply(lambda x:round(x, 2))
        chart['Diff10'] = chart.MA10.diff().fillna(0).apply(lambda x:round(x, 2))
        chart['Diff20'] = chart.MA20.diff().fillna(0).apply(lambda x:round(x, 2))
        chart['DiffDiff5'] = chart.Diff5.diff().fillna(0).apply(lambda x:round(x, 2))
        chart['DiffDiff10'] = chart.Diff10.diff().fillna(0).apply(lambda x:round(x, 2))
        chart['DiffDiff20'] = chart.Diff20.diff().fillna(0).apply(lambda x:round(x, 2))

    def update_custom_chart(self, item):
        chart = item.chart
        chart_len = len(chart)
        ma5 = -5
        ma10 = -10
        ma20 = -20
        if chart_len < 5:
            ma5 = chart_len * -1
            ma10 = chart_len * -1
            ma20 = chart_len * -1
        elif chart_len < 10:
            ma10 = chart_len * -1
            ma20 = chart_len * -1
        elif chart_len < 20:
            ma20 = chart_len * -1

        chart.MA5[-1] = round(chart.Close[ma5:].mean(), 2)
        chart.MA10[-1] = round(chart.Close[ma10:].mean(), 2)
        chart.MA20[-1] = round(chart.Close[ma20:].mean(), 2)
        chart.Diff5[-1] = chart.MA5[-1] - chart.MA5[-2]
        chart.Diff10[-1] = chart.MA10[-1] - chart.MA10[-2]
        chart.Diff20[-1] = chart.MA20[-1] - chart.MA20[-2]
        chart.DiffDiff5[-1] = chart.Diff5[-1] - chart.Diff5[-2]
        chart.DiffDiff10[-1] = chart.Diff10[-1] - chart.Diff10[-2]
        chart.DiffDiff20[-1] = chart.Diff20[-1] - chart.Diff20[-2]

    def display_chart(self):
        chart = self.futures.chart
        if not len(chart):
            return

        self.trader.ax.clear()

        # Axis ticker formatting
        if len(chart) // 30 > len(self.chart_locator) - 1:
            for index in range(len(self.chart_locator) * 30, len(chart), 30):
                time_format = chart.index[index].strftime('%H:%M')
                self.chart_locator.append(index)
                self.chart_formatter.append(time_format)
        self.trader.ax.xaxis.set_major_locator(ticker.FixedLocator(self.chart_locator))
        self.trader.ax.xaxis.set_major_formatter(ticker.FixedFormatter(self.chart_formatter))

        # Axis yticks & lines
        max_price = chart.High.max()
        min_price = chart.Low.min()
        if max_price > self.top_price or min_price < self.bottom_price:
            self.top_price = math.ceil(max_price / self.interval) * self.interval
            self.bottom_price = math.floor(min_price / self.interval) * self.interval
            self.interval_prices = numpy.arange(self.bottom_price, self.top_price + self.interval, self.interval)
            self.loss_cut_prices = numpy.arange(self.bottom_price + self.interval - self.loss_cut, self.top_price, self.interval)
        self.trader.ax.grid(axis='x', alpha=0.5)
        self.trader.ax.set_yticks(self.interval_prices)
        for price in self.interval_prices:
            self.trader.ax.axhline(price, alpha=0.5, linewidth=0.2)
        for price in self.loss_cut_prices:
            self.trader.ax.axhline(price, alpha=0.4, linewidth=0.2, color='Gray')

        # Current Price Annotation
        current_time = len(chart)
        current_price = chart.Close.iloc[-1]
        self.trader.ax.text(current_time + 0.5, current_price, format(current_price, ','))

        # Moving average
        x = range(0, len(chart))
        self.trader.ax.plot(x, chart.MA5, label='MA5')
        self.trader.ax.plot(x, chart.MA10, label='MA10')
        self.trader.ax.plot(x, chart.MA20, label='MA20')
        self.trader.ax.legend(loc='best')

        # Slope
        slope_x = range(len(chart) - 1, len(chart) + 1)
        slope = numpy.polyfit(slope_x, chart.MA5[-2:], 1)
        x = range(len(chart) - 20, len(chart))
        y = numpy.poly1d(slope)
        self.trader.ax.plot(x, y(x))

        # Set lim
        x2 = len(chart)
        x1 = x2 - self.chart_scope
        if x1 < 0:
            x1 = 0
        elif x1 > x2 - 1:
            x1 = x2 - 1
        y1 = self.get_min_price(x1, x2) - 0.1
        y2 = self.get_max_price(x1, x2) + 0.1
        self.trader.ax.set_xlim(x1, x2)
        self.trader.ax.set_ylim(y1, y2)

        # After price data acquired
        if self.reference_price:
            self.annotate_chart(current_time)

        # Draw chart
        candlestick2_ohlc(self.trader.ax, chart.Open, chart.High, chart.Low, chart.Close,
                          width=0.4, colorup='red', colordown='blue')
        self.trader.fig.tight_layout()
        self.trader.canvas.draw()

    def annotate_chart(self, current_time):
        x_lim = self.trader.ax.get_xlim()[0]
        y_lim = self.trader.ax.get_ylim()[0]

        # Start time
        if self.start_time > x_lim:
            self.trader.ax.plot(self.start_time, self.start_price, marker='o', markersize=3, color='Lime')
            self.trader.ax.vlines(self.start_time, self.bottom_price, self.start_price, alpha=0.8, linewidth=0.2, color='Green')
            self.trader.ax.text(self.start_time, y_lim + 5, self.start_comment, color='RebeccaPurple')

        # References
        reference_offset = 0.5
        self.trader.ax.axhline(self.reference_price, alpha=1, linewidth=0.2, color='Maroon')
        self.trader.ax.text(x_lim + reference_offset, self.reference_price, 'Reference')
        self.trader.ax.axhline(self.buy_limit, alpha=1, linewidth=0.2, color='Maroon')
        self.trader.ax.text(x_lim + reference_offset, self.buy_limit, 'Buy limit')
        self.trader.ax.axhline(self.loss_limit, alpha=1, linewidth=0.2, color='DeepPink')
        self.trader.ax.text(x_lim + reference_offset, self.loss_limit, 'Loss cut')

        # Purchases and Sales
        total_range = self.top_price - self.bottom_price
        offset = total_range * 0.035
        x = current_time
        y = self.reference_price
        sales = copy.deepcopy(self.futures.sales)
        for order in sales.values():
            if order.open_amount:
                y += offset
                self.trader.ax.text(x, y, '({}/{})'.format(order.executed_amount_sum, order.order_amount))

        y = self.buy_limit - offset
        purchases = copy.deepcopy(self.futures.purchases)
        for order in purchases.values():
            if order.open_amount:
                y -= offset
                self.trader.ax.text(x, y, '({}/{})'.format(order.executed_amount_sum, order.order_amount))

    def get_max_price(self, x1, x2):
        max_price = self.futures.chart.High[x1:x2].max()
        return max_price

    def get_min_price(self, x1, x2):
        min_price = self.futures.chart.Low[x1:x2].min()
        return min_price