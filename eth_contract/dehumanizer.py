"""
parse human-readable abi definition into json format
"""

from eth_typing import ABIComponent, ABIComponentIndexed, ABIElement


def _append(groups, obj):
    "before append new obj, strip spaces for the last string in the group"
    if groups and isinstance(groups[-1], str):
        groups[-1] = groups[-1].strip()
    groups.append(obj)


def _locate(groups, depth):
    while depth:
        groups = groups[-1]
        depth -= 1
    return groups


def _strip(g):
    if g and isinstance(g[-1], str):
        g[-1] = g[-1].strip()
        if not g[-1]:
            g.pop()


def _open(groups, depth):
    g = _locate(groups, depth)
    _strip(g)
    g.append([])


def _close(groups, depth):
    g = _locate(groups, depth)
    _strip(g)


def _append_str(groups, depth, s):
    g = _locate(groups, depth)
    if not g or not isinstance(g[-1], str):
        g.append("")
    g[-1] += s


def _split_str(groups, depth):
    g = _locate(groups, depth)
    _strip(g)
    g.append("")


def parse_parentheses(s):
    groups = []
    depth = 0

    try:
        for char in s:
            if char == "(":
                _open(groups, depth)
                depth += 1
            elif char == ")":
                _close(groups, depth)
                depth -= 1
            elif char == ",":
                _split_str(groups, depth)
            else:
                _append_str(groups, depth, char)
    except IndexError:
        raise ValueError("Parentheses mismatch")

    if depth > 0:
        raise ValueError("Parentheses mismatch")

    return groups


def parse_component(s) -> ABIComponent:
    if isinstance(s, list):
        # nested component
        return {"type": "tuple", "components": [parse_component(item) for item in s]}
    else:
        return {"type": s}


def parse_indexed_component(s) -> ABIComponentIndexed:
    c = parse_component(s)
    parts = c["type"].rsplit(maxsplit=1)
    if len(parts) == 2 and parts[1] == "indexed":
        c["type"] = parts[0]
        indexed = True
    else:
        indexed = False
    return {**c, "indexed": indexed}


def dehumanize(s, type="function") -> ABIElement:
    """
    Convert a human-readable ABI definition into a JSON-like structure.
    """
    parts = parse_parentheses(s)
    if len(parts) == 2:
        name, inputs = parts
        outputs = []
        parts = name.split(maxsplit=1)
        if len(parts) == 2:
            # "function transfer(address,uint256)"
            type, name = parts
        else:
            # "transfer(address,uint256)"
            name = parts[0]
    elif len(parts) == 3:
        name, inputs, outputs = parts
        parts = name.split(maxsplit=1)
        if len(parts) == 2:
            # "function balanceOf(address)(uint256)"
            type, name = parts
        else:
            # "balanceOf(address)(uint256)"
            name = parts[0]
    else:
        raise ValueError("Invalid ABI format")

    if type == "event":
        return {
            "type": "event",
            "name": name,
            "inputs": [parse_indexed_component(i) for i in inputs],
        }
    elif name == "constructor":
        return {
            "type": "constructor",
            "inputs": [parse_component(i) for i in inputs],
        }
    elif name == "fallback":
        return {
            "type": "fallback",
        }
    elif name == "receive":
        return {
            "type": "receive",
        }

    return {
        "type": "function",
        "name": name,
        "inputs": [parse_component(i) for i in inputs],
        "outputs": [parse_component(o) for o in outputs],
    }
