#!/usr/bin/python

import json, pprint, re, copy, argparse, random, netaddr, subprocess, time, redis, timeit, os.path

parser = argparse.ArgumentParser(description="Simulates iSDX TCAM size of the fabric")
parser.add_argument("participants", type=int, help="the number of IXP participants")
parser.add_argument("path", type=str, help="path to the iSDX directory")
parser.add_argument("routeDbPath", type=str, help="path to the BIRD RIB dump")
parser.add_argument("meshPercentile", type=int, help="the percentage of all IXP participant each participant will define outbound policies for")
parser.add_argument("maxPolicies", type=int, help="maximum number of outbound policies every participant will generate")
args = parser.parse_args()

pp = pprint.PrettyPrinter(indent=4)
with open('updateTemplate.json') as data_file:    
	updateTemplate = json.load(data_file)

with open('participantTemplate.json') as participantTemplate:
    participantTemplate = json.load(participantTemplate)

def randomMAC():
    return ':'.join(map(lambda x: "%02x" % x, [ 0x00, 0x16, 0x3e,
        random.randint(0x00, 0x7f),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff) ]))

def getUpdateDict(neighborIp, neighborAs, prefix, asPath, community, med):
    updateDict = copy.deepcopy(updateTemplate)
    updateDict["neighbor"]["ip"] = neighborIp
    updateDict["neighbor"]["address"]["peer"] = neighborIp
    updateDict["neighbor"]["asn"]["peer"] = neighborAs
    updateDict["neighbor"]["message"]["update"]["attribute"]["as-path"] = asPath
    if community: updateDict["neighbor"]["message"]["update"]["attribute"]["community"] = community
    if med: updateDict["neighbor"]["message"]["update"]["attribute"]["med"] = med
    updateDict["neighbor"]["message"]["update"]["announce"]["ipv4 unicast"][neighborIp] = {}
    updateDict["neighbor"]["message"]["update"]["announce"]["ipv4 unicast"][neighborIp][prefix] = {}
    return updateDict

def getParticipantDict(identifier, asn, peers, inboundRules, outboundRules, ports):
    participantDict = copy.deepcopy(participantTemplate)
    participantDict["Ports"] = ports
    participantDict["ASN"] = asn
    participantDict["Peers"] = peers
    participantDict["Inbound Rules"] = inboundRules
    participantDict["Outbound Rules"] = outboundRules
    participantDict["Flanc Key"] = "Part%sKey" % identifier
    return participantDict

def generateIxpConfig(participants):
    with open('sdxTemplate.json') as configTemplate:
        configTemplate = json.load(configTemplate)
    configTemplate["Participants"] = participants
    mainSwFabricConnections = dict()
    for participantId, participant in participants.iteritems():
        ports = [ port["Id"] for port in participant["Ports"]]
        if len(ports) <= 1:
            ports = ports[0]
        mainSwFabricConnections[participantId] = ports
    mainSwFabricConnections["arp"] = 1
    mainSwFabricConnections["route server"] = 2
    mainSwFabricConnections["refmon"] = 3
    configTemplate["RefMon Settings"]["fabric connections"]["main"] = mainSwFabricConnections
    configTemplate["VNHs"] = "10.0.0.1/8"
    with open('%s/examples/test-mtsim/config/sdx_global.cfg' % args.path, 'w') as configFile:
        configFile.write(json.dumps(configTemplate, indent=4))
        configFile.close()

# Every ASN is a unique participant
# Get routes belonging to each participant
# Every next hop belonging to the same participant gets its own port number on the IXP
def generateIxpParticipants(routeSet):
    fullMesh = [i for i in xrange(1, len(routeSet["ases"])+1)]
    participantId = 1
    portNumber = 4
    participants = dict()
    for asn in routeSet["ases"]:
        nextHops = list()
        participantPorts = list()
        routes = [ item for item in routeSet["updates"] if item["neighborAs"] == asn ]
        for route in routes:
            if route["neighborIp"] in nextHops:
                continue
            participantPorts.append({"Id": portNumber, "MAC": randomMAC(), "IP": route["neighborIp"]})
            nextHops.append(route["neighborIp"])
            portNumber+=1
        participants[str(participantId)] = getParticipantDict(participantId, route["neighborAs"], fullMesh , False, True, participantPorts)
        participantId += 1
    return participants

def generatePrefixPolicyFile(routeSet, participants):
    policies = dict()
    prefixes = routeSet["prefixes"]
    duplicates = 0
    noOfPolicies = 0
    prefixesCount = routeSet["prefixesCount"]
    for participantId, participant in participants.iteritems():
#        start = time.time()
        participantPolicies = {"outbound": list()}
        policyId = 1
#        while True:
        randomPrefixes = random.sample(xrange(1, len(prefixes)), (len(prefixes) / 100) * args.meshPercentile)
        participantPrefixes = [prefix for prefix in prefixesCount if int(participant["ASN"]) in prefixesCount[prefix]]
#            if any(randomPrefix in participantPrefixes for randomPrefix in randomPrefixes):
#                print 'hit'
#                continue
#            else:
#                break
        participantOutboundPorts = list()
#        print 'first part ' + str(time.time() - start)
#        start = time.time()
        for policyPrefix in randomPrefixes:
            # Generate one to x TCP egress policies for each selected prefix
            for numberOfPolicies in range(0, random.randint(1, args.maxPolicies)):
#                while True:
                randomPortNumber = random.randint(1, 65536)
#                    if randomPortNumber not in participantOutboundPorts:
#                        participantOutboundPorts.append(randomPortNumber)
#                        break
#                    else: continue
                # Find out which particpants advertise this prefix, and select one of them to route this traffic to
                egressParticipant = prefixesCount[prefixes[policyPrefix]].pop()
                prefixesCount[prefixes[policyPrefix]].add(egressParticipant)
                participantPolicies["outbound"].append({
                    "cookie": policyId,
                    "match": {
                        "ipv4_dst": policyPrefix,
                        "tcp_dst": randomPortNumber
                    },
                    "action": {
                        "fwd": egressParticipant
                    }
                })
                if policyPrefix in policies:
                    if egressParticipant in policies[policyPrefix]:
                        if randomPortNumber in policies[policyPrefix][egressParticipant]:
                            duplicates +=1
                        else: policies[policyPrefix][egressParticipant].append(randomPortNumber)
                    else: policies[policyPrefix][egressParticipant] = [randomPortNumber]
                else:
                    policies[policyPrefix] ={ egressParticipant: [randomPortNumber] }
                policyId+=1
                noOfPolicies +=1
#        print 'second part ' + str(time.time() - start)
#        with open('%s/examples/test-mtsim/policies/participant_%s.py' % ( args.path, participantId ), 'w') as policyFile:
#            policyFile.write(json.dumps(participantPolicies, indent=4))
#            policyFile.close()
    print "TOTAL: %s OPTIMUM: %s" % (str(noOfPolicies), str(noOfPolicies-duplicates))

def generateParticipantPolicyFile(routeSet, participants):
    policies = dict()
    duplicates = 0
    noOfPolicies = 0
    prefixesCount = routeSet["prefixesCount"]
    for participantId, participant in participants.iteritems():
        participantPolicies = {"outbound": list()}
        policyId = 1
        while True:
            if len(routeSet["ases"]) < 10:
                randomParticipants = random.sample(xrange(1, len(routeSet["ases"])), args.participants)
                if any(x in participant["Ports"] for x in randomParticipants):
                    continue
                else:
                    break
            else:
                randomParticipants = random.sample(xrange(1, len(routeSet["ases"])), (args.participants / 100) * args.meshPercentile)
                if any(x in participant["Ports"] for x in randomParticipants):
                    continue
                else:
                    break
        participantOutboundPorts = list()
        for policyParticipant in randomParticipants:
            for numberOfPolicies in range(0, random.randint(1, args.maxPolicies)):
                while True:
                    randomPortNumber = random.randint(1, 65536)
                    if randomPortNumber not in participantOutboundPorts:
                        participantOutboundPorts.append(randomPortNumber)
                        break
                    else: continue
                participantPolicies["outbound"].append({
                    "cookie": policyId,
                    "match": {
                        "tcp_dst": randomPortNumber
                    },
                    "action": {
                        "fwd": policyParticipant
                    }
                })
                if policyParticipant in policies.keys():
                    if randomPortNumber in policies[policyParticipant]:
                        duplicates +=1
                    else: policies[policyParticipant].append(randomPortNumber)
                else:
                    policies[policyParticipant] = [randomPortNumber]
                policyId+=1
                noOfPolicies +=1
#        print "DEBUG:\t No. of policies for participant %s is %s" % (str(participantId), str(len(participantPolicies["outbound"])))
#        with open('%s/examples/test-mtsim/policies/participant_%s.py' % ( args.path, participantId ), 'w') as policyFile:
#            policyFile.write(json.dumps(participantPolicies, indent=4))
#            policyFile.close()
    print "TOTAL: %s OPTIMUM: %s" % (str(noOfPolicies), str(noOfPolicies-duplicates))

def generateIxpPolicyFile(numOfAses):
    with open('%s/examples/test-mtsim/config/sdx_policies.cfg' % args.path, 'w') as policyFile:
        policyFile.write(json.dumps({ str(item): 'participant_%s.py' % str(item) for item in range(1,numOfAses+2) }))
        policyFile.close()

# Parse arg.participant prefixes in the BIRD RIB into dicts
def parseRoutes():
    prefixesCount = dict()
    update = dict()
    prefixes = list()
    netaddrPrefixes = list()
    updates = list()
    nexthops = list()
    ases = list()
    if not os.path.isfile('./bgpRoutes.json'):
        update = {"neighborIp": None, "neighborAs": None, "prefix": None, "community": None, "med": None}
    #    for routeDb in ['ipv4_1.txt', 'ipv4_2.txt', 'ipv6_1.txt', 'ipv6_2.txt']:
        for routeDb in ['ipv4_1.txt']:
            with open( args.routeDbPath + '/' + routeDb) as prefixFile:
                for line in prefixFile:
                    # Match on begin of line
                    ip = re.match("(^[^\s]+|^[\s]+via)", line)
                    if ip:
                        if len(ases) >= args.participants:
                            break
                        else:
                            if update["neighborAs"] is not None:
                                if update["neighborAs"] not in ases and 'duplicateAdvertisement' not in update.keys():
                                    ases.append(update["neighborAs"])
                                    print len(ases)
    #                            if 'duplicateAdvertisement' not in update.keys():
    #                                updates.append(update)
    #                                prefixes.append(lastPrefix)
                                updates.append(update)
                                prefixes.append(update["prefix"])
                                if update["prefix"] in prefixesCount.keys():
                                    prefixesCount[update["prefix"]].add(update["neighborAs"])
                                else:
                                    prefixesCount[update["prefix"]] = {update["neighborAs"]}
                        lastPrefix = update["prefix"]
                        lastAs = update["neighborAs"]
                        update = {"neighborIp": None, "neighborAs": None, "prefix": None, "community": None, "med": None}
                        if len(ip.group(0).strip()) < 5:
                            update["prefix"] = lastPrefix
                            update["duplicateAdvertisement"] = True
                        else:
                            update["prefix"] = ip.group(0)
                        continue
                    neighborIp = re.search("(?<=next_hop: ).*$", line)
                    if neighborIp:
                        update["neighborIp"] = neighborIp.group(0)
                        nexthops.append(update["neighborIp"])
                        continue
                    asPath = re.search("(?<=as_path: )(\s\d|\d)+", line)
                    if asPath:
                        update["asPath"] = map(int, asPath.group(0).split())
                        update["neighborAs"] = update["asPath"][0]
                        continue
                    med = re.search("(?<=med: ).*$", line)
                    if med:
                        update["med"] = med.group(0)
                    else:
                        update["med"] = 0
                    continue
                    community = re.search("(?<=\.community: ).*$", line)
                    if community:
                        temp = str(community.group(0)).replace(')','').replace('(','')
                        temp = map(str, temp.split())
                        update["community"] = [map(int, i.split(',')) for i in temp]
                    else:
                        community = '()'
                        continue
        if update not in updates:
            updates.append(update)
        if update["neighborAs"] not in ases:
            ases.append(update["neighborAs"])
        nextHopRange = list(netaddr.IPNetwork('192.168.0.0/16'))
        for prefix in prefixes:
            netaddrPrefixes.append(netaddr.IPNetwork(prefix))
        counter = 0
        with open(args.routeDbPath + '/customRoutes.txt', 'w') as routeFile:
            while len(ases) < args.participants:
                newPrefixes = list()
                # 25 percent chance the participant AS has multiple ports (next hops on the IXP)
                nextHop = nextHopRange[counter]
                if random.randint(0, 100) < 80 or counter == 0:
                    while True:
                        asn = random.randint(1, 65536)
                        if asn not in ases:
                            ases.append(asn)
                            break
                while len(newPrefixes) < 5:
                    while True:
                        randomIPRange = netaddr.IPNetwork(".".join(str(random.randint(1, 255)) for i in range(4)) + '/' + str(random.randint(12, 30))).cidr
                        if True in [randomIPRange in existingRange for existingRange in netaddrPrefixes]:
                            continue
                        else:
                            break
                    newPrefixes.append(randomIPRange)
                    update = {"neighborIp": str(nextHop), "neighborAs": asn, "prefix": str(randomIPRange), "community": None, "med": None}
                    prefixes.append(str(randomIPRange))
                    updates.append(update)
                    routeFile.write("%s   via 80.249.210.31 on eth4\n" % str(randomIPRange))
                    routeFile.write("       as_path: %s\n" % str(asn))
                    routeFile.write("       next_hop: %s\n" % str(nextHop))
                    if str(randomIPRange) in prefixesCount.keys():
                        prefixesCount[str(randomIPRange)].add(asn)
                    else:
                        prefixesCount[str(randomIPRange)] = {asn}
                counter += 1
                print 'random participant %s' + str(counter)
            routeFile.close()
        with open('./bgpRoutes.json', 'w') as bgpRoutes:
            bgpRoutes.write(json.dumps(updates))
    else:
        with open('./bgpRoutes.json', 'r') as bgpRoutes:
            updates = json.load(bgpRoutes)
    bgpRoutes.close()
    finalUpdates = list()
    nrprefixes = 0
    ases = {update['neighborAs'] for update in updates if update['neighborAs']}
    ases = random.sample(ases, args.participants)
    for update in updates:
        if update['neighborAs'] not in ases: continue
        prefixes.append(update['prefix'])
        finalUpdates.append(update)
        if str(update['prefix']) in prefixesCount:
            prefixesCount[update['prefix']].add(update['neighborAs'])
        else:
            prefixesCount[update['prefix']] = {update['neighborAs']}
#    print 'ases: ' + str(len(ases))
#    print 'prefixes: ' + str(len(prefixes))
#    print 'uniuqe prefixes: ' + str(len(set(prefixes)))
#    print 'final updates: ' + str(len(finalUpdates))
    routeSet = {"ases": ases, "updates": finalUpdates, "prefixesCount": prefixesCount, "prefixes": prefixes}
    return routeSet

def printRoutes(routeSet, participants):
    efficientRouteSet = list()
    nextHops = list()
    for update in routeSet["updates"]:
        if update["neighborIp"] in nextHops: continue
        nextHops.append(update["neighborIp"])
        efficientRouteSet.append(update)
    print len(efficientRouteSet)
    routeInjection = subprocess.Popen(["/home/vagrant/iSDX/xrs/client.py"], stdin=subprocess.PIPE)
    i = 0
    with open('/home/vagrant/iSDX/ownscript.output', 'w') as outputfile:
        for update in efficientRouteSet:
            time.sleep(2)
            #routeInjection.communicate(input=str(json.dumps(getUpdateDict(
            str = json.dumps(getUpdateDict(
                update["neighborIp"],
                update["neighborAs"],
                update["prefix"],
                update["asPath"],
                update["community"],
                update["med"]))
            outputfile.write(str + '\n\n')
            print str
            routeInjection.stdin.write(str + '\n\n')
            print i
            i+=1
        routeInjection.communicate()

def main():
#    print ["nohup", "/home/vagrant/iSDX/launch.sh", "test-mtsim", "3", "%s" % str(args.participants)]
#    r = redis.StrictRedis(host='localhost', port=6379, db=0)
#    r.delete('flowqueue')
    routeSet = parseRoutes()
    participants = generateIxpParticipants(routeSet)
#    generateIxpConfig(participants)
#    generateIxpPolicyFile(len(routeSet["ases"]))
    generatePrefixPolicyFile(routeSet, participants)
#    subprocess.Popen(["nohup", "/usr/bin/screen", "-dmS", "one", "/home/vagrant/iSDX/launch.sh", "test-mtsim", "1"])
#    time.sleep(3)
#    subprocess.Popen(["nohup", "/usr/bin/screen", "-dmS", "two", "/home/vagrant/iSDX/launch.sh", "test-mtsim", "2"])
#    time.sleep(5)
#    subprocess.Popen(["nohup", "/home/vagrant/iSDX/launch.sh", "test-mtsim", "3", "%s" % str(args.participants)])
#    time.sleep(10)
#    printRoutes(routeSet, participants)

if __name__ == "__main__": main()
