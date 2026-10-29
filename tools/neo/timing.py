"""Separate data timing from asynchronous reset timing in a Gowin report."""
import re


def timing_checks(text):
    result = {}
    for index, label in enumerate(('Setup','Hold','Recovery','Removal'),1):
        table = re.search(r'^3\.1\.'+str(index)+' '+label+
            r' Paths Table\n(.*?)(?=^3\.\d+(?:\.\d+)? [A-Z])', text, re.M | re.S)
        values = re.findall(r'^\s*\d+\s+(-?\d+\.\d+)\s+',table[1],re.M) if table else []
        if not values:
            raise ValueError('Missing '+label+' timing paths')
        result[label.lower()] = min(map(float,values))
    return result
