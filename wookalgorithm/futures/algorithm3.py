import numpy
from mplfinance.original_flavor import candlestick2_ohlc
from matplotlib import ticker
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from datetime import datetime
from wookitem import Order, Episode, AlgorithmItem, FuturesAlgorithmItem
from wookutil import wmath
from wookdata import *
from wookalgorithm.futuresalgorithmbase import FuturesAlgorithmBase
import pandas
import math, copy

'''
Original Algorithm (2021, 07, 15)
1. Price average first degree regression model
2. Dynamic volatility (no shift, moving loss cut) 
3. Limit order
'''

class FMAlgorithm3(FuturesAlgorithmBase):
    def __init__(self, trader, log):
        super().__init__(trader, log)
        self.futures = None
        self.slope = None
        self.long_position_history = dict()
        self.short_position_history = dict()

        # Regression
        self.polynomial_features1 = PolynomialFeatures(degree=1, include_bias=False)
        self.polynomial_features2 = PolynomialFeatures(degree=2, include_bias=False)
        self.polynomial_features3 = PolynomialFeatures(degree=3, include_bias=False)
        self.linear_regression = LinearRegression()
        self.r3_interval = 9
        self.r1_interval = 30
        self.par1_slope_interval = 4

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

    def set_reference(self, price):
        self.reference_price = price
        if self.trade_position == LONG_POSITION:
            self.loss_limit = self.reference_price - self.loss_cut
            self.episode_amount = int(self.capital // (self.reference_price * MULTIPLIER))
        elif self.trade_position == SHORT_POSITION:
            self.loss_limit = self.reference_price + self.loss_cut
            self.episode_amount = int(self.capital // (self.reference_price * MULTIPLIER))

    def shift_reference_up(self):
        self.set_reference(self.reference_price + self.loss_cut)

    def shift_reference_down(self):
        self.set_reference(self.reference_price - self.loss_cut)

    def market_status(self, item):
        if not self.start_time:
            self.start_work(item.current_price)

        # Update chart
        self.update_chart_prices(item.item_code, item.current_price, item.volume)

        if self.work_in_progress():
            return

        # For debugging
        chart = self.futures.chart
        # pandas.set_option('display.max_columns', 5)
        chart = chart[-3:]
        chart = chart.loc[:, ['PAR3_DiffDiffDiff', 'MAR3_DiffDiffDiff', 'PAR1_Slope', 'PAR1_SlopeSlope']]
        chart.columns = ['PAR3', 'MAR3', 'PAR1 Slope', 'PAR1 SlopeSlope']
        # print(chart)
        # print('------------------------------------------------------------------------------------')

        self.correct_orders()
        # self.consider_stop_loss(item.current_price)
        # Purchase decision & shift transition
        # if self.episode_in_progress:
        #     self.consider_stop_loss(item.current_price)
        #     self.consider_take_profit(item.current_price)
        # else:
        #     self.consider_transaction(item.current_price)

    def start_work(self, current_price):
        self.start_time_text = datetime.now().strftime('%H:%M')
        self.start_time = self.to_min_count(self.start_time_text)
        self.start_price = current_price
        self.start_comment = 'start\n' + self.start_time_text + '\n' + format(self.start_price, ',')

        # Initial order
        self.episode_count += 1
        self.episode_amount = int(self.capital // (current_price * MULTIPLIER))
        chart = self.futures.chart
        buy_limit = self.get_buy_limit()
        sell_limit = self.get_sell_limit()
        self.buy(buy_limit, self.episode_amount, 'LIMIT')
        self.sell(sell_limit, self.episode_amount, 'LIMIT')
        self.trade_position = NEUTRAL_POSITION

    def work_in_progress(self):
        # if self.futures.ordered:
        #     self.post_without_repetition('(BLOCK)', 'order not executed completely')
        #     return True
        if self.open_purchase_correct_orders:
            self.post('(BLOCK)', 'open purchase correct orders', self.open_purchase_correct_orders)
            return True
        elif self.open_sale_correct_orders:
            self.post('(BLOCK)', 'open sale correct orders', self.open_sale_correct_orders)
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
        if chart.PAR1_Slope[-1] >= 0:
            self.post_without_repetition('Bull Market')
            return True
        else:
            return False

    def bear_market(self):
        chart = self.futures.chart
        if chart.PAR1_Slope[-1] < 0:
            self.post_without_repetition('Bear Market')
            return True
        else:
            return False

    def over_valued(self, current_price):
        chart = self.futures.chart
        # if chart.PAR1[-1] < current_price < chart.PAR1[-1] + self.loss_cut:
        if chart.PAR1[-1] < current_price:
            self.post_magenta('Over Valued!')
            return True
        else:
            return False

    def under_valued(self, current_price):
        chart = self.futures.chart
        # if chart.PAR1[-1] - self.loss_cut < current_price < chart.PAR1[-1]:
        if current_price < chart.PAR1[-1]:
            self.post_magenta('Under Valued!')
            return True
        else:
            return False

    def under_buy_limit(self, current_price):
        chart = self.futures.chart
        if current_price <= chart.PAR1[-1] - self.interval:
            self.post_magenta('Under Buy Limit!')
            return True
        else:
            return False

    def over_sell_limit(self, current_price):
        chart = self.futures.chart
        if current_price >= chart.PAR1[-1] + self.interval:
            self.post_magenta('Over Sell Limit!')
            return True
        else:
            return False

    def overshooting(self, current_price):
        chart = self.futures.chart
        if current_price >= chart.PAR1[-1] + self.loss_cut:
            self.post_cyan('Overshooting!!')
            return True
        else:
            return False

    def undershooting(self, current_price):
        chart = self.futures.chart
        if current_price <= chart.PAR1[-1] - self.loss_cut:
            self.post_cyan('Undershooting!!')
            return True
        else:
            return False

    def turnaround(self):
        return
        chart = self.futures.chart

        if (self.indicator.MA5_R3_Diff[-4] < 0) and (self.indicator.MA5_R3_Diff[-2] > 0):
            return True
        else:
            return False

    def downswing(self):
        return
        chart = self.futures.chart

        if (self.indicator.MA5_R3_Diff[-4] > 0) and (self.indicator.MA5_R3_Diff[-2] < 0):
            return True
        else:
            return False

    def buy(self, price, amount, order_type='LIMIT'):
        # self.episode_count += 1
        self.episode_in_progress = True
        # self.trade_position = LONG_POSITION
        self.set_reference(price)
        # self.futures.purchase.ordered = True
        # self.open_position.virtual_open_amount += self.episode_amount
        purchase_amount = self.episode_amount if not amount else amount
        self.futures.buy(price, purchase_amount, order_type)

    def sell(self, price, amount, order_type='LIMIT'):
        # self.episode_count += 1
        self.episode_in_progress = True
        # self.trade_position = SHORT_POSITION
        self.set_reference(price)
        # self.futures.sale.ordered = True
        # self.open_position.virtual_open_amount += self.episode_amount
        sale_amount = self.episode_amount if not amount else amount
        self.futures.sell(price, sale_amount, order_type)

    def correct_orders(self):
        if self.long_position.open_amount:
            buy_limit = self.get_buy_limit()
            if self.long_position.order_price != buy_limit:
                self.open_purchase_correct_orders = len(self.futures.purchases)
                self.futures.correct_purchases(buy_limit)
        elif self.short_position.open_amount:
            sell_limit = self.get_sell_limit()
            if self.short_position.order_price != sell_limit:
                self.open_sale_correct_orders = len(self.futures.sales)
                self.futures.correct_sales(sell_limit)

    def consider_transaction(self, current_price):
        # if self.bull_market() and self.under_buy_limit(current_price):
        if self.under_buy_limit(current_price):
            self.post('GO LONG!!')
            self.buy(current_price, 0, 'MARKET')
        # elif self.bear_market() and self.over_sell_limit(current_price):
        elif self.over_sell_limit(current_price):
            self.post('GO SHORT!!')
            self.sell(current_price, 0, 'MARKET')

    def consider_take_profit(self, current_price):
        if self.trade_position == LONG_POSITION:
            # if self.overshooting(current_price):
            if self.over_sell_limit(current_price):
                self.post('TAKE PROFIT BY OVERSHOOTING!')
                self.counter_trade()
        elif self.trade_position == SHORT_POSITION:
            # if self.undershooting(current_price):
            if self.under_buy_limit(current_price):
                self.post('TAKE PROFIT BY UNDERSHOOTING!')
                self.counter_trade()

    def consider_stop_loss(self, current_price):
        if self.trade_position == LONG_POSITION:
            if self.undershooting(current_price):
                self.post('STOP LOSS BY UNDERSHOOTING!')
                self.counter_trade()
        elif self.trade_position == SHORT_POSITION:
            if self.overshooting(current_price):
                self.post('STOP LOSS BY OVERSHOOTING!')
                self.counter_trade()

    def counter_trade(self):
        if self.trade_position == LONG_POSITION:
            self.open_cancel_orders = len(self.futures.sales)
            self.stop_loss_ordered = True
            self.futures.sell_off()
            self.time_off()
        elif self.trade_position == SHORT_POSITION:
            self.open_cancel_orders = len(self.futures.purchases)
            self.stop_loss_ordered = True
            self.futures.buy_off()
            self.time_off()

    def shift_transition(self, current_price):
        if self.trade_position == LONG_POSITION:
            self.long_position_shift(current_price)
        elif self.trade_position == SHORT_POSITION:
            self.short_position_shift(current_price)

    def long_position_shift(self, current_price):
        if current_price >= self.reference_price + self.loss_cut:
            self.post('Situation 1')
            self.shift_reference_up()
            # self.open_purchase_correct_orders = len(self.futures.purchases)
            # if self.open_purchase_correct_orders:
            #     if self.bull_market():
            #         self.futures.correct_purchases(self.trade_limit)
            #     else:
            #         self.open_purchase_cancel_orders = len(self.futures.purchases)
            #         if self.open_purchase_cancel_orders:
            #             self.futures.cancel_purchases()
            # elif self.futures.holding_amount:
            #     self.loss_limit -= self.loss_cut
        elif current_price <= self.loss_limit:
            self.post('Situation 4')
            # self.shift_reference_down()
            if self.futures.holding_amount:
                self.post('STOP LOSS BY LOSS CUT!!')
                # self.stop_loss()

    def short_position_shift(self, current_price):
        if current_price < self.reference_price - self.loss_cut:
            self.post('Situation 1')
            self.shift_reference_down()
            # self.open_sale_correct_orders = len(self.futures.sales)
            # if self.open_sale_correct_orders:
            #     if self.bear_market():
            #         self.futures.correct_sales(self.trade_limit)
            #     else:
            #         self.open_sale_cancel_orders = len(self.futures.sales)
            #         if self.open_sale_cancel_orders:
            #             self.futures.cancel_sales()
            # elif self.futures.holding_amount:
            #     self.loss_limit += self.loss_cut
        elif current_price >= self.loss_limit:
            self.post('Situation 4')
            # self.shift_reference_up()
            if self.futures.holding_amount:
                self.post('STOP LOSS BY LOSS CUT!!')
                # self.stop_loss()

    def update_execution_info(self, order):
        # Update Algorithm item orders
        self.futures.update_orders(order)

        # Update algorithm item contracts
        if order.executed_amount:
            if self.futures.holding_amount * order.executed_amount >= 0:
                self.futures.add_contract(order)
            else:
                self.futures.settle_contracts(order)

        # Update episode positions
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.update_long_position(order)
        elif order.order_position in (SELL, CORRECT_SELL):
            self.update_short_position(order)

        # Order processing
        # self.set_position_by(self.futures)
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
            self.set_reference(self.open_position.executed_price_avg)
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
            self.episode_in_progress = False

    def update_long_position(self, order):
        executed_amount = abs(order.executed_amount)
        self.long_position.episode_number = self.get_episode_number() + 'L'
        self.long_position.item_name = order.item_name
        # self.long_position.virtual_open_amount = old_open_position.virtual_open_amount
        self.orders[self.long_position.episode_number] = self.long_position
        self.long_position.order_price = order.order_price
        self.long_position.executed_time = order.executed_time
        self.long_position.order_number = order.order_number
        self.long_position.order_position = order.order_position
        self.long_position.order_state = order.order_state
        self.long_position.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT and order.order_position == PURCHASE:
            self.long_position.order_amount += order.order_amount
            self.long_position.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.set_reference(self.long_position.executed_price_avg)
            self.long_position.open_amount -= executed_amount
            self.long_position.virtual_open_amount -= executed_amount
            self.long_position.executed_amount_sum += executed_amount

            self.short_position.profit += order.profit
            self.short_position.net_profit += order.net_profit
            self.total_profit += order.profit
            self.total_fee += order.total_fee
            self.net_profit += order.net_profit

            sell_limit = self.get_sell_limit()
            self.sell(sell_limit, executed_amount, 'LIMIT')

            self.long_position_history[self.long_position.executed_time] = self.long_position.executed_price_avg

    def update_short_position(self, order):
        executed_amount = abs(order.executed_amount)
        self.short_position.episode_number = self.get_episode_number() + 'S'
        self.short_position.item_name = order.item_name
        self.short_position.order_price = order.order_price
        # self.short_position.virtual_open_amount = old_close_position.virtual_open_amount
        self.orders[self.short_position.episode_number] = self.short_position
        self.short_position.executed_time = order.executed_time
        self.short_position.order_number = order.order_number
        self.short_position.order_position = order.order_position
        self.short_position.order_state = order.order_state
        self.short_position.executed_price_avg = order.executed_price_avg
        if order.order_state == RECEIPT and order.order_position == SELL:
            self.short_position.order_amount += order.order_amount
            self.short_position.open_amount += order.open_amount
        elif order.order_state == ORDER_EXECUTED:
            self.short_position.open_amount -= executed_amount
            self.short_position.virtual_open_amount -= executed_amount
            self.short_position.executed_amount_sum += executed_amount

            self.long_position.profit += order.profit
            self.long_position.net_profit += order.net_profit
            self.total_profit += order.profit
            self.total_fee += order.total_fee
            self.net_profit += order.net_profit

            buy_limit = self.get_buy_limit()
            self.buy(buy_limit, executed_amount, 'LIMIT')

            self.short_position_history[self.short_position.executed_time] = self.short_position.executed_price_avg

        if self.stop_loss_ordered and not order.open_amount:
            self.stop_loss_ordered = False
            self.episode_in_progress = False

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
        chart['PA'] = round((chart.High + chart.Low) / 2, 3)
        chart[['X1', 'PAR1', 'PAR1_Slope', 'PAR1_SlopeSlope', 'BL', 'SL', 'LLL', 'ULL']] = 0
        chart[['X3', 'PAR3', 'PAR3_Diff', 'PAR3_DiffDiff', 'PAR3_DiffDiffDiff']] = 0
        chart[['MA5R3', 'MA5R3_Diff', 'MA5R3_DiffDiff', 'MA5R3_DiffDiffDiff']] = 0

        x1, PAR1 = self.get_linear_regression(chart, chart.PA, self.r1_interval)
        x3, PAR3 = self.get_cubic_regression(chart, chart.PA, self.r3_interval)
        x3, MA5R3 = self.get_cubic_regression(chart, chart.MA5, self.r3_interval)

        chart_len = len(chart)
        x1_len = self.r1_interval
        if chart_len < self.r1_interval:
            x1_len = chart_len
        x1_interval = chart.index[-x1_len:]
        x3_len = self.r3_interval
        if chart_len < self.r3_interval:
            x3_len = chart_len
        x3_interval = chart.index[-x3_len:]

        PAR1_Slope = numpy.polyfit(x1, PAR1, 1)[0]
        chart.loc[x1_interval, 'X1'] = x1
        chart.loc[x1_interval, 'PAR1_Slope'] = PAR1_Slope

        x_slope_interval = chart.index[-self.par1_slope_interval:]
        x_slopeslope = chart.loc[x_slope_interval, 'X1']
        y_slopeslope = chart.loc[x_slope_interval, 'PAR1_Slope']
        PAR1_SlopeSlope = numpy.polyfit(x_slopeslope, y_slopeslope, 1)[0]

        chart.loc[x1_interval, 'PAR1'] = PAR1

        chart.loc[x1_interval, 'BL'] = PAR1 - self.interval
        chart.loc[x1_interval, 'SL'] = PAR1 + self.interval
        chart.loc[x1_interval, 'LLL'] = PAR1 - self.loss_cut
        chart.loc[x1_interval, 'ULL'] = PAR1 + self.loss_cut

        chart.loc[x1_interval, 'PAR1_SlopeSlope'] = PAR1_SlopeSlope
        chart.loc[x3_interval, 'X3'] = x3
        chart.loc[x3_interval, 'PAR3'] = PAR3
        chart.loc[x3_interval, 'PAR3_Diff'] = chart.PAR3.diff().fillna(0)
        chart.loc[x3_interval, 'PAR3_DiffDiff'] = chart.PAR3_Diff.diff().fillna(0)
        chart.loc[x3_interval, 'PAR3_DiffDiffDiff'] = chart.PAR3_DiffDiff.diff().fillna(0)
        chart.loc[x3_interval, 'MAR3'] = MA5R3
        chart.loc[x3_interval, 'MAR3_Diff'] = chart.MAR3.diff().fillna(0)
        chart.loc[x3_interval, 'MAR3_DiffDiff'] = chart.MAR3_Diff.diff().fillna(0)
        chart.loc[x3_interval, 'MAR3_DiffDiffDiff'] = chart.MAR3_DiffDiff.diff().fillna(0)

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
        chart.loc[current_time, 'PA'] = round(((chart.High[-1] + chart.Low[-1]) / 2), 3)

        x1, PAR1 = self.get_linear_regression(chart, chart.PA, self.r1_interval)
        x3, PAR3 = self.get_cubic_regression(chart, chart.PA, self.r3_interval)
        x3, MA5R3 = self.get_cubic_regression(chart, chart.MA5, self.r3_interval)

        chart_len = len(chart)
        x1_len = self.r1_interval
        x3_len = self.r3_interval
        if chart_len < self.r1_interval:
            x1_len = chart_len
        x1_interval = chart.index[-x1_len:]
        if chart_len < self.r3_interval:
            x3_len = chart_len
        x3_interval = chart.index[-x3_len:]

        PAR1_Slope = numpy.polyfit(x1, PAR1, 1)[0]
        chart.loc[x1_interval, 'X1'] = x1
        chart.loc[x1_interval, 'PAR1'] = PAR1

        chart.loc[x1_interval, 'BL'] = PAR1 - self.interval
        chart.loc[x1_interval, 'SL'] = PAR1 + self.interval
        chart.loc[x1_interval, 'LLL'] = PAR1 - self.loss_cut
        chart.loc[x1_interval, 'ULL'] = PAR1 + self.loss_cut

        x_slope_interval = chart.index[-self.par1_slope_interval:]
        x_slopeslope = chart.loc[x_slope_interval, 'X1']
        y_slopeslope = chart.loc[x_slope_interval, 'PAR1_Slope']
        PAR1_SlopeSlope = numpy.polyfit(x_slopeslope, y_slopeslope, 1)[0]

        chart.loc[chart.index[-1], 'PAR1_Slope'] = PAR1_Slope
        chart.loc[chart.index[-1], 'PAR1_SlopeSlope'] = PAR1_SlopeSlope
        chart.loc[x3_interval, 'X3'] = x3
        chart.loc[x3_interval, 'PAR3'] = PAR3
        chart.loc[x3_interval, 'PAR3_Diff'] = chart.PAR3.diff().fillna(0)
        chart.loc[x3_interval, 'PAR3_DiffDiff'] = chart.PAR3_Diff.diff().fillna(0)
        chart.loc[chart.index[-1], 'PAR3_DiffDiffDiff'] = chart.PAR3_DiffDiff[-1] - chart.PAR3_DiffDiff[-2]
        chart.loc[x3_interval, 'MAR3'] = MA5R3
        chart.loc[x3_interval, 'MAR3_Diff'] = chart.MAR3.diff().fillna(0)
        chart.loc[x3_interval, 'MAR3_DiffDiff'] = chart.MAR3_Diff.diff().fillna(0)
        chart.loc[chart.index[-1], 'MAR3_DiffDiffDiff'] = chart.MAR3_DiffDiff[-1] - chart.MAR3_DiffDiff[-2]

    def display_chart(self):
        chart = self.futures.chart
        chart_len = len(chart)
        if not chart_len:
            return

        self.trader.ax.clear()

        # Axis ticker formatting
        if chart_len // 30 > len(self.chart_locator) - 1:
            for index in range(len(self.chart_locator) * 30, chart_len, 30):
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
        current_time = chart_len
        current_price = chart.Close.iloc[-1]
        self.trader.ax.text(current_time + 0.5, current_price, format(current_price, ',.2f'))

        # Moving average
        x = range(0, len(chart))
        self.trader.ax.plot(x, chart.MA5, label='MA5', color='Magenta')
        self.trader.ax.plot(x, chart.MA10, label='MA10', color='RoyalBlue')
        self.trader.ax.plot(x, chart.MA20, label='MA20', color='Gold')
        self.trader.ax.legend(loc='best')

        # Slope
        x_range = range(chart_len - 1, chart_len + 1)
        self.slope = numpy.polyfit(x_range, chart.MA5[-2:], 1)
        x = range(chart_len - 20, chart_len)
        y = numpy.poly1d(self.slope)
        self.trader.ax.plot(x, y(x), color='Sienna')

        # Regression
        x1_len = self.r1_interval
        x3_len = self.r3_interval
        if chart_len < x1_len:
            x1_len = chart_len
        if chart_len < x3_len:
            x3_len = chart_len

        self.trader.ax.plot(chart.X1[-x1_len:], chart.PAR1[-x1_len:], color='DarkOrange')
        self.trader.ax.plot(chart.X3[-x3_len:], chart.PAR3[-x3_len:], color='Cyan')
        self.trader.ax.plot(chart.X3[-x3_len:], chart.MAR3[-x3_len:], color='DarkSlateGray')
        self.trader.ax.plot(chart.X1[-x1_len:], chart.PAR1[-x1_len:] + self.loss_cut, color='Gray')
        self.trader.ax.plot(chart.X1[-x1_len:], chart.PAR1[-x1_len:] - self.loss_cut, color='Gray')
        self.trader.ax.plot(chart.X1[-x1_len:], chart.PAR1[-x1_len:] - self.interval, color='DarkGray')
        self.trader.ax.plot(chart.X1[-x1_len:], chart.PAR1[-x1_len:] + self.interval, color='DarkGray')

        # Set lim
        x2 = chart_len
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
        # try:
        #     for trade_time, price in self.open_position_purchase_history.items():
        #         x = self.to_min_count2(trade_time)
        #         if x > x1:
        #             self.trader.ax.text(x + 0.5, price, 'P')
        #             self.trader.ax.plot(x, price, marker='o', markersize=4, color='Cyan')
        #     for trade_time, price in self.open_position_sale_history.items():
        #         x = self.to_min_count2(trade_time)
        #         if x > x1:
        #             self.trader.ax.text(x + 0.5, price, 'S')
        #             self.trader.ax.plot(x, price, marker='o', markersize=4, color='Cyan')
        #     for trade_time, price in self.close_position_purchase_history.items():
        #         x = self.to_min_count2(trade_time)
        #         if x > x1:
        #             self.trader.ax.text(x - 1, price, 'P')
        #             self.trader.ax.plot(x, price, marker='o', markersize=4, color='Bitter lime')
        #     for trade_time, price in self.close_position_sale_history.items():
        #         x = self.to_min_count2(trade_time)
        #         if x > x1:
        #             self.trader.ax.text(x - 1, price, 'S')
        #             self.trader.ax.plot(x, price, marker='o', markersize=4, color='Bitter lime')
        try:
            for trade_time, price in self.long_position_history.items():
                x = self.to_min_count2(trade_time)
                if x > x1:
                    self.trader.ax.text(x + 0.5, price, 'P')
                    self.trader.ax.plot(x, price, marker='o', markersize=4, color='SkyBlue')
            for trade_time, price in self.short_position_history.items():
                x = self.to_min_count2(trade_time)
                if x > x1:
                    self.trader.ax.text(x + 0.5, price, 'S')
                    self.trader.ax.plot(x, price, marker='o', markersize=4, color='MidNightBlue')
        except Exception as e:
            self.warning('Runtime warning(during trade history):', e)

        # References
        # if not self.episode_in_progress:
        #     return
        # reference_offset = 0.5
        # self.trader.ax.axhline(self.reference_price, alpha=1, linewidth=0.2, color='Maroon')
        # self.trader.ax.text(x1 + reference_offset, self.reference_price, 'Reference')
        # self.trader.ax.axhline(self.loss_limit, alpha=1, linewidth=0.2, color='DeepPink')
        # self.trader.ax.text(x1 + reference_offset, self.loss_limit, 'Loss limit')
        # # if self.trade_position == LONG_POSITION:
        # #     self.trader.ax.axhline(self.trade_limit, alpha=1, linewidth=0.2, color='Maroon')
        # #     self.trader.ax.text(x1 + reference_offset, self.trade_limit, 'Buy limit')
        # # elif self.trade_position == SHORT_POSITION:
        # #     self.trader.ax.axhline(self.trade_limit, alpha=1, linewidth=0.2, color='Maroon')
        # #     self.trader.ax.text(x1 + reference_offset, self.trade_limit, 'Sell limit')

        # Purchases and Sales
        chart = self.futures.chart
        total_range = self.top_price - self.bottom_price
        offset = total_range * 0.025
        x = current_time
        y = chart.ULL[-1]
        sales = copy.deepcopy(self.futures.sales)
        for order in sales.values():
            if order.open_amount:
                y += offset
                self.trader.ax.text(x, y, '({}/{})'.format(order.executed_amount_sum, order.order_amount))

        y = chart.LLL[-1] - offset
        purchases = copy.deepcopy(self.futures.purchases)
        for order in purchases.values():
            if order.open_amount:
                y -= offset
                self.trader.ax.text(x, y, '({}/{})'.format(order.executed_amount_sum, order.order_amount))

    def get_regression(self, x, y, interval, predict_len, polynomial_features):
        if interval is None:
            interval = self.r3_interval

        x_len = len(x)
        if x_len < interval:
            interval = x_len

        x2 = x_len
        x1 = x2 - interval
        x3 = x2 + predict_len
        x_regression = numpy.arange(x1, x3)
        x_reshape = x_regression.reshape(-1, 1)
        x_fitted = polynomial_features.fit_transform(x_reshape)
        self.linear_regression.fit(x_fitted, y.values[x1:x2])
        y_regression = self.linear_regression.predict(x_fitted)

        return x_regression, y_regression

    def get_linear_regression(self, x, y, interval=None, predict_len=0):
        x_regression, y_regression = self.get_regression(x, y, interval, predict_len, self.polynomial_features1)
        return x_regression, y_regression

    def get_quadratic_regression(self, x, y, interval=None, predict_len=0):
        x_regression, y_regression = self.get_regression(x, y, interval, predict_len, self.polynomial_features2)
        return x_regression, y_regression

    def get_cubic_regression(self, x, y, interval=None, predict_len=0):
        x_regression, y_regression = self.get_regression(x, y, interval, predict_len, self.polynomial_features3)
        return x_regression, y_regression

    def get_buy_limit(self):
        buy_limit = float(self.futures.chart.PAR1[-1]) - self.interval
        corrected_buy_limit = wmath.get_nearest_bottom(buy_limit)
        return corrected_buy_limit

    def get_sell_limit(self):
        sell_limit = float(self.futures.chart.PAR1[-1]) + self.interval
        corrected_sell_limit = wmath.get_nearest_top(sell_limit)
        return corrected_sell_limit

    def get_max_price(self, x1, x2):
        max_price = self.futures.chart.High[x1:x2].max()
        return max_price

    def get_min_price(self, x1, x2):
        min_price = self.futures.chart.Low[x1:x2].min()
        return min_price