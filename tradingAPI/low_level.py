# -*- coding: utf-8 -*-

"""
tradingAPI.low_level
~~~~~~~~~~~~~~

This module provides the low level functions with the service.
"""

import time
import re
from datetime import datetime
from pyvirtualdisplay import Display
from bs4 import BeautifulSoup
from splinter import Browser
from .glob import Glob
from .links import path
from .utils import num, expect, get_pip
# exceptions
from tradingAPI import exceptions
import selenium.common.exceptions

# logging
import logging
logger = logging.getLogger('tradingAPI.low_level')


class LowLevelAPI(object):
    """low level api to interface with the service"""
    def __init__(self, brow="firefox"):
        self.brow_name = brow
        Glob()

    def launch(self):
        """launch browser and virtual display, first of all to be launched"""
        try:
            # init virtual Display
            self.vbro = Display()
            self.vbro.start()
            logger.debug("virtual display launched")
        except Exception:
            raise exceptions.VBroException()
        try:
            self.browser = Browser(self.brow_name)
            logger.debug(f"browser {self.brow_name} launched")
        except Exception:
            raise exceptions.BrowserException(
                self.brow_name, "failed to launch")
        return True

    def css(self, css_path, dom=None):
        """css find function abbreviation"""
        if dom is None:
            dom = self.browser
        return expect(dom.find_by_css, args=[css_path])

    def css1(self, css_path, dom=None):
        """return the first value of self.css"""
        if dom is None:
            dom = self.browser
        return self.css(css_path, dom)[0]

    def search_name(self, name, dom=None):
        """name find function abbreviation"""
        if dom is None:
            dom = self.browser
        return expect(dom.find_by_name, args=[name])

    def xpath(self, xpath, dom=None):
        """xpath find function abbreviation"""
        if dom is None:
            dom = self.browser
        return expect(dom.find_by_xpath, args=[xpath])

    def elCss(self, css_path, dom=None):
        """check if element is present by css"""
        if dom is None:
            dom = self.browser
        return expect(dom.is_element_present_by_css, args=[css_path])

    def elXpath(self, xpath, dom=None):
        """check if element is present by css"""
        if dom is None:
            dom = self.browser
        return expect(dom.is_element_present_by_xpath, args=[xpath])

    def login(self, username, password, mode="demo"):
        """login function"""
        url = "https://trading212.com/it/login"
        try:
            logger.debug(f"visiting %s" % url)
            self.browser.visit(url)
            logger.debug(f"connected to %s" % url)
        except selenium.common.exceptions.WebDriverException:
            logger.critical("connection timed out")
            raise
        try:
            self.search_name("login[username]").fill(username)
            self.search_name("login[password]").fill(password)
            self.css1(path['log']).click()
            # define a timeout for logging in
            timeout = time.time() + 30
            while not self.elCss(path['logo']):
                if time.time() > timeout:
                    logger.critical("login failed")
                    raise CredentialsException(username)
            time.sleep(1)
            logger.info(f"logged in as {username}")
            # check if it's a weekend
            if mode == "demo" and datetime.now().isoweekday() in range(5, 8):
                timeout = time.time() + 10
                while not self.elCss(path['alert-box']):
                    if time.time() > timeout:
                        logger.warning("weekend trading alert-box not closed")
                        break
                if self.elCss(path['alert-box']):
                    self.css1(path['alert-box']).click()
                    logger.debug("weekend trading alert-box closed")
        except Exception as e:
            logger.critical("login failed")
            raise exceptions.BaseExc(e)
        return True

    def logout(self):
        """logout func (quit browser)"""
        try:
            self.browser.quit()
        except Exception:
            raise exceptions.BrowserException(self.brow_name, "not started")
            return False
        self.vbro.stop()
        logger.info("logged out")
        return True

    def get_bottom_info(self, info):
        accepted_values = {
            'free_funds': 'equity-free',
            'account_value': 'equity-total',
            'live_result': 'equity-ppl',
            'used_margin': 'equity-margin'}
        try:
            info_label = accepted_values[info]
            val = self.css1("div#%s span.equity-item-value" % info_label).text
            return num(val)
        except KeyError as e:
            raise exceptions.BaseExc(e)

    def get_price(self, name):
        soup = BeautifulSoup(
            self.css1("div.scrollable-area-content").html, "html.parser")
        for product in soup.select("div.tradebox"):
            fullname = product.select("span.instrument-name")[0].text.lower()
            if fullname.find(name.lower()) != -1:
                mark_closed_list = [x for x in product.select(
                    "div.quantity-list-input-wrapper") if x.select(
                    "div.placeholder")[0].text.lower().find("close") != -1]
                if mark_closed_list:
                    sell_price = product.select("div.tradebox-price-sell")[0]\
                        .text
                    return float(sell_price)
                else:
                    return False

    class MovementWindow(object):
        """add movement window"""
        def __init__(self, api, name):
            self.api = api
            self.name = name
            self.state = 'initialized'
            self.insfu = False

        def open(self, name_counter=None):
            """open the window"""
            if self.api.css1(path['add-mov']).visible:
                self.api.css1(path['add-mov']).click()
            else:
                self.api.css1('span.dataTable-no-data-action').click()
            logger.debug("opened window")
            self.api.css1(path['search-box']).fill(self.name)
            if self.get_result(0) is None:
                logger.error("%s not found" % self.name)
                self.close_mov()
                raise ValueError('%s not found in mov list' % self.name)
            result, name = self.search_res(self.name, name_counter)
            result.click()
            if self.api.elCss("div.widget_message"):
                self.decode(self.api.css1("div.widget_message"))
            self.name = name
            self.state = 'open'

        def _check_open(self):
            if self.state == 'open':
                return True
            else:
                raise exceptions.WindowException()

        def close(self):
            """close a movement"""
            self._check_open()
            self.api.css1(path['close']).click()
            self.state = 'closed'
            logger.debug("closed window")

        def confirm(self):
            """confirm the movement"""
            self._check_open()
            self.api.css1(path['confirm-btn']).click()
            widg = self.api.css("div.widget_message")
            if widg:
                self.decode(widg[0])
                raise exceptions.WidgetException(widg)
            self.state = 'conclused'
            logger.debug("confirmed movement")

        def search_res(self, res, check_counter=None):
            """search for a res"""
            logger.debug("searching result")
            result = self.get_result(0)
            name = self.get_research_name(result)
            x = 0
            while not self.check_name(res, name, counter=check_counter):
                name = self.get_research_name(self.get_result(x))
                logger.debug(name)
                if self.check_name(res, name, counter=check_counter):
                    return self.get_result(x)
                x += 1
            return result, name

        def check_name(self, name, string, counter=None):
            """if both in string return False"""
            name = name.lower()
            string = string.lower()
            if counter is None:
                if name in string:
                    return True
                else:
                    return False
            counter = counter.lower()
            if name in string and counter in string:
                logger.debug("check_name: counter found in string")
                return False
            elif name in string and counter not in string:
                return True
            else:
                return False

        def get_research_name(self, res):
            """return result name"""
            return self.api.css1("span.instrument-name", res).text

        def get_result(self, pos):
            """get pos result, where 0 is first"""
            evalxpath = path['res'] + f"[{pos + 1}]"
            try:
                return self.api.xpath(evalxpath)[0]
                logger.debug("returned product at position %d" % pos + 1)
            except Exception:
                return None

        def set_limit(self, category, mode, value):
            """set limit in movement window"""
            self._check_open()
            if (mode not in ["unit", "value"] or category
                    not in ["gain", "loss", "both"]):
                raise ValueError()
            if not hasattr(self, 'stop_limit'):
                self.stop_limit = {'gain': {}, 'loss': {}}
                logger.debug("initialized stop_limit")
            if category == 'gain':
                self.api.xpath(
                    path['limit-gain-%s' % mode])[0].fill(str(value))
            elif category == 'loss':
                self.api.xpath(
                    path['limit-loss-%s' % mode])[0].fill(str(value))
            if category != 'both':
                self.stop_limit[category]['mode'] = mode
                self.stop_limit[category]['value'] = value
            elif category == 'both':
                self.api.xpath(
                    path['limit-gain-%s' % mode])[0].fill(str(value))
                self.api.xpath(
                    path['limit-loss-%s' % mode])[0].fill(str(value))
                for cat in ['gain', 'loss']:
                    self.stop_limit[cat]['mode'] = mode
                    self.stop_limit[cat]['value'] = value
            logger.debug("set limit")

        def decode(self, message):
            """decode text pop-up"""
            title = self.api.css1("div.title", message).text
            text = self.api.css1("div.text", message).text
            if title == "Insufficient Funds":
                self.insfu = True
            elif title == "Maximum Quantity Limit":
                raise exceptions.MaxQuantLimit(num(text))
            logger.debug("decoded message")

        def decode_update(self, message, value, mult=0.1):
            """decode and update the value"""
            try:
                msg_text = self.api.css1("div.text", message).text
                return num(msg_text)
            except Exception:
                if msg_text.lower().find("higher") != -1:
                    value += value * mult
                    return value
                else:
                    self.decode(message)
                    return None

        def get_mov_margin(self):
            """get the margin of the movement"""
            self._check_open()
            return num(self.api.css1("span.cfd-order-info-item-value").text)

        def set_mode(self, mode):
            """set mode (buy or sell)"""
            self._check_open()
            if mode not in ["buy", "sell"]:
                raise ValueError()
            self.api.css1(path[mode + '-btn']).click()
            self.mode = mode
            logger.debug("mode set")

        def get_quantity(self):
            """gte current quantity"""
            self._check_open()
            quant = int(num(self.api.css1(path['quantity']).value))
            self.quantity = quant
            return quant

        def set_quantity(self, quant):
            """set quantity"""
            self._check_open()
            self.api.css1(path['quantity']).fill(str(quant))
            self.quantity = quant
            logger.debug("quantity set")

        def get_price(self, mode='buy'):
            """get current price"""
            if mode not in ['buy', 'sell']:
                raise ValueError()
            self._check_open()
            price = num(self.api.css1(
                "div.orderdialog div.tradebox-price-%s" % mode).text)
            self.price = price
            return price

        def get_unit_value(self):
            """get unit value of stock based on margin, memoized"""
            # find in the collection
            try:
                unit_value = Glob().theCollector.collection['unit_value']
                unit_value_res = unit_value[self.name]
                logger.debug("unit_value found in the collection")
                return unit_value_res
            except KeyError:
                logger.debug("unit_value not found in the collection")
            pip = get_pip(mov=self)
            quant = 1 / pip
            if hasattr(self, 'quantity'):
                old_quant == self.quantity
            self.set_quantity(quant)
            # update the site
            time.sleep(0.5)
            margin = self.get_mov_margin()
            logger.debug(f"quant: {quant} - pip: {pip} - margin: {margin}")
            if 'old_quant' in locals():
                self.set_quantity(old_quant)
            unit_val = margin / quant
            self.unit_value = unit_val
            Glob().unit_valueHandler.add_val({self.name: unit_val})
            return unit_val

    def new_mov(self, name):
        return self.MovementWindow(self, name)
