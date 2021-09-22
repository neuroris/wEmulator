from PyQt5.QtWidgets import QFileDialog, QTableWidgetSelectionRange
from PyQt5.QtCore import Qt
import numpy as np
import pandas
from matplotlib import ticker
from mplfinance.original_flavor import candlestick2_ohlc
from datetime import datetime
from emulatorbase import EmulatorBase
from kiwoom import Kiwoom
from wookutil import TransactionEvent
from wookalgorithm.futures.algorithm6 import FMAlgorithm6
from wookitem import Item, FuturesItem
from deprecated.wookdata_deprecated import *
import math, time


class Emulator(EmulatorBase):
    def __init__(self, log, key):
        self.broker = Kiwoom(self, log, key)
        # self.broker = Bankis(self, log, key)
        self.algorithm = FMAlgorithm6(self, log)
        self.general_account_index = 1
        self.futures_account_index = 0
        super().__init__(log)

        # Initial work
        # self.connect_broker()
        # self.get_account_list()

        # Initial Values
        self.sb_capital.setValue(250000000)
        self.sb_interval.setValue(0.05)
        self.sb_loss_cut.setValue(0.20)
        self.sb_fee.setValue(0.003)
        self.sb_min_transaction.setValue(10)
        self.sb_amount.setValue(1)

        # Init Fields
        self.interval = self.sb_interval.value()
        self.loss_cut = self.sb_loss_cut.value()

        # Test setup
        self.cbb_item_name.setCurrentIndex(3)
        self.on_add_item()
        self.broker.get_stock_prices()
        self.transaction_event = TransactionEvent(self.broker.update_monitoring_items, self.broker.prices)

    def test1(self):
        self.debug('test1 button clicked')

        self.transaction_event.set_interval(0.5)
        self.transaction_event.start()

        # count = 0
        # for index in range(len(self.broker.prices)):
        #     self.transaction_event.start()
        #     # self.broker.update_monitoring_items()
        #     time.sleep(2)
        #     print(count)
        #     count += 1

    def test2(self):
        self.debug('test2 button clicked')

        self.transaction_event.stop()

        # now = datetime.now().replace(second=0, microsecond=0)
        # self.algorithm.trend_start = now

    def connect_broker(self):
        # if self.cb_auto_login.isChecked():
        #     self.broker.auto_login()
        # else:
        #     self.broker.login()
        #     self.broker.set_account_password()

        self.broker.auto_login()

    def get_account_list(self):
        account_list = self.broker.get_account_list()
        if account_list is not None:
            self.cbb_account.addItems(self.broker.account_list)

    def get_deposit(self):
        if self.running_futures_account():
            self.broker.request_futures_deposit_info()
        else:
            self.broker.request_deposit_info()

    def get_portfolio(self):
        if self.running_futures_account():
            self.broker.request_futures_portfolio_info()
        else:
            self.broker.request_portfolio_info()

    def get_order_history(self):
        self.broker.request_order_history()

    def go_chart(self):
        if self.algorithm.is_running:
            return

        self.chart_item_code = self.cbb_item_code.currentText()
        item_name = self.cbb_item_name.currentText()
        self.broker.chart_prices.clear()
        self.chart = self.chart[0:0]
        self.chart_locator = list()
        self.chart_formatter = list()
        self.interval_prices = list()
        self.loss_cut_prices = list()
        self.top_price = 0
        self.bottom_price = 0

        self.broker.chart_prices.clear()
        if self.chart_item_code[:3] == FUTURES_CODE:
            self.broker.request_futures_stock_price_min(self.chart_item_code)
        else:
            self.broker.request_stock_price_min(self.chart_item_code)

        self.broker.is_running_chart = True
        self.timer.start()
        self.on_add_item()
        self.info('Go Charting', item_name)

    def stop_chart(self):
        self.broker.is_running_chart = False
        self.timer.stop()
        self.info('Stop Charting')

    def send_order(self):
        item_code = self.cbb_item_code.currentText()
        order_position = self.cbb_order_position.currentText()
        price = self.sb_price.value()
        amount = self.sb_amount.value()
        order_type = self.cbb_order_type.currentText()
        order_number = self.le_order_number.text()

        self.broker.order(item_code, price, amount, order_position, order_type, order_number)

    def update_deposit_info(self):
        if not self.broker.deposit or not self.broker.orderable_money:
            self.debug('No deposit information')
            return

        deposit = '\\' + self.formalize(self.broker.deposit)
        orderable_money = '\\' + self.formalize(self.broker.orderable_money)
        self.lb_deposit.setText(deposit)
        self.lb_orderable.setText(orderable_money)

    def update_order_variables(self):
        if not self.broker.account_number:
            return

        item = Item()
        item_code = self.cbb_item_code.currentText()
        if item_code in self.broker.portfolio:
            item = self.broker.portfolio[item_code]

        buyable_amount = 'no info'
        if item.current_price != 0 and type(self.broker.orderable_money) != str:
            buyable_amount = self.formalize(self.broker.orderable_money // item.current_price)
        self.lb_buyable.setText(buyable_amount)
        self.lb_sellable.setText(self.formalize(item.holding_amount))
        self.sb_price.setValue(item.current_price)

    def go(self):
        if self.algorithm.is_running:
            self.debug('Algorithm is already running')
            return

        capital = self.sb_capital.value()
        interval = self.sb_interval.value()
        loss_cut = self.sb_loss_cut.value()
        fee = self.sb_fee.value()
        minimum_transaction_amount = self.sb_min_transaction.value()
        self.algorithm.start(self.broker, capital, interval, loss_cut, fee, minimum_transaction_amount)
        self.log_info('Algorithm started')

    def stop(self):
        self.algorithm.stop()
        self.log_info('Algorithm stopped')

    def display_portfolio(self):
        self.clear_table(self.table_portfolio)
        for item in self.broker.portfolio.values():
            self.table_portfolio.insertRow(0)
            self.table_portfolio.setRowHeight(0, 8)
            self.table_portfolio.setItem(0, 0, self.to_item(item.item_name))
            self.table_portfolio.setItem(0, 1, self.to_item_float2(item.current_price))
            self.table_portfolio.setItem(0, 2, self.to_item_float3(item.purchase_price))
            self.table_portfolio.setItem(0, 3, self.to_item_sign(item.holding_amount))
            self.table_portfolio.setItem(0, 4, self.to_item(item.purchase_sum))
            self.table_portfolio.setItem(0, 5, self.to_item(item.evaluation_sum))
            self.table_portfolio.setItem(0, 6, self.to_item(item.total_fee))
            self.table_portfolio.setItem(0, 7, self.to_item(item.tax))
            self.table_portfolio.setItem(0, 8, self.to_item_sign(item.profit))
            self.table_portfolio.setItem(0, 9, self.to_item_sign(item.profit_rate))
            if isinstance(item, FuturesItem):
                self.display_futures_portfolio(item)
        self.table_portfolio.sortItems(0, Qt.AscendingOrder)

    def display_futures_portfolio(self, futures_item):
        for index, contract in enumerate(futures_item.contracts):
            self.table_portfolio.insertRow(0)
            self.table_portfolio.setRowHeight(0, 8)
            self.table_portfolio.setItem(0, 0, self.to_item_gray(contract.item_name + ' ({})'.format(index)))
            self.table_portfolio.setItem(0, 1, self.to_item_float2(contract.current_price))
            self.table_portfolio.setItem(0, 2, self.to_item_float2(contract.purchase_price))
            self.table_portfolio.setItem(0, 3, self.to_item_sign(contract.holding_amount))
            self.table_portfolio.setItem(0, 4, self.to_item(contract.purchase_sum))
            self.table_portfolio.setItem(0, 5, self.to_item(contract.evaluation_sum))
            self.table_portfolio.setItem(0, 6, self.to_item(contract.total_fee))
            self.table_portfolio.setItem(0, 7, self.to_item(contract.tax))
            self.table_portfolio.setItem(0, 8, self.to_item_sign(contract.profit))
            self.table_portfolio.setItem(0, 9, self.to_item_sign(contract.profit_rate))

    def display_monitoring_items(self):
        self.clear_table(self.table_monitoring_items)
        for item in self.broker.monitoring_items.values():
            self.table_monitoring_items.insertRow(0)
            self.table_monitoring_items.setRowHeight(0, 8)
            self.table_monitoring_items.setItem(0, 0, self.to_item(item.item_name))
            self.table_monitoring_items.setItem(0, 1, self.to_item_time(item.transaction_time))
            self.table_monitoring_items.setItem(0, 2, self.to_item_float2(item.current_price))
            self.table_monitoring_items.setItem(0, 3, self.to_item_float2(item.ask_price))
            self.table_monitoring_items.setItem(0, 4, self.to_item_float2(item.bid_price))
            self.table_monitoring_items.setItem(0, 5, self.to_item(item.volume))
            self.table_monitoring_items.setItem(0, 6, self.to_item(item.accumulated_volume))
            self.table_monitoring_items.setItem(0, 7, self.to_item_float2(item.high_price))
            self.table_monitoring_items.setItem(0, 8, self.to_item_float2(item.low_price))
            self.table_monitoring_items.setItem(0, 9, self.to_item_float2(item.open_price))
        self.table_monitoring_items.sortItems(0, Qt.DescendingOrder)

    def display_balance(self):
        self.clear_table(self.table_balance)
        for item in self.broker.balance.values():
            self.table_balance.insertRow(0)
            self.table_balance.setRowHeight(0, 8)
            self.table_balance.setItem(0, 0, self.to_item(item.item_name))
            self.table_balance.setItem(0, 1, self.to_item_float2(item.current_price))
            self.table_balance.setItem(0, 2, self.to_item_float2(item.reference_price))
            self.table_balance.setItem(0, 3, self.to_item(item.purchase_price_avg))
            self.table_balance.setItem(0, 4, self.to_item(item.holding_amount))
            self.table_balance.setItem(0, 5, self.to_item(item.purchase_sum))
            self.table_balance.setItem(0, 6, self.to_item_sign(item.purchase_amount_net_today))
            self.table_balance.setItem(0, 7, self.to_item_sign(item.balance_profit_net_today))
            self.table_balance.setItem(0, 8, self.to_item_sign(item.balance_profit_rate))
            self.table_balance.setItem(0, 9, self.to_item_sign(item.balance_profit_realization))
        self.table_balance.sortItems(0, Qt.DescendingOrder)

    def display_open_orders(self):
        self.clear_table(self.table_open_orders)
        for order in self.broker.open_orders.values():
            self.table_open_orders.insertRow(0)
            self.table_open_orders.setRowHeight(0, 8)
            self.table_open_orders.setItem(0, 0, self.to_item(order.item_name))
            self.table_open_orders.setItem(0, 1, self.to_item_time(order.executed_time))
            self.table_open_orders.setItem(0, 2, self.to_item(order.order_amount))
            self.table_open_orders.setItem(0, 3, self.to_item(order.executed_amount_sum))
            self.table_open_orders.setItem(0, 4, self.to_item(order.open_amount))
            self.table_open_orders.setItem(0, 5, self.to_item_plain(order.order_number))
            self.table_open_orders.setItem(0, 6, self.to_item_plain(order.original_order_number))
            self.table_open_orders.setItem(0, 7, self.to_item_float2(order.order_price))
            self.table_open_orders.setItem(0, 8, self.to_item(order.executed_price_avg))
            self.table_open_orders.setItem(0, 9, self.to_item_center(order.order_position))
            self.table_open_orders.setItem(0, 10, self.to_item_center(order.order_state))
        self.table_open_orders.sortItems(1, Qt.DescendingOrder)

    def display_order_history(self):
        self.clear_table(self.table_order_history)
        for order in self.broker.order_history.values():
            self.table_order_history.insertRow(0)
            self.table_order_history.setRowHeight(0, 8)
            self.table_order_history.setItem(0, 0, self.to_item(order.item_name))
            self.table_order_history.setItem(0, 1, self.to_item_time(order.executed_time))
            self.table_order_history.setItem(0, 2, self.to_item(order.order_amount))
            self.table_order_history.setItem(0, 3, self.to_item(order.executed_amount_sum))
            self.table_order_history.setItem(0, 4, self.to_item(order.open_amount))
            self.table_order_history.setItem(0, 5, self.to_item_plain(order.order_number))
            self.table_order_history.setItem(0, 6, self.to_item_plain(order.original_order_number))
            self.table_order_history.setItem(0, 7, self.to_item_float2(order.order_price))
            self.table_order_history.setItem(0, 8, self.to_item_float2(order.executed_price_avg))
            self.table_order_history.setItem(0, 9, self.to_item_center(order.order_position))
            self.table_order_history.setItem(0, 10, self.to_item_center(order.order_state))
        self.table_order_history.sortItems(1, Qt.DescendingOrder)

    def display_algorithm_trading(self):
        self.clear_table(self.table_algorithm_trading)
        for algorithm_number, order in self.algorithm.orders.items():
            self.table_algorithm_trading.insertRow(0)
            self.table_algorithm_trading.setRowHeight(0, 8)
            self.table_algorithm_trading.setItem(0, 0, self.to_item(order.item_name))
            self.table_algorithm_trading.setItem(0, 1, self.to_item_time(order.executed_time))
            self.table_algorithm_trading.setItem(0, 2, self.to_item_plain(order.episode_number))
            self.table_algorithm_trading.setItem(0, 3, self.to_item_plain(order.order_number))
            self.table_algorithm_trading.setItem(0, 4, self.to_item_center(order.order_position))
            self.table_algorithm_trading.setItem(0, 5, self.to_item_center(order.order_state))
            self.table_algorithm_trading.setItem(0, 6, self.to_item_float2(order.order_price))
            self.table_algorithm_trading.setItem(0, 7, self.to_item_float2(order.executed_price_avg))
            self.table_algorithm_trading.setItem(0, 8, self.to_item(order.order_amount))
            self.table_algorithm_trading.setItem(0, 9, self.to_item(order.executed_amount_sum))
            self.table_algorithm_trading.setItem(0, 10, self.to_item_sign(order.open_amount))
            self.table_algorithm_trading.setItem(0, 11, self.to_item_sign(order.net_profit))
        self.table_algorithm_trading.sortItems(2, Qt.DescendingOrder)

    def clear_table(self, table):
        for row in range(table.rowCount()):
            table.removeRow(0)

    def display_algorithm_results(self):
        total_profit = self.algorithm.total_profit
        formalized_profit = self.formalize(total_profit)
        profit_rate = round(total_profit / self.sb_capital.value() * 100, 2)
        profit_display = '{} ({}%)'.format(formalized_profit, profit_rate)
        self.lb_total_profit.setText(profit_display)

        total_fee = self.algorithm.total_fee
        formalized_fee = self.formalize(total_fee)
        self.lb_total_fee.setText(formalized_fee)

        net_profit = self.algorithm.net_profit
        formalized_net_profit = self.formalize(net_profit)
        net_profit_rate = round(net_profit / self.sb_capital.value() * 100, 2)
        net_profit_display = '{} ({}%)'.format(formalized_net_profit, net_profit_rate)
        self.lb_net_profit.setText(net_profit_display)

    def process_past_chart_prices(self, item_code, chart_prices):
        if self.algorithm.is_running:
            self.algorithm.process_past_chart_prices(item_code, chart_prices)
            return
        elif item_code != self.chart_item_code:
            return

        columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        past_chart = pandas.DataFrame(chart_prices, columns=columns)
        past_chart.Time = pandas.to_datetime(past_chart.Time)
        past_chart.set_index('Time', inplace=True)
        # self.chart = past_chart.append(self.chart)
        self.chart = past_chart

        self.draw_chart.start()

    def update_chart_prices(self, price, volume, item_code):
        if item_code != self.chart_item_code:
            return

        # current_time = datetime.now().replace(second=0, microsecond=0)
        current_time_str = str(self.broker.prices.Time[self.broker.index])
        current_time = datetime.strptime(current_time_str, '%Y%m%d%H%M%S')
        if not len(self.chart):
            price_data = [price, price, price, price, volume]
            self.chart.loc[current_time] = price_data
        elif current_time > self.chart.index[-1]:
            price_data = [price, price, price, price, volume]
            self.chart.loc[current_time] = price_data
        else:
            if price > self.chart.High[-1]:
                self.chart.loc[current_time, 'High'] = price
            elif price < self.chart.Low[-1]:
                self.chart.loc[current_time, 'Low'] = price
            last_price = self.chart.Close[-1]
            self.chart.loc[current_time, 'Close'] = price
            self.chart.loc[current_time, 'Volume'] += volume
            if last_price == price:
                return
        self.draw_chart.start()

    def on_every_minute(self):
        current_time = datetime.now().replace(second=0, microsecond=0)
        if not len(self.chart):
            return
        if current_time > self.chart.index[-1]:
            price = self.chart.Close[-1]
            price_data = [price, price, price, price, 0]
            self.chart.loc[current_time] = price_data
            self.draw_chart.start()

    def display_chart(self):
        if not len(self.chart):
            return

        self.ax.clear()

        # Axis ticker formatting
        if len(self.chart) // 30 > len(self.chart_locator) - 1:
            for index in range(len(self.chart_locator) * 30, len(self.chart), 30):
                time_format = self.chart.index[index].strftime('%H:%M')
                self.chart_locator.append(index)
                self.chart_formatter.append(time_format)
        self.ax.xaxis.set_major_locator(ticker.FixedLocator(self.chart_locator))
        self.ax.xaxis.set_major_formatter(ticker.FixedFormatter(self.chart_formatter))

        # Axis yticks & lines
        max_price = self.chart.High.max()
        min_price = self.chart.Low.min()
        if max_price > self.top_price or min_price < self.bottom_price:
            self.top_price = math.ceil(max_price / self.interval) * self.interval
            self.bottom_price = math.floor(min_price / self.interval) * self.interval
            self.interval_prices = np.arange(self.bottom_price, self.top_price + self.interval, self.interval)
            self.loss_cut_prices = np.arange(self.bottom_price + self.interval - self.loss_cut, self.top_price, self.interval)
        self.ax.grid(axis='x', alpha=0.5)
        self.ax.set_yticks(self.interval_prices)
        for price in self.interval_prices:
            self.ax.axhline(price, alpha=0.5, linewidth=0.2)
        for price in self.loss_cut_prices:
            self.ax.axhline(price, alpha=0.4, linewidth=0.2, color='Gray')

        # Current Price Annotation
        current_time = len(self.chart)
        current_price = self.chart.Close.iloc[-1]
        if self.chart_item_code[:3] == FUTURES_CODE:
            formatted_current_price = format(current_price, ',.2f')
        else:
            formatted_current_price = format(current_price, ',')
        # self.ax.text(current_time + 2, current_price, format(current_price, ','))
        self.ax.text(current_time + 2, current_price, formatted_current_price)

        # Draw Chart
        candlestick2_ohlc(self.ax, self.chart.Open, self.chart.High, self.chart.Low, self.chart.Close,
                          width=0.4, colorup='red', colordown='blue')
        self.fig.tight_layout()
        self.canvas.draw()

    def on_select_account(self, index):
        self.broker.account_number = self.cbb_account.currentText()

        if index == self.futures_account_index:
            self.broker.request_futures_deposit_info()
            self.broker.request_futures_portfolio_info()
            if not self.running_futures_code():
                self.cbb_item_code.setCurrentText('101')
        else:
            self.broker.request_deposit_info()
            self.broker.request_portfolio_info()
            if self.running_futures_code():
                self.cbb_item_code.setCurrentText('')

    def on_select_item_code(self, item_code):
        item_name = CODES.get(item_code)
        if item_name is None:
            item_name = self.broker.get_item_name(item_code)
            if item_name != '':
                CODES[item_code] = item_name
                self.cbb_item_code.addItem(item_code)
                self.cbb_item_name.addItem(item_name)

        if item_code[:3] == FUTURES_CODE:
            self.cbb_order_type.clear()
            self.cbb_order_type.addItems(FUTURES_ORDER_TYPE)
            self.cbb_account.setCurrentIndex(self.futures_account_index)
        else:
            self.cbb_order_type.clear()
            self.cbb_order_type.addItems(ORDER_TYPE)
            self.cbb_account.setCurrentIndex(self.general_account_index)

        self.cbb_item_name.setCurrentText(item_name)
        self.update_order_variables()

    def on_select_item_name(self, index):
        item_name = self.cbb_item_name.currentText()
        item_code = self.broker.get_item_code(item_name)
        self.cbb_item_code.setCurrentText(item_code)

    def on_add_item(self):
        item_code = self.cbb_item_code.currentText()
        item_name = self.cbb_item_name.currentText()
        if item_code in self.broker.monitoring_items:
            return

        item = Item()
        item.item_code = item_code
        item.item_name = item_name
        self.broker.demand_monitoring_items_info(item)
        self.display_monitoring_items()
        self.info(item.item_name, 'trading information begins to be monitored')

    def on_remove_item(self):
        item_code = self.cbb_item_code.currentText()
        item_name = self.cbb_item_name.currentText()
        if item_code not in self.broker.monitoring_items:
            return

        self.broker.init_screen(item_code)
        del self.broker.monitoring_items[item_code]
        self.table_monitoring_items.clearContents()
        self.display_monitoring_items()
        self.info(item_name, 'stock information monitoring is finished')

    def on_select_portfolio_table(self, row, column):
        column_count = self.table_portfolio.columnCount() - 1
        selection_range = QTableWidgetSelectionRange(row, 0, row, column_count)
        self.table_portfolio.setRangeSelected(selection_range, True)

        item_name_column = 0
        item_name_item = self.table_portfolio.item(row, item_name_column)
        item_name = item_name_item.text()
        if item_name[:2] == 'F ':
            item_name = item_name[:8]
        index = self.cbb_item_name.findText(item_name)
        self.cbb_item_name.setCurrentIndex(index)

        current_price_column = 1
        current_price_item = self.table_portfolio.item(row, current_price_column)
        current_price = self.process_type(current_price_item.text())
        self.sb_price.setValue(current_price)

        holding_amount_column = 3
        holding_amount_item = self.table_portfolio.item(row, holding_amount_column)
        holding_amount = self.process_type(holding_amount_item.text())
        self.sb_amount.setValue(abs(holding_amount))

        self.cbb_order_type.setCurrentText('MARKET')
        if holding_amount > 0:
            self.cbb_order_position.setCurrentText('SELL')
        else:
            self.cbb_order_position.setCurrentText('BUY')

    def on_select_trading_items_table(self, row, column):
        column_count = self.table_monitoring_items.columnCount() - 1
        selection_range = QTableWidgetSelectionRange(row, 0, row, column_count)
        self.table_monitoring_items.setRangeSelected(selection_range, True)

        item_name_column = 0
        item_name_item = self.table_monitoring_items.item(row, item_name_column)
        item_name = item_name_item.text()
        index = self.cbb_item_name.findText(item_name)
        self.cbb_item_name.setCurrentIndex(index)

        current_price_column = 2
        current_price_item = self.table_monitoring_items.item(row, current_price_column)
        current_price = self.process_type(current_price_item.text())
        self.sb_price.setValue(current_price)

    def on_select_balance_table(self, row, column):
        column_count = self.table_balance.columnCount() - 1
        selection_range = QTableWidgetSelectionRange(row, 0, row, column_count)
        self.table_balance.setRangeSelected(selection_range, True)

        item_name_column = 0
        item_name_item = self.table_balance.item(row, item_name_column)
        item_name = item_name_item.text()
        index = self.cbb_item_name.findText(item_name)
        self.cbb_item_name.setCurrentIndex(index)

        current_price_column = 1
        current_price_item = self.table_balance.item(row, current_price_column)
        current_price = self.process_type(current_price_item.text())
        self.sb_price.setValue(current_price)

    def on_select_open_orders_table(self, row, column):
        column_count = self.table_order_history.columnCount() - 1
        selection_range = QTableWidgetSelectionRange(row, 0, row, column_count)
        self.table_open_orders.setRangeSelected(selection_range, True)

        item_name_column = 0
        item_name_item = self.table_open_orders.item(row, item_name_column)
        item_name = item_name_item.text()
        index = self.cbb_item_name.findText(item_name)
        self.cbb_item_name.setCurrentIndex(index)

        open_amount_column = 4
        open_amount_item = self.table_open_orders.item(row, open_amount_column)
        open_amount = self.process_type(open_amount_item.text())
        self.sb_amount.setValue(open_amount)

        order_number_column = 5
        order_number_item = self.table_open_orders.item(row, order_number_column)
        order_number = order_number_item.text()
        self.le_order_number.setText(order_number)

        order_price_column = 7
        order_price_item = self.table_open_orders.item(row, order_price_column)
        order_price = self.process_type(order_price_item.text())
        self.sb_price.setValue(order_price)

        order_position_column = 9
        order_position_item = self.table_open_orders.item(row, order_position_column)
        order_position = order_position_item.text()
        if order_position == PURCHASE[-2:]:
            self.cbb_order_position.setCurrentText('CANCEL BUY')
        elif order_position == SELL[-2:]:
            self.cbb_order_position.setCurrentText('CANCEL SELL')

    def on_select_order_history_table(self, row, column):
        column_count = self.table_order_history.columnCount() - 1
        selection_range = QTableWidgetSelectionRange(row, 0, row, column_count)
        self.table_order_history.setRangeSelected(selection_range, True)

        item_name_column = 0
        item_name_item = self.table_order_history.item(row, item_name_column)
        item_name = item_name_item.text()
        index = self.cbb_item_name.findText(item_name)
        self.cbb_item_name.setCurrentIndex(index)

        open_amount_column = 4
        open_amount_item = self.table_order_history.item(row, open_amount_column)
        open_amount = self.process_type(open_amount_item.text())
        self.sb_amount.setValue(open_amount)

        order_number_column = 5
        order_number_item = self.table_order_history.item(row, order_number_column)
        order_number = order_number_item.text()
        self.le_order_number.setText(order_number)

        order_price_column = 7
        order_price_item = self.table_order_history.item(row, order_price_column)
        order_price = self.process_type(order_price_item.text())
        self.sb_price.setValue(order_price)

    def on_select_algorithm_trading_table(self, row, column):
        column_count = self.table_algorithm_trading.columnCount() - 1
        selection_range = QTableWidgetSelectionRange(row, 0, row, column_count)
        self.table_algorithm_trading.setRangeSelected(selection_range, True)

        item_name_column = 0
        item_name_item = self.table_algorithm_trading.item(row, item_name_column)
        item_name = item_name_item.text()
        index = self.cbb_item_name.findText(item_name)
        self.cbb_item_name.setCurrentIndex(index)

        order_number_column = 3
        order_number_item = self.table_algorithm_trading.item(row, order_number_column)
        order_number = order_number_item.text()
        self.le_order_number.setText(order_number)

        order_price_column = 6
        order_price_item = self.table_algorithm_trading.item(row, order_price_column)
        order_price = self.process_type(order_price_item.text())
        if order_price:
            self.sb_price.setValue(order_price)

        open_amount_column = 10
        open_amount_item = self.table_algorithm_trading.item(row, open_amount_column)
        open_amount = self.process_type(open_amount_item.text())
        self.sb_amount.setValue(open_amount)

    def set_algorithm_parameters(self):
        self.interval = self.sb_interval.value()
        self.loss_cut = self.sb_loss_cut.value()
        self.algorithm.capital = self.sb_capital.value()
        self.algorithm.interval = self.interval
        self.algorithm.loss_cut = self.loss_cut
        self.algorithm.fee = self.sb_fee.value()
        self.algorithm.minimum_transaction_amount = self.sb_min_transaction.value()

    def on_edit_save_file(self):
        file = self.le_save_file.text()
        self.broker.log_file = file

    def on_change_save_file(self):
        file = QFileDialog.getOpenFileName(self, 'Select File', self.setting['save_folder'])[0]
        if file != '':
            self.le_save_file.setText(file)
            self.broker.log_file = file

    def running_futures_code(self):
        if self.cbb_item_code.currentText()[:3] == FUTURES_CODE:
            return True
        else:
            return False

    def running_futures_account(self):
        if self.cbb_account.currentIndex() == self.futures_account_index:
            return True
        else:
            return False

    def edit_setting(self):
        self.debug('setting')

    def log(self, *args):
        message = str(args[0])
        for arg in args[1:]:
            message += ' ' + str(arg)
        current_time = datetime.now().strftime('%H:%M:%S') + ' '
        self.te_info.append(current_time + message)
        self.info(message)

    def log_info(self, *args):
        message = str(args[0])
        for arg in args[1:]:
            message += ' ' + str(arg)
        current_time = datetime.now().strftime('%H:%M:%S') + ' '
        self.te_info.append(current_time + message)

    def status(self, *args):
        message = str(args[0])
        for arg in args[1:]:
            message += ' ' + str(arg)
        self.status_bar.showMessage(message)

    def closeEvent(self, event):
        # self.broker.log('Closing process initializing...')
        self.broker.close_process()
        self.broker.clear()
        self.broker.deleteLater()
        self.deleteLater()