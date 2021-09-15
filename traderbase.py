from PyQt5.QtWidgets import QMainWindow, QLabel, QPushButton, QLineEdit, \
    QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, QRadioButton, QGridLayout, \
    QCheckBox, QComboBox, QGroupBox, QDateTimeEdit, QAction, QFileDialog, QTableWidget, \
    QTableWidgetItem, QSpinBox, QDoubleSpinBox, QGraphicsView, QGraphicsScene, QSystemTrayIcon
from PyQt5.QtCore import Qt, QDateTime, QPoint, QRect, QTimer
from PyQt5.QtGui import QIcon, QBrush
from matplotlib import ticker
import pandas
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import datetime, os, math
import ctypes
import json
from wookutil import WookLog, WookUtil, ChartDrawer
from wookdata import *

class TraderBase(QMainWindow, WookLog, WookUtil):
    def __init__(self, log):
        super().__init__()
        WookLog.custom_init(self, log)
        WookUtil.__init__(self)
        with open('setting.json') as r_file:
            self.setting = json.load(r_file)

        # Initialize fields
        self.chart = pandas.DataFrame(list(), columns=['Open', 'High', 'Low', 'Close', 'Volume'])
        self.draw_chart = ChartDrawer(self.display_chart)
        self.timer = QTimer()
        self.timer.setInterval(60000)
        self.timer.timeout.connect(self.on_every_minute)
        self.chart_item_code = ''
        self.chart_locator = list()
        self.chart_formatter = list()
        self.interval_prices = list()
        self.loss_cut_prices = list()
        self.top_price = 0
        self.bottom_price = 0
        self.chart_rect = QRect(QPoint(1330, 1180), QPoint(2500, 1640))

        self.initUI()

    def initUI(self):
        ###### Account
        # self.cb_auto_login = QCheckBox('Auto')
        # self.cb_auto_login.setChecked(True)
        self.cbb_broker = QComboBox()
        self.cbb_broker.addItem('Kiwoom')
        self.cbb_broker.addItem('Bankis')
        # self.cbb_broker.currentTextChanged.connect(self.on_select_broker)
        self.cbb_broker.setMinimumHeight(30)
        self.cbb_broker.setEditable(True)
        self.cbb_broker.lineEdit().setReadOnly(True)
        self.cbb_broker.lineEdit().setAlignment(Qt.AlignCenter)
        self.cbb_broker.setStyleSheet('font-weight:bold; color:blue')
        self.btn_login = QPushButton('Login', self)
        self.btn_login.clicked.connect(self.connect_broker)
        lb_account = QLabel('Account')
        self.cbb_account = QComboBox()
        # self.cbb_account.currentTextChanged.connect(self.on_select_account)
        self.cbb_account.currentIndexChanged.connect(self.on_select_account)
        self.cbb_account.setMinimumHeight(30)
        lb_deposit = QLabel('Deposit')
        self.lb_deposit = QLabel('No info')
        self.lb_deposit.setStyleSheet('font-weight:bold; color:brown')
        lb_orderable = QLabel('Orderable')
        self.lb_orderable = QLabel('No info')
        self.lb_orderable.setStyleSheet('font-weight:bold; color:olive')

        account_grid = QGridLayout()
        # account_grid.addWidget(self.cb_auto_login, 0, 0)
        account_grid.addWidget(self.cbb_broker, 0, 0)
        account_grid.addWidget(self.btn_login, 0, 1)
        account_grid.addWidget(lb_account, 1, 0)
        account_grid.addWidget(self.cbb_account, 1, 1)
        account_grid.addWidget(lb_deposit, 2, 0)
        account_grid.addWidget(self.lb_deposit, 2, 1)
        account_grid.addWidget(lb_orderable, 3, 0)
        account_grid.addWidget(self.lb_orderable, 3, 1)
        account_gbox = QGroupBox('Account')
        account_gbox.setLayout(account_grid)

        ##### Manual Order
        # Order Parameters
        lb_price = QLabel('Price')
        self.sb_price = QDoubleSpinBox()
        self.sb_price.setGroupSeparatorShown(True)
        self.sb_price.setMinimumHeight(30)
        self.sb_price.setRange(0, 9000000)
        self.sb_price.setSingleStep(0.05)
        lb_amount = QLabel('Amount')
        self.sb_amount = QSpinBox()
        self.sb_amount.setGroupSeparatorShown(True)
        self.sb_amount.setMinimumHeight(30)
        self.sb_amount.setRange(0, 9000000)
        self.cbb_order_position = QComboBox()
        self.cbb_order_position.addItems(ORDER_POSITION_DICT)
        self.cbb_order_position.setMinimumHeight(32)
        self.cbb_order_position.setEditable(True)
        self.cbb_order_position.lineEdit().setReadOnly(True)
        self.cbb_order_position.lineEdit().setAlignment(Qt.AlignCenter)
        self.cbb_order_type = QComboBox()
        self.cbb_order_type.setMinimumHeight(32)
        self.cbb_order_type.setEditable(True)
        self.cbb_order_type.lineEdit().setReadOnly(True)
        self.cbb_order_type.lineEdit().setAlignment(Qt.AlignCenter)
        self.cbb_order_type.addItems(ORDER_TYPE)
        self.btn_order = QPushButton('Order')
        self.btn_order.setStyleSheet('font-weight:bold; background-color:peru')
        self.btn_order.clicked.connect(self.send_order)

        # Item information
        lb_item_code = QLabel('Code')
        lb_item_name = QLabel('Name')
        self.cbb_item_code = QComboBox()
        self.cbb_item_name = QComboBox()
        self.cbb_item_code.setEditable(True)
        self.cbb_item_name.setEditable(True)
        self.cbb_item_code.editTextChanged.connect(self.on_select_item_code)
        self.cbb_item_name.currentIndexChanged.connect(self.on_select_item_name)
        self.cbb_item_code.addItems(CODES)
        self.cbb_item_name.addItems(CODES.values())
        self.btn_add_item = QPushButton('Add')
        self.btn_add_item.clicked.connect(self.on_add_item)
        self.btn_remove_item = QPushButton('Remove')
        self.btn_remove_item.clicked.connect(self.on_remove_item)
        self.btn_remove_item.setMinimumWidth(150)

        # Order Correction
        lb_order_number = QLabel('Order Number')
        self.le_order_number = QLineEdit()
        self.le_order_number.setMaximumWidth(80)

        order_number_hbox = QHBoxLayout()
        order_number_hbox.addWidget(lb_order_number)
        order_number_hbox.addWidget(self.le_order_number)

        # Tradable Parameters
        lb_buyable = QLabel('Buyable')
        self.lb_buyable = QLabel()
        self.lb_buyable.setStyleSheet('font-weight:bold; color:indigo')
        lb_sellable = QLabel('Sellable')
        self.lb_sellable = QLabel()
        self.lb_sellable.setStyleSheet('font-weight:bold; color:purple')

        tradeable_hbox = QHBoxLayout()
        tradeable_hbox.addWidget(lb_buyable)
        tradeable_hbox.addWidget(self.lb_buyable)
        tradeable_hbox.addWidget(lb_sellable)
        tradeable_hbox.addWidget(self.lb_sellable)

        # Chart
        self.btn_go_chart = QPushButton('Go Chart')
        self.btn_go_chart.clicked.connect(self.go_chart)
        self.btn_stop_chart = QPushButton('Stop Chart')
        self.btn_stop_chart.clicked.connect(self.stop_chart)

        # Test
        self.le_test = QLineEdit()
        self.le_test.setMaximumWidth(150)
        self.btn_test1 = QPushButton('Test1')
        self.btn_test1.clicked.connect(self.test1)
        self.btn_test1.setMaximumWidth(70)
        self.btn_test2 = QPushButton('Test2')
        self.btn_test2.clicked.connect(self.test2)

        # Manual Check
        self.btn_deposit = QPushButton('Deposit')
        self.btn_deposit.clicked.connect(self.get_deposit)
        self.btn_portfolio = QPushButton('Portfolio')
        self.btn_portfolio.clicked.connect(self.get_portfolio)
        self.btn_order_history = QPushButton('Order history')
        self.btn_order_history.clicked.connect(self.get_order_history)

        # Order grid layout
        order_grid = QGridLayout()
        order_grid.addWidget(lb_item_code, 0, 0)
        order_grid.addWidget(self.cbb_item_code, 0, 1)
        order_grid.addWidget(lb_item_name, 0, 2)
        order_grid.addWidget(self.cbb_item_name, 0, 3, 1, 3)
        order_grid.addWidget(self.btn_add_item, 0, 6)
        order_grid.addWidget(self.btn_remove_item, 0, 7)
        order_grid.addWidget(lb_price, 1, 0)
        order_grid.addWidget(self.sb_price, 1, 1)
        order_grid.addWidget(lb_amount, 1, 2, 1, 2)
        order_grid.addWidget(self.sb_amount, 1, 4)
        order_grid.addWidget(self.cbb_order_position, 1, 5)
        order_grid.addWidget(self.cbb_order_type, 1, 6)
        order_grid.addWidget(self.btn_order, 1, 7)
        order_grid.addLayout(order_number_hbox, 2, 0, 1, 3)
        order_grid.addLayout(tradeable_hbox, 2, 3, 1, 3)
        order_grid.addWidget(self.btn_go_chart, 2, 6)
        order_grid.addWidget(self.btn_stop_chart, 2, 7)
        order_grid.addWidget(self.le_test, 3, 0, 1, 2)
        order_grid.addWidget(self.btn_test1, 3, 2, 1, 2)
        order_grid.addWidget(self.btn_test2, 3, 4, 1, 1)
        order_grid.addWidget(self.btn_deposit, 3, 5)
        order_grid.addWidget(self.btn_portfolio, 3, 6)
        order_grid.addWidget(self.btn_order_history, 3, 7)
        order_gbox = QGroupBox('Manual Order')
        order_gbox.setLayout(order_grid)

        ##### Portfolio table
        portfolio_header = ['Item', 'Current\nPrice', 'Purchase\nPrice', 'Holding\nAmount', 'Purchase\nSum']
        portfolio_header += ['Evaluation\nSum', 'Fee', 'Tax', 'Profit', 'Profit\nRate']
        self.table_portfolio = QTableWidget(0, 10)
        self.table_portfolio.cellClicked.connect(self.on_select_portfolio_table)
        self.table_portfolio.setHorizontalHeaderLabels(portfolio_header)
        for column in range(1, self.table_portfolio.columnCount()):
            self.table_portfolio.setColumnWidth(column, 92)
        self.table_portfolio.setColumnWidth(0, 215)
        self.table_portfolio.setColumnWidth(4, 119)
        self.table_portfolio.setColumnWidth(5, 119)
        self.table_portfolio.setColumnWidth(6, 92)
        self.table_portfolio.setColumnWidth(7, 92)
        self.table_portfolio.setColumnWidth(9, 93)

        portfolio_gbox = QGroupBox('Portfolio')
        portfolio_grid = QGridLayout()
        portfolio_grid.addWidget(self.table_portfolio)
        portfolio_gbox.setLayout(portfolio_grid)
        # portfolio_gbox.setMinimumHeight(140)

        ##### Monitoring items table
        monitoring_items_header = ['Item', 'Time', 'Price', 'Ask', 'Bid']
        monitoring_items_header += ['Volume', 'Volume(A)', 'High', 'Low', 'Open']
        self.table_monitoring_items = QTableWidget(0, 10)
        self.table_monitoring_items.cellClicked.connect(self.on_select_trading_items_table)
        self.table_monitoring_items.setHorizontalHeaderLabels(monitoring_items_header)
        for column in range(1, self.table_monitoring_items.columnCount()):
            self.table_monitoring_items.setColumnWidth(column, 100)
        self.table_monitoring_items.setColumnWidth(0, 215)
        self.table_monitoring_items.setColumnWidth(6, 120)

        monitoring_items_gbox = QGroupBox('Monitoring')
        monitoring_items_grid = QGridLayout()
        monitoring_items_grid.addWidget(self.table_monitoring_items)
        monitoring_items_gbox.setLayout(monitoring_items_grid)
        monitoring_items_gbox.setMaximumHeight(250)

        ##### Balance table
        balance_header = ['Item', 'Current\nPrice', 'Reference\nPrice', 'Purchase\nPrice']
        balance_header += ['Holding\nAmount', 'Purchase\nSum', 'Purchase\nToday', 'Profit\nToday']
        balance_header += ['Profit\nRate', 'Profit\nRealization']
        self.table_balance = QTableWidget(0, 10)
        self.table_balance.cellClicked.connect(self.on_select_balance_table)
        self.table_balance.setHorizontalHeaderLabels(balance_header)
        for column in range(1, self.table_balance.columnCount()):
            self.table_balance.setColumnWidth(column, 100)
        self.table_balance.setColumnWidth(0, 215)
        self.table_balance.setColumnWidth(5, 130)

        balance_gbox = QGroupBox('Balance')
        balance_grid = QGridLayout()
        balance_grid.addWidget(self.table_balance)
        balance_gbox.setLayout(balance_grid)
        balance_gbox.setMaximumHeight(250)

        ##### Information
        self.te_info = QTextEdit()
        info_grid = QGridLayout()
        info_grid.addWidget(self.te_info, 0, 0)
        info_gbox = QGroupBox('Information')
        info_gbox.setLayout(info_grid)
        info_gbox.setMinimumHeight(500)

        ##### Go Algorithm
        lb_capital = QLabel('Capital')
        self.sb_capital = QSpinBox()
        self.sb_capital.setGroupSeparatorShown(True)
        self.sb_capital.setMinimumHeight(30)
        self.sb_capital.setRange(0, 2000000000)
        self.sb_capital.setSingleStep(1000000)
        lb_interval = QLabel('Interval')
        self.sb_interval = QDoubleSpinBox()
        self.sb_interval.setMinimumHeight(30)
        self.sb_interval.setRange(0, 300)
        self.sb_interval.setSingleStep(0.05)
        lb_loss_cut = QLabel('Loss-cut')
        self.sb_loss_cut = QDoubleSpinBox()
        self.sb_loss_cut.setMinimumHeight(30)
        self.sb_loss_cut.setRange(0, 200)
        self.sb_loss_cut.setSingleStep(0.05)
        lb_fee_set = QLabel('Fee(%)')
        self.sb_fee = QDoubleSpinBox()
        self.sb_fee.setMinimumHeight(30)
        self.sb_fee.setMinimumWidth(55)
        self.sb_fee.setDecimals(3)
        self.sb_fee.setRange(0.0, 1.0)
        self.sb_fee.setSingleStep(0.001)
        lb_min_transaction = QLabel('Binning')
        self.sb_min_transaction = QSpinBox()
        self.sb_min_transaction.setMinimumHeight(30)
        self.sb_min_transaction.setMinimumWidth(60)
        self.sb_min_transaction.setRange(0, 100000)
        self.btn_algorithm_set = QPushButton('Set')
        self.btn_algorithm_set.setMaximumWidth(80)
        self.btn_algorithm_set.clicked.connect(self.set_algorithm_parameters)
        self.btn_go_algorithm = QPushButton('&Go')
        self.btn_go_algorithm.clicked.connect(self.go)
        self.btn_go_algorithm.setStyleSheet('font-weight:bold; background-color:Goldenrod')
        self.btn_stop_algorithm = QPushButton('&Stop')
        self.btn_stop_algorithm.clicked.connect(self.stop)
        self.btn_stop_algorithm.setStyleSheet('font-weight:bold; background-color:IndianRed')

        lb_total_profit = QLabel('Total Profit')
        self.lb_total_profit = QLabel()
        self.lb_total_profit.setStyleSheet('font-weight:bold; color:indigo')
        hbox_total_profit = QHBoxLayout()
        hbox_total_profit.addWidget(lb_total_profit)
        hbox_total_profit.addWidget(self.lb_total_profit)
        lb_total_fee = QLabel('Total Fee')
        self.lb_total_fee = QLabel()
        self.lb_total_fee.setStyleSheet('font-weight:bold; color:indigo')
        hbox_total_fee = QHBoxLayout()
        hbox_total_fee.addWidget(lb_total_fee)
        hbox_total_fee.addWidget(self.lb_total_fee)
        lb_net_profit = QLabel('Net Profit')
        self.lb_net_profit = QLabel()
        self.lb_net_profit.setStyleSheet('font-weight:bold; color:indigo')
        hbox_net_profit = QHBoxLayout()
        hbox_net_profit.addWidget(lb_net_profit)
        hbox_net_profit.addWidget(self.lb_net_profit)

        algorithm_grid = QGridLayout()
        algorithm_grid.addWidget(lb_capital, 0, 0)
        algorithm_grid.addWidget(self.sb_capital, 0, 1)
        algorithm_grid.addWidget(lb_interval, 0, 2)
        algorithm_grid.addWidget(self.sb_interval, 0, 3)
        algorithm_grid.addWidget(lb_loss_cut, 0, 4)
        algorithm_grid.addWidget(self.sb_loss_cut, 0, 5)
        algorithm_grid.addWidget(lb_fee_set, 0, 6)
        algorithm_grid.addWidget(self.sb_fee, 0, 7)
        algorithm_grid.addWidget(lb_min_transaction, 0, 8)
        algorithm_grid.addWidget(self.sb_min_transaction, 0, 9)
        algorithm_grid.addWidget(self.btn_algorithm_set, 0, 10)
        algorithm_grid.addWidget(self.btn_go_algorithm, 0, 11, 1, 4)
        algorithm_grid.addWidget(self.btn_stop_algorithm, 0, 15, 1, 4)

        # algorithm_grid.addLayout(hbox_holding_amount, 1, 0, 1, 2)
        algorithm_grid.addLayout(hbox_total_profit, 1, 0, 1, 3)
        algorithm_grid.addLayout(hbox_total_fee, 1, 4, 1, 2)
        algorithm_grid.addLayout(hbox_net_profit, 1, 6, 1, 3)
        algorithm_gbox = QGroupBox('Algorithm')
        algorithm_gbox.setLayout(algorithm_grid)

        ##### Open Order Table
        open_orders_header = ['Item', 'Time', 'Order\nAmount', 'Executed\nAmount', 'Open\nAmount']
        open_orders_header += ['Order\nNumber', 'Original\nNumber']
        open_orders_header += ['Order\nPrice', 'Executed\nPrice', 'Order\nPosition', 'Order\nState']
        self.table_open_orders = QTableWidget(0, 11)
        self.table_open_orders.cellClicked.connect(self.on_select_open_orders_table)
        self.table_open_orders.setHorizontalHeaderLabels(open_orders_header)
        for column in range(1, self.table_open_orders.columnCount()):
            self.table_open_orders.setColumnWidth(column, 100)
        self.table_open_orders.setColumnWidth(0, 215)

        open_orders_gbox = QGroupBox('Open Orders')
        open_orders_grid = QGridLayout()
        open_orders_grid.addWidget(self.table_open_orders)
        open_orders_gbox.setLayout(open_orders_grid)
        open_orders_gbox.setMaximumHeight(220)

        ##### Order History Table
        order_history_header = ['Item', 'Time', 'Order\nAmount', 'Executed\nAmount', 'Open\nAmount']
        order_history_header += ['Order\nNumber', 'Original\nNumber', 'Order\nPrice', 'Executed\nPrice']
        order_history_header += ['Order\nPosition', 'Order\nState']
        self.table_order_history = QTableWidget(0, 11)
        self.table_order_history.cellClicked.connect(self.on_select_order_history_table)
        self.table_order_history.setHorizontalHeaderLabels(order_history_header)
        for column in range(1, self.table_order_history.columnCount()):
            self.table_order_history.setColumnWidth(column, 100)
        self.table_order_history.setColumnWidth(0, 210)

        order_history_gbox = QGroupBox('Order History')
        order_history_grid = QGridLayout()
        order_history_grid.addWidget(self.table_order_history)
        order_history_gbox.setLayout(order_history_grid)
        order_history_gbox.setMaximumHeight(300)

        ##### Algorithm Trading Table
        algorithm_trading_header = ['Item', 'Time', 'E.N.', 'Order\nNumber', 'Order\nPosition', 'Order\nState']
        algorithm_trading_header += ['Order\nPrice', 'Executed\nPrice', 'Order\nAmount', 'Executed\nAmount']
        algorithm_trading_header += ['Open\nAmount', 'Profit']
        self.table_algorithm_trading = QTableWidget(0, 12)
        self.table_algorithm_trading.cellClicked.connect(self.on_select_algorithm_trading_table)
        self.table_algorithm_trading.setHorizontalHeaderLabels(algorithm_trading_header)
        for column in range(1, self.table_algorithm_trading.columnCount()):
            self.table_algorithm_trading.setColumnWidth(column, 95)
        self.table_algorithm_trading.setColumnWidth(0, 215)
        self.table_algorithm_trading.setColumnWidth(1, 90)
        self.table_algorithm_trading.setColumnWidth(2, 50)
        self.table_algorithm_trading.setColumnWidth(4, 80)
        self.table_algorithm_trading.setColumnWidth(5, 80)

        algorithm_trading_gbox = QGroupBox('Algorithm Trading')
        algorithm_trading_grid = QGridLayout()
        algorithm_trading_grid.addWidget(self.table_algorithm_trading)
        algorithm_trading_gbox.setLayout(algorithm_trading_grid)

        ##### Chart Display
        self.fig = plt.Figure()
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot()
        self.fig.tight_layout()

        canvas_grid = QGridLayout()
        canvas_grid.addWidget(self.canvas, 0, 0)
        canvas_gbox = QGroupBox('Chart')
        canvas_gbox.setLayout(canvas_grid)

        ##### Left Layout #####
        left_top_grid = QGridLayout()
        left_top_grid.addWidget(account_gbox, 0, 0, 1, 3)
        left_top_grid.addWidget(order_gbox, 0, 3, 1, 8)

        left_vbox = QVBoxLayout()
        left_vbox.addLayout(left_top_grid)
        left_vbox.addWidget(portfolio_gbox)
        left_vbox.addWidget(monitoring_items_gbox)
        left_vbox.addWidget(balance_gbox)
        left_vbox.addWidget(info_gbox)

        ##### Right Layout #####
        right_vbox = QVBoxLayout()
        right_vbox.addWidget(algorithm_gbox)
        right_vbox.addWidget(open_orders_gbox)
        right_vbox.addWidget(order_history_gbox)
        right_vbox.addWidget(algorithm_trading_gbox)
        right_vbox.addWidget(canvas_gbox)

        ##### Central Layout #####
        central_grid = QGridLayout()
        central_grid.addLayout(left_vbox, 0, 0, 1, 10)
        central_grid.addLayout(right_vbox, 0, 10, 1, 11)

        # Central widget
        cw = QWidget()
        cw.setLayout(central_grid)

        # Menu bar
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet('background:rgb(140,230,255)')
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(exit_action)

        setting_action = QAction('Setting', self)
        setting_action.triggered.connect(self.edit_setting)
        edit_menu = menu_bar.addMenu('&Edit')
        edit_menu.addAction(setting_action)

        # Window setting
        self.setCentralWidget(cw)
        self.status_bar = self.statusBar()
        self.status_bar.showMessage('ready')
        self.setWindowTitle('wook\'s algorithm trader')
        self.resize(2550, 1700)
        self.move(-700, 100)
        # self.move(100, 100)
        self.setWindowIcon(QIcon('data/wTrader.png'))
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('myApp')
        self.show()

    def wheelEvent(self, event):
        mouse_position = event.position().toPoint()
        wheel_position = event.angleDelta().y()
        if self.chart_rect.contains(mouse_position):
            self.magnify_chart(mouse_position, wheel_position)
        else:
            self.debug('OUT')

    def magnify_chart(self, mouse_position, wheel_position):
        if not self.algorithm.is_running:
            return

        if self.algorithm.chart_scope < 0 or self.algorithm.chart_scope > 400:
            return

        magnification = 5
        if wheel_position > 0:
            self.algorithm.chart_scope += magnification
        else:
            self.algorithm.chart_scope -= magnification

        # sign = 1
        # if wheel_position > 0:
        #     sign = -1
        #     self.debug('Up', mouse_position)
        # else:
        #     self.debug('Down', mouse_position)

        # rect_width = self.chart_rect.width()
        # rect_position = self.chart_rect.topLeft()
        # relative_mouse_position = mouse_position - rect_position
        #
        # magnification_ratio = 10
        #
        # current_x1, current_x2 = self.ax.get_xlim()
        # ax_length = current_x2 - current_x1
        # cut_amount = ax_length * magnification_ratio / 100
        # cut_ratio = relative_mouse_position.x() / rect_width
        # x1_cut = cut_amount * cut_ratio * sign
        # x2_cut = (cut_amount - x1_cut) * sign
        #
        # x1 = round(current_x1 + x1_cut)
        # x2 = round(current_x2 - x2_cut)
        #
        # if x1 < 0:
        #     x1 = 0
        # if x2 < 0:
        #     x2 = 0

        # if self.algorithm.is_running:
        #     max_price = self.algorithm.get_max_price(x1, x2)
        #     min_price = self.algorithm.get_min_price(x1, x2)
        # else:
        #     max_price = self.chart.High[x1:x2].max()
        #     min_price = self.chart.Low[x1:x2].min()
        #
        # y1 = math.floor(min_price / self.interval) * self.interval
        # y2 = math.ceil(max_price / self.interval) * self.interval
        # self.ax.set_xlim(x1, x2)
        # self.ax.set_ylim(y1, y2)
        #
        # print(self.ax.get_xlim())

        # self.canvas.draw()
