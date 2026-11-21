"""購買システム (data/) の読み出し。正解表 (scoring/gold/) はここでは読まない。"""
import functools
import json
import os

from . import paths


def _load(name):
    with open(paths.data(name), "r", encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def company():
    return _load("company.json")


@functools.lru_cache(maxsize=None)
def suppliers():
    return {s["code"]: s for s in _load("suppliers.json")["suppliers"]}


@functools.lru_cache(maxsize=None)
def tier2():
    return {s["code"]: s for s in _load("suppliers.json")["tier2"]}


def any_company(code):
    return suppliers().get(code) or tier2().get(code)


@functools.lru_cache(maxsize=None)
def items():
    return {i["id"]: i for i in _load("items.json")}


@functools.lru_cache(maxsize=None)
def network():
    return _load("network.json")


def products():
    return {p["id"]: p for p in network()["products"]}


def customers():
    return {c["id"]: c for c in network()["customers"]}


def sources():
    return network()["sources"]


@functools.lru_cache(maxsize=None)
def rfqs():
    return {r["id"]: r for r in _load("rfqs.json")}


@functools.lru_cache(maxsize=None)
def quotes():
    return {q["id"]: q for q in _load("quotes.json")}


@functools.lru_cache(maxsize=None)
def purchase_orders():
    return _load("purchase_orders.json")


@functools.lru_cache(maxsize=None)
def _requests():
    return _load("requests.json")


def requests():
    return {r["id"]: r for r in _requests()["requests"]}


def req05_email():
    return _requests()["req05_email"]


@functools.lru_cache(maxsize=None)
def _neg():
    return _load("negotiations.json")


def ledger():
    return _neg()["ledger"]


def cases():
    return {c["id"]: c for c in _neg()["cases"]}


@functools.lru_cache(maxsize=None)
def news():
    return {n["id"]: n for n in _load("news.json")}


@functools.lru_cache(maxsize=None)
def questions():
    return {q["id"]: q for q in _load("questions.json")}


def handbook(name):
    with open(os.path.join(paths.HANDBOOK, name), "r", encoding="utf-8") as f:
        return f.read()


def handbook_names():
    return sorted(os.listdir(paths.HANDBOOK))


def today():
    return company()["today"]
