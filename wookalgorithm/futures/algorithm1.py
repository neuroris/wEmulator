import numpy
from mplfinance.original_flavor import candlestick2_ohlc
from matplotlib import ticker
from datetime import datetime
from wookitem import Order, Episode, AlgorithmItem, FuturesAlgorithmItem
from wookutil import wmath
from wookdata import *
from wookalgorithm.futuresalgorithmbase import FuturesAlgorithmBase
import pandas
import math, copy

'''
Original Algorithm (2021, 06, 17)
1. Moving average algorithm
2. Moving average is calculated by simple close price 
3. Futures!!
'''

class FMAlgorithm1(FuturesAlgorithmBase):
    def __init__(self, trader, log):
        super().__init__(trader, log)
        self.futures = None
        self.slope = None
        self.open_position_purchase_history = dict()
        self.close_position_purchase_history = dict()
        self.open_position_sale_history = dict()
        self.close_position_sale_history = dict()

        self.diffdiff5 = dict()

    def start(self, broker, capital, interval, loss_cut, fee, minimum_transaction_amount):
        self.futures = FuturesAlgorithmItem('101R9000')
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

    def market_status(self, item):
        if not self.start_time:
            self.start_work(item.current_price)

        # Update chart
        self.update_chart_prices(item.item_code, item.current_price, item.volume)

        if self.work_in_progress():
            return

        # For debugging
        # self.debug('Slope', self.slope)
        chart = self.futures.chart
        self.post_white_without_repetition(
            'DiffDiff5[-5]:{}, DiffDiff5[-4]:{}, DiffDiff5[-3]:{}, DiffDiff5[-2]:{}, DiffDiff5[-1]:{}'.format
            (chart.DiffDiff5[-5], chart.DiffDiff5[-4], chart.DiffDiff5[-3], chart.DiffDiff5[-2],
             chart.DiffDiff5[-1]))
        # self.post_magenta('Diff5[-3]:{}, Diff5[-2]:{}, Diff[-1]:{}'.format(chart.Diff5[-3], chart.Diff5[-2], chart.Diff5[-1]))
        # self.debug('Diff5[-2]:{}, Diff10[-2]:{}, Diff20[-2]:{}, Diff5[-1]:{}, Diff10[-1]:{}, Diff20[-1]:{}'.format
        #            (chart.Diff5[-2], chart.Diff10[-2], chart.Diff20[-2], chart.Diff5[-1], chart.Diff10[-1], chart.Diff20[-1]))
        # self.debug('Diff5[-4]:{} Diff5[-3]:{}, Diff5[-2]:{}, Diff[-1]:{}'.format
        #            (chart.Diff5[-4], chart.Diff5[-3], chart.Diff5[-2], chart.Diff5[-1]))
        # self.debug('Diff5: {}, DiffDifff5[-2]:{}, Diff10[-2]:{}, DiffDiff10[-2]: {}'.format
        #            (chart.Diff5[-2], chart.DiffDiff5[-2], chart.Diff10[-2], chart.DiffDiff10[-1]))
        # self.debug('Diff5: {}, DiffDifff5[-1]:{}, Diff10[-1]:{}, DiffDiff10[-1]: {}'.format
        #            (chart.Diff5[-1], chart.DiffDiff5[-1], chart.Diff10[-1], chart.DiffDiff10[-1]))
        # self.debug('MA5[-1]', chart.MA5[-1], 'MA5[-2]', chart.MA5[-2])

        # Purchase decision & shift transition
        if self.episode_in_progress:
            self.shift_transition(item.current_price)
            self.consider_stop_loss(item.current_price)
        else:
            self.consider_transaction(item.current_price)

    def start_work(self, current_price):
        self.start_time_text = datetime.now().strftime('%H:%M')
        self.start_time = self.to_min_count(self.start_time_text)
        self.start_price = current_price
        self.start_comment = 'start\n' + self.start_time_text + '\n' + format(self.start_price, ',')

    def work_in_progress(self):
        if self.open_purchase_correct_orders or self.open_sale_correct_orders:
            self.post('(BLOCK)', 'open correct orders', self.open_correct_orders)
            return True
        elif self.open_purchase_cancel_orders or self.open_sale_cancel_orders:
            self.post('(BLOCK)', 'open cancel orders', self.open_cancel_orders)
            return True
        elif self.open_cancel_orders:
            self.post('(BLOCK)', 'open cancel orders', self.open_cancel_orders)
            return True
        elif self.stop_loss_ordered:
            self.post_without_repetition('(BLOCK)', 'stop loss ordered')
            return True
        elif self.time_off_in_progress:
            self.post_without_repetition('(BLOCK)', 'time off')
            return True
        elif self.settle_up_in_progress:
            self.post_without_repetition('(BLOCK)', 'settle up in progress')
            return True
        elif self.finish_up_in_progress:
            self.post_without_repetition('(BLOCK)', 'finish in progress')
            return True
        else:
            return False

    def bull_market(self):
        chart = self.futures.chart
        if chart.Diff5[-2] > 0 and chart.Diff10[-2] > 0 and chart.Diff20[-2] > 0:
            if chart.Diff5[-1] > 0 and chart.Diff10[-1] > 0 and chart.Diff20[-1] > 0:
                self.post('Bull Market')
                return True
        else:
            return False

    def bear_market(self):
        chart = self.futures.chart
        if chart.Diff5[-2] < 0 and chart.Diff10[-2] < 0 and chart.Diff20[-2] < 0:
            if chart.Diff5[-1] < 0 and chart.Diff10[-1] < 0 and chart.Diff20[-1] < 0:
                self.post('Bear Market')
                return True
        else:
            return False

    def turnaround(self):
        chart = self.futures.chart
        if (chart.DiffDiff5[-4] <= 0) and \
                (chart.Diff5[-4] < 0) and \
                (chart.DiffDiff5[-3] - chart.DiffDiff5[-4]) >= -0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-3]) >= -0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-1]) >= -0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-4]) >= 0 and \
                (chart.DiffDiff5[-1] - chart.DiffDiff5[-3]) >= 0 and \
                ((chart.DiffDiff5[-2] > 0 and chart.DiffDiff5[-1] > 0) or (chart.DiffDiff5[-1] >= 0.02)):
            self.post('Turnaround')
            return True
        else:
            return False

    def downswing(self):
        chart = self.futures.chart
        if (chart.DiffDiff5[-4] >= 0) and \
                (chart.Diff5[-4] > 0) and \
                (chart.DiffDiff5[-3] - chart.DiffDiff5[-4]) <= 0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-3]) <= 0.01 and \
                (chart.DiffDiff5[-1] - chart.DiffDiff5[-2]) <= 0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-4]) <= 0 and \
                (chart.DiffDiff5[-1] - chart.DiffDiff5[-3]) <= 0 and \
                ((chart.DiffDiff5[-2] < 0 and chart.DiffDiff5[-1] < 0) or (chart.DiffDiff5[-1] <= 0.02)):
            self.post('Downswing')
            return True
        else:
            return False

    def turnaround2(self):
        chart = self.futures.chart
        if (chart.DiffDiff5[-5] <= 0) and \
                (chart.Diff5[-5] < 0) and \
                (chart.Diff5[-4] < 0) and \
                (chart.DiffDiff5[-4] - chart.DiffDiff5[-5]) >= -0.01 and\
                (chart.DiffDiff5[-3] - chart.DiffDiff5[-4]) >= -0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-3]) >= -0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-1]) >= -0.01 and \
                (chart.DiffDiff5[-3] - chart.DiffDiff5[-5]) >= 0 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-4]) >= 0 and \
                (chart.DiffDiff5[-1] - chart.DiffDiff5[-3]) >= 0 and \
                ((chart.DiffDiff5[-2] > 0 and chart.DiffDiff5[-1] > 0) or (chart.DiffDiff5[-1] >= 0.02)):
            self.post('Turnaround')
            return True
        else:
            return False

    def downswing2(self):
        chart = self.futures.chart
        if (chart.DiffDiff5[-5] >= 0) and \
                (chart.Diff5[-5] > 0) and \
                (chart.Diff5[-4] > 0) and \
                (chart.DiffDiff5[-4] - chart.DiffDiff5[-5]) <= 0.01 and \
                (chart.DiffDiff5[-3] - chart.DiffDiff5[-4]) <= 0.01 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-3]) <= 0.01 and \
                (chart.DiffDiff5[-1] - chart.DiffDiff5[-2]) <= 0.01 and \
                (chart.DiffDiff5[-3] - chart.DiffDiff5[-5]) <= 0 and \
                (chart.DiffDiff5[-2] - chart.DiffDiff5[-4]) <= 0 and \
                (chart.DiffDiff5[-1] - chart.DiffDiff5[-3]) <= 0 and \
                ((chart.DiffDiff5[-2] < 0 and chart.DiffDiff5[-1] < 0) or (chart.DiffDiff5[-1] <= 0.02)):
            self.post('Downswing')
            return True
        else:
            return False

    def consider_transaction(self, current_price):
        if self.turnaround():
            self.buy(current_price)
        elif self.downswing():
            self.sell(current_price)

    def buy(self, current_price):
        self.episode_count += 1
        self.episode_in_progress = True
        self.trade_position = LONG_POSITION
        self.set_reference(current_price)
        # self.open_position.virtual_open_amount += self.episode_amount
        self.futures.buy(0, self.episode_amount, 'MARKET')

    def sell(self, current_price):
        self.episode_count += 1
        self.episode_in_progress = True
        self.trade_position = SHORT_POSITION
        self.set_reference(current_price)
        # self.open_position.virtual_open_amount += self.episode_amount
        self.futures.sell(0, self.episode_amount, 'MARKET')

    def consider_stop_loss(self, current_price):
        if self.trade_position == LONG_POSITION:
            if self.downswing():
                self.post('STOP LOSS BY DOWNSWING!')
                self.stop_loss()
        elif self.trade_position == SHORT_POSITION:
            if self.turnaround():
                self.post('STOP LOSS BY TURNAROUND!')
                self.stop_loss()

    def stop_loss(self):
        if self.trade_position == LONG_POSITION:
            self.open_cancel_orders = len(self.futures.sales)
            self.stop_loss_ordered = True
            self.episode_in_progress = False
            self.futures.sell_off()
            self.time_off()
        elif self.trade_position == SHORT_POSITION:
            self.open_cancel_orders = len(self.futures.purchases)
            self.stop_loss_ordered = True
            self.episode_in_progress = False
            self.futures.buy_off()
            self.time_off()

    def shift_transition(self, current_price):
        if self.trade_position == LONG_POSITION:
            self.long_position_shift(current_price)
        elif self.trade_position == SHORT_POSITION:
            self.short_position_shift(current_price)

    def long_position_shift(self, current_price):
        # if current_price >= (self.reference_price + self.loss_cut):
        if current_price > self.reference_price + self.loss_cut:
            self.post('Situation 1')
            self.shift_reference_up()
            self.open_purchase_correct_orders = len(self.futures.purchases)
            if self.open_purchase_correct_orders:
                if self.bull_market():
                    self.futures.correct_purchases(self.trade_limit)
                else:
                    self.open_purchase_cancel_orders = len(self.futures.purchases)
                    if self.open_purchase_cancel_orders:
                        self.futures.cancel_purchases()
            # elif self.futures.holding_amount:
            #     self.loss_limit -= self.loss_cut
        elif current_price <= self.loss_limit:
            self.post('Situation 4')
            self.shift_reference_down()
            if self.futures.holding_amount:
                self.post('STOP LOSS BY LOSS CUT!!')
                self.stop_loss()

    def short_position_shift(self, current_price):
        # if current_price <= (self.reference_price - self.loss_cut):
        if current_price < self.reference_price:
            self.post('Situation 1')
            self.shift_reference_down()
            self.open_sale_correct_orders = len(self.futures.sales)
            if self.open_sale_correct_orders:
                if self.bear_market():
                    self.futures.correct_sales(self.trade_limit)
                else:
                    self.open_sale_cancel_orders = len(self.futures.sales)
                    if self.open_sale_cancel_orders:
                        self.futures.cancel_sales()
            # elif self.futures.holding_amount:
            #     self.loss_limit += self.loss_cut
        elif current_price >= self.loss_limit:
            self.post('Situation 4')
            self.shift_reference_up()
            if self.futures.holding_amount:
                self.post('STOP LOSS BY LOSS CUT!!')
                self.stop_loss()

    def update_execution_info(self, order):
        # Update Algorithm item orders
        self.futures.update_orders(order)

        # Update algorithm item contracts
        if order.executed_amount:
            if self.trade_position == order.order_position:
                self.futures.add_contract(order)
            else:
                self.futures.settle_contracts(order)

        # Update episode positions
        if self.trade_position == order.order_position:
            self.update_open_position(order)
        else:
            self.update_close_position(order)

        # Order processing
        self.subsequent_orders(order)
        self.count_open_orders(order)

        # Display
        self.post_order_details(order)
        self.trader.display_algorithm_trading()
        self.trader.display_algorithm_results()
        self.draw_chart.start()

    def post_order_details(self, order):
        msg = (order.item_name, order.order_position, order.order_state)
        msg += ('order:' + str(order.order_amount), 'executed_each:' + str(order.executed_amount))
        msg += ('open:' + str(order.open_amount), 'number:' + str(order.order_number))
        msg += ('purchase:' + str(order.purchase_price), 'executed:' + str(order.executed_price))
        msg += ('holding:' + str(self.futures.holding_amount),)
        executed_time = str(order.executed_time)
        time_format = executed_time[:2] + ':' + executed_time[2:4] + ':' + executed_time[4:]
        self.post_green('(EXECUTION)', *msg)
        self.post_blue('(DEBUG)', time_format, 'Purchases', len(self.futures.purchases),
                       'Sales', len(self.futures.sales))

    def subsequent_orders(self, order):
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            pass
        elif order.order_position in (SELL, CORRECT_SELL):
            pass

    def count_open_orders(self, order):
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
        elif self.settle_up_in_progress:
            self.open_orders -= 1
            if not self.open_orders:
                self.settle_up_proper()
        elif self.finish_up_in_progress:
            self.open_orders -= 1
            if not self.open_orders:
                self.finish_up_proper()

    def update_open_position(self, order):
        executed_amount = abs(order.executed_amount)
        if self.episode_count != self.open_position.get_episode_count():
            old_open_position = self.open_position
            self.open_position = Episode()
            self.open_position.episode_number = self.get_episode_number() + 'E'
            self.open_position.item_name = order.item_name
            self.open_position.virtual_open_amount = old_open_position.virtual_open_amount
            self.orders[self.open_position.episode_number] = self.open_position
        self.open_position.order_price = order.order_price
        self.open_position.executed_time = order.executed_time
        self.open_position.order_number = order.order_number
        self.open_position.order_position = order.order_position
        self.open_position.order_state = order.order_state
        self.open_position.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT:
            self.open_position.order_amount += order.order_amount
            self.open_position.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.open_position.open_amount -= executed_amount
            self.open_position.virtual_open_amount -= executed_amount
            self.open_position.executed_amount_sum += executed_amount
            if not self.open_position.open_amount:
                if self.trade_position == PURCHASE:
                    self.open_position_purchase_history[self.open_position.executed_time] = self.open_position.executed_price_avg
                else:
                    self.open_position_sale_history[self.open_position.executed_time] = self.open_position.executed_price_avg

    def update_close_position(self, order):
        executed_amount = abs(order.executed_amount)
        if self.episode_count != self.close_position.get_episode_count():
            old_close_position = self.close_position
            self.close_position = Episode()
            self.close_position.episode_number = self.get_episode_number() + 'S'
            self.close_position.item_name = order.item_name
            self.close_position.order_price = order.order_price
            self.close_position.virtual_open_amount = old_close_position.virtual_open_amount
            self.orders[self.close_position.episode_number] = self.close_position
        self.close_position.executed_time = order.executed_time
        self.close_position.order_number = order.order_number
        self.close_position.order_position = order.order_position
        self.close_position.order_state = order.order_state
        self.close_position.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT:
            self.close_position.order_amount += order.order_amount
            self.close_position.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.close_position.open_amount -= executed_amount
            self.close_position.virtual_open_amount -= executed_amount
            self.close_position.executed_amount_sum += executed_amount
            self.close_position.profit += order.profit
            self.close_position.net_profit += order.net_profit
            self.total_profit += order.profit
            self.total_fee += order.total_fee
            self.net_profit += order.net_profit
            if not self.close_position.open_amount:
                if self.trade_position == SELL:
                    self.close_position_purchase_history[self.close_position.executed_time] = self.close_position.executed_price_avg
                else:
                    self.close_position_sale_history[self.close_position.executed_time] = self.close_position.executed_price_avg

        if self.stop_loss_ordered and not order.open_amount:
            self.stop_loss_ordered = False

    def customize_past_chart(self, item):
        chart = item.chart
        chart['MA5'] = chart.Close.rolling(5, 1).mean().apply(lambda x:round(x, 3))
        chart['MA10'] = chart.Close.rolling(10, 1).mean().apply(lambda x:round(x, 3))
        chart['MA20'] = chart.Close.rolling(20, 1).mean().apply(lambda x:round(x, 3))
        chart['Diff5'] = chart.MA5.diff().fillna(0).apply(lambda x:round(x, 3))
        chart['Diff10'] = chart.MA10.diff().fillna(0).apply(lambda x:round(x, 3))
        chart['Diff20'] = chart.MA20.diff().fillna(0).apply(lambda x:round(x, 3))
        chart['DiffDiff5'] = chart.Diff5.diff().fillna(0).apply(lambda x:round(x, 3))
        chart['DiffDiff10'] = chart.Diff10.diff().fillna(0).apply(lambda x:round(x, 3))
        chart['DiffDiff20'] = chart.Diff20.diff().fillna(0).apply(lambda x:round(x, 3))

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

        current_time = chart.index[-1]
        chart.loc[current_time, 'MA5'] = round(chart.Close[ma5:].mean(), 3)
        chart.loc[current_time, 'MA10'] = round(chart.Close[ma10:].mean(), 3)
        chart.loc[current_time, 'MA20'] = round(chart.Close[ma20:].mean(), 3)
        chart.loc[current_time, 'Diff5'] = round(chart.MA5[-1] - chart.MA5[-2], 3)
        chart.loc[current_time, 'Diff10'] = round(chart.MA10[-1] - chart.MA10[-2], 3)
        chart.loc[current_time, 'Diff20'] = round(chart.MA20[-1] - chart.MA20[-2], 3)
        chart.loc[current_time, 'DiffDiff5'] = round(chart.Diff5[-1] - chart.Diff5[-2], 3)
        chart.loc[current_time, 'DiffDiff10'] = round(chart.Diff10[-1] - chart.Diff10[-2], 3)
        chart.loc[current_time, 'DiffDiff20'] = round(chart.Diff20[-1] - chart.Diff20[-2], 3)

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
        self.trader.ax.text(current_time + 0.5, current_price, format(current_price, ',.2f'))

        # Moving average
        x = range(0, len(chart))
        self.trader.ax.plot(x, chart.MA5, label='MA5', color='Magenta')
        self.trader.ax.plot(x, chart.MA10, label='MA10', color='RoyalBlue')
        self.trader.ax.plot(x, chart.MA20, label='MA20', color='Gold')
        self.trader.ax.legend(loc='best')

        # Slope
        x_range = range(len(chart) - 1, len(chart) + 1)
        self.slope = numpy.polyfit(x_range, chart.MA5[-2:], 1)
        x = range(len(chart) - 20, len(chart))
        y = numpy.poly1d(self.slope)
        self.trader.ax.plot(x, y(x), color='Sienna')

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
        if self.start_time:
            self.annotate_chart(current_time, x1, x2, y1, y2)

        # Draw chart
        candlestick2_ohlc(self.trader.ax, chart.Open, chart.High, chart.Low, chart.Close,
                          width=0.4, colorup='red', colordown='blue')
        self.trader.fig.tight_layout()
        self.trader.canvas.draw()

    def annotate_chart(self, current_time, x1, x2, y1, y2):
        # Start time
        if self.start_time > x1:
            self.trader.ax.plot(self.start_time, self.start_price, marker='o', markersize=3, color='Lime')
            self.trader.ax.vlines(self.start_time, y1, self.start_price, alpha=0.8, linewidth=0.2, color='Green')
            self.trader.ax.text(self.start_time, y1 + 0.05, self.start_comment, color='RebeccaPurple')

        # Trade history
        try:
            for trade_time, price in self.open_position_purchase_history.items():
                x = self.to_min_count2(trade_time)
                if x > x1:
                    self.trader.ax.text(x + 0.5, price, 'P')
                    self.trader.ax.plot(x, price, marker='o', markersize=4, color='Cyan')

            for trade_time, price in self.open_position_sale_history.items():
                x = self.to_min_count2(trade_time)
                if x > x1:
                    self.trader.ax.text(x + 0.5, price, 'S')
                    self.trader.ax.plot(x, price, marker='o', markersize=4, color='Cyan')

            for trade_time, price in self.close_position_purchase_history.items():
                x = self.to_min_count2(trade_time)
                if x > x1:
                    self.trader.ax.text(x - 1, price, 'P')
                    self.trader.ax.plot(x, price, marker='o', markersize=4, color='Yellow')

            for trade_time, price in self.close_position_sale_history.items():
                x = self.to_min_count2(trade_time)
                if x > x1:
                    self.trader.ax.text(x - 1, price, 'S')
                    self.trader.ax.plot(x, price, marker='o', markersize=4, color='Yellow')
        except Exception as e:
            self.warning('Runtime warning(during trade history):', e)

        # chart = self.futures.chart
        # alternate = 1
        # for time in chart.index[x1:]:
        #     time_text = time.strftime('%H%M')
        #     x = self.to_min_count(time_text)
        #     if alternate > 0:
        #         price = chart.loc[time, 'Low']
        #     else:
        #         price = chart.loc[time, 'High']
        #     diffdiff5 = chart.loc[time, 'DiffDiff5']
        #     self.trader.ax.text(x, price, diffdiff5)
        #     alternate *= -1

        # References
        if not self.episode_in_progress:
            return
        reference_offset = 0.5
        self.trader.ax.axhline(self.reference_price, alpha=1, linewidth=0.2, color='Maroon')
        self.trader.ax.text(x1 + reference_offset, self.reference_price, 'Reference')
        self.trader.ax.axhline(self.loss_limit, alpha=1, linewidth=0.2, color='DeepPink')
        self.trader.ax.text(x1 + reference_offset, self.loss_limit, 'Loss limit')
        if self.trade_position == LONG_POSITION:
            self.trader.ax.axhline(self.trade_limit, alpha=1, linewidth=0.2, color='Maroon')
            self.trader.ax.text(x1 + reference_offset, self.trade_limit, 'Buy limit')
        elif self.trade_position == SHORT_POSITION:
            self.trader.ax.axhline(self.trade_limit, alpha=1, linewidth=0.2, color='Maroon')
            self.trader.ax.text(x1 + reference_offset, self.trade_limit, 'Sell limit')

        # Purchases and Sales
        total_range = self.top_price - self.bottom_price
        offset = total_range * 0.005
        x = current_time
        y = self.reference_price
        sales = copy.deepcopy(self.futures.sales)
        for order in sales.values():
            if order.open_amount:
                y += offset
                self.trader.ax.text(x, y, '({}/{})'.format(order.executed_amount_sum, order.order_amount))

        y = self.trade_limit - offset
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