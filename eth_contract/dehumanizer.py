"""
parse human-readable abi definition into json format
"""

from typing import Any
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


def parse_parentheses(s: str) -> list:
    s = s.strip()
    result: list[Any] = []
    i = 0
    # extract function name
    paren_pos = s.find('(')
    if paren_pos == -1:
        return [s]
    name = s[:paren_pos].strip()
    result.append(name)
    i = paren_pos
    while i < len(s):
        if s[i] == '(':
            # find matching closing parenthesis
            paren_count = 1
            j = i + 1
            while j < len(s) and paren_count > 0:
                if s[j] == '(':
                    paren_count += 1
                elif s[j] == ')':
                    paren_count -= 1
                j += 1
            # extract content between parentheses
            inner = s[i+1:j-1]
            # check for array notation after parentheses
            array_suffix = ""
            if j < len(s) and s[j] == '[':
                k = j
                while k < len(s) and s[k] != ']':
                    k += 1
                if k < len(s):
                    array_suffix = s[j:k+1]
                    j = k + 1
            # parse inner content
            if inner.strip():
                inner_parts = parse_comma_separated(inner + array_suffix)
                result.append(inner_parts)
            else:
                result.append([])
            i = j
        else:
            i += 1
    return result


def parse_comma_separated(s: str) -> list:
    s = s.strip()
    if not s:
        return []
    parts = []
    current = ""
    paren_depth = 0
    for char in s:
        if char == ',' and paren_depth == 0:
            if current.strip():
                parts.append(current.strip())
            current = ""
        else:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def parse_component(s) -> ABIComponent:
    if isinstance(s, list):
        # nested component
        return {"type": "tuple", "components": [parse_component(item) for item in s]}
    else:
        s = s.strip()
        if s.endswith('[]'):
            base_type = s[:-2].strip()
            if base_type.startswith('(') and base_type.endswith(')'):
                inner = base_type[1:-1]
                components = parse_comma_separated(inner)
                return {
                    "type": "tuple[]",
                    "components": [parse_component(comp) for comp in components]
                }
            else:
                return {"type": s}
        elif s.startswith('(') and s.endswith(')'):
            inner = s[1:-1]
            components = parse_comma_separated(inner)
            return {
                "type": "tuple",
                "components": [parse_component(comp) for comp in components]
            }
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
