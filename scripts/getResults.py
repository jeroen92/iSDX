#!/usr/bin/python

import json, pprint, re, copy, argparse, random, netaddr, subprocess, time, redis, collections, csv

# Parse arg.participant prefixes in the BIRD RIB into dicts
def parseRoutes():
    update = dict()
    prefixesCount = dict()
    ases = list()
    lastPrefix = '192.168.1.0'
    update = {"neighborIp": None, "neighborAs": None, "prefix": None, "community": None, "med": None}
    for routeDb in ['ipv4_1.txt', 'ipv4_2.txt']:
        with open( '../../' + routeDb) as prefixFile:
            for line in prefixFile:
                if len(prefixesCount.keys()) > 1000: break
                # Match on begin of line
                ip = re.match("(^[^\s]+|^[\s]+via)", line)
                if ip:
                    lastPrefix = update["prefix"]
                    lastAs = update["neighborAs"]
                    update = {"neighborIp": None, "neighborAs": None, "prefix": None, "community": None, "med": None}
                    if len(ip.group(0).strip()) < 5:
                        update["prefix"] = lastPrefix
                    else:
                        update["prefix"] = ip.group(0)
                    if update["prefix"] in prefixesCount.keys():
                        prefixesCount[update["prefix"]].add(lastAs)
                    else:
                        prefixesCount[update["prefix"]] = {lastAs}
                    continue
                asPath = re.search("(?<=as_path: )(\s\d|\d)+", line)
                if asPath:
                    update["asPath"] = map(int, asPath.group(0).split())
                    update["neighborAs"] = update["asPath"][0]
                    continue
    occurences = [len(prefixesCount[prefix]) for prefix in prefixesCount]
    occurences = collections.Counter(occurences)
    print occurences.keys()
    with open('occurences.csv', 'wb') as outputFile:
        w = csv.DictWriter(outputFile, occurences.keys())
        w.writeheader()
        w.writerow(occurences)

def main():
    routeSet = parseRoutes()
if __name__ == "__main__": main()
