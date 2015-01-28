#!/usr/bin/env python

import sys
import math
import time
import logging
import os
import random


# logging.basicConfig(filename='botlog1-%d.log' % os.getpid(),level=logging.DEBUG)

prevturns = []
known_allies = []
intrd = False

flights_in_progress = {}


def proximity(planet1, planet2):
    return math.ceil(math.sqrt((planet2.x - planet1.x)**2 + (planet2.y - planet1.y)**2))

def estimatd_defense(planet, travel_time=1):
    return planet.num_ships + travel_time*planet.growth_rate

def profitable_time(planet, travel_time=1):
    return math.ceil(estimatd_defense(planet,travel_time) / float(planet.growth_rate))+travel_time

def score(planet, travel_time=1, src_str=None, risk_value=0.1):
    pt = profitable_time(planet, travel_time)
    ed = estimatd_defense(planet,travel_time)
    enemy_coef = planet.is_enemy() and 1.3 or 1 #otherwise assumed neutral
    difficulty = 1
    if src_str:
        difficulty = (1 - (float(ed)/src_str)) * (1 + risk_value)
        if difficulty < 0: difficulty = 0

    if pt == 0:
        return 0
    return 100*(difficulty * (float(1)/pt) * (planet.growth_rate) * enemy_coef)

def rscore(src,p):
    return score(p, travel_time=proximity(src,p), src_str=src.num_ships, risk_value=0.5)


def proc(state,response):

    m = state.message
    if m and m not in known_allies:
        known_allies.append(m)

    global intrd
    if not intrd:
        if not m:
            response.set_outgoing_message(state.playerID)
        else:
            if m == state.playerID:
                intrd = True
            else:
                response.set_outgoing_message(state.message) #pass received message further

    hostile_planets = [p for p in state.planets if p.hostility >= 3]

    for src in state.planets_mine:
        L = [p for p in hostile_planets if rscore(src,p) > 0.5]
        L.sort(key=lambda p: rscore(src,p), reverse=True)

        # logging.debug("=====\r\n")
        # for e in L: 
            # logging.debug("%r\r\n" % e)

        choice = None
        k = 0
        while not choice and k < 3: 
            i = random.randint(0+k,3)
            k +=1
            try:
                if L[i] in flights_in_progress:
                    continue
            
                choice = L.pop(i)
            except IndexError:
                break

        if not choice:
            continue
            
        dst = choice
        dst_ships = estimatd_defense(dst, travel_time=proximity(src,dst))

        grc = 1

        overkill = math.floor(((src.num_ships - dst_ships) /2.0) * grc)

        fleetsize = dst_ships + overkill

        flights_in_progress[dst] = True

        prev_ships = src.num_ships
        response.send_fleet(src, dst, fleetsize)   





class Planet(object):
    def __init__(self, id, x, y, growth_rate, owner, num_ships):
        self.id = id
        self.x = x
        self.y = y
        self.growth_rate = growth_rate
        self.owner = owner
        self.num_ships = num_ships
        self.hostility = 3 

    def __repr__(self):
        return "<P ID%d O%d G%d N%d>" % (self.id, self.owner, self.growth_rate, self.num_ships)

    def is_allied(self):
        return self.hostility == 1

    def is_enemy(self):
        return self.hostility == 4

    def is_netural(self):
        return self.hostility == 3

    def is_mine(self):
        return self.hostility == 0

class Response(object):
    def __init__(self):
        self.fleetcommands = []
        self.outmessage = None

    def send_fleet(self, src_planet, dst_planet, num_ships):
        src_planet.num_ships -= num_ships
        self.fleetcommands.append( (src_planet.id, dst_planet.id, num_ships) )

    def set_outgoing_message(self, msg):
        self.outmessage = msg

    def send(self):
        for fcmd in self.fleetcommands:
            logging.debug("F %d %d %d\r\n" % fcmd)
            sys.stdout.write("F %d %d %d\r\n" % fcmd)
        if self.outmessage != None:
            logging.debug("M %d\r\n" % self.outmessage)
            sys.stdout.write("M %d\r\n" % self.outmessage)
        logging.debug(".\r\n")
        sys.stdout.write(".\r\n") # termination
        sys.stdout.flush()


class TurnState(object):
    def  __init__(self):
        self.planets = []
        self.planets_mine = []
        self.planets_ally = []
        self.planets_enemy = []
        self.planets_neutral = []

        self.playerID = -1
        self.message = None
        self._finished = False

    def add_planet(self,p):
        return self.planets.append(p)

    def set_playerID(self, id):
        self.playerID = id

    def set_incoming_message(self, msg):
        self.message = msg

    def is_finished(self):
        return self._finished

    def process_turn(self):
        for planet in self.planets:
            if planet.owner == self.playerID:
                planet.hostility = 0 # Mine
                self.planets_mine.append(planet)
            elif planet.owner in known_allies:
                planet.hostility = 1 # Ally
                self.planets_ally.append(planet)
            elif planet.owner == 0:
                planet.hostility = 3 # Neutral
                self.planets_neutral.append(planet)
            else:
                planet.hostility = 4 # Enemy
                self.planets_enemy.append(planet)

        self.total_growth_rate = sum(x.growth_rate for x in self.planets_mine)
        self.total_ships = sum(x.num_ships for x in self.planets_mine)

        R = Response()
        proc(self, R)
        R.send()

        self._finished = True
        return True


def main():
    cturn = TurnState()
    while(1):
        time.sleep(0.001)
        if cturn.is_finished():
            prevturns.append(cturn)
            cturn = TurnState()

        try:
            line = sys.stdin.readline()
            logging.debug("%s" % line)
            la = line.split()
            cmd = la[0]
            if cmd == "P":
                planetID = int(la[1])
                x = float(la[2])
                y = float(la[3])
                growth_rate = int(la[4])
                owner = int(la[5])
                num_ships = int(la[6])
                p = Planet(planetID, x, y, growth_rate, owner, num_ships)
                cturn.add_planet(p)

            elif cmd == "M":
                cturn.set_incoming_message(int(la[1]))

            elif cmd == "Y":
                cturn.set_playerID(int(la[1]))
                logging.debug("Processing...\r\n" % la)
                cturn.process_turn()
        except IndexError:
            pass


if __name__ == "__main__":
    try:
        random.seed(time.time())
        main()
    except KeyboardInterrupt:
        exit(1)