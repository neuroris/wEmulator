import copy
import numpy as np
import pandas
from wookutil import WookLog
from wookdata import *

class Item:
    def __init__(self):
        self.item_code = ''
        self.item_name = ''
        self.transaction_time = ''
        self.current_price = 0
        self.purchase_price = 0
        self.ask_price = 0
        self.bid_price = 0
        self.open_price = 0
        self.high_price = 0
        self.low_price = 0
        self.reference_price = 0
        self.purchase_price_avg = 0
        self.purchase_sum = 0
        self.evaluation_sum = 0
        self.purchase_amount = 0
        self.purchase_amount_net_today = 0
        self.order_amount = 0
        self.holding_amount = 0
        self.target_amount = 0
        self.sellable_amount = 0
        self.volume = 0
        self.accumulated_volume = 0
        self.profit = 0
        self.profit_rate = 0.0
        self.profit_realization = 0
        self.profit_realization_rate = 0.0
        self.net_profit = 0
        self.net_profit_rate = 0.0
        self.purchase_fee = 0
        self.evaluation_fee = 0
        self.transaction_fee = 0
        self.total_fee = 0
        self.fee_ratio = 0.0
        self.tax_ratio = 0.0
        self.futures_fee_ratio = 0.0
        self.futures_tax_ratio = 0.0
        self.tax = 0
        self.trade_position = ''

class BalanceItem(Item):
    balance_profit_net_today = 0
    balance_profit_rate = 0.0
    balance_profit_realization = 0
    balance_profit_realization_rate = 0.0

    def __init__(self):
        super().__init__()

class FuturesItem(Item):
    def __init__(self, item, broker):
        super().__init__()
        self.contracts = list()

        self.futures_fee_ratio = broker.futures_fee_ratio
        self.futures_tax_ratio = broker.futures_tax_ratio

        self.item_code = item.item_code
        if item.item_name[:5] == 'KOSPI':
            item.item_name = item.item_name[6:]
        self.item_name = item.item_name + ' - SUM'

    def append(self, item):
        self.contracts.append(item)

        self.current_price = item.current_price
        self.holding_amount += item.holding_amount
        self.purchase_sum += item.purchase_sum
        self.purchase_price = self.purchase_sum / abs(self.holding_amount) / MULTIPLIER
        self.evaluation_sum = int(abs(self.holding_amount) * item.current_price * MULTIPLIER)
        self.purchase_fee = self.purchase_sum * self.futures_fee_ratio
        self.evaluation_fee = self.evaluation_sum * self.futures_fee_ratio
        self.total_fee = int((self.purchase_fee + self.evaluation_fee) / 10) * 10
        self.tax = int(self.evaluation_sum * self.futures_tax_ratio)
        self.profit += item.profit
        self.profit_rate = round(self.profit / self.purchase_sum * 100, 2)

    def pop(self):
        contract = self.contracts.pop(0)

        self.holding_amount -= contract.holding_amount
        if not self.holding_amount:
            return
        self.purchase_sum -= contract.purchase_sum
        self.purchase_price = self.purchase_sum / abs(self.holding_amount) / MULTIPLIER
        self.evaluation_sum = int(abs(self.holding_amount) * contract.current_price * MULTIPLIER)
        self.purchase_fee = self.purchase_sum * self.futures_fee_ratio
        self.evaluation_fee = self.evaluation_sum * self.futures_fee_ratio
        self.total_fee = int((self.purchase_fee + self.evaluation_fee) / 10) * 10
        self.tax = int(self.evaluation_sum * self.futures_tax_ratio)
        self.profit -= contract.profit
        self.profit_rate = round(self.profit / self.purchase_sum * 100, 2)

        return contract

    def add(self, order):
        item = Item()
        item.item_code = order.item_code
        item.item_name = order.item_name
        item.current_price = order.current_price
        item.purchase_price = order.executed_price_avg
        item.holding_amount = order.executed_amount
        item.purchase_sum = int(order.executed_price_avg * abs(order.executed_amount) * MULTIPLIER)
        item.evaluation_sum = int(order.current_price * abs(order.executed_amount) * MULTIPLIER)
        item.purchase_fee = item.purchase_sum * self.futures_fee_ratio
        item.evaluation_fee = item.evaluation_sum * self.futures_fee_ratio
        item.total_fee = int((item.purchase_fee + item.evaluation_fee) / 10) * 10
        item.tax = int(item.evaluation_sum * self.futures_tax_ratio)
        item.profit = (item.evaluation_sum - item.purchase_sum) * np.sign(item.holding_amount)
        # item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)

        if item.purchase_sum == 0:
            print('Item.purchase_sum is zero. check please')
            return
        else:
            item.profit_rate = round(item.profit / item.purchase_sum * 100, 2)

        self.append(item)

    def settle(self, order):
        contract = self.contracts[0]
        contract.holding_amount += order.executed_amount
        contract.purchase_sum = int(abs(contract.holding_amount) * contract.purchase_price * MULTIPLIER)
        contract.purchase_fee = int(contract.purchase_sum * self.futures_fee_ratio)

    def update(self, current_price):
        self.current_price = current_price
        self.holding_amount = 0
        self.purchase_sum = 0
        self.evaluation_sum = 0
        self.purchase_fee = 0
        self.evaluation_fee = 0
        self.total_fee = 0
        self.tax = 0
        self.profit = 0

        for contract in self.contracts:
            contract.current_price = current_price
            contract.evaluation_sum = int(abs(contract.holding_amount) * current_price * MULTIPLIER)
            contract.evaluation_fee = contract.evaluation_sum * self.futures_fee_ratio
            contract.total_fee = int((contract.purchase_fee + contract.evaluation_fee) / 10) * 10
            contract.tax = int(self.evaluation_sum * self.futures_tax_ratio)
            contract.profit = (contract.evaluation_sum - contract.purchase_sum) * np.sign(contract.holding_amount)
            contract.profit = contract.profit - contract.total_fee - contract.tax
            contract.profit_rate = round(contract.profit / contract.purchase_sum * 100, 2)

            self.holding_amount += contract.holding_amount
            self.purchase_sum += contract.purchase_sum
            self.evaluation_sum += contract.evaluation_sum
            self.purchase_fee += contract.purchase_fee
            self.evaluation_fee += contract.evaluation_fee
            self.total_fee += contract.total_fee
            self.tax += contract.tax
            self.purchase_price = self.purchase_sum / abs(self.holding_amount) / MULTIPLIER
            self.profit += contract.profit
            self.profit_rate = round(self.profit / self.purchase_sum * 100, 2)

class Order(Item):
    def __init__(self):
        super().__init__()
        self.executed_time = ''
        self.order_state = ''
        self.order_type = ''
        self.order_position = ''
        self.order_price = 0
        self.executed_price = 0
        self.executed_price_avg = 0
        self.executed_amount = 0
        self.executed_amount_sum = 0
        self.previous_order_amount = 0
        self.open_amount = 0
        self.virtual_open_amount = 0
        self.order_number = 0
        self.original_order_number = 0
        self.executed_order_number = 0
        self.ordered = False

class Episode(Order):
    def __init__(self):
        super().__init__()
        self.episode_number = ''

    def get_episode_count(self):
        if self.episode_number:
            return int(self.episode_number[:-1])
        else:
            return 0

class AlgorithmItem(Order, WookLog):
    def __init__(self, item_code):
        super().__init__()
        self.broker = None
        self.item_code = item_code
        self.item_name = CODES[item_code]
        self.purchase = Order()
        self.sale = Order()
        self.purchases = dict()
        self.sales = dict()
        self.previous_msg = ()
        self.chart = pandas.DataFrame(list(), columns=['Open', 'High', 'Low', 'Close', 'Volume'])

    def set_broker(self, broker):
        self.broker = broker

    def set_log(self, log):
        WookLog.custom_init(self, log)

    def post_cyan(self, *args):
        if args != self.previous_msg:
            self.debug('\033[96mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_green(self, *args):
        if args != self.previous_msg:
            self.debug('\033[92mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_blue(self, *args):
        if args != self.previous_msg:
            self.debug('\033[94mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def update_execution_info(self, order):
        executed_amount = abs(order.executed_amount)
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.purchases[order.order_number] = order
            if not order.open_amount:
                del self.purchases[order.order_number]
            if order.order_state == ORDER_EXECUTED:
                self.holding_amount += executed_amount
                self.purchase_price = order.executed_price
                self.purchase_sum += executed_amount * order.executed_price
                self.purchase_price_avg = self.purchase_sum / self.holding_amount
        elif order.order_position in (SELL, CORRECT_SELL):
            if order.order_number in self.sales:
                old_order = self.sales[order.order_number]
                order.purchase_price = old_order.purchase_price
            else:
                order.purchase_price = self.purchase_price
            if order.order_state == ORDER_EXECUTED:
                self.holding_amount -= executed_amount
                self.purchase_sum = self.purchase_price_avg * self.holding_amount
                order.profit = int((order.executed_price - order.purchase_price) * order.executed_amount)
                purchase_fee = order.purchase_price * executed_amount * (self.fee_ratio / 100)
                sale_fee = order.executed_price_avg * executed_amount * (self.fee_ratio / 100)
                order.transaction_fee = int(purchase_fee + sale_fee)
                order.net_profit = order.profit - order.transaction_fee
                self.profit += order.profit
                self.total_fee += order.transaction_fee
                self.net_profit += order.net_profit
            self.sale = order
            self.sales[order.order_number] = order
            self.sale.ordered = False
            if not order.open_amount:
                del self.sales[order.order_number]
        elif order.order_position == CANCEL_PURCHASE and order.order_state == CONFIRMED:
            if order.original_order_number in self.purchases:
                del self.purchases[order.original_order_number]
        elif order.order_position == CANCEL_SELL and order.order_state == CONFIRMED:
            if order.original_order_number in self.sales:
                del self.sales[order.original_order_number]

        # Update message
        msg = (order.item_name, order.order_position, order.order_state)
        msg += ('order:' + str(order.order_amount), 'executed_each:' + str(order.executed_amount))
        msg += ('open:' + str(order.open_amount), 'number:' + str(order.order_number))
        msg += ('purchase:' + str(order.purchase_price), 'executed:' + str(order.executed_price))
        msg += ('holding:' + str(self.holding_amount),)
        executed_time = str(order.executed_time)
        time_format = executed_time[:2] + ':' + executed_time[2:4] + ':' + executed_time[4:]
        self.post_green('(EXECUTION)', *msg)
        self.post_blue('(DEBUG)', time_format, 'Purchases', len(self.purchases), 'Sales', len(self.sales))

    def buy(self, price, amount, order_type='LIMIT'):
        msg = ('holding:' + str(self.holding_amount), 'price:' + str(price), 'amount:' + str(amount))
        self.post_cyan('(BUY)', *msg)
        self.purchase.ordered = True
        self.target_amount = amount
        self.broker.buy(self.item_code, price, amount, order_type)

    def buy_over(self, price, amount, order_type='LIMIT'):
        if self.purchase.ordered:
            return

        msg = ('holding:' + str(self.holding_amount), 'open:' + str(self.purchase.open_amount))
        self.post_cyan('(BUY_OVER)', *msg)

        self.purchase.ordered = True
        self.target_amount = amount
        if self.purchase.open_amount:
            self.broker.cancel_and_buy(self.purchase, price, amount, order_type)
        else:
            self.broker.buy(self.item_code, price, amount, order_type)

    def buy_up(self):
        if self.purchase.ordered:
            return

        purchase_amount = self.target_amount - self.holding_amount
        refill_amount = purchase_amount - self.purchase.open_amount

        msg = ('holding:'+str(self.holding_amount), 'order:'+str(self.purchase.order_amount))
        msg += ('open:'+str(self.purchase.open_amount), 'refill:'+str(refill_amount))
        if refill_amount:
            msg = ('\033[94mEXECUTED\033[97m',) + msg
        self.post_cyan('(BUY_UP)', *msg)

        if refill_amount:
            self.purchase.ordered = True
            if self.purchase.open_amount:
                self.broker.cancel_and_buy(self.purchase, self.purchase.order_price, purchase_amount)
            else:
                self.broker.buy(self.item_code, self.purchase.order_price, purchase_amount)

    def sell(self, price, amount, order_type='LIMIT'):
        msg = ('holding:' + str(self.holding_amount), 'price:' + str(price), 'amount:' + str(amount))
        self.post_cyan('(SELL)', *msg)

        self.sale.ordered = True
        self.broker.sell(self.item_code, price, amount, order_type)

    def sell_out(self, price):
        if self.sale.ordered:
            return

        sell_amount = self.holding_amount + self.sale.executed_amount_sum - self.sale.order_amount

        msg = ('holding:'+str(self.holding_amount), 'order:'+str(self.sale.order_amount))
        msg += ('executed:'+str(self.sale.executed_amount_sum), 'open:'+str(self.sale.open_amount))
        msg += ('sell:'+str(sell_amount),)
        if sell_amount:
            msg = ('\033[94mEXECUTED\033[97m',) + msg
        self.post_cyan('(SELL_OUT)', *msg)

        if sell_amount:
            self.sale.ordered = True
            if self.sale.open_amount:
                self.broker.cancel_and_sell(self.sale, price, self.holding_amount)
            else:
                self.broker.sell(self.item_code, price, self.holding_amount)

    def sell_off(self):
        if not self.holding_amount or self.sale.ordered:
            return

        msg = ('holding:' + str(self.holding_amount), 'purchase.open:' + str(self.purchase.open_amount))
        msg += ('sale.open:' + str(self.sale.open_amount),)
        self.post_cyan('(SELL_OFF)', *msg)

        self.purchase.ordered = False
        self.sale.ordered = True
        self.broker.sell(self.item_code, 0, self.holding_amount, 'MARKET')

    def sell_off_deprecated(self):
        if not self.holding_amount or self.sale.ordered:
            return

        msg = ('holding:' + str(self.holding_amount), 'purchase.open:' + str(self.purchase.open_amount))
        msg += ('sale.open:' + str(self.sale.open_amount),)
        self.post_cyan('(SELL_OFF)', *msg)

        self.sale.ordered = True
        if self.purchase.open_amount:
            self.broker.cancel(self.purchase)
        if self.sale.open_amount:
            self.broker.cancel_and_sell(self.sale, 0, self.holding_amount, 'MARKET')
        else:
            self.broker.sell(self.item_code, 0, self.holding_amount, 'MARKET')

    def correct(self, order, price, amount=None):
        self.broker.correct(order, price, amount)

    def correct_purchase(self, price):
        if self.purchase.executed_amount_sum:
            self.broker.cancel_and_buy(self.purchase, price)
        else:
            self.broker.correct(self.purchase, price)

    def correct_sale(self, price):
        if self.sale.ordered:
            self.correct(self.sale, price)

    def correct_purchases(self, price):
        purchases = copy.deepcopy(self.purchases)
        self.purchases.clear()

        for order in purchases.values():
            self.broker.correct(order, price)

    def correct_sales(self, price):
        sales = copy.deepcopy(self.sales)
        self.sales.clear()

        for order in sales.values():
            self.broker.correct(order, price)

    def cancel(self, order):
        self.broker.cancel(order)

    def cancel_purchases(self):
        for order in self.purchases.values():
            if order.open_amount:
                self.cancel(order)

    def cancel_sales(self):
        for order in self.sales.values():
            if order.open_amount:
                self.cancel(order)

    def cancel_and_purchase(self, order, price, amount):
        self.broker.cancel_and_buy(order, price, amount)

    def cancel_and_sell(self, order, price, amount):
        self.broker.cancel_and_sell(order, price, amount)

    def clear_purchases(self):
        self.purchases.clear()

    def clear_sales(self):
        self.sales.clear()

    def init_purchase(self):
        self.purchase = Order()

    def init_sale(self):
        self.sale = Order()

    def get_open_purchases(self):
        open_amount = 0
        for order in self.purchases.values():
            open_amount += order.open_amount
        return open_amount

    def get_open_sales(self):
        open_amount = 0
        for order in self.sales.values():
            open_amount += order.open_amount
        return open_amount

    def add_purchase(self, order):
        self.purchases[order.order_number] = order

    def add_sale(self, order):
        self.sales[order.order_number] = order

    def remove_purchase(self, order):
        del self.purchases[order.order_number]

    def remove_sale(self, order):
        del self.sales[order.order_number]

    def succeed_purchase(self):
        self.add_purchase(self.purchase)

    def succeed_sale(self):
        self.add_sale(self.sale)

class FuturesAlgorithmItem(Order, WookLog):
    def __init__(self, item_code):
        super().__init__()
        self.broker = None
        self.item_code = item_code
        self.item_name = CODES[item_code]
        self.purchase = Order()
        self.sale = Order()
        self.purchases = dict()
        self.sales = dict()
        self.contracts = list()
        self.previous_msg = ()
        self.virtual_holding_amount = 0
        self.chart = pandas.DataFrame(list(), columns=['Open', 'High', 'Low', 'Close', 'Volume'])

    def set_broker(self, broker):
        self.broker = broker
        self.futures_fee_ratio = broker.futures_fee_ratio
        self.futures_tax_ratio = broker.futures_tax_ratio

    def set_log(self, log):
        WookLog.custom_init(self, log)

    def post_cyan(self, *args):
        if args != self.previous_msg:
            self.debug('\033[96mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_green(self, *args):
        if args != self.previous_msg:
            self.debug('\033[92mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def post_blue(self, *args):
        if args != self.previous_msg:
            self.debug('\033[94mALGORITHM', *args, '\033[97m')
            self.previous_msg = args

    def add_contract(self, order):
        order.holding_amount = order.executed_amount
        order.purchase_sum = int(order.executed_price_avg * abs(order.executed_amount) * MULTIPLIER)
        order.evaluation_sum = int(order.current_price * abs(order.executed_amount) * MULTIPLIER)
        # order.purchase_fee = order.purchase_sum * self.futures_fee_ratio
        # order.evaluation_fee = order.evaluation_sum * self.futures_fee_ratio
        # order.total_fee = int((order.purchase_fee + order.evaluation_fee) / 10) * 10
        # order.tax = int(order.evaluation_sum * self.futures_tax_ratio)
        order.profit = (order.evaluation_sum - order.purchase_sum) * np.sign(order.executed_amount)
        order.profit_rate = round(order.profit / order.purchase_sum * 100, 2)

        self.current_price = order.current_price
        self.holding_amount += order.executed_amount
        self.purchase_sum += order.purchase_sum
        self.purchase_price = self.purchase_sum / abs(self.holding_amount) / MULTIPLIER
        self.evaluation_sum = int(abs(self.holding_amount) * order.current_price * MULTIPLIER)
        self.purchase_fee = self.purchase_sum * self.futures_fee_ratio
        self.evaluation_fee = self.evaluation_sum * self.futures_fee_ratio
        self.total_fee = int((self.purchase_fee + self.evaluation_fee) / 10) * 10
        self.tax = int(self.evaluation_sum * self.futures_tax_ratio)
        self.profit = (self.evaluation_sum - self.purchase_sum) * np.sign(self.holding_amount)
        self.profit_rate = round(self.profit / self.purchase_sum * 100, 2)

        self.contracts.append(order)

    def pop_contract(self):
        contract = self.contracts.pop(0)
        self.holding_amount -= contract.holding_amount
        if not self.holding_amount:
            return contract
        self.purchase_sum -= contract.purchase_sum
        self.purchase_price = self.purchase_sum / abs(self.holding_amount) / MULTIPLIER
        self.evaluation_sum = int(abs(self.holding_amount) * self.current_price * MULTIPLIER)
        self.purchase_fee = self.purchase_sum * self.futures_fee_ratio
        self.evaluation_fee = self.evaluation_sum * self.futures_fee_ratio
        self.total_fee = int((self.purchase_fee + self.evaluation_fee) / 10) * 10
        self.tax = int(self.evaluation_sum * self.futures_tax_ratio)
        self.profit = (self.evaluation_sum - self.purchase_sum) * np.sign(self.holding_amount)
        self.profit_rate = round(self.profit / self.purchase_sum * 100, 2)
        self.net_profit = self.profit - self.total_fee - self.tax
        self.net_profit_rate = round(self.net_profit / self.purchase_sum * 100, 2)
        return contract

    def settle_contracts_deprecated(self, order):
        settle_amount = copy.deepcopy(abs(order.executed_amount))
        contracts = copy.deepcopy(self.contracts)
        for individual_contract in contracts:
            if abs(individual_contract.holding_amount) <= settle_amount:
                contract = self.pop_contract()
                evaluation_sum = int(order.executed_price_avg * abs(contract.holding_amount) * MULTIPLIER)
                purchase_sum = contract.purchase_sum
                settle_amount -= abs(contract.holding_amount)
            else:
                contract = self.contracts[0]
                contract.holding_amount -= settle_amount * np.sign(contract.holding_amount)
                contract.purchase_sum -= int(settle_amount * order.executed_price_avg * MULTIPLIER)
                contract.evaluation_sum = int(order.current_price * abs(contract.holding_amount) * MULTIPLIER)
                evaluation_sum = int(settle_amount * order.executed_price_avg * MULTIPLIER)
                purchase_sum = int(settle_amount * contract.executed_price_avg * MULTIPLIER)
                settle_amount = 0

            evaluation_fee = evaluation_sum * self.futures_fee_ratio
            purchase_fee = purchase_sum * self.futures_fee_ratio
            total_fee = int((purchase_fee + evaluation_fee) / 10) * 10
            tax = int(evaluation_sum * self.futures_tax_ratio)
            profit = (evaluation_sum - purchase_sum) * np.sign(contract.holding_amount)
            order.profit += profit
            order.total_fee += total_fee
            order.tax += tax
            order.net_profit += profit - total_fee - tax
            if not settle_amount:
                return

    def settle_contracts(self, order):
        # settle_amount = copy.deepcopy(abs(order.executed_amount))
        working_order = copy.deepcopy(order)
        contracts = copy.deepcopy(self.contracts)
        for individual_contract in contracts:
            if abs(individual_contract.holding_amount) <= abs(working_order.executed_amount):
                contract = self.pop_contract()
                evaluation_sum = int(order.executed_price_avg * abs(contract.holding_amount) * MULTIPLIER)
                purchase_sum = contract.purchase_sum
                working_order.executed_amount += individual_contract.holding_amount
            else:
                contract = self.contracts[0]
                contract.holding_amount += working_order.executed_amount
                contract.purchase_sum -= int(abs(working_order.executed_amount) * order.executed_price_avg * MULTIPLIER)
                contract.evaluation_sum = int(order.current_price * abs(contract.holding_amount) * MULTIPLIER)
                evaluation_sum = int(abs(working_order.executed_amount) * order.executed_price_avg * MULTIPLIER)
                purchase_sum = int(abs(working_order.executed_amount) * contract.executed_price_avg * MULTIPLIER)
                working_order.executed_amount = 0

            purchase_fee = purchase_sum * self.futures_fee_ratio
            evaluation_fee = evaluation_sum * self.futures_fee_ratio
            total_fee = int((purchase_fee + evaluation_fee) / 10) * 10
            tax = int(evaluation_sum * self.futures_tax_ratio)
            profit = (evaluation_sum - purchase_sum) * np.sign(contract.holding_amount)
            order.profit += profit
            order.total_fee += total_fee
            order.tax += tax
            order.net_profit += profit - total_fee - tax
            if not working_order.executed_amount:
                break

        self.update_contracts(order.current_price)

        if working_order.executed_amount:
            self.add_contract(working_order)

    def update_contracts(self, current_price=None):
        current_price = self.current_price if current_price is None else current_price
        self.holding_amount = 0
        self.purchase_sum = 0
        self.evaluation_sum = 0
        self.purchase_fee = 0
        self.evaluation_fee = 0
        self.total_fee = 0
        self.tax = 0
        self.profit = 0

        for contract in self.contracts:
            contract.current_price = current_price
            contract.evaluation_sum = int(abs(contract.holding_amount) * current_price * MULTIPLIER)
            contract.evaluation_fee = contract.evaluation_sum * self.futures_fee_ratio
            contract.total_fee = int((contract.purchase_fee + contract.evaluation_fee) / 10) * 10
            contract.tax = int(self.evaluation_sum * self.futures_tax_ratio)
            contract.profit = (contract.evaluation_sum - contract.purchase_sum) * np.sign(contract.holding_amount)
            contract.profit = contract.profit - contract.total_fee - contract.tax
            contract.profit_rate = round(contract.profit / contract.purchase_sum * 100, 2)

            self.holding_amount += contract.holding_amount
            self.purchase_sum += contract.purchase_sum
            self.evaluation_sum += contract.evaluation_sum
            self.purchase_fee += contract.purchase_fee
            self.evaluation_fee += contract.evaluation_fee
            self.total_fee += contract.total_fee
            self.tax += contract.tax
            self.purchase_price = self.purchase_sum / abs(self.holding_amount) / MULTIPLIER
            self.profit += contract.profit
            self.profit_rate = round(self.profit / self.purchase_sum * 100, 2)

    # def update_execution_info_deprecated(self, order):
    #     executed_amount = abs(order.executed_amount)
    #
    #     if order.order_position in (PURCHASE, CORRECT_PURCHASE):
    #         self.purchases[order.order_number] = order
    #         if not order.open_amount:
    #             del self.purchases[order.order_number]
    #         # if order.order_state == ORDER_EXECUTED:
    #             # self.add_contract(order)
    #             # self.holding_amount += executed_amount
    #             # self.purchase_price = order.executed_price
    #             # self.purchase_sum += int(executed_amount * order.executed_price) * MULTIPLIER
    #             # self.purchase_price_avg = self.purchase_sum / self.holding_amount / MULTIPLIER
    #     elif order.order_position in (SELL, CORRECT_SELL):
    #         if order.order_number in self.sales:
    #             old_order = self.sales[order.order_number]
    #             order.purchase_price = old_order.purchase_price
    #         else:
    #             order.purchase_price = self.purchase_price
    #         if order.order_state == ORDER_EXECUTED:
    #             self.holding_amount -= executed_amount
    #             self.purchase_sum = int(self.purchase_price_avg * self.holding_amount)
    #             order.profit = int((order.executed_price - order.purchase_price) * order.executed_amount)
    #             purchase_fee = order.purchase_price * executed_amount * (self.fee_ratio / 100)
    #             sale_fee = order.executed_price_avg * executed_amount * (self.fee_ratio / 100)
    #             order.transaction_fee = int(purchase_fee + sale_fee)
    #             order.net_profit = order.profit - order.transaction_fee
    #             self.profit += order.profit
    #             self.total_fee += order.transaction_fee
    #             self.net_profit += order.net_profit
    #         self.sale = order
    #         self.sales[order.order_number] = order
    #         self.sale.ordered = False
    #         if not order.open_amount:
    #             del self.sales[order.order_number]
    #     elif order.order_position == CANCEL_PURCHASE and order.order_state == CONFIRMED:
    #         if order.original_order_number in self.purchases:
    #             del self.purchases[order.original_order_number]
    #     elif order.order_position == CANCEL_SELL and order.order_state == CONFIRMED:
    #         if order.original_order_number in self.sales:
    #             del self.sales[order.original_order_number]
    #
    #     # Update message
    #     msg = (order.item_name, order.order_position, order.order_state)
    #     msg += ('order:' + str(order.order_amount), 'executed_each:' + str(order.executed_amount))
    #     msg += ('open:' + str(order.open_amount), 'number:' + str(order.order_number))
    #     msg += ('purchase:' + str(order.purchase_price), 'executed:' + str(order.executed_price))
    #     msg += ('holding:' + str(self.holding_amount),)
    #     executed_time = str(order.executed_time)
    #     time_format = executed_time[:2] + ':' + executed_time[2:4] + ':' + executed_time[4:]
    #     self.post_green('(EXECUTION)', *msg)
    #     self.post_blue('(DEBUG)', time_format, 'Purchases', len(self.purchases), 'Sales', len(self.sales))

    def update_orders(self, order):
        if order.order_position in (PURCHASE, CORRECT_PURCHASE):
            self.purchases[order.order_number] = order
            if not order.open_amount:
                del self.purchases[order.order_number]
        elif order.order_position in (SELL, CORRECT_SELL):
            self.sales[order.order_number] = order
            if not order.open_amount:
                del self.sales[order.order_number]
        elif order.order_position == CANCEL_PURCHASE and order.order_state == CONFIRMED:
            if order.original_order_number in self.purchases:
                del self.purchases[order.original_order_number]
        elif order.order_position == CANCEL_SELL and order.order_state == CONFIRMED:
            if order.original_order_number in self.sales:
                del self.sales[order.original_order_number]

    def buy(self, price, amount, order_type='LIMIT'):
        msg = ('holding:' + str(self.holding_amount), 'price:' + str(price), 'amount:' + str(amount))
        self.post_cyan('(BUY)', *msg)
        self.target_amount = amount
        self.broker.buy(self.item_code, price, amount, order_type)

    def sell(self, price, amount, order_type='LIMIT'):
        msg = ('holding:' + str(self.holding_amount), 'price:' + str(price), 'amount:' + str(amount))
        self.post_cyan('(SELL)', *msg)
        self.target_amount = amount
        self.broker.sell(self.item_code, price, amount, order_type)

    def buy_off(self):
        msg = ('holding:' + str(self.holding_amount), 'purchases:' + str(len(self.purchases)))
        self.post_cyan('(BUY_OFF)', *msg)
        self.broker.buy(self.item_code, 0, abs(self.holding_amount), 'MARKET')

    def sell_off(self):
        msg = ('holding:' + str(self.holding_amount), 'sales:' + str(len(self.sales)))
        self.post_cyan('(SELL_OFF)', *msg)
        self.broker.sell(self.item_code, 0, abs(self.holding_amount), 'MARKET')

    def correct(self, order, price, amount=None):
        self.broker.correct(order, price, amount)

    def correct_purchases(self, price):
        purchases = copy.deepcopy(self.purchases)
        self.purchases.clear()

        for order in purchases.values():
            self.broker.correct(order, price)

    def correct_sales(self, price):
        sales = copy.deepcopy(self.sales)
        self.sales.clear()

        for order in sales.values():
            self.broker.correct(order, price)

    def cancel(self, order):
        self.broker.cancel(order)

    def cancel_purchases(self):
        for order in self.purchases.values():
            if order.open_amount:
                self.post_green('&&&&&&&&&&&&&&&&& before cancel purchase &&&&&&&&&&&&&&&&&&&&')
                self.cancel(order)
                self.post_green('&&&&&&&&&&&&&&&&& after cancel purchase &&&&&&&&&&&&&&&&&&&&')

    def cancel_sales(self):
        for order in self.sales.values():
            if order.open_amount:
                self.post_green('&&&&&&&&&&&&&&&&& before cancel sale &&&&&&&&&&&&&&&&&&&&')
                self.cancel(order)
                self.post_green('&&&&&&&&&&&&&&&&& after cancel sale &&&&&&&&&&&&&&&&&&&&')

    def get_open_purchases(self):
        open_amount = 0
        for order in self.purchases.values():
            open_amount += order.open_amount
        return open_amount

    def get_open_sales(self):
        open_amount = 0
        for order in self.sales.values():
            open_amount += order.open_amount
        return open_amount